# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import codex_working_flow_delivery_proof as working_flow
from wild_boar_proxy import official_e2e_working_flow_proof_join as proof
from wild_boar_proxy import official_mcp_working_flow_delivery_join as delivery_join
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_codex_working_flow_delivery_proof import (  # noqa: E402
    EXPECTED_TEXT,
    PROMPT,
    RAW_PROVIDER_TEXT,
    ROUTE_ID,
    _command_assistant_event,
    _command_execution_event,
    _events_for_packet,
    _file_metadata as _working_flow_file_metadata,
    _integrated_packet,
)
from test_official_mcp_delivery_candidate_join import (  # noqa: E402
    _packet as _candidate_packet,
)
from test_official_mcp_working_flow_delivery_join import (  # noqa: E402
    _file_metadata as _delivery_join_file_metadata,
)


def _secret_values() -> list[str]:
    return [PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT]


def _working_flow_packet(source: dict[str, object]) -> dict[str, object]:
    packet = working_flow.build_codex_working_flow_delivery_proof_packet(
        source,
        _events_for_packet(source),
        file_metadata=_working_flow_file_metadata(),
        secret_values=_secret_values(),
    )
    assert packet["status"] == "ok"
    return packet


def _command_working_flow_packet(source: dict[str, object]) -> dict[str, object]:
    packet = working_flow.build_codex_working_flow_delivery_proof_packet(
        source,
        [
            {"type": "thread.started", "thread_id": "thread-command-flow"},
            {"type": "turn.started"},
            _command_execution_event(source),
            _command_assistant_event(),
            {"type": "turn.completed"},
        ],
        file_metadata=_working_flow_file_metadata(),
    )
    assert packet["status"] == "ok"
    assert packet["command_execution_delivery_surface_proven"] is True
    return packet


def _delivery_join_packet(
    working_flow_packet: dict[str, object],
) -> dict[str, object]:
    candidate = dict(_candidate_packet())
    candidate["handoff_payload_digest"] = working_flow_packet["handoff_payload_digest"]
    candidate["approved_source_marker_digest"] = working_flow_packet[
        "handoff_payload_digest"
    ]
    candidate["codex_exec_transcript_sha256"] = working_flow_packet[
        "codex_exec_transcript_sha256"
    ]
    candidate["approved_source_digest"] = working_flow_packet[
        "codex_exec_transcript_sha256"
    ]
    candidate["assistant_continuation_source_digest"] = working_flow_packet[
        "codex_exec_transcript_sha256"
    ]
    packet = delivery_join.build_official_mcp_working_flow_delivery_join_packet(
        official_delivery_candidate_packet=candidate,
        working_flow_delivery_proof_packet=working_flow_packet,
        file_metadata=_delivery_join_file_metadata(),
        secret_values=_secret_values(),
    )
    assert packet["status"] == "ok"
    return packet


def _positive_pair() -> tuple[dict[str, object], dict[str, object]]:
    real_hook = _integrated_packet()
    return real_hook, _delivery_join_packet(_working_flow_packet(real_hook))


def _file_metadata() -> dict[str, object]:
    return {
        "real_custom_hook_proof_file_required": True,
        "real_custom_hook_proof_file_present": True,
        "real_custom_hook_proof_file_read": True,
        "real_custom_hook_proof_file_valid_json": True,
        "real_custom_hook_proof_file_mapping": True,
        "real_custom_hook_proof_file_error_code": "",
        "real_custom_hook_proof_file_path_recorded": False,
        "official_working_flow_delivery_join_file_required": True,
        "official_working_flow_delivery_join_file_present": True,
        "official_working_flow_delivery_join_file_read": True,
        "official_working_flow_delivery_join_file_valid_json": True,
        "official_working_flow_delivery_join_file_mapping": True,
        "official_working_flow_delivery_join_file_error_code": "",
        "official_working_flow_delivery_join_file_path_recorded": False,
    }


def _packet(
    *,
    real_hook: dict[str, object] | None = None,
    delivery: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
    secret_values: list[str] | None = None,
) -> dict[str, object]:
    positive_real_hook, positive_delivery = _positive_pair()
    return proof.build_official_e2e_working_flow_proof_join_packet(
        real_custom_hook_proof_packet=(
            positive_real_hook if real_hook is None else real_hook
        ),
        official_working_flow_delivery_join_packet=(
            positive_delivery if delivery is None else delivery
        ),
        file_metadata=_file_metadata() if metadata is None else metadata,
        secret_values=_secret_values() if secret_values is None else secret_values,
    )


def _assert_no_ui_native_or_product_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["native_free_chat_router_product_ready"])
    testcase.assertFalse(packet["native_free_chat_router_delivery_proven"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_ui"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


def _assert_no_raw_prompt_route_or_provider(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in _secret_values():
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["raw_task_recorded"])
    testcase.assertFalse(packet["raw_jsonl_recorded"])
    testcase.assertFalse(packet["tool_call_arguments_recorded"])
    testcase.assertFalse(packet["route_candidate_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


def _assert_no_writes(testcase: unittest.TestCase, packet: dict[str, object]) -> None:
    testcase.assertFalse(packet["state_written"])
    testcase.assertFalse(packet["evidence_written"])
    testcase.assertFalse(packet["file_mutation_attempted"])
    testcase.assertEqual(packet["changed_files"], [])


class OfficialE2EWorkingFlowProofJoinTests(unittest.TestCase):
    def test_positive_joins_real_custom_hook_to_official_working_flow_delivery(self) -> None:
        real_hook, delivery = _positive_pair()
        packet = _packet(real_hook=real_hook, delivery=delivery)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            proof.OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["real_custom_hook_proof_file_read"])
        self.assertTrue(packet["official_working_flow_delivery_join_file_read"])
        self.assertFalse(packet["real_custom_hook_proof_file_path_recorded"])
        self.assertFalse(packet["official_working_flow_delivery_join_file_path_recorded"])
        self.assertEqual(
            packet["e2e_working_flow_truth_source"],
            proof.E2E_WORKING_FLOW_TRUTH_SOURCE,
        )
        self.assertEqual(
            packet["source_kind_claim_ceiling"],
            proof.E2E_WORKING_FLOW_CLAIM_CEILING,
        )
        self.assertTrue(packet["official_e2e_working_flow_proven"])
        self.assertTrue(packet["custom_codex_hook_to_official_working_flow_bound"])
        self.assertTrue(packet["custom_codex_flow_origin_proven"])
        self.assertTrue(packet["hook_producer_ledger_proven"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["hook_ledger_written"])
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["thread_or_turn_digest_bound"])
        self.assertEqual(packet["hook_event_digest"], real_hook["hook_event_digest"])
        self.assertEqual(packet["hook_thread_digest"], real_hook["hook_thread_digest"])
        self.assertEqual(packet["hook_turn_digest"], real_hook["hook_turn_digest"])
        self.assertEqual(packet["hook_session_digest"], real_hook["hook_session_digest"])
        self.assertTrue(packet["hook_event_digest_bound_to_working_flow"])
        self.assertTrue(packet["hook_thread_or_turn_digest_bound_to_working_flow"])
        self.assertTrue(packet["hook_session_digest_bound_to_working_flow"])
        self.assertTrue(packet["working_flow_hook_prompt_digest_bound"])
        self.assertTrue(packet["working_flow_hook_runtime_context_digest_bound"])
        self.assertEqual(packet["prompt_digest"], real_hook["prompt_digest"])
        self.assertEqual(packet["runtime_context_digest"], real_hook["runtime_context_digest"])
        self.assertTrue(packet["prompt_digest_bound_to_working_flow"])
        self.assertTrue(packet["runtime_context_digest_bound_to_working_flow"])
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["route_id_allowed"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["provider_response_proven"])
        self.assertTrue(packet["live_provider_proven"])
        self.assertTrue(packet["live_provider_response_proven"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertTrue(packet["live_provider_response_bound_to_working_flow"])
        self.assertTrue(packet["controlled_provider_response_bound_to_working_flow"])
        self.assertTrue(packet["approved_handoff_ready"])
        self.assertTrue(packet["approved_handoff_payload_sanitized"])
        self.assertTrue(packet["handoff_delivered"])
        self.assertTrue(packet["delivery_observed"])
        self.assertTrue(packet["handoff_payload_bound_to_working_flow"])
        self.assertTrue(packet["approved_exec_source_delivery_candidate"])
        self.assertTrue(packet["official_delivery_candidate_lineage_proven"])
        self.assertTrue(packet["official_observation_lineage_file_backed"])
        self.assertTrue(packet["approved_delivery_surface_proven"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["official_mcp_delivery_candidate_joined_to_working_flow"])
        self.assertEqual(packet["real_custom_hook_failures"], [])
        self.assertEqual(packet["official_working_flow_delivery_join_failures"], [])
        self.assertEqual(packet["source_unsafe_claim_failures"], [])
        self.assertEqual(packet["digest_binding_failures"], [])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_positive_accepts_direct_command_execution_working_flow_delivery(self) -> None:
        real_hook = _integrated_packet()
        delivery = _command_working_flow_packet(real_hook)
        packet = _packet(real_hook=real_hook, delivery=delivery)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["official_e2e_working_flow_proven"])
        self.assertTrue(packet["custom_codex_hook_to_official_working_flow_bound"])
        self.assertTrue(packet["custom_codex_flow_origin_proven"])
        self.assertEqual(
            packet["official_delivery_surface_kind"],
            working_flow.DELIVERY_SURFACE_CODEX_COMMAND_EXECUTION_LIVE_FORMAT_CHECK,
        )
        self.assertTrue(packet["official_command_execution_delivery_joined_to_working_flow"])
        self.assertTrue(packet["official_working_flow_delivery_joined_to_working_flow"])
        self.assertFalse(packet["official_mcp_delivery_candidate_joined_to_working_flow"])
        self.assertFalse(packet["approved_exec_source_delivery_candidate"])
        self.assertTrue(packet["official_delivery_candidate_lineage_proven"])
        self.assertTrue(packet["official_observation_lineage_file_backed"])
        self.assertTrue(packet["approved_delivery_surface_proven"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["prompt_digest_bound_to_working_flow"])
        self.assertTrue(packet["runtime_context_digest_bound_to_working_flow"])
        self.assertTrue(packet["live_provider_response_bound_to_working_flow"])
        self.assertTrue(packet["controlled_provider_response_bound_to_working_flow"])
        self.assertEqual(packet["real_custom_hook_failures"], [])
        self.assertEqual(packet["official_working_flow_delivery_join_failures"], [])
        self.assertEqual(packet["digest_binding_failures"], [])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_direct_command_execution_working_flow_failure_list_blocks_join(self) -> None:
        real_hook = _integrated_packet()
        delivery = _command_working_flow_packet(real_hook)
        delivery["command_execution_delivery_failures"] = [
            "forged_failure_list_must_block"
        ]
        packet = _packet(real_hook=real_hook, delivery=delivery)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_DELIVERY_INVALID,
        )
        self.assertIn(
            "working_flow_command_delivery_failures_not_empty",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["official_e2e_working_flow_proven"])
        self.assertFalse(packet["official_command_execution_delivery_joined_to_working_flow"])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_direct_command_execution_working_flow_requires_file_backed_metadata(
        self,
    ) -> None:
        real_hook = _integrated_packet()
        delivery = _command_working_flow_packet(real_hook)
        delivery["codex_exec_jsonl_file_read"] = False
        delivery["codex_exec_jsonl_file_valid_jsonl"] = False
        delivery["codex_exec_event_count"] = 0
        packet = _packet(real_hook=real_hook, delivery=delivery)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_DELIVERY_INVALID,
        )
        self.assertIn(
            "working_flow_codex_exec_jsonl_not_read",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "working_flow_codex_exec_jsonl_not_valid",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "working_flow_codex_exec_event_count_missing",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["official_e2e_working_flow_proven"])
        self.assertFalse(packet["official_command_execution_delivery_joined_to_working_flow"])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_real_hook_contract_failures_block_join(self) -> None:
        real_hook, delivery = _positive_pair()
        cases = {
            "missing_file": (
                real_hook,
                {**_file_metadata(), "real_custom_hook_proof_file_read": False},
                "real_custom_hook_proof_file_not_read",
            ),
            "wrong_packet_kind": (
                {**real_hook, "packet_kind": "wrong"},
                _file_metadata(),
                "real_custom_hook_proof_packet_kind_invalid",
            ),
            "hook_not_run": (
                {**real_hook, "user_prompt_submit_hook_ran": False},
                _file_metadata(),
                "user_prompt_submit_hook_not_run",
            ),
            "changed_files_not_empty": (
                {**real_hook, "changed_files": ["unexpected.json"]},
                _file_metadata(),
                "real_custom_hook_proof_changed_files_not_empty",
            ),
        }
        for name, (real_hook_source, metadata, reason) in cases.items():
            with self.subTest(name=name):
                packet = _packet(
                    real_hook=real_hook_source,
                    delivery=delivery,
                    metadata=metadata,
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_HOOK_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["official_e2e_working_flow_proven"])
                _assert_no_ui_native_or_product_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                _assert_no_writes(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_delivery_join_contract_failures_block_join(self) -> None:
        real_hook, delivery = _positive_pair()
        cases = {
            "missing_file": (
                delivery,
                {
                    **_file_metadata(),
                    "official_working_flow_delivery_join_file_read": False,
                },
                "official_working_flow_delivery_join_file_not_read",
            ),
            "wrong_packet_kind": (
                {**delivery, "packet_kind": "wrong"},
                _file_metadata(),
                "official_working_flow_delivery_join_packet_kind_invalid",
            ),
            "working_flow_not_proven": (
                {**delivery, "codex_working_flow_delivery_proven": False},
                _file_metadata(),
                "codex_working_flow_delivery_not_proven",
            ),
            "lineage_not_proven": (
                {**delivery, "official_delivery_candidate_lineage_proven": False},
                _file_metadata(),
                "official_working_flow_delivery_join_lineage_not_proven",
            ),
            "lineage_not_file_backed": (
                {**delivery, "official_observation_lineage_file_backed": False},
                _file_metadata(),
                "official_working_flow_delivery_join_lineage_not_file_backed",
            ),
            "missing_pass_through_digest": (
                {**delivery, "working_flow_source_prompt_digest": ""},
                _file_metadata(),
                "working_flow_source_prompt_digest_missing",
            ),
            "missing_hook_event_digest": (
                {**delivery, "working_flow_source_hook_event_digest": ""},
                _file_metadata(),
                "working_flow_source_hook_event_digest_missing",
            ),
            "missing_hook_thread_and_turn_digest": (
                {
                    **delivery,
                    "working_flow_source_hook_thread_digest": "",
                    "working_flow_source_hook_turn_digest": "",
                },
                _file_metadata(),
                "working_flow_source_hook_thread_or_turn_digest_missing",
            ),
        }
        for name, (delivery_source, metadata, reason) in cases.items():
            with self.subTest(name=name):
                packet = _packet(
                    real_hook=real_hook,
                    delivery=delivery_source,
                    metadata=metadata,
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_DELIVERY_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["official_e2e_working_flow_proven"])
                _assert_no_ui_native_or_product_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                _assert_no_writes(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_digest_mismatches_block_join_as_not_bound(self) -> None:
        real_hook, delivery = _positive_pair()
        cases = {
            "prompt_mismatch": (
                {**delivery, "working_flow_source_prompt_digest": "f" * 64},
                "prompt_digest_mismatch",
            ),
            "route_mismatch": (
                {**delivery, "working_flow_selected_api_route_id_sha256": "e" * 64},
                "selected_route_digest_mismatch",
            ),
            "live_response_mismatch": (
                {**delivery, "working_flow_live_provider_response_digest": "d" * 64},
                "live_provider_response_digest_mismatch",
            ),
            "controlled_response_mismatch": (
                {
                    **delivery,
                    "working_flow_controlled_provider_response_digest": "c" * 64,
                },
                "controlled_provider_response_digest_mismatch",
            ),
            "route_bound_request_mismatch": (
                {**delivery, "working_flow_route_bound_request_sha256": "b" * 64},
                "route_bound_request_digest_mismatch",
            ),
            "hook_event_mismatch": (
                {**delivery, "working_flow_source_hook_event_digest": "a" * 64},
                "hook_event_digest_mismatch",
            ),
            "hook_thread_mismatch": (
                {**delivery, "working_flow_source_hook_thread_digest": "9" * 64},
                "hook_thread_digest_mismatch",
            ),
            "hook_session_mismatch": (
                {**delivery, "working_flow_source_hook_session_digest": "8" * 64},
                "hook_session_digest_mismatch",
            ),
        }
        for name, (delivery_source, reason) in cases.items():
            with self.subTest(name=name):
                packet = _packet(real_hook=real_hook, delivery=delivery_source)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_NOT_BOUND,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["official_e2e_working_flow_proven"])
                _assert_no_ui_native_or_product_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                _assert_no_writes(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unsafe_claims_and_secret_leaks_block_join(self) -> None:
        real_hook, delivery = _positive_pair()
        cases = {
            "real_hook_product_ready": (
                {**real_hook, "product_ready": True},
                delivery,
                "real_hook_product_ready",
            ),
            "real_hook_custom_ui": (
                {**real_hook, "custom_codex_ui_visibility_proven": True},
                delivery,
                "real_hook_custom_codex_ui_visibility_claimed",
            ),
            "delivery_product_ready": (
                real_hook,
                {**delivery, "product_ready": True},
                "delivery_product_ready",
            ),
            "delivery_custom_ui": (
                real_hook,
                {**delivery, "custom_codex_ui_visibility_proven": True},
                "delivery_custom_codex_ui_visibility_claimed",
            ),
            "real_hook_secret_payload": (
                {**real_hook, "debug_secret_payload": PROMPT},
                delivery,
                "real_hook_packet_secret_leak",
            ),
            "delivery_secret_payload": (
                real_hook,
                {**delivery, "debug_secret_payload": ROUTE_ID},
                "delivery_join_packet_secret_leak",
            ),
        }
        for name, (real_hook_source, delivery_source, reason) in cases.items():
            with self.subTest(name=name):
                packet = _packet(real_hook=real_hook_source, delivery=delivery_source)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_UNSAFE_SOURCE,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["official_e2e_working_flow_proven"])
                _assert_no_ui_native_or_product_claim(self, packet)
                if "secret_payload" not in name:
                    _assert_no_raw_prompt_route_or_provider(self, packet)
                _assert_no_writes(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_reads_packet_files_and_emits_join_packet(self) -> None:
        real_hook, delivery = _positive_pair()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_hook_file = root / "real-hook.json"
            delivery_file = root / "delivery.json"
            real_hook_file.write_text(
                json.dumps(real_hook, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            delivery_file.write_text(
                json.dumps(delivery, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "official-e2e-working-flow-proof-join",
                        "--real-custom-hook-proof-file",
                        str(real_hook_file),
                        "--official-working-flow-delivery-join-file",
                        str(delivery_file),
                        "--json",
                    ]
                )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertTrue(payload["official_e2e_working_flow_proven"])
        self.assertTrue(payload["custom_codex_hook_to_official_working_flow_bound"])
        _assert_no_ui_native_or_product_claim(self, payload)
        _assert_no_raw_prompt_route_or_provider(self, payload)
        _assert_no_writes(self, payload)
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])

    def test_cli_blocks_missing_files_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            missing_real_hook = root / "missing-real-hook.json"
            missing_delivery = root / "missing-delivery.json"
            stdout = io.StringIO()

            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "official-e2e-working-flow-proof-join",
                        "--real-custom-hook-proof-file",
                        str(missing_real_hook),
                        "--official-working-flow-delivery-join-file",
                        str(missing_delivery),
                        "--json",
                    ]
                )

        payload = json.loads(stdout.getvalue())
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(
            payload["machine_error_code"],
            proof.OFFICIAL_E2E_WORKING_FLOW_PROOF_JOIN_HOOK_INVALID,
        )
        self.assertFalse(payload["real_custom_hook_proof_file_present"])
        self.assertFalse(payload["official_working_flow_delivery_join_file_present"])
        self.assertIn("real_custom_hook_proof_file_not_read", payload["blocking_reasons"])
        self.assertFalse(payload["official_e2e_working_flow_proven"])
        _assert_no_ui_native_or_product_claim(self, payload)
        _assert_no_writes(self, payload)
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])

    def test_cli_effect_classifier_marks_e2e_join_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "official-e2e-working-flow-proof-join",
                "--real-custom-hook-proof-file",
                "real-hook.json",
                "--official-working-flow-delivery-join-file",
                "delivery.json",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")

    def test_cli_emits_join_packet_from_runner(self) -> None:
        expected = _packet()
        stdout = io.StringIO()

        with (
            mock.patch(
                "wild_boar_proxy.cli.run_official_e2e_working_flow_proof_join_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "official-e2e-working-flow-proof-join",
                    "--real-custom-hook-proof-file",
                    "real-hook.json",
                    "--official-working-flow-delivery-join-file",
                    "delivery.json",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertTrue(payload["official_e2e_working_flow_proven"])
        run_command.assert_called_once_with(
            real_custom_hook_proof_file="real-hook.json",
            official_working_flow_delivery_join_file="delivery.json",
        )
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()
