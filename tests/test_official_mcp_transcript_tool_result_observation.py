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
from wild_boar_proxy import official_mcp_transcript_tool_result_observation as proof
from wild_boar_proxy import codex_transcript_delivery_observation as transcript
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text
from wild_boar_proxy.observed_machine_handoff_delivery import (
    DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
    _safe_delivery_payload,
)
from wild_boar_proxy.approved_handoff import (
    HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
    _safe_handoff_payload,
)


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_official_mcp_handoff_source_proof import (  # noqa: E402
    PROMPT,
    RAW_PROVIDER_TEXT,
    ROUTE_ID,
    _packet as _handoff_source_packet,
    _working_flow_source_packet,
)
from test_codex_working_flow_delivery_proof import (  # noqa: E402
    EXPECTED_TEXT as WORKING_FLOW_EXPECTED_TEXT,
    PROMPT as WORKING_FLOW_PROMPT,
    RAW_PROVIDER_TEXT as WORKING_FLOW_RAW_PROVIDER_TEXT,
    ROUTE_ID as WORKING_FLOW_ROUTE_ID,
    _events_for_packet as _working_flow_events_for_packet,
    _file_metadata as _working_flow_delivery_file_metadata,
    _integrated_packet as _working_flow_integrated_packet,
)


def _source_packet() -> dict[str, object]:
    return _handoff_source_packet()


def _delivery_payload_for_source(source: dict[str, object]) -> dict[str, object]:
    normalized = proof._normalized_controlled_dispatch(source)
    handoff_payload = _safe_handoff_payload(
        normalized,
        HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
    )
    return _safe_delivery_payload(
        handoff_payload,
        delivery_surface_kind=DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
    )


def _tool_result_event(
    structured_content: dict[str, object],
    *,
    server_name: str = "wbp",
    tool_name: str = "delegate_to_dip",
    is_error: bool = False,
    content_text: str | None = None,
) -> dict[str, object]:
    text = (
        json.dumps(
            structured_content,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        if content_text is None
        else content_text
    )
    return {
        "type": "item.completed",
        "item": {
            "id": "item-delegate-result",
            "type": "mcp_tool_result",
            "server_name": server_name,
            "tool_name": tool_name,
            "status": "completed",
            "result": {
                "content": [{"type": "text", "text": text}],
                "structuredContent": structured_content,
                "isError": is_error,
            },
        },
    }


def _assistant_event(structured_content: dict[str, object]) -> dict[str, object]:
    return {
        "type": "assistant/output",
        "item": {
            "id": "item-assistant-output",
            "type": "output_text",
            "role": "assistant",
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            structured_content,
                            ensure_ascii=True,
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    }
                ],
                "structuredContent": structured_content,
                "isError": False,
            },
        },
    }


def _events_for_source(
    source: dict[str, object],
    *,
    event: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    structured = _delivery_payload_for_source(source)
    return [
        {"type": "thread.started", "thread_id": "thread-official-transcript"},
        {"type": "turn.started"},
        _tool_result_event(structured) if event is None else event,
        {"type": "turn.completed"},
    ]


def _jsonl(events: list[dict[str, object]]) -> str:
    return "\n".join(json.dumps(event, ensure_ascii=True) for event in events)


def _packet(
    *,
    source: dict[str, object] | None = None,
    events: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    source_packet = _source_packet() if source is None else source
    return proof.build_official_mcp_transcript_tool_result_observation_packet(
        handoff_source_packet=source_packet,
        codex_exec_events=_events_for_source(source_packet) if events is None else events,
        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
    )


def _working_flow_source_events_and_packet() -> tuple[
    dict[str, object],
    list[dict[str, object]],
    dict[str, object],
]:
    integrated_source = _working_flow_integrated_packet()
    events = _working_flow_events_for_packet(integrated_source)
    working_flow_packet = working_flow.build_codex_working_flow_delivery_proof_packet(
        integrated_source,
        events,
        file_metadata=_working_flow_delivery_file_metadata(),
        secret_values=[
            WORKING_FLOW_PROMPT,
            WORKING_FLOW_ROUTE_ID,
            WORKING_FLOW_RAW_PROVIDER_TEXT,
            WORKING_FLOW_EXPECTED_TEXT,
        ],
    )
    source = _working_flow_source_packet(
        working_flow_delivery_packet=working_flow_packet
    )
    return source, events, working_flow_packet


def _working_flow_transcript_metadata(events: list[dict[str, object]]) -> dict[str, object]:
    return {
        "handoff_source_file_required": True,
        "handoff_source_file_present": True,
        "handoff_source_file_read": True,
        "handoff_source_file_valid_json": True,
        "handoff_source_file_mapping": True,
        "handoff_source_file_error_code": "",
        "handoff_source_file_path_recorded": False,
        "codex_exec_jsonl_file_required": True,
        "codex_exec_jsonl_file_present": True,
        "codex_exec_jsonl_file_read": True,
        "codex_exec_jsonl_file_valid_jsonl": True,
        "codex_exec_jsonl_file_error_code": "",
        "codex_exec_jsonl_file_path_recorded": False,
        "codex_exec_jsonl_parse_error_count": 0,
        "codex_exec_event_count": len(events),
    }


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
    testcase.assertFalse(packet["tool_call_arguments_recorded"])
    testcase.assertFalse(packet["route_candidate_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


def _assert_no_assistant_ui_live_or_product_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["assistant_continuation_proven"])
    testcase.assertFalse(packet["codex_exec_assistant_continuation_proven"])
    testcase.assertFalse(packet["codex_working_flow_delivery_proven"])
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["native_free_chat_router_product_ready"])
    testcase.assertFalse(packet["native_free_chat_router_delivery_proven"])
    testcase.assertFalse(packet["live_provider_proven"])
    testcase.assertFalse(packet["live_provider_response_proven"])
    testcase.assertFalse(packet["external_live_provider_response_proven"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_assistant_continuation"])
    testcase.assertTrue(packet["does_not_prove_codex_working_flow_delivery"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_ui"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_live_provider"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


class OfficialMcpTranscriptToolResultObservationTests(unittest.TestCase):
    def test_positive_observes_official_handoff_source_in_transcript(self) -> None:
        packet = _packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            proof.OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["handoff_source_valid"])
        self.assertTrue(packet["handoff_source_proven"])
        self.assertTrue(packet["approved_handoff_ready"])
        self.assertTrue(packet["approved_handoff_payload_sanitized"])
        self.assertTrue(packet["handoff_payload_digest"])
        self.assertEqual(
            packet["handoff_payload_digest"],
            packet["expected_handoff_payload_digest"],
        )
        self.assertTrue(packet["handoff_payload_digest_bound"])
        self.assertTrue(packet["handoff_source_digest_bound"])
        self.assertTrue(packet["working_flow_source_bound"])
        self.assertTrue(packet["adapter_handoff_completed"])
        self.assertTrue(packet["adapter_handoff_envelope_built"])
        self.assertEqual(
            packet["transcript_observation_packet_kind"],
            transcript.CODEX_TRANSCRIPT_DELIVERY_OBSERVATION_PACKET_KIND,
        )
        self.assertTrue(packet["transcript_observation_valid"])
        self.assertEqual(packet["observation_path"], "codex_exec_json_mcp_tool_result")
        self.assertTrue(packet["codex_exec_json_events_observed"])
        self.assertTrue(packet["codex_exec_transcript_sha256"])
        self.assertTrue(packet["mcp_tool_result_observed"])
        self.assertTrue(packet["mcp_tool_result_structured_content_present"])
        self.assertFalse(packet["mcp_tool_result_is_error"])
        self.assertTrue(packet["mcp_server_allowed"])
        self.assertTrue(packet["mcp_tool_allowed"])
        self.assertTrue(packet["content_text_json_matches_structured_content"])
        self.assertTrue(packet["structured_content_digest"])
        self.assertEqual(
            packet["declared_handoff_payload_digest"],
            packet["handoff_payload_digest"],
        )
        self.assertEqual(
            packet["observed_handoff_payload_digest"],
            packet["handoff_payload_digest"],
        )
        self.assertTrue(packet["structured_content_matches_handoff"])
        self.assertTrue(packet["transcript_tool_result_observed"])
        self.assertTrue(packet["codex_transcript_delivery_observed"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_assistant_ui_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_positive_observes_working_flow_handoff_source_in_transcript(
        self,
    ) -> None:
        source, events, working_flow_packet = _working_flow_source_events_and_packet()
        packet = proof.build_official_mcp_transcript_tool_result_observation_packet(
            handoff_source_packet=source,
            codex_exec_events=events,
            file_metadata=_working_flow_transcript_metadata(events),
            secret_values=[
                WORKING_FLOW_PROMPT,
                WORKING_FLOW_ROUTE_ID,
                WORKING_FLOW_RAW_PROVIDER_TEXT,
                WORKING_FLOW_EXPECTED_TEXT,
            ],
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["handoff_source_valid"])
        self.assertTrue(packet["official_working_flow_delivery_source_proven"])
        self.assertTrue(packet["working_flow_delivery_source_file_backed"])
        self.assertEqual(
            packet["handoff_source_truth_source"],
            "file_backed_codex_working_flow_delivery_proof",
        )
        self.assertTrue(packet["handoff_source_proven"])
        self.assertTrue(packet["approved_handoff_ready"])
        self.assertTrue(packet["approved_handoff_payload_sanitized"])
        self.assertEqual(
            packet["handoff_payload_digest"],
            working_flow_packet["handoff_payload_digest"],
        )
        self.assertEqual(
            packet["expected_handoff_payload_digest"],
            working_flow_packet["handoff_payload_digest"],
        )
        self.assertTrue(packet["handoff_payload_digest_bound"])
        self.assertTrue(packet["handoff_source_digest_bound"])
        self.assertTrue(packet["working_flow_source_bound"])
        self.assertTrue(packet["adapter_handoff_completed"])
        self.assertTrue(packet["adapter_handoff_envelope_built"])
        self.assertTrue(packet["transcript_observation_valid"])
        self.assertTrue(packet["mcp_tool_result_observed"])
        self.assertTrue(packet["mcp_tool_allowed"])
        self.assertTrue(packet["mcp_server_allowed"])
        self.assertTrue(packet["structured_content_matches_handoff"])
        self.assertTrue(packet["transcript_tool_result_observed"])
        self.assertTrue(packet["codex_transcript_delivery_observed"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["live_provider_proven"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packet["blocking_reasons"], [])
        serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        for forbidden in (
            WORKING_FLOW_PROMPT,
            WORKING_FLOW_ROUTE_ID,
            WORKING_FLOW_RAW_PROVIDER_TEXT,
            WORKING_FLOW_EXPECTED_TEXT,
        ):
            self.assertNotIn(forbidden, serialized)
            self.assertFalse(packet_contains_text(packet, forbidden))
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_working_flow_source_without_file_backed_claim_blocks_observation(
        self,
    ) -> None:
        source, events, _working_flow_packet = _working_flow_source_events_and_packet()
        source["working_flow_delivery_source_file_backed"] = False
        packet = proof.build_official_mcp_transcript_tool_result_observation_packet(
            handoff_source_packet=source,
            codex_exec_events=events,
            file_metadata=_working_flow_transcript_metadata(events),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_SOURCE_INVALID,
        )
        self.assertIn(
            "working_flow_delivery_source_not_file_backed",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["official_working_flow_delivery_source_proven"])
        self.assertFalse(packet["transcript_tool_result_observed"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_controlled_source_digest_mismatch_blocks_observation(self) -> None:
        source = _source_packet()
        source["controlled_provider_response_sha256"] = "f" * 64
        packet = _packet(source=source, events=_events_for_source(_source_packet()))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_SOURCE_INVALID,
        )
        self.assertIn("provider_response_digest_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["handoff_source_proven"])
        self.assertFalse(packet["transcript_tool_result_observed"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_direct_official_handoff_source_is_not_transcript_verifier_input(self) -> None:
        source = _source_packet()
        packet = transcript.build_codex_transcript_delivery_observation_packet(
            source,
            _events_for_source(source),
            secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            transcript.CODEX_TRANSCRIPT_DELIVERY_HANDOFF_PROOF_INVALID,
        )
        self.assertIn("handoff_proof_packet_kind_invalid", packet["blocking_reasons"])
        self.assertFalse(packet["codex_transcript_delivery_observed"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_source_digest_mismatch_blocks_observation(self) -> None:
        source = _source_packet()
        source["handoff_payload_digest"] = "f" * 64
        packet = _packet(source=source, events=_events_for_source(_source_packet()))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_SOURCE_DIGEST_MISMATCH,
        )
        self.assertIn("handoff_source_digest_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["handoff_source_proven"])
        self.assertFalse(packet["transcript_observation_valid"])
        self.assertFalse(packet["transcript_tool_result_observed"])
        _assert_no_assistant_ui_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_source_packet_contract_regressions_block_observation(self) -> None:
        cases = {
            "wrong_packet_kind": ("packet_kind", "wrong", "handoff_source_packet_kind_invalid"),
            "status_not_ok": ("status", "error", "handoff_source_packet_not_ok"),
            "machine_error_not_ok": (
                "machine_error_code",
                "BROKEN",
                "handoff_source_machine_error_not_ok",
            ),
            "effect_not_probe": ("effect", "mutate", "handoff_source_effect_not_probe"),
            "changed_files_not_empty": (
                "changed_files",
                ["unexpected.json"],
                "handoff_source_changed_files_not_empty",
            ),
        }
        for name, (field, value, reason) in cases.items():
            with self.subTest(name=name):
                source = _source_packet()
                source[field] = value
                packet = _packet(source=source, events=_events_for_source(_source_packet()))

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_SOURCE_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["handoff_source_proven"])
                self.assertFalse(packet["mcp_tool_result_observed"])
                _assert_no_assistant_ui_live_or_product_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_transcript_tool_result_negative_cases_block_observation(self) -> None:
        source = _source_packet()
        valid_structured = _delivery_payload_for_source(source)
        digest_mismatch = dict(valid_structured)
        digest_mismatch["handoff_payload_sha256"] = "f" * 64
        content_mismatch_text = json.dumps(
            {"packet_kind": "wrong"},
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        cases = {
            "wrong_server": (
                _tool_result_event(valid_structured, server_name="browser"),
                "mcp_tool_result_server_not_wbp",
            ),
            "wrong_tool": (
                _tool_result_event(valid_structured, tool_name="other_tool"),
                "mcp_tool_result_tool_name_invalid",
            ),
            "is_error": (
                _tool_result_event(valid_structured, is_error=True),
                "mcp_tool_result_is_error",
            ),
            "structured_mismatch": (
                _tool_result_event(digest_mismatch),
                "handoff_payload_declared_digest_mismatch",
            ),
            "content_text_mismatch": (
                _tool_result_event(valid_structured, content_text=content_mismatch_text),
                "mcp_tool_result_content_text_structured_content_mismatch",
            ),
            "content_text_missing": (
                _tool_result_event(valid_structured, content_text=""),
                "mcp_tool_result_content_text_missing",
            ),
            "assistant_only": (
                _assistant_event(valid_structured),
                "mcp_tool_result_not_observed",
            ),
        }
        for name, (event, reason) in cases.items():
            with self.subTest(name=name):
                packet = _packet(
                    source=source,
                    events=[
                        {"type": "turn.started"},
                        event,
                        {"type": "turn.completed"},
                    ],
                )

                self.assertEqual(packet["status"], "error")
                self.assertNotEqual(packet["machine_error_code"], "OK")
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["transcript_tool_result_observed"])
                self.assertFalse(packet["transcript_observation_valid"])
                self.assertFalse(packet["codex_transcript_delivery_observed"])
                _assert_no_assistant_ui_live_or_product_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unsafe_claims_block_observation(self) -> None:
        source = _source_packet()
        source["product_ready"] = True
        packet = _packet(source=source, events=_events_for_source(_source_packet()))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_UNSAFE_SOURCE,
        )
        self.assertIn("product_ready_must_not_be_claimed", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["transcript_tool_result_observed"])
        _assert_no_assistant_ui_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_handoff_source_file_blocks_cli(self) -> None:
        source = _source_packet()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            jsonl_file = root / "codex.jsonl"
            jsonl_file.write_text(_jsonl(_events_for_source(source)) + "\n", encoding="utf-8")
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "official-mcp-transcript-tool-result-observe",
                        "--handoff-source-file",
                        str(root / "missing-source.json"),
                        "--codex-exec-jsonl-file",
                        str(jsonl_file),
                        "--json",
                    ]
                )

        packet = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_SOURCE_INVALID,
        )
        self.assertFalse(packet["handoff_source_file_present"])
        self.assertEqual(
            packet["handoff_source_file_error_code"],
            "handoff_source_file_missing",
        )
        self.assertIn("handoff_source_packet_kind_invalid", packet["blocking_reasons"])
        self.assertFalse(packet["transcript_tool_result_observed"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_malformed_handoff_source_file_blocks_cli(self) -> None:
        source = _source_packet()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = root / "source.json"
            jsonl_file = root / "codex.jsonl"
            source_file.write_text("{not-json\n", encoding="utf-8")
            jsonl_file.write_text(_jsonl(_events_for_source(source)) + "\n", encoding="utf-8")
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "official-mcp-transcript-tool-result-observe",
                        "--handoff-source-file",
                        str(source_file),
                        "--codex-exec-jsonl-file",
                        str(jsonl_file),
                        "--json",
                    ]
                )

        packet = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["handoff_source_file_valid_json"])
        self.assertEqual(
            packet["handoff_source_file_error_code"],
            "handoff_source_file_invalid",
        )
        self.assertFalse(packet["transcript_tool_result_observed"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_or_malformed_jsonl_blocks_cli(self) -> None:
        source = _source_packet()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = root / "source.json"
            source_file.write_text(json.dumps(source, sort_keys=True) + "\n", encoding="utf-8")
            cases = {
                "missing": root / "missing.jsonl",
                "malformed": root / "malformed.jsonl",
            }
            cases["malformed"].write_text("{not-json}\n", encoding="utf-8")
            for name, jsonl_file in cases.items():
                with self.subTest(name=name):
                    stdout = io.StringIO()
                    with mock.patch("sys.stdout", stdout):
                        exit_code = cli_mod.main(
                            [
                                "router-hook",
                                "official-mcp-transcript-tool-result-observe",
                                "--handoff-source-file",
                                str(source_file),
                                "--codex-exec-jsonl-file",
                                str(jsonl_file),
                                "--json",
                            ]
                        )

                    packet = json.loads(stdout.getvalue())
                    self.assertEqual(exit_code, 1)
                    self.assertEqual(packet["status"], "error")
                    self.assertFalse(packet["transcript_tool_result_observed"])
                    self.assertFalse(packet["codex_transcript_delivery_observed"])
                    self.assertIn(
                        "mcp_tool_result_not_observed",
                        packet["blocking_reasons"],
                    )
                    self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_observation_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "official-mcp-transcript-tool-result-observe",
                "--handoff-source-file",
                "source.json",
                "--codex-exec-jsonl-file",
                "codex.jsonl",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")

    def test_cli_emits_observation_packet(self) -> None:
        expected = _packet()
        stdout = io.StringIO()

        with (
            mock.patch(
                "wild_boar_proxy.cli."
                "run_official_mcp_transcript_tool_result_observation_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "official-mcp-transcript-tool-result-observe",
                    "--handoff-source-file",
                    "source.json",
                    "--codex-exec-jsonl-file",
                    "codex.jsonl",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertEqual(
            payload["packet_kind"],
            proof.OFFICIAL_MCP_TRANSCRIPT_TOOL_RESULT_OBSERVATION_PACKET_KIND,
        )
        self.assertTrue(payload["transcript_tool_result_observed"])
        self.assertFalse(payload["codex_working_flow_delivery_proven"])
        self.assertFalse(payload["product_ready"])
        run_command.assert_called_once()
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()
