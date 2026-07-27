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
from wild_boar_proxy import codex_transcript_delivery_observation as transcript
from wild_boar_proxy import official_mcp_approved_codex_exec_source_observation as proof
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_official_mcp_assistant_continuation_observation import (  # noqa: E402
    PROMPT,
    RAW_PROVIDER_TEXT,
    ROUTE_ID,
    _assistant_event,
    _events,
    _jsonl,
    _packet as _assistant_continuation_packet,
    _subagent_event,
)


def _positive_source_and_events() -> tuple[dict[str, object], list[dict[str, object]]]:
    _handoff_source, events = _events()
    return _assistant_continuation_packet(events=events), events


def _file_metadata(event_count: int) -> dict[str, object]:
    return {
        "official_assistant_continuation_observation_file_required": True,
        "official_assistant_continuation_observation_file_present": True,
        "official_assistant_continuation_observation_file_read": True,
        "official_assistant_continuation_observation_file_valid_json": True,
        "official_assistant_continuation_observation_file_mapping": True,
        "official_assistant_continuation_observation_file_error_code": "",
        "official_assistant_continuation_observation_file_path_recorded": False,
        "codex_exec_jsonl_file_required": True,
        "codex_exec_jsonl_file_present": True,
        "codex_exec_jsonl_file_read": True,
        "codex_exec_jsonl_file_valid_jsonl": True,
        "codex_exec_jsonl_file_error_code": "",
        "codex_exec_jsonl_file_path_recorded": False,
        "codex_exec_jsonl_parse_error_count": 0,
        "codex_exec_event_count": event_count,
    }


def _packet(
    *,
    source: dict[str, object] | None = None,
    events: list[dict[str, object]] | None = None,
    approved_source_kind: str = proof.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    if source is None or events is None:
        default_source, default_events = _positive_source_and_events()
        source = default_source if source is None else source
        events = default_events if events is None else events
    return proof.build_official_mcp_approved_codex_exec_source_observation_packet(
        assistant_continuation_observation_packet=source,
        codex_exec_events=events,
        approved_source_kind=approved_source_kind,
        file_metadata=_file_metadata(len(events)) if metadata is None else metadata,
        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
    )


def _assert_no_product_ui_live_or_working_flow_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["codex_working_flow_delivery_proven"])
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


class OfficialMcpApprovedCodexExecSourceObservationTests(unittest.TestCase):
    def test_positive_observes_official_continuation_in_approved_exec_source(
        self,
    ) -> None:
        source, events = _positive_source_and_events()

        packet = _packet(source=source, events=events)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            proof.OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["source_valid"])
        self.assertTrue(packet["official_assistant_continuation_observation_valid"])
        self.assertTrue(packet["transcript_tool_result_observed"])
        self.assertTrue(packet["assistant_continuation_observed"])
        self.assertTrue(packet["assistant_response_after_tool_result"])
        self.assertTrue(packet["assistant_continuation_bound_to_tool_result"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertTrue(packet["handoff_payload_digest"])
        self.assertTrue(packet["codex_exec_transcript_sha256"])
        self.assertEqual(
            packet["approved_source_kind"],
            proof.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
        )
        self.assertTrue(packet["official_assistant_continuation_observation_file_backed"])
        self.assertTrue(packet["official_codex_exec_jsonl_file_backed"])
        self.assertTrue(packet["official_observation_lineage_file_backed"])
        self.assertTrue(packet["official_observation_lineage_proven"])
        self.assertEqual(packet["official_observation_lineage_failures"], [])
        self.assertTrue(packet["approved_source_kind_allowed"])
        self.assertTrue(packet["approved_codex_exec_source_observed"])
        self.assertTrue(packet["approved_source_read"])
        self.assertTrue(packet["approved_source_events_observed"])
        self.assertTrue(packet["approved_source_digest"])
        self.assertTrue(packet["assistant_continuation_source_digest"])
        self.assertTrue(packet["approved_source_digest_bound"])
        self.assertTrue(packet["approved_source_digest_matches_continuation"])
        self.assertTrue(packet["matching_mcp_tool_result_observed"])
        self.assertTrue(packet["approved_source_assistant_output_observed"])
        self.assertTrue(packet["approved_source_marker_observed"])
        self.assertFalse(packet["approved_source_marker_digest_mismatch"])
        self.assertTrue(packet["approved_source_marker_bound_to_handoff_digest"])
        self.assertEqual(
            packet["approved_source_marker_digest"],
            packet["handoff_payload_digest"],
        )
        self.assertEqual(
            packet["approved_source_marker_binding_method"],
            "safe_digest_metadata",
        )
        self.assertTrue(packet["assistant_continuation_source_bound"])
        self.assertEqual(packet["source_failures"], [])
        self.assertEqual(packet["source_unsafe_claim_failures"], [])
        self.assertEqual(packet["approved_source_failures"], [])
        self.assertEqual(packet["approved_source_unsafe_failures"], [])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["codex_native_subagent_used_as_dip"])
        self.assertFalse(packet["approved_source_secret_value_present"])
        _assert_no_product_ui_live_or_working_flow_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_non_file_backed_observation_cannot_be_approved_source(self) -> None:
        source, events = _positive_source_and_events()

        packet = _packet(source=source, events=events, metadata={})

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_SOURCE_INVALID,
        )
        self.assertIn(
            "official_assistant_continuation_observation_file_not_read",
            packet["blocking_reasons"],
        )
        self.assertIn("codex_exec_jsonl_file_not_read", packet["blocking_reasons"])
        self.assertIn(
            "approved_exec_source_observation_not_file_backed",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["official_observation_lineage_file_backed"])
        self.assertFalse(packet["official_observation_lineage_proven"])
        self.assertFalse(packet["approved_codex_exec_source_observed"])
        self.assertFalse(packet["assistant_continuation_source_bound"])
        _assert_no_product_ui_live_or_working_flow_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_source_contract_and_unsafe_claims_block_before_exec_source(self) -> None:
        source, events = _positive_source_and_events()
        cases = {
            "wrong_packet_kind": (
                {"packet_kind": "wrong"},
                proof.OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_SOURCE_INVALID,
                "official_assistant_continuation_packet_kind_invalid",
            ),
            "status_not_ok": (
                {"status": "error"},
                proof.OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_SOURCE_INVALID,
                "official_assistant_continuation_packet_not_ok",
            ),
            "changed_files_not_empty": (
                {"changed_files": ["unexpected.json"]},
                proof.OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_SOURCE_INVALID,
                "official_assistant_continuation_changed_files_not_empty",
            ),
            "product_ready": (
                {"product_ready": True},
                proof.OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_UNSAFE_SOURCE,
                "product_ready_must_not_be_claimed",
            ),
            "raw_prompt": (
                {"raw_prompt_recorded": True},
                proof.OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_UNSAFE_SOURCE,
                "raw_prompt_recorded",
            ),
        }
        for name, (patch, machine_error, reason) in cases.items():
            with self.subTest(name=name):
                broken = dict(source)
                broken.update(patch)
                packet = _packet(source=broken, events=events)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_error)
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["approved_codex_exec_source_observed"])
                self.assertFalse(packet["assistant_continuation_source_bound"])
                _assert_no_product_ui_live_or_working_flow_claim(self, packet)
                if name != "raw_prompt":
                    _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unapproved_source_kind_blocks_fail_closed(self) -> None:
        packet = _packet(approved_source_kind="codex_native_observer_snapshot")

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_SOURCE_KIND_NOT_ALLOWED,
        )
        self.assertIn("approved_visible_source_kind_not_allowed", packet["blocking_reasons"])
        self.assertFalse(packet["approved_source_kind_allowed"])
        self.assertFalse(packet["approved_codex_exec_source_observed"])
        self.assertFalse(packet["assistant_continuation_source_bound"])
        _assert_no_product_ui_live_or_working_flow_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_approved_source_must_match_same_exec_transcript_and_marker(self) -> None:
        source, events = _positive_source_and_events()
        no_marker_events = list(events)
        no_marker_events[3] = _assistant_event(
            str(source["handoff_payload_digest"]),
            include_marker=False,
        )
        no_marker_source = dict(source)
        no_marker_source["codex_exec_transcript_sha256"] = (
            transcript._codex_exec_transcript_digest(no_marker_events)
        )
        different_events = list(events)
        different_events[3] = _assistant_event(
            str(source["handoff_payload_digest"]),
            text="Different approved source text.",
        )
        cases = {
            "source_digest_mismatch": (
                source,
                different_events,
                proof.OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_EXEC_SOURCE_INVALID,
                "visible_source_digest_not_bound",
            ),
            "marker_missing": (
                no_marker_source,
                no_marker_events,
                proof.OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_NOT_BOUND,
                "visible_source_marker_missing",
            ),
        }
        for name, (candidate_source, source_events, machine_error, reason) in cases.items():
            with self.subTest(name=name):
                packet = _packet(source=candidate_source, events=source_events)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_error)
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["approved_codex_exec_source_observed"])
                self.assertFalse(packet["assistant_continuation_source_bound"])
                _assert_no_product_ui_live_or_working_flow_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_approved_source_blocks_secret_and_native_subagent_imitation(self) -> None:
        source, events = _positive_source_and_events()
        secret_events = list(events)
        secret_events[3] = _assistant_event(
            str(source["handoff_payload_digest"]),
            text=f"Unsafe raw prompt: {PROMPT}",
        )
        subagent_events = [events[0], events[1], events[2], _subagent_event(), events[3], events[4]]
        cases = {
            "secret": (secret_events, "secret_value_present_in_visible_source"),
            "subagent": (subagent_events, "native_codex_subagent_used_as_dip"),
        }
        for name, (source_events, reason) in cases.items():
            with self.subTest(name=name):
                packet = _packet(source=source, events=source_events)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_EXEC_SOURCE_UNSAFE,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["approved_codex_exec_source_observed"])
                _assert_no_product_ui_live_or_working_flow_claim(self, packet)
                if name == "secret":
                    self.assertTrue(packet["approved_source_secret_value_present"])
                else:
                    _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_reads_source_and_exec_jsonl_and_emits_packet(self) -> None:
        source, events = _positive_source_and_events()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = root / "assistant-continuation.json"
            jsonl_file = root / "codex.jsonl"
            source_file.write_text(json.dumps(source, sort_keys=True) + "\n", encoding="utf-8")
            jsonl_file.write_text(_jsonl(events) + "\n", encoding="utf-8")
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "official-mcp-approved-codex-exec-source-observe",
                        "--assistant-continuation-observation-file",
                        str(source_file),
                        "--approved-source-kind",
                        proof.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
                        "--codex-exec-jsonl-file",
                        str(jsonl_file),
                        "--json",
                    ]
                )

        packet = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            packet["packet_kind"],
            proof.OFFICIAL_MCP_APPROVED_CODEX_EXEC_SOURCE_OBSERVATION_PACKET_KIND,
        )
        self.assertTrue(packet["official_assistant_continuation_observation_file_present"])
        self.assertTrue(packet["official_assistant_continuation_observation_file_read"])
        self.assertFalse(packet["official_assistant_continuation_observation_file_path_recorded"])
        self.assertTrue(packet["codex_exec_jsonl_file_present"])
        self.assertTrue(packet["codex_exec_jsonl_file_read"])
        self.assertFalse(packet["codex_exec_jsonl_file_path_recorded"])
        self.assertTrue(packet["official_observation_lineage_file_backed"])
        self.assertTrue(packet["official_observation_lineage_proven"])
        self.assertTrue(packet["approved_codex_exec_source_observed"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_or_malformed_files_block_cli(self) -> None:
        source, events = _positive_source_and_events()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = root / "assistant-continuation.json"
            source_file.write_text(json.dumps(source, sort_keys=True) + "\n", encoding="utf-8")
            malformed_source = root / "malformed.json"
            malformed_source.write_text("{not-json}\n", encoding="utf-8")
            jsonl_file = root / "codex.jsonl"
            jsonl_file.write_text(_jsonl(events) + "\n", encoding="utf-8")
            malformed_jsonl = root / "malformed.jsonl"
            malformed_jsonl.write_text("{not-json}\n", encoding="utf-8")
            cases = {
                "missing_source": (root / "missing.json", jsonl_file),
                "malformed_source": (malformed_source, jsonl_file),
                "missing_jsonl": (source_file, root / "missing.jsonl"),
                "malformed_jsonl": (source_file, malformed_jsonl),
            }
            for name, (candidate_source, candidate_jsonl) in cases.items():
                with self.subTest(name=name):
                    stdout = io.StringIO()
                    with mock.patch("sys.stdout", stdout):
                        exit_code = cli_mod.main(
                            [
                                "router-hook",
                                "official-mcp-approved-codex-exec-source-observe",
                                "--assistant-continuation-observation-file",
                                str(candidate_source),
                                "--codex-exec-jsonl-file",
                                str(candidate_jsonl),
                                "--json",
                            ]
                        )
                    packet = json.loads(stdout.getvalue())

                    self.assertEqual(exit_code, 1)
                    self.assertEqual(packet["status"], "error")
                    self.assertFalse(packet["approved_codex_exec_source_observed"])
                    self.assertFalse(packet["assistant_continuation_source_bound"])
                    _assert_no_product_ui_live_or_working_flow_claim(self, packet)
                    self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_official_exec_source_observation_as_probe(
        self,
    ) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "official-mcp-approved-codex-exec-source-observe",
                "--assistant-continuation-observation-file",
                "source.json",
                "--codex-exec-jsonl-file",
                "codex.jsonl",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")

    def test_cli_emits_official_exec_source_observation_packet(self) -> None:
        expected = _packet()
        stdout = io.StringIO()

        with (
            mock.patch(
                "wild_boar_proxy.cli."
                "run_official_mcp_approved_codex_exec_source_observation_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "official-mcp-approved-codex-exec-source-observe",
                    "--assistant-continuation-observation-file",
                    "source.json",
                    "--codex-exec-jsonl-file",
                    "codex.jsonl",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertTrue(payload["approved_codex_exec_source_observed"])
        self.assertFalse(payload["custom_codex_ui_visibility_proven"])
        self.assertFalse(payload["codex_working_flow_delivery_proven"])
        self.assertFalse(payload["product_ready"])
        run_command.assert_called_once()
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()
