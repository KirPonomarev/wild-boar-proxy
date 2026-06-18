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
from wild_boar_proxy import official_mcp_working_flow_delivery_join as proof
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_codex_working_flow_delivery_proof import (  # noqa: E402
    EXPECTED_TEXT,
    PROMPT as WORKING_FLOW_PROMPT,
    RAW_PROVIDER_TEXT as WORKING_FLOW_RAW_PROVIDER_TEXT,
    ROUTE_ID as WORKING_FLOW_ROUTE_ID,
    _events_for_packet,
    _file_metadata as _working_flow_file_metadata,
    _integrated_packet,
)
from test_official_mcp_delivery_candidate_join import (  # noqa: E402
    PROMPT as CANDIDATE_PROMPT,
    RAW_PROVIDER_TEXT as CANDIDATE_RAW_PROVIDER_TEXT,
    ROUTE_ID as CANDIDATE_ROUTE_ID,
    _packet as _candidate_packet,
)


def _file_metadata() -> dict[str, object]:
    return {
        "official_delivery_candidate_file_required": True,
        "official_delivery_candidate_file_present": True,
        "official_delivery_candidate_file_read": True,
        "official_delivery_candidate_file_valid_json": True,
        "official_delivery_candidate_file_mapping": True,
        "official_delivery_candidate_file_error_code": "",
        "official_delivery_candidate_file_path_recorded": False,
        "working_flow_delivery_proof_file_required": True,
        "working_flow_delivery_proof_file_present": True,
        "working_flow_delivery_proof_file_read": True,
        "working_flow_delivery_proof_file_valid_json": True,
        "working_flow_delivery_proof_file_mapping": True,
        "working_flow_delivery_proof_file_error_code": "",
        "working_flow_delivery_proof_file_path_recorded": False,
    }


def _secret_values() -> list[str]:
    return [
        CANDIDATE_PROMPT,
        CANDIDATE_ROUTE_ID,
        CANDIDATE_RAW_PROVIDER_TEXT,
        WORKING_FLOW_PROMPT,
        WORKING_FLOW_ROUTE_ID,
        EXPECTED_TEXT,
        WORKING_FLOW_RAW_PROVIDER_TEXT,
    ]


def _working_flow_packet() -> dict[str, object]:
    source = _integrated_packet()
    events = _events_for_packet(source)
    packet = working_flow.build_codex_working_flow_delivery_proof_packet(
        source,
        events,
        file_metadata=_working_flow_file_metadata(),
        secret_values=_secret_values(),
    )
    assert packet["status"] == "ok"
    return packet


def _positive_pair() -> tuple[dict[str, object], dict[str, object]]:
    working_flow_packet = _working_flow_packet()
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
    return candidate, working_flow_packet


def _packet(
    *,
    candidate: dict[str, object] | None = None,
    working_flow_packet: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    positive_candidate, positive_working_flow = _positive_pair()
    return proof.build_official_mcp_working_flow_delivery_join_packet(
        official_delivery_candidate_packet=(
            positive_candidate if candidate is None else candidate
        ),
        working_flow_delivery_proof_packet=(
            positive_working_flow if working_flow_packet is None else working_flow_packet
        ),
        file_metadata=_file_metadata() if metadata is None else metadata,
        secret_values=_secret_values(),
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


class OfficialMcpWorkingFlowDeliveryJoinTests(unittest.TestCase):
    def test_positive_joins_official_candidate_to_canonical_working_flow_delivery(
        self,
    ) -> None:
        packet = _packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            proof.OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["official_delivery_candidate_file_read"])
        self.assertTrue(packet["working_flow_delivery_proof_file_read"])
        self.assertFalse(packet["official_delivery_candidate_file_path_recorded"])
        self.assertFalse(packet["working_flow_delivery_proof_file_path_recorded"])
        self.assertEqual(
            packet["working_flow_join_truth_source"],
            proof.WORKING_FLOW_JOIN_TRUTH_SOURCE,
        )
        self.assertEqual(
            packet["source_kind_claim_ceiling"],
            proof.WORKING_FLOW_JOIN_CLAIM_CEILING,
        )
        self.assertTrue(packet["official_delivery_candidate_valid"])
        self.assertTrue(packet["canonical_working_flow_delivery_valid"])
        self.assertTrue(packet["candidate_bound_to_working_flow"])
        self.assertEqual(packet["candidate_failures"], [])
        self.assertEqual(packet["working_flow_failures"], [])
        self.assertEqual(packet["binding_failures"], [])
        self.assertEqual(packet["source_unsafe_claim_failures"], [])
        self.assertTrue(packet["approved_exec_source_delivery_candidate"])
        self.assertTrue(packet["delivery_candidate_source_file_backed"])
        self.assertTrue(packet["official_approved_exec_source_observation_valid"])
        self.assertTrue(packet["approved_codex_exec_source_observed"])
        self.assertTrue(packet["approved_delivery_surface_proven"])
        self.assertTrue(packet["live_provider_proven"])
        self.assertTrue(packet["live_provider_response_proven"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertFalse(packet["does_not_prove_live_provider"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertTrue(packet["handoff_delivered"])
        self.assertTrue(packet["delivery_observed"])
        self.assertTrue(packet["approved_handoff_ready"])
        self.assertTrue(packet["approved_handoff_payload_sanitized"])
        self.assertTrue(packet["candidate_handoff_payload_digest"])
        self.assertTrue(packet["working_flow_handoff_payload_digest"])
        self.assertEqual(
            packet["candidate_handoff_payload_digest"],
            packet["working_flow_handoff_payload_digest"],
        )
        self.assertEqual(
            packet["candidate_codex_exec_transcript_sha256"],
            packet["working_flow_codex_exec_transcript_sha256"],
        )
        self.assertTrue(packet["candidate_transcript_bound_to_working_flow"])
        self.assertTrue(
            packet["candidate_approved_source_bound_to_working_flow_transcript"]
        )
        self.assertTrue(
            packet["candidate_assistant_source_bound_to_working_flow_transcript"]
        )
        self.assertTrue(packet["candidate_handoff_bound_to_working_flow_handoff"])
        self.assertTrue(packet["candidate_marker_bound_to_working_flow_handoff"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["working_flow_delivery_proven"])
        self.assertTrue(packet["official_mcp_delivery_candidate_joined_to_working_flow"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["codex_native_subagent_used_as_dip"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_candidate_contract_failures_block_join(self) -> None:
        candidate, working_flow_packet = _positive_pair()
        cases = {
            "missing_file": (
                candidate,
                {**_file_metadata(), "official_delivery_candidate_file_read": False},
                "official_delivery_candidate_file_not_read",
            ),
            "wrong_packet_kind": (
                {**candidate, "packet_kind": "wrong"},
                _file_metadata(),
                "official_delivery_candidate_packet_kind_invalid",
            ),
            "status_not_ok": (
                {**candidate, "status": "error"},
                _file_metadata(),
                "official_delivery_candidate_packet_not_ok",
            ),
            "changed_files_not_empty": (
                {**candidate, "changed_files": ["unexpected.json"]},
                _file_metadata(),
                "official_delivery_candidate_changed_files_not_empty",
            ),
            "not_candidate": (
                {**candidate, "approved_exec_source_delivery_candidate": False},
                _file_metadata(),
                "approved_exec_source_delivery_candidate_not_true",
            ),
        }
        for name, (candidate_source, metadata, reason) in cases.items():
            with self.subTest(name=name):
                packet = _packet(
                    candidate=candidate_source,
                    working_flow_packet=working_flow_packet,
                    metadata=metadata,
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_CANDIDATE_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["codex_working_flow_delivery_proven"])
                self.assertFalse(packet["candidate_bound_to_working_flow"])
                _assert_no_ui_native_or_product_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                _assert_no_writes(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_working_flow_contract_failures_block_join(self) -> None:
        candidate, working_flow_packet = _positive_pair()
        cases = {
            "missing_file": (
                working_flow_packet,
                {
                    **_file_metadata(),
                    "working_flow_delivery_proof_file_read": False,
                },
                "working_flow_delivery_proof_file_not_read",
            ),
            "wrong_packet_kind": (
                {**working_flow_packet, "packet_kind": "wrong"},
                _file_metadata(),
                "working_flow_delivery_packet_kind_invalid",
            ),
            "delivery_not_observed": (
                {**working_flow_packet, "delivery_observed": False},
                _file_metadata(),
                "delivery_not_observed",
            ),
        }
        for name, (working_flow_source, metadata, reason) in cases.items():
            with self.subTest(name=name):
                packet = _packet(
                    candidate=candidate,
                    working_flow_packet=working_flow_source,
                    metadata=metadata,
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_WORKING_FLOW_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["codex_working_flow_delivery_proven"])
                self.assertFalse(packet["candidate_bound_to_working_flow"])
                _assert_no_ui_native_or_product_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                _assert_no_writes(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_binding_mismatch_blocks_join_as_not_bound(self) -> None:
        candidate, working_flow_packet = _positive_pair()
        cases = {
            "candidate_transcript_mismatch": (
                {**candidate, "codex_exec_transcript_sha256": "f" * 64},
                "candidate_transcript_not_bound_to_working_flow_transcript",
            ),
            "candidate_source_digest_mismatch": (
                {**candidate, "approved_source_digest": "e" * 64},
                "candidate_approved_source_not_bound_to_working_flow_transcript",
            ),
            "candidate_handoff_mismatch": (
                {**candidate, "handoff_payload_digest": "d" * 64},
                "candidate_handoff_not_bound_to_working_flow_handoff",
            ),
            "candidate_marker_mismatch": (
                {**candidate, "approved_source_marker_digest": "c" * 64},
                "candidate_marker_not_bound_to_working_flow_handoff",
            ),
        }
        for name, (candidate_source, reason) in cases.items():
            with self.subTest(name=name):
                packet = _packet(
                    candidate=candidate_source,
                    working_flow_packet=working_flow_packet,
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_NOT_BOUND,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["codex_working_flow_delivery_proven"])
                self.assertFalse(packet["candidate_bound_to_working_flow"])
                _assert_no_ui_native_or_product_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                _assert_no_writes(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unsafe_preclaims_and_secret_leaks_block_join(self) -> None:
        candidate, working_flow_packet = _positive_pair()
        cases = {
            "candidate_product_ready": (
                {**candidate, "product_ready": True},
                working_flow_packet,
                "candidate_product_ready_must_not_be_claimed",
            ),
            "candidate_working_flow_preclaim": (
                {**candidate, "codex_working_flow_delivery_proven": True},
                working_flow_packet,
                "candidate_codex_working_flow_delivery_must_not_be_preclaimed",
            ),
            "candidate_secret_payload": (
                {**candidate, "debug_raw_prompt": CANDIDATE_PROMPT},
                working_flow_packet,
                "candidate_packet_secret_leak",
            ),
            "working_flow_custom_ui": (
                candidate,
                {**working_flow_packet, "custom_codex_ui_visibility_proven": True},
                "working_flow_custom_codex_ui_visibility_must_not_be_claimed",
            ),
            "working_flow_product_ready": (
                candidate,
                {**working_flow_packet, "product_ready": True},
                "working_flow_product_ready_must_not_be_claimed",
            ),
            "working_flow_local_imitation": (
                candidate,
                {**working_flow_packet, "local_imitation_used": True},
                "working_flow_local_imitation_used",
            ),
            "working_flow_live_provider_preclaim_without_delivery": (
                candidate,
                {
                    **working_flow_packet,
                    "codex_working_flow_delivery_proven": False,
                },
                "live_provider_must_not_be_claimed",
            ),
            "working_flow_live_provider_claim_without_digest": (
                candidate,
                {
                    **working_flow_packet,
                    "live_provider_response_digest": "",
                },
                "live_provider_must_not_be_claimed",
            ),
            "working_flow_live_provider_claim_contradiction": (
                candidate,
                {
                    **working_flow_packet,
                    "does_not_prove_live_provider": True,
                },
                "live_provider_must_not_be_claimed",
            ),
        }
        for name, (candidate_source, working_flow_source, reason) in cases.items():
            with self.subTest(name=name):
                packet = _packet(
                    candidate=candidate_source,
                    working_flow_packet=working_flow_source,
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_MCP_WORKING_FLOW_DELIVERY_JOIN_UNSAFE_SOURCE,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["codex_working_flow_delivery_proven"])
                self.assertFalse(packet["candidate_bound_to_working_flow"])
                _assert_no_ui_native_or_product_claim(self, packet)
                if name != "candidate_secret_payload":
                    _assert_no_raw_prompt_route_or_provider(self, packet)
                _assert_no_writes(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_reads_packet_files_and_emits_join_packet(self) -> None:
        candidate, working_flow_packet = _positive_pair()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate_file = root / "candidate.json"
            working_flow_file = root / "working-flow.json"
            candidate_file.write_text(
                json.dumps(candidate, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            working_flow_file.write_text(
                json.dumps(working_flow_packet, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "official-mcp-working-flow-delivery-join",
                        "--delivery-candidate-file",
                        str(candidate_file),
                        "--working-flow-delivery-proof-file",
                        str(working_flow_file),
                        "--json",
                    ]
                )

        packet = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(packet["official_delivery_candidate_file_present"])
        self.assertTrue(packet["official_delivery_candidate_file_read"])
        self.assertFalse(packet["official_delivery_candidate_file_path_recorded"])
        self.assertTrue(packet["working_flow_delivery_proof_file_present"])
        self.assertTrue(packet["working_flow_delivery_proof_file_read"])
        self.assertFalse(packet["working_flow_delivery_proof_file_path_recorded"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["official_mcp_delivery_candidate_joined_to_working_flow"])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_blocks_missing_or_malformed_packet_files(self) -> None:
        candidate, working_flow_packet = _positive_pair()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate_file = root / "candidate.json"
            working_flow_file = root / "working-flow.json"
            malformed_file = root / "malformed.json"
            candidate_file.write_text(
                json.dumps(candidate, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            working_flow_file.write_text(
                json.dumps(working_flow_packet, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            malformed_file.write_text("{not-json}\n", encoding="utf-8")
            cases = {
                "missing_candidate": (root / "missing.json", working_flow_file),
                "malformed_working_flow": (candidate_file, malformed_file),
            }
            for name, (candidate_path, working_flow_path) in cases.items():
                with self.subTest(name=name):
                    stdout = io.StringIO()
                    with mock.patch("sys.stdout", stdout):
                        exit_code = cli_mod.main(
                            [
                                "router-hook",
                                "official-mcp-working-flow-delivery-join",
                                "--delivery-candidate-file",
                                str(candidate_path),
                                "--working-flow-delivery-proof-file",
                                str(working_flow_path),
                                "--json",
                            ]
                        )
                    packet = json.loads(stdout.getvalue())

                    self.assertEqual(exit_code, 1)
                    self.assertEqual(packet["status"], "error")
                    self.assertFalse(packet["codex_working_flow_delivery_proven"])
                    self.assertFalse(packet["candidate_bound_to_working_flow"])
                    _assert_no_ui_native_or_product_claim(self, packet)
                    _assert_no_writes(self, packet)
                    self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_join_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "official-mcp-working-flow-delivery-join",
                "--delivery-candidate-file",
                "candidate.json",
                "--working-flow-delivery-proof-file",
                "working-flow.json",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")

    def test_cli_emits_join_packet_from_runner(self) -> None:
        expected = _packet()
        stdout = io.StringIO()

        with (
            mock.patch(
                "wild_boar_proxy.cli.run_official_mcp_working_flow_delivery_join_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "official-mcp-working-flow-delivery-join",
                    "--delivery-candidate-file",
                    "candidate.json",
                    "--working-flow-delivery-proof-file",
                    "working-flow.json",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertTrue(payload["codex_working_flow_delivery_proven"])
        self.assertTrue(payload["official_mcp_delivery_candidate_joined_to_working_flow"])
        _assert_no_ui_native_or_product_claim(self, payload)
        _assert_no_writes(self, payload)
        run_command.assert_called_once_with(
            delivery_candidate_file="candidate.json",
            working_flow_delivery_proof_file="working-flow.json",
        )
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()
