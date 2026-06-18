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
from wild_boar_proxy import official_mcp_delivery_candidate_join as proof
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_official_mcp_approved_codex_exec_source_observation import (  # noqa: E402
    PROMPT,
    RAW_PROVIDER_TEXT,
    ROUTE_ID,
    _packet as _approved_exec_source_packet,
)


def _file_metadata() -> dict[str, object]:
    return {
        "official_approved_exec_source_file_required": True,
        "official_approved_exec_source_file_present": True,
        "official_approved_exec_source_file_read": True,
        "official_approved_exec_source_file_valid_json": True,
        "official_approved_exec_source_file_mapping": True,
        "official_approved_exec_source_file_error_code": "",
        "official_approved_exec_source_file_path_recorded": False,
    }


def _source() -> dict[str, object]:
    return _approved_exec_source_packet()


def _packet(
    *,
    source: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    return proof.build_official_mcp_delivery_candidate_join_packet(
        approved_exec_source_observation_packet=_source() if source is None else source,
        file_metadata=_file_metadata() if metadata is None else metadata,
        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
    )


def _assert_no_working_flow_ui_live_or_product_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["codex_working_flow_delivery_proven"])
    testcase.assertFalse(packet["working_flow_delivery_proven"])
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["native_free_chat_router_product_ready"])
    testcase.assertFalse(packet["native_free_chat_router_delivery_proven"])
    testcase.assertFalse(packet["live_provider_proven"])
    testcase.assertFalse(packet["live_provider_response_proven"])
    testcase.assertFalse(packet["external_live_provider_response_proven"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_codex_working_flow_delivery"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_ui"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_live_provider"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


def _assert_no_raw_prompt_route_or_provider(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in (PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT):
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


class OfficialMcpDeliveryCandidateJoinTests(unittest.TestCase):
    def test_positive_promotes_approved_exec_source_to_delivery_candidate(self) -> None:
        packet = _packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            proof.OFFICIAL_MCP_DELIVERY_CANDIDATE_JOIN_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["official_approved_exec_source_file_read"])
        self.assertFalse(packet["official_approved_exec_source_file_path_recorded"])
        self.assertTrue(packet["source_valid"])
        self.assertEqual(packet["source_failures"], [])
        self.assertEqual(packet["source_binding_failures"], [])
        self.assertEqual(packet["source_unsafe_claim_failures"], [])
        self.assertTrue(packet["approved_exec_source_delivery_candidate"])
        self.assertTrue(packet["delivery_candidate_source_file_backed"])
        self.assertEqual(
            packet["delivery_candidate_truth_source"],
            proof.DELIVERY_CANDIDATE_TRUTH_SOURCE,
        )
        self.assertEqual(
            packet["source_kind_claim_ceiling"],
            proof.DELIVERY_CANDIDATE_CLAIM_CEILING,
        )
        self.assertTrue(packet["official_approved_exec_source_observation_valid"])
        self.assertTrue(packet["approved_codex_exec_source_observed"])
        self.assertTrue(packet["assistant_continuation_source_bound"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertTrue(packet["transcript_tool_result_observed"])
        self.assertTrue(packet["assistant_continuation_observed"])
        self.assertEqual(
            packet["approved_source_kind"],
            proof.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
        )
        self.assertTrue(packet["approved_source_kind_allowed"])
        self.assertTrue(packet["approved_source_events_observed"])
        self.assertTrue(packet["approved_source_assistant_output_observed"])
        self.assertTrue(packet["matching_mcp_tool_result_observed"])
        self.assertTrue(packet["handoff_payload_digest"])
        self.assertTrue(packet["codex_exec_transcript_sha256"])
        self.assertEqual(
            packet["approved_source_digest"],
            packet["codex_exec_transcript_sha256"],
        )
        self.assertEqual(
            packet["assistant_continuation_source_digest"],
            packet["codex_exec_transcript_sha256"],
        )
        self.assertEqual(
            packet["approved_source_marker_digest"],
            packet["handoff_payload_digest"],
        )
        self.assertTrue(packet["approved_source_digest_bound_to_transcript"])
        self.assertTrue(packet["assistant_source_digest_bound_to_transcript"])
        self.assertTrue(packet["approved_source_marker_bound_to_handoff_digest"])
        self.assertTrue(packet["working_flow_delivery_candidate_only"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["codex_native_subagent_used_as_dip"])
        _assert_no_working_flow_ui_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_source_contract_failures_block_candidate(self) -> None:
        source = _source()
        cases = {
            "missing_file": (
                source,
                {**_file_metadata(), "official_approved_exec_source_file_read": False},
                "official_approved_exec_source_file_not_read",
            ),
            "wrong_packet_kind": (
                {**source, "packet_kind": "wrong"},
                _file_metadata(),
                "approved_exec_source_packet_kind_invalid",
            ),
            "status_not_ok": (
                {**source, "status": "error"},
                _file_metadata(),
                "approved_exec_source_packet_not_ok",
            ),
            "changed_files_not_empty": (
                {**source, "changed_files": ["unexpected.json"]},
                _file_metadata(),
                "approved_exec_source_changed_files_not_empty",
            ),
            "missing_observation": (
                {**source, "approved_codex_exec_source_observed": False},
                _file_metadata(),
                "approved_codex_exec_source_not_observed",
            ),
        }
        for name, (candidate_source, metadata, reason) in cases.items():
            with self.subTest(name=name):
                packet = _packet(source=candidate_source, metadata=metadata)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_MCP_DELIVERY_CANDIDATE_SOURCE_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["approved_exec_source_delivery_candidate"])
                _assert_no_working_flow_ui_live_or_product_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                _assert_no_writes(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_digest_binding_failures_block_candidate_as_not_bound(self) -> None:
        source = _source()
        cases = {
            "approved_source_digest_mismatch": (
                {**source, "approved_source_digest": "f" * 64},
                "approved_source_digest_not_bound_to_transcript",
            ),
            "assistant_source_digest_mismatch": (
                {**source, "assistant_continuation_source_digest": "e" * 64},
                "assistant_source_digest_not_bound_to_transcript",
            ),
            "marker_digest_mismatch": (
                {**source, "approved_source_marker_digest": "d" * 64},
                "approved_source_marker_not_bound_to_handoff_digest",
            ),
        }
        for name, (candidate_source, reason) in cases.items():
            with self.subTest(name=name):
                packet = _packet(source=candidate_source)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_MCP_DELIVERY_CANDIDATE_NOT_BOUND,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["approved_exec_source_delivery_candidate"])
                self.assertFalse(packet["approved_source_digest_bound_to_transcript"])
                _assert_no_working_flow_ui_live_or_product_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                _assert_no_writes(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unsafe_preclaims_and_secret_leaks_block_candidate(self) -> None:
        source = _source()
        cases = {
            "working_flow_preclaim": (
                {**source, "codex_working_flow_delivery_proven": True},
                "codex_working_flow_delivery_must_not_be_preclaimed",
            ),
            "custom_ui_preclaim": (
                {**source, "custom_codex_ui_visibility_proven": True},
                "custom_codex_ui_visibility_must_not_be_claimed",
            ),
            "product_ready": (
                {**source, "product_ready": True},
                "product_ready_must_not_be_claimed",
            ),
            "fallback": ({**source, "fallback_used": True}, "fallback_used"),
            "secret_flag": (
                {**source, "approved_source_secret_value_present": True},
                "secret_value_present_in_approved_source",
            ),
            "secret_payload": (
                {**source, "debug_raw_prompt": PROMPT},
                "approved_exec_source_packet_secret_leak",
            ),
        }
        for name, (candidate_source, reason) in cases.items():
            with self.subTest(name=name):
                packet = _packet(source=candidate_source)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_MCP_DELIVERY_CANDIDATE_UNSAFE_SOURCE,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["approved_exec_source_delivery_candidate"])
                _assert_no_working_flow_ui_live_or_product_claim(self, packet)
                if name != "secret_payload":
                    _assert_no_raw_prompt_route_or_provider(self, packet)
                _assert_no_writes(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_reads_source_file_and_emits_candidate_packet(self) -> None:
        source = _source()
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "approved-source.json"
            source_file.write_text(json.dumps(source, sort_keys=True) + "\n", encoding="utf-8")
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "official-mcp-delivery-candidate-join",
                        "--approved-exec-source-observation-file",
                        str(source_file),
                        "--json",
                    ]
                )

        packet = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(packet["official_approved_exec_source_file_present"])
        self.assertTrue(packet["official_approved_exec_source_file_read"])
        self.assertFalse(packet["official_approved_exec_source_file_path_recorded"])
        self.assertTrue(packet["approved_exec_source_delivery_candidate"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["product_ready"])
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_blocks_missing_or_malformed_source_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            malformed = root / "malformed.json"
            malformed.write_text("{not-json}\n", encoding="utf-8")
            cases = {"missing": root / "missing.json", "malformed": malformed}
            for name, source_file in cases.items():
                with self.subTest(name=name):
                    stdout = io.StringIO()
                    with mock.patch("sys.stdout", stdout):
                        exit_code = cli_mod.main(
                            [
                                "router-hook",
                                "official-mcp-delivery-candidate-join",
                                "--approved-exec-source-observation-file",
                                str(source_file),
                                "--json",
                            ]
                        )
                    packet = json.loads(stdout.getvalue())

                    self.assertEqual(exit_code, 1)
                    self.assertEqual(packet["status"], "error")
                    self.assertEqual(
                        packet["machine_error_code"],
                        proof.OFFICIAL_MCP_DELIVERY_CANDIDATE_SOURCE_INVALID,
                    )
                    self.assertFalse(packet["approved_exec_source_delivery_candidate"])
                    _assert_no_working_flow_ui_live_or_product_claim(self, packet)
                    _assert_no_writes(self, packet)
                    self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_candidate_join_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "official-mcp-delivery-candidate-join",
                "--approved-exec-source-observation-file",
                "source.json",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")

    def test_cli_emits_candidate_packet_from_runner(self) -> None:
        expected = _packet()
        stdout = io.StringIO()

        with (
            mock.patch(
                "wild_boar_proxy.cli.run_official_mcp_delivery_candidate_join_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "official-mcp-delivery-candidate-join",
                    "--approved-exec-source-observation-file",
                    "source.json",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertTrue(payload["approved_exec_source_delivery_candidate"])
        self.assertFalse(payload["codex_working_flow_delivery_proven"])
        self.assertFalse(payload["custom_codex_ui_visibility_proven"])
        self.assertFalse(payload["product_ready"])
        _assert_no_writes(self, payload)
        run_command.assert_called_once_with(
            approved_exec_source_observation_file="source.json",
        )
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()
