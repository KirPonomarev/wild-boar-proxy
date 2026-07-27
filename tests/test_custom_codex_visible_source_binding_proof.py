# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import codex_working_flow_delivery_proof as working_flow
from wild_boar_proxy import custom_codex_visible_source_binding_proof as binding
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_custom_origin_bound_live_provider_join import (  # noqa: E402
    EXPECTED_TEXT,
    OTHER_PROMPT,
    OTHER_ROUTE_ID,
    PROMPT,
    RAW_PROVIDER_TEXT,
    ROUTE_ID,
    _packet as _custom_origin_live_provider_join_packet,
)
from test_custom_origin_bound_working_flow_delivery_proof import (  # noqa: E402
    _events_for_source,
    _file_metadata as _working_flow_file_metadata,
    _jsonl_from_events,
)


ROOT = Path(__file__).resolve().parents[1]


def _runtime_context() -> dict[str, object]:
    return {
        "packet_kind": "codex_custom_native_agent_runtime_context",
        "allowed_api_route_ids": [ROUTE_ID],
        "agent_id_to_route": {"Agent 2": ROUTE_ID},
        "agent_bindings": [
            {
                "slot": "Agent 2",
                "display_name": "DIP",
                "route_id": ROUTE_ID,
            }
        ],
    }


def _file_metadata(event_count: int = 5) -> dict[str, object]:
    return {
        "working_flow_delivery_proof_file_required": True,
        "working_flow_delivery_proof_file_present": True,
        "working_flow_delivery_proof_file_read": True,
        "working_flow_delivery_proof_file_valid_json": True,
        "working_flow_delivery_proof_file_mapping": True,
        "working_flow_delivery_proof_file_error_code": "",
        "working_flow_delivery_proof_file_path_recorded": False,
        "codex_exec_jsonl_file_required": True,
        "codex_exec_jsonl_file_present": True,
        "codex_exec_jsonl_file_read": True,
        "codex_exec_jsonl_file_valid_jsonl": True,
        "codex_exec_jsonl_file_error_code": "",
        "codex_exec_jsonl_file_path_recorded": False,
        "codex_exec_jsonl_parse_error_count": 0,
        "codex_exec_event_count": event_count,
    }


def _working_flow_packet(
    *,
    source_overrides: dict[str, object] | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    source = _custom_origin_live_provider_join_packet()
    events = _events_for_source(source)
    packet = working_flow.build_codex_working_flow_delivery_proof_packet(
        source,
        events,
        file_metadata=_working_flow_file_metadata(),
        secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
    )
    if packet["status"] != "ok":
        raise AssertionError(packet)
    if source_overrides:
        packet.update(source_overrides)
    return packet, events


def _assistant_event(
    handoff_digest: str,
    *,
    include_marker: bool = True,
    marker_digest: str | None = None,
    text: str = "WBP custom visible source binding receipt.",
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {}
    if include_marker:
        metadata["wbp_handoff_digest"] = handoff_digest if marker_digest is None else marker_digest
    if extra:
        metadata.update(extra)
    return {
        "type": "item.completed",
        "item": {
            "id": "item-visible-source-binding-assistant",
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
            "text": "Local sub-agent DIP produced a response.",
        },
    }


def _replace_assistant_event(
    events: list[dict[str, object]],
    assistant: dict[str, object],
) -> list[dict[str, object]]:
    replaced = list(events)
    replaced[3] = assistant
    return replaced


def _assert_no_product_or_ui_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_ui"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


def _assert_no_raw_prompt_route_or_provider(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        PROMPT,
        OTHER_PROMPT,
        ROUTE_ID,
        OTHER_ROUTE_ID,
        EXPECTED_TEXT,
        RAW_PROVIDER_TEXT,
    ):
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
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


class CustomCodexVisibleSourceBindingProofTests(unittest.TestCase):
    def test_positive_binds_visible_source_to_working_flow_handoff(self) -> None:
        source, events = _working_flow_packet()
        packet = binding.build_custom_codex_visible_source_binding_proof_packet(
            source,
            events,
            visible_source_kind=binding.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
            file_metadata=_file_metadata(),
            secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            binding.CUSTOM_CODEX_VISIBLE_SOURCE_BINDING_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(
            packet["source_packet_kind"],
            working_flow.CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
        )
        self.assertTrue(packet["source_packet_file_backed"])
        self.assertTrue(packet["working_flow_delivery_proof_valid"])
        self.assertTrue(packet["working_flow_delivery_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["approved_delivery_surface_proven"])
        self.assertTrue(packet["mcp_delivery_surface_proven"])
        self.assertTrue(packet["approved_handoff_ready"])
        self.assertTrue(packet["approved_handoff_payload_sanitized"])
        self.assertTrue(packet["handoff_delivered"])
        self.assertTrue(packet["delivery_observed"])
        self.assertTrue(packet["handoff_payload_digest_present"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertTrue(packet["assistant_response_bound_to_handoff_digest"])
        self.assertTrue(packet["live_provider_response_proven"])
        self.assertTrue(packet["live_provider_response_digest_bound_to_handoff"])
        self.assertTrue(packet["approved_visible_source_allowed"])
        self.assertTrue(packet["visible_source_read"])
        self.assertTrue(packet["visible_source_events_observed"])
        self.assertTrue(packet["visible_source_digest"])
        self.assertTrue(packet["working_flow_codex_exec_transcript_sha256"])
        self.assertTrue(packet["visible_source_digest_bound"])
        self.assertTrue(packet["visible_source_digest_matches_working_flow"])
        self.assertTrue(packet["matching_mcp_tool_result_observed"])
        self.assertTrue(packet["visible_source_assistant_output_observed"])
        self.assertTrue(packet["visible_source_assistant_output_event_index_present"])
        self.assertTrue(packet["visible_source_after_delivery"])
        self.assertTrue(packet["visible_source_marker_observed"])
        self.assertFalse(packet["visible_source_marker_digest_mismatch"])
        self.assertTrue(packet["visible_source_bound_to_handoff"])
        self.assertTrue(packet["visible_source_observed"])
        self.assertTrue(packet["visible_source_binding_proven"])
        self.assertTrue(packet["custom_codex_visible_source_binding_proven"])
        self.assertEqual(packet["visible_source_marker_digest"], packet["handoff_payload_digest"])
        self.assertEqual(packet["visible_source_marker_binding_method"], "safe_digest_metadata")
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_without_file_backed_working_flow_source(self) -> None:
        source, events = _working_flow_packet()
        packet = binding.build_custom_codex_visible_source_binding_proof_packet(
            source,
            events,
            secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            binding.VISIBLE_SOURCE_BINDING_WORKING_FLOW_INVALID,
        )
        self.assertIn(
            "working_flow_delivery_proof_file_not_read",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["source_packet_file_backed"])
        self.assertFalse(packet["visible_source_binding_proven"])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_invalid_working_flow_source_fields(self) -> None:
        cases = [
            ("status", "error", "working_flow_delivery_packet_not_ok"),
            (
                "codex_working_flow_delivery_proven",
                False,
                "working_flow_delivery_not_proven",
            ),
            ("mcp_delivery_surface_proven", False, "mcp_delivery_surface_not_proven"),
            ("handoff_payload_digest", "", "handoff_payload_digest_missing"),
            (
                "custom_codex_ui_visibility_proven",
                True,
                "custom_codex_ui_visibility_must_not_be_claimed",
            ),
            ("product_ready", True, "product_ready_must_not_be_claimed"),
        ]
        for field, value, reason in cases:
            with self.subTest(field=field):
                source, events = _working_flow_packet(source_overrides={field: value})
                packet = binding.build_custom_codex_visible_source_binding_proof_packet(
                    source,
                    events,
                    file_metadata=_file_metadata(),
                    secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    binding.VISIBLE_SOURCE_BINDING_WORKING_FLOW_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["working_flow_delivery_proof_valid"])
                self.assertFalse(packet["visible_source_binding_proven"])
                _assert_no_product_or_ui_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_diagnoses_command_exec_only_source_as_approved_visible_source_unavailable(self) -> None:
        source, events = _working_flow_packet()
        handoff_digest = str(source["handoff_payload_digest"])
        command_exec_events = [
            _assistant_event(
                handoff_digest,
                text="Command execution receipt is not an MCP tool result.",
            )
        ]
        source = dict(source)
        source.update(
            {
                "mcp_delivery_surface_proven": False,
                "command_execution_delivery_surface_proven": True,
                "working_flow_delivery_surface_kind": (
                    "codex_command_execution_live_format_check"
                ),
                "matching_mcp_tool_result_observed": False,
                "mcp_tool_result_structured_content_present": False,
                "structured_content_matches_handoff": False,
                "assistant_response_after_tool_result": False,
                "approved_delivery_surface_proven": True,
                "codex_exec_transcript_sha256": (
                    working_flow._codex_exec_transcript_digest(command_exec_events)
                ),
            }
        )
        packet = binding.build_custom_codex_visible_source_binding_proof_packet(
            source,
            command_exec_events,
            file_metadata=_file_metadata(event_count=1),
            secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            binding.APPROVED_VISIBLE_SOURCE_UNAVAILABLE,
        )
        self.assertTrue(packet["approved_visible_source_unavailable"])
        self.assertEqual(packet["approved_visible_source_expected"], "mcp_tool_response")
        self.assertTrue(packet["command_exec_only_evidence_available"])
        self.assertTrue(packet["command_exec_only_not_accepted_as_visible_source"])
        self.assertIn("approved_visible_source_unavailable", packet["blocking_reasons"])
        self.assertIn("mcp_delivery_surface_not_proven", packet["blocking_reasons"])
        self.assertIn("matching_mcp_tool_result_not_observed", packet["blocking_reasons"])
        self.assertIn(
            "mcp_delivery_surface_proven",
            packet["approved_visible_source_unblockers"],
        )
        self.assertFalse(packet["visible_source_binding_proven"])
        self.assertFalse(packet["custom_codex_visible_source_binding_proven"])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_unapproved_source_missing_source_and_invalid_jsonl(self) -> None:
        source, events = _working_flow_packet()
        cases = [
            (
                "unapproved_source",
                source,
                events,
                "browser_dom_snapshot",
                _file_metadata(),
                binding.VISIBLE_SOURCE_BINDING_SOURCE_NOT_ALLOWED,
                "approved_visible_source_kind_not_allowed",
            ),
            (
                "missing_events",
                source,
                [],
                binding.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
                _file_metadata(event_count=0),
                binding.VISIBLE_SOURCE_BINDING_SOURCE_NOT_OBSERVED,
                "visible_source_events_not_observed",
            ),
            (
                "invalid_jsonl_metadata",
                source,
                events,
                binding.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
                {**_file_metadata(), "codex_exec_jsonl_parse_error_count": 1},
                binding.VISIBLE_SOURCE_BINDING_SOURCE_NOT_OBSERVED,
                "visible_source_jsonl_parse_error",
            ),
        ]
        for name, source_packet, source_events, source_kind, metadata, machine_error, reason in cases:
            with self.subTest(name=name):
                packet = binding.build_custom_codex_visible_source_binding_proof_packet(
                    source_packet,
                    source_events,
                    visible_source_kind=source_kind,
                    file_metadata=metadata,
                    secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_error)
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["visible_source_binding_proven"])
                _assert_no_product_or_ui_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_marker_digest_failures_and_assistant_before_delivery(self) -> None:
        source, events = _working_flow_packet()
        handoff_digest = str(source["handoff_payload_digest"])
        no_marker_events = _replace_assistant_event(
            events,
            _assistant_event(handoff_digest, include_marker=False),
        )
        no_marker_source = dict(source)
        no_marker_source["codex_exec_transcript_sha256"] = (
            working_flow._codex_exec_transcript_digest(no_marker_events)
        )
        mismatch_events = _replace_assistant_event(
            events,
            _assistant_event(handoff_digest, marker_digest="f" * 64),
        )
        mismatch_source = dict(source)
        mismatch_source["codex_exec_transcript_sha256"] = (
            working_flow._codex_exec_transcript_digest(mismatch_events)
        )
        assistant_before_events = [events[0], events[1], events[3], events[2], events[4]]
        assistant_before_source = dict(source)
        assistant_before_source["codex_exec_transcript_sha256"] = (
            working_flow._codex_exec_transcript_digest(assistant_before_events)
        )
        cases = [
            (
                "no_marker",
                no_marker_source,
                no_marker_events,
                binding.VISIBLE_SOURCE_BINDING_NOT_BOUND,
                "visible_source_marker_missing",
            ),
            (
                "marker_mismatch",
                mismatch_source,
                mismatch_events,
                binding.VISIBLE_SOURCE_BINDING_NOT_BOUND,
                "visible_source_marker_digest_mismatch",
            ),
            (
                "assistant_before_delivery",
                assistant_before_source,
                assistant_before_events,
                binding.VISIBLE_SOURCE_BINDING_SOURCE_NOT_OBSERVED,
                "visible_source_assistant_output_not_observed",
            ),
        ]
        for name, source_packet, source_events, machine_error, reason in cases:
            with self.subTest(name=name):
                packet = binding.build_custom_codex_visible_source_binding_proof_packet(
                    source_packet,
                    source_events,
                    file_metadata=_file_metadata(),
                    secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_error)
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["visible_source_bound_to_handoff"])
                self.assertFalse(packet["visible_source_binding_proven"])
                _assert_no_product_or_ui_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_visible_source_unsafe_claim_secret_and_subagent_cases(self) -> None:
        source, events = _working_flow_packet()
        handoff_digest = str(source["handoff_payload_digest"])
        cases = [
            (
                "ui_visibility",
                _replace_assistant_event(
                    events,
                    _assistant_event(
                        handoff_digest,
                        extra={"custom_codex_ui_visibility_proven": True},
                    ),
                ),
                "custom_codex_ui_visibility_must_not_be_claimed",
            ),
            (
                "product_ready",
                _replace_assistant_event(
                    events,
                    _assistant_event(handoff_digest, extra={"product_ready": True}),
                ),
                "product_ready_must_not_be_claimed",
            ),
            (
                "secret_value",
                _replace_assistant_event(
                    events,
                    _assistant_event(handoff_digest, text=f"Unsafe raw route {ROUTE_ID}"),
                ),
                "secret_value_present_in_visible_source",
            ),
            (
                "subagent",
                [events[0], events[1], events[2], _subagent_event(), events[3], events[4]],
                "native_codex_subagent_used_as_dip",
            ),
        ]
        for name, source_events, reason in cases:
            with self.subTest(name=name):
                source_packet = dict(source)
                source_packet["codex_exec_transcript_sha256"] = (
                    working_flow._codex_exec_transcript_digest(source_events)
                )
                packet = binding.build_custom_codex_visible_source_binding_proof_packet(
                    source_packet,
                    source_events,
                    file_metadata=_file_metadata(event_count=len(source_events)),
                    secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    binding.VISIBLE_SOURCE_BINDING_PAYLOAD_UNSAFE,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["visible_source_binding_proven"])
                _assert_no_product_or_ui_claim(self, packet)
                if name != "secret_value":
                    _assert_no_raw_prompt_route_or_provider(self, packet)
                else:
                    self.assertTrue(packet["visible_source_secret_value_present"])
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_reads_files_and_emits_single_json(self) -> None:
        source, events = _working_flow_packet()
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_path = Path(temp_dir) / "working-flow.json"
            jsonl_path = Path(temp_dir) / "codex.jsonl"
            context_path = Path(temp_dir) / "runtime-context.json"
            sentinel = Path(temp_dir) / "sentinel.txt"
            proof_path.write_text(json.dumps(source) + "\n", encoding="utf-8")
            jsonl_path.write_text(_jsonl_from_events(events) + "\n", encoding="utf-8")
            context_path.write_text(
                json.dumps(_runtime_context()) + "\n",
                encoding="utf-8",
            )
            sentinel.write_text("unchanged", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "visible-source-binding-proof",
                    "--working-flow-delivery-proof-file",
                    str(proof_path),
                    "--visible-source-kind",
                    binding.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
                    "--codex-exec-jsonl-file",
                    str(jsonl_path),
                    "--runtime-context-file",
                    str(context_path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            sentinel_text = sentinel.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sentinel_text, "unchanged")
        packet = json.loads(result.stdout)
        self.assertEqual(result.stdout.strip(), json.dumps(packet, ensure_ascii=True))
        self.assertTrue(packet["working_flow_delivery_proof_file_present"])
        self.assertTrue(packet["working_flow_delivery_proof_file_read"])
        self.assertFalse(packet["working_flow_delivery_proof_file_path_recorded"])
        self.assertTrue(packet["codex_exec_jsonl_file_present"])
        self.assertTrue(packet["codex_exec_jsonl_file_read"])
        self.assertFalse(packet["codex_exec_jsonl_file_path_recorded"])
        self.assertTrue(packet["runtime_context_file_read"])
        self.assertFalse(packet["runtime_context_file_path_recorded"])
        self.assertEqual(packet["route_secret_screening_values_count"], 1)
        self.assertTrue(packet["route_secret_screening_proven"])
        self.assertFalse(packet["visible_source_route_secret_value_present"])
        self.assertTrue(packet["visible_source_binding_proven"])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_blocks_runtime_context_route_leak_closed(self) -> None:
        source, events = _working_flow_packet()
        handoff_digest = str(source["handoff_payload_digest"])
        leaked_events = _replace_assistant_event(
            events,
            _assistant_event(
                handoff_digest,
                text=f"Unsafe visible route leak {ROUTE_ID}",
            ),
        )
        source = dict(source)
        source["codex_exec_transcript_sha256"] = (
            working_flow._codex_exec_transcript_digest(leaked_events)
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_path = Path(temp_dir) / "working-flow.json"
            jsonl_path = Path(temp_dir) / "codex.jsonl"
            context_path = Path(temp_dir) / "runtime-context.json"
            proof_path.write_text(json.dumps(source) + "\n", encoding="utf-8")
            jsonl_path.write_text(
                _jsonl_from_events(leaked_events) + "\n",
                encoding="utf-8",
            )
            context_path.write_text(
                json.dumps(_runtime_context()) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "visible-source-binding-proof",
                    "--working-flow-delivery-proof-file",
                    str(proof_path),
                    "--visible-source-kind",
                    binding.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
                    "--codex-exec-jsonl-file",
                    str(jsonl_path),
                    "--runtime-context-file",
                    str(context_path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertEqual(
            packet["machine_error_code"],
            binding.VISIBLE_SOURCE_BINDING_PAYLOAD_UNSAFE,
        )
        self.assertTrue(packet["runtime_context_file_read"])
        self.assertTrue(packet["route_secret_screening_proven"])
        self.assertTrue(packet["visible_source_route_secret_value_present"])
        self.assertIn("secret_value_present_in_visible_source", packet["blocking_reasons"])
        self.assertFalse(packet["visible_source_binding_proven"])
        _assert_no_product_or_ui_claim(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_blocks_invalid_jsonl_closed(self) -> None:
        source, _events = _working_flow_packet()
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_path = Path(temp_dir) / "working-flow.json"
            jsonl_path = Path(temp_dir) / "codex.jsonl"
            proof_path.write_text(json.dumps(source) + "\n", encoding="utf-8")
            jsonl_path.write_text("{not-json}\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "visible-source-binding-proof",
                    "--working-flow-delivery-proof-file",
                    str(proof_path),
                    "--visible-source-kind",
                    binding.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
                    "--codex-exec-jsonl-file",
                    str(jsonl_path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(
            packet["machine_error_code"],
            binding.VISIBLE_SOURCE_BINDING_SOURCE_NOT_OBSERVED,
        )
        self.assertIn("visible_source_jsonl_parse_error", packet["blocking_reasons"])
        self.assertFalse(packet["visible_source_binding_proven"])
        _assert_no_product_or_ui_claim(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_blocks_non_utf8_proof_file_closed(self) -> None:
        _source, events = _working_flow_packet()
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_path = Path(temp_dir) / "working-flow.json"
            jsonl_path = Path(temp_dir) / "codex.jsonl"
            proof_path.write_bytes(b"\xff\xfe\xff")
            jsonl_path.write_text(_jsonl_from_events(events) + "\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "visible-source-binding-proof",
                    "--working-flow-delivery-proof-file",
                    str(proof_path),
                    "--visible-source-kind",
                    binding.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
                    "--codex-exec-jsonl-file",
                    str(jsonl_path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        packet = json.loads(result.stdout)
        self.assertEqual(
            packet["machine_error_code"],
            binding.VISIBLE_SOURCE_BINDING_WORKING_FLOW_INVALID,
        )
        self.assertEqual(
            packet["working_flow_delivery_proof_file_error_code"],
            "working_flow_delivery_proof_file_invalid",
        )
        self.assertFalse(packet["working_flow_delivery_proof_file_read"])
        self.assertFalse(packet["visible_source_binding_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_blocks_non_utf8_jsonl_file_closed(self) -> None:
        source, _events = _working_flow_packet()
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_path = Path(temp_dir) / "working-flow.json"
            jsonl_path = Path(temp_dir) / "codex.jsonl"
            proof_path.write_text(json.dumps(source) + "\n", encoding="utf-8")
            jsonl_path.write_bytes(b"\xff\xfe\xff")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "visible-source-binding-proof",
                    "--working-flow-delivery-proof-file",
                    str(proof_path),
                    "--visible-source-kind",
                    binding.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
                    "--codex-exec-jsonl-file",
                    str(jsonl_path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        packet = json.loads(result.stdout)
        self.assertEqual(
            packet["machine_error_code"],
            binding.VISIBLE_SOURCE_BINDING_SOURCE_NOT_OBSERVED,
        )
        self.assertEqual(
            packet["codex_exec_jsonl_file_error_code"],
            "codex_exec_jsonl_file_unreadable",
        )
        self.assertFalse(packet["codex_exec_jsonl_file_read"])
        self.assertFalse(packet["visible_source_binding_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_binding_proof_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "visible-source-binding-proof",
                "--working-flow-delivery-proof-file",
                "/tmp/wbp-working-flow.json",
                "--visible-source-kind",
                binding.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
                "--codex-exec-jsonl-file",
                "/tmp/wbp-codex.jsonl",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")


if __name__ == "__main__":
    unittest.main()
