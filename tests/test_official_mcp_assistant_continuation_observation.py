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
from wild_boar_proxy import official_mcp_assistant_continuation_observation as proof
from wild_boar_proxy import official_mcp_transcript_tool_result_observation as source_proof
from wild_boar_proxy.codex_exec_assistant_continuation_proof import (
    BINDING_METHOD_SAFE_DIGEST_METADATA,
)
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_official_mcp_handoff_source_proof import (  # noqa: E402
    PROMPT,
    RAW_PROVIDER_TEXT,
    ROUTE_ID,
    _packet as _handoff_source_packet,
)
from test_official_mcp_transcript_tool_result_observation import (  # noqa: E402
    _delivery_payload_for_source,
    _jsonl,
    _tool_result_event,
)


def _assistant_event(
    digest: str,
    *,
    include_marker: bool = True,
    marker_digest: str | None = None,
    text: str = "WBP assistant continuation receipt.",
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {}
    if include_marker:
        metadata["wbp_handoff_digest"] = digest if marker_digest is None else marker_digest
    if extra:
        metadata.update(extra)
    return {
        "type": "item.completed",
        "item": {
            "id": "item-assistant-continuation",
            "type": "assistant_message",
            "role": "assistant",
            "status": "completed",
            "text": text,
            "metadata": metadata,
        },
    }


def _subagent_event() -> dict[str, object]:
    return {
        "type": "item.completed",
        "item": {
            "id": "item-subagent",
            "type": "codex_subagent",
            "name": "DIP",
            "status": "completed",
            "text": "Local subagent Agent 2 response.",
        },
    }


def _events(
    *,
    assistant_event: dict[str, object] | None = None,
    include_tool_result: bool = True,
    assistant_before_tool: bool = False,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    handoff_source = _handoff_source_packet()
    structured = _delivery_payload_for_source(handoff_source)
    tool_event = _tool_result_event(structured)
    assistant = (
        _assistant_event(str(handoff_source["handoff_payload_digest"]))
        if assistant_event is None
        else assistant_event
    )
    events: list[dict[str, object]] = [
        {"type": "thread.started", "thread_id": "thread-official-continuation"},
        {"type": "turn.started"},
    ]
    if assistant_before_tool:
        events.append(assistant)
    if include_tool_result:
        events.append(tool_event)
    if not assistant_before_tool and assistant_event is not False:
        events.append(assistant)
    events.append({"type": "turn.completed"})
    return handoff_source, events


def _source_packet_for_events(events: list[dict[str, object]]) -> dict[str, object]:
    return source_proof.build_official_mcp_transcript_tool_result_observation_packet(
        handoff_source_packet=_handoff_source_packet(),
        codex_exec_events=events,
        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
    )


def _packet(
    *,
    source: dict[str, object] | None = None,
    events: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    if events is None:
        _handoff_source, events = _events()
    source_packet = _source_packet_for_events(events) if source is None else source
    return proof.build_official_mcp_assistant_continuation_observation_packet(
        transcript_observation_packet=source_packet,
        codex_exec_events=events,
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


class OfficialMcpAssistantContinuationObservationTests(unittest.TestCase):
    def test_positive_observes_assistant_continuation_after_official_tool_result(
        self,
    ) -> None:
        packet = _packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            proof.OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["source_valid"])
        self.assertTrue(packet["official_mcp_transcript_tool_result_observation_valid"])
        self.assertTrue(packet["transcript_tool_result_observed"])
        self.assertTrue(packet["codex_transcript_delivery_observed"])
        self.assertTrue(packet["mcp_tool_result_observed"])
        self.assertTrue(packet["mcp_tool_result_structured_content_present"])
        self.assertTrue(packet["structured_content_matches_handoff"])
        self.assertTrue(packet["handoff_payload_digest"])
        self.assertTrue(packet["continuation_valid"])
        self.assertTrue(packet["same_codex_exec_jsonl_bound"])
        self.assertTrue(packet["matching_mcp_tool_result_observed"])
        self.assertTrue(packet["assistant_continuation_observed"])
        self.assertTrue(packet["assistant_response_after_tool_result"])
        self.assertTrue(packet["assistant_machine_marker_observed"])
        self.assertFalse(packet["assistant_marker_digest_mismatch"])
        self.assertTrue(packet["assistant_continuation_bound_to_tool_result"])
        self.assertTrue(packet["assistant_response_bound_to_handoff_digest"])
        self.assertEqual(packet["binding_method"], BINDING_METHOD_SAFE_DIGEST_METADATA)
        self.assertEqual(packet["assistant_binding_digest"], packet["handoff_payload_digest"])
        self.assertTrue(packet["assistant_continuation_proven"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["transcript_secret_value_present"])
        _assert_no_product_ui_live_or_working_flow_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_source_contract_regressions_block_before_continuation(self) -> None:
        _handoff_source, events = _events()
        source = _source_packet_for_events(events)
        cases = {
            "wrong_packet_kind": (
                "packet_kind",
                "wrong",
                "official_transcript_observation_packet_kind_invalid",
            ),
            "status_not_ok": (
                "status",
                "error",
                "official_transcript_observation_packet_not_ok",
            ),
            "machine_error_not_ok": (
                "machine_error_code",
                "BROKEN",
                "official_transcript_observation_machine_error_not_ok",
            ),
            "effect_not_probe": (
                "effect",
                "mutate",
                "official_transcript_observation_effect_not_probe",
            ),
            "changed_files_not_empty": (
                "changed_files",
                ["unexpected.json"],
                "official_transcript_observation_changed_files_not_empty",
            ),
        }
        for name, (field, value, reason) in cases.items():
            with self.subTest(name=name):
                broken = dict(source)
                broken[field] = value
                packet = _packet(source=broken, events=events)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_SOURCE_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["source_valid"])
                self.assertFalse(packet["assistant_continuation_observed"])
                self.assertFalse(packet["codex_exec_assistant_continuation_proven"])
                _assert_no_product_ui_live_or_working_flow_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_source_unsafe_preclaims_block_before_continuation(self) -> None:
        _handoff_source, events = _events()
        source = _source_packet_for_events(events)
        cases = {
            "product_ready": ("product_ready", "product_ready_must_not_be_claimed"),
            "ui": (
                "custom_codex_ui_visibility_proven",
                "custom_codex_ui_visibility_must_not_be_claimed",
            ),
            "working_flow": (
                "codex_working_flow_delivery_proven",
                "codex_working_flow_delivery_must_not_be_claimed",
            ),
            "assistant_preclaim": (
                "codex_exec_assistant_continuation_proven",
                "codex_exec_assistant_continuation_must_not_be_preclaimed",
            ),
            "raw_prompt": ("raw_prompt_recorded", "raw_prompt_recorded"),
        }
        for name, (field, reason) in cases.items():
            with self.subTest(name=name):
                broken = dict(source)
                broken[field] = True
                packet = _packet(source=broken, events=events)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_UNSAFE_SOURCE,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["assistant_continuation_observed"])
                self.assertFalse(packet["codex_exec_assistant_continuation_proven"])
                _assert_no_product_ui_live_or_working_flow_claim(self, packet)
                if name != "raw_prompt":
                    _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_transcript_missing_early_unbound_or_mismatched_assistant_blocks(
        self,
    ) -> None:
        handoff_source = _handoff_source_packet()
        digest = str(handoff_source["handoff_payload_digest"])
        cases: dict[str, tuple[list[dict[str, object]], str, str]] = {}

        _source, base_events = _events()
        cases["no_assistant"] = (
            [base_events[0], base_events[1], base_events[2], base_events[-1]],
            proof.OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_TRANSCRIPT_INVALID,
            "assistant_response_after_tool_result_not_observed",
        )
        _source, early_events = _events(assistant_before_tool=True)
        cases["assistant_before_tool"] = (
            early_events,
            proof.OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_TRANSCRIPT_INVALID,
            "assistant_response_after_tool_result_not_observed",
        )
        _source, no_marker_events = _events(
            assistant_event=_assistant_event(digest, include_marker=False)
        )
        cases["no_marker"] = (
            no_marker_events,
            proof.OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_NOT_BOUND,
            "assistant_response_machine_digest_marker_missing",
        )
        _source, mismatch_events = _events(
            assistant_event=_assistant_event(digest, marker_digest="f" * 64)
        )
        cases["mismatch"] = (
            mismatch_events,
            proof.OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_NOT_BOUND,
            "assistant_response_handoff_digest_mismatch",
        )

        for name, (events, machine_error, reason) in cases.items():
            with self.subTest(name=name):
                source = _source_packet_for_events(events)
                packet = _packet(source=source, events=events)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_error)
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["assistant_continuation_observed"])
                self.assertFalse(packet["assistant_continuation_bound_to_tool_result"])
                self.assertFalse(packet["codex_exec_assistant_continuation_proven"])
                _assert_no_product_ui_live_or_working_flow_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_assistant_only_without_mcp_result_blocks_fail_closed(self) -> None:
        handoff_source = _handoff_source_packet()
        _source, events = _events(
            assistant_event=_assistant_event(str(handoff_source["handoff_payload_digest"])),
            include_tool_result=False,
        )
        source = _source_packet_for_events(events)

        packet = _packet(source=source, events=events)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_SOURCE_INVALID,
        )
        self.assertIn("transcript_tool_result_not_observed", packet["blocking_reasons"])
        self.assertFalse(packet["mcp_tool_result_observed"])
        self.assertFalse(packet["assistant_continuation_observed"])
        self.assertFalse(packet["codex_exec_assistant_continuation_proven"])
        _assert_no_product_ui_live_or_working_flow_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_transcript_unsafe_secret_and_local_imitation_block(self) -> None:
        handoff_source = _handoff_source_packet()
        digest = str(handoff_source["handoff_payload_digest"])
        _source, secret_events = _events(
            assistant_event=_assistant_event(
                digest,
                text=f"Unsafe secret echo: {PROMPT}",
            )
        )
        _source, subagent_events = _events()
        subagent_events.insert(3, _subagent_event())
        cases = {
            "secret": (
                secret_events,
                "secret_value_present_in_transcript",
            ),
            "subagent": (
                subagent_events,
                "native_codex_subagent_used_as_dip",
            ),
        }
        for name, (events, reason) in cases.items():
            with self.subTest(name=name):
                source = _source_packet_for_events(events)
                packet = _packet(source=source, events=events)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_TRANSCRIPT_UNSAFE,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["codex_exec_assistant_continuation_proven"])
                _assert_no_product_ui_live_or_working_flow_claim(self, packet)
                if name == "secret":
                    self.assertTrue(packet["transcript_secret_value_present"])
                else:
                    _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_or_malformed_source_file_blocks_cli(self) -> None:
        _source, events = _events()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            malformed = root / "malformed.json"
            malformed.write_text("{not-json}\n", encoding="utf-8")
            jsonl_file = root / "codex.jsonl"
            jsonl_file.write_text(_jsonl(events) + "\n", encoding="utf-8")
            cases = {
                "missing": root / "missing.json",
                "malformed": malformed,
            }
            for name, source_file in cases.items():
                with self.subTest(name=name):
                    stdout = io.StringIO()
                    with mock.patch("sys.stdout", stdout):
                        exit_code = cli_mod.main(
                            [
                                "router-hook",
                                "official-mcp-assistant-continuation-observe",
                                "--transcript-observation-file",
                                str(source_file),
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
                        proof.OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_SOURCE_INVALID,
                    )
                    self.assertFalse(packet["assistant_continuation_observed"])
                    self.assertIn(
                        "official_transcript_observation_packet_kind_invalid",
                        packet["blocking_reasons"],
                    )
                    self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_or_malformed_jsonl_blocks_cli(self) -> None:
        _source, events = _events()
        source = _source_packet_for_events(events)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = root / "source.json"
            source_file.write_text(json.dumps(source, sort_keys=True) + "\n", encoding="utf-8")
            malformed = root / "malformed.jsonl"
            malformed.write_text("{not-json}\n", encoding="utf-8")
            cases = {
                "missing": root / "missing.jsonl",
                "malformed": malformed,
            }
            for name, jsonl_file in cases.items():
                with self.subTest(name=name):
                    stdout = io.StringIO()
                    with mock.patch("sys.stdout", stdout):
                        exit_code = cli_mod.main(
                            [
                                "router-hook",
                                "official-mcp-assistant-continuation-observe",
                                "--transcript-observation-file",
                                str(source_file),
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
                        proof.OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_TRANSCRIPT_INVALID,
                    )
                    self.assertFalse(packet["assistant_continuation_observed"])
                    self.assertFalse(packet["codex_exec_assistant_continuation_proven"])
                    self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_official_observation_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "official-mcp-assistant-continuation-observe",
                "--transcript-observation-file",
                "source.json",
                "--codex-exec-jsonl-file",
                "codex.jsonl",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")

    def test_cli_emits_official_assistant_continuation_packet(self) -> None:
        expected = _packet()
        stdout = io.StringIO()

        with (
            mock.patch(
                "wild_boar_proxy.cli."
                "run_official_mcp_assistant_continuation_observation_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "official-mcp-assistant-continuation-observe",
                    "--transcript-observation-file",
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
            proof.OFFICIAL_MCP_ASSISTANT_CONTINUATION_OBSERVATION_PACKET_KIND,
        )
        self.assertTrue(payload["assistant_continuation_observed"])
        self.assertTrue(payload["codex_exec_assistant_continuation_proven"])
        self.assertFalse(payload["codex_working_flow_delivery_proven"])
        self.assertFalse(payload["custom_codex_ui_visibility_proven"])
        self.assertFalse(payload["product_ready"])
        run_command.assert_called_once()
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()
