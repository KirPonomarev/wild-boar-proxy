# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from wild_boar_proxy import codex_transcript_delivery_observation as transcript
from wild_boar_proxy import controlled_dispatch_handoff_proof as handoff_proof
from wild_boar_proxy import controlled_ingress_api_dispatch_proof as dispatch_proof
from wild_boar_proxy import custom_codex_ingress_proof as ingress
from wild_boar_proxy import mcp_delegate
from wild_boar_proxy import observed_machine_handoff_delivery as delivery
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy.approved_handoff import (
    HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
    _safe_handoff_payload,
)
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, дай задачу DIP: prove transcript delivery."
RAW_PROVIDER_TEXT = "raw provider response must not be stored"


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


def _jsonl_for_tool_call() -> str:
    return "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "thread-transcript"}),
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item-delegate-call",
                        "type": "mcp_tool_call",
                        "server_name": "wbp",
                        "tool_name": "delegate_to_dip",
                        "status": "completed",
                        "arguments": {"task": PROMPT},
                    },
                },
                ensure_ascii=True,
            ),
            json.dumps({"type": "turn.completed"}),
        ]
    )


def _ingress_packet() -> dict[str, object]:
    prompt_packet = mcp_delegate.build_prompt_observation_packet(
        PROMPT,
        source="codex_exec_json",
    )
    codex_packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
        _jsonl_for_tool_call(),
        prompt_packet=prompt_packet,
    )
    router_packet = hook_entry.build_router_hook_entry_packet(
        prompt_text=PROMPT,
        runtime_context=_runtime_context(),
        hook_surface_kind=hook_entry.HOOK_SURFACE_PROMPT_PREPROCESSOR,
    )
    return ingress.build_custom_codex_ingress_proof_packet(
        prompt_packet=prompt_packet,
        codex_tool_call_packet=codex_packet,
        router_hook_entry_packet=router_packet,
        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
    )


def _dispatch_packet() -> dict[str, object]:
    return dispatch_proof.build_controlled_ingress_api_dispatch_proof_packet(
        ingress_proof_packet=_ingress_packet(),
        prompt_text=PROMPT,
        runtime_context=_runtime_context(),
        hook_surface_kind=hook_entry.HOOK_SURFACE_PROMPT_PREPROCESSOR,
        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
    )


def _handoff_packet(
    *,
    dispatch_packet: dict[str, object] | None = None,
) -> dict[str, object]:
    return handoff_proof.build_controlled_dispatch_handoff_proof_packet(
        _dispatch_packet() if dispatch_packet is None else dispatch_packet,
        handoff_surface_kind=HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
    )


def _delivery_payload_for_dispatch(dispatch_packet: dict[str, object]) -> dict[str, object]:
    normalized = handoff_proof._normalized_controlled_dispatch_packet(dispatch_packet)
    handoff_payload = _safe_handoff_payload(
        normalized,
        HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
    )
    return delivery._safe_delivery_payload(
        handoff_payload,
        delivery_surface_kind=delivery.DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
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


def _jsonl_for_tool_result(event: dict[str, object]) -> str:
    return "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "thread-transcript"}),
            json.dumps({"type": "turn.started"}),
            json.dumps(event, ensure_ascii=True),
            json.dumps({"type": "turn.completed"}),
        ]
    )


def _matching_handoff_and_events() -> tuple[dict[str, object], list[dict[str, object]]]:
    dispatch_packet = _dispatch_packet()
    handoff_packet = _handoff_packet(dispatch_packet=dispatch_packet)
    structured = _delivery_payload_for_dispatch(dispatch_packet)
    assert structured["handoff_payload_sha256"] == handoff_packet["handoff_payload_digest"]
    return handoff_packet, [
        {"type": "thread.started", "thread_id": "thread-transcript"},
        {"type": "turn.started"},
        _tool_result_event(structured),
        {"type": "turn.completed"},
    ]


def _assert_no_product_or_native_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["codex_working_flow_delivery_proven"])
    testcase.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
    testcase.assertFalse(packet["live_provider_proven"])
    testcase.assertFalse(packet["live_provider_response_proven"])
    testcase.assertFalse(packet["external_live_provider_response_proven"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_ui"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_live_provider"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


def _assert_no_raw_payload_data(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    testcase.assertNotIn(PROMPT, serialized)
    testcase.assertNotIn(ROUTE_ID, serialized)
    testcase.assertNotIn(RAW_PROVIDER_TEXT, serialized)
    testcase.assertFalse(packet_contains_text(packet, PROMPT))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["raw_jsonl_recorded"])
    testcase.assertFalse(packet["tool_call_arguments_recorded"])
    testcase.assertFalse(packet["route_candidate_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


class CodexTranscriptDeliveryObservationTests(unittest.TestCase):
    def test_positive_observes_handoff_payload_in_codex_exec_mcp_tool_result(self) -> None:
        handoff_packet, events = _matching_handoff_and_events()

        packet = transcript.build_codex_transcript_delivery_observation_packet(
            handoff_packet,
            events,
            secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            transcript.CODEX_TRANSCRIPT_DELIVERY_OBSERVATION_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(
            packet["handoff_proof_kind"],
            handoff_proof.CONTROLLED_DISPATCH_HANDOFF_PACKET_KIND,
        )
        self.assertTrue(packet["handoff_proof_valid"])
        self.assertTrue(packet["handoff_completed"])
        self.assertTrue(packet["handoff_envelope_built"])
        self.assertTrue(packet["machine_response_envelope_observed"])
        self.assertTrue(packet["machine_response_structured_content_present"])
        self.assertEqual(
            packet["observation_path"],
            transcript.OBSERVATION_PATH_CODEX_EXEC_JSON_MCP_TOOL_RESULT,
        )
        self.assertTrue(packet["codex_exec_json_events_observed"])
        self.assertTrue(packet["codex_exec_transcript_sha256"])
        self.assertTrue(packet["mcp_tool_result_observed"])
        self.assertTrue(packet["mcp_tool_result_structured_content_present"])
        self.assertEqual(packet["mcp_tool_result_event_type"], "item.completed")
        self.assertEqual(packet["mcp_tool_result_item_type"], "mcp_tool_result")
        self.assertEqual(packet["mcp_server_name_observed"], "wbp")
        self.assertEqual(packet["mcp_tool_name_observed"], "delegate_to_dip")
        self.assertFalse(packet["mcp_tool_result_is_error"])
        self.assertTrue(packet["mcp_tool_result_server_allowed"])
        self.assertTrue(packet["mcp_tool_result_name_allowed"])
        self.assertTrue(packet["mcp_tool_result_content_text_present"])
        self.assertTrue(packet["mcp_tool_result_content_text_json_mapping_present"])
        self.assertTrue(
            packet["mcp_tool_result_content_text_json_matches_structured_content"]
        )
        self.assertTrue(packet["content_text_structured_content_digest"])
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
        self.assertTrue(packet["codex_transcript_delivery_observed"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_invalid_handoff_and_missing_transcript_result(self) -> None:
        handoff_packet, _events = _matching_handoff_and_events()
        invalid_handoff = dict(handoff_packet)
        invalid_handoff["status"] = "error"

        cases = [
            (
                "invalid_handoff",
                invalid_handoff,
                [{"type": "thread.started"}],
                transcript.CODEX_TRANSCRIPT_DELIVERY_HANDOFF_PROOF_INVALID,
            ),
            (
                "no_tool_result",
                handoff_packet,
                [{"type": "thread.started"}, {"type": "turn.completed"}],
                transcript.CODEX_TRANSCRIPT_DELIVERY_TRANSCRIPT_NOT_OBSERVED,
            ),
        ]
        for name, handoff, events, machine_error in cases:
            with self.subTest(name=name):
                packet = transcript.build_codex_transcript_delivery_observation_packet(
                    handoff,
                    events,
                    secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_error)
                self.assertFalse(packet["codex_transcript_delivery_observed"])
                self.assertFalse(packet["product_ready"])
                _assert_no_product_or_native_claim(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_digest_content_error_and_wrong_surface_cases(self) -> None:
        dispatch_packet = _dispatch_packet()
        handoff_packet = _handoff_packet(dispatch_packet=dispatch_packet)
        valid_structured = _delivery_payload_for_dispatch(dispatch_packet)

        digest_mismatch = dict(valid_structured)
        digest_mismatch["handoff_payload_sha256"] = "f" * 64

        content_mismatch_text = json.dumps(
            {"packet_kind": "wrong"},
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )

        cases = [
            (
                "digest_mismatch",
                _tool_result_event(digest_mismatch),
                transcript.CODEX_TRANSCRIPT_DELIVERY_DIGEST_MISMATCH,
                "handoff_payload_declared_digest_mismatch",
            ),
            (
                "content_text_mismatch",
                _tool_result_event(valid_structured, content_text=content_mismatch_text),
                transcript.CODEX_TRANSCRIPT_DELIVERY_DIGEST_MISMATCH,
                "mcp_tool_result_content_text_structured_content_mismatch",
            ),
            (
                "is_error_result",
                _tool_result_event(valid_structured, is_error=True),
                transcript.CODEX_TRANSCRIPT_DELIVERY_DIGEST_MISMATCH,
                "mcp_tool_result_is_error",
            ),
            (
                "wrong_server",
                _tool_result_event(valid_structured, server_name="browser"),
                transcript.CODEX_TRANSCRIPT_DELIVERY_DIGEST_MISMATCH,
                "mcp_tool_result_server_not_wbp",
            ),
            (
                "wrong_tool",
                _tool_result_event(valid_structured, tool_name="other_tool"),
                transcript.CODEX_TRANSCRIPT_DELIVERY_DIGEST_MISMATCH,
                "mcp_tool_result_tool_name_invalid",
            ),
        ]
        for name, event, machine_error, reason in cases:
            with self.subTest(name=name):
                packet = transcript.build_codex_transcript_delivery_observation_packet(
                    handoff_packet,
                    [{"type": "turn.started"}, event, {"type": "turn.completed"}],
                    secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_error)
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["codex_transcript_delivery_observed"])
                self.assertFalse(packet["product_ready"])
                _assert_no_product_or_native_claim(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_unsafe_transcript_result_claims(self) -> None:
        handoff_packet, events = _matching_handoff_and_events()
        unsafe_events = [dict(event) for event in events]
        unsafe_events[2] = dict(unsafe_events[2])
        unsafe_events[2]["raw_provider_response_recorded"] = True

        packet = transcript.build_codex_transcript_delivery_observation_packet(
            handoff_packet,
            unsafe_events,
            secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            transcript.CODEX_TRANSCRIPT_DELIVERY_PAYLOAD_UNSAFE,
        )
        self.assertIn("raw_provider_response_recorded", packet["blocking_reasons"])
        self.assertFalse(packet["codex_transcript_delivery_observed"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_assistant_output_payload_as_tool_result_false_green(self) -> None:
        dispatch_packet = _dispatch_packet()
        handoff_packet = _handoff_packet(dispatch_packet=dispatch_packet)
        structured = _delivery_payload_for_dispatch(dispatch_packet)
        assistant_output_event = {
            "type": "assistant/output",
            "item": {
                "id": "item-assistant-output",
                "type": "output_text",
                "role": "assistant",
                "result": {
                    "structuredContent": structured,
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                structured,
                                ensure_ascii=True,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                        }
                    ],
                    "isError": False,
                },
            },
        }

        packet = transcript.build_codex_transcript_delivery_observation_packet(
            handoff_packet,
            [{"type": "turn.started"}, assistant_output_event, {"type": "turn.completed"}],
            secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            transcript.CODEX_TRANSCRIPT_DELIVERY_TRANSCRIPT_NOT_OBSERVED,
        )
        self.assertIn("mcp_tool_result_not_observed", packet["blocking_reasons"])
        self.assertFalse(packet["mcp_tool_result_observed"])
        self.assertFalse(packet["codex_transcript_delivery_observed"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_selects_matching_result_instead_of_stale_result(self) -> None:
        dispatch_packet = _dispatch_packet()
        handoff_packet = _handoff_packet(dispatch_packet=dispatch_packet)
        valid_structured = _delivery_payload_for_dispatch(dispatch_packet)
        stale_structured = dict(valid_structured)
        stale_structured["handoff_payload_sha256"] = "0" * 64

        packet = transcript.build_codex_transcript_delivery_observation_packet(
            handoff_packet,
            [
                {"type": "turn.started"},
                _tool_result_event(stale_structured, server_name="browser"),
                _tool_result_event(valid_structured),
                {"type": "turn.completed"},
            ],
            secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["codex_transcript_delivery_observed"])
        self.assertEqual(packet["mcp_server_name_observed"], "wbp")
        self.assertTrue(packet["structured_content_matches_handoff"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_reads_handoff_and_jsonl_files_and_emits_single_json(self) -> None:
        dispatch_packet = _dispatch_packet()
        handoff_packet = _handoff_packet(dispatch_packet=dispatch_packet)
        structured = _delivery_payload_for_dispatch(dispatch_packet)
        jsonl_text = _jsonl_for_tool_result(_tool_result_event(structured))

        with tempfile.TemporaryDirectory() as temp_dir:
            handoff_path = Path(temp_dir) / "handoff.json"
            jsonl_path = Path(temp_dir) / "codex.jsonl"
            handoff_path.write_text(json.dumps(handoff_packet) + "\n", encoding="utf-8")
            jsonl_path.write_text(jsonl_text + "\n", encoding="utf-8")
            sentinel = Path(temp_dir) / "sentinel.txt"
            sentinel.write_text("unchanged", encoding="utf-8")
            env = os.environ.copy()
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "transcript-observe",
                    "--handoff-proof-file",
                    str(handoff_path),
                    "--codex-exec-jsonl-file",
                    str(jsonl_path),
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            sentinel_text = sentinel.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sentinel_text, "unchanged")
        packet = json.loads(result.stdout)
        self.assertEqual(result.stdout.strip(), json.dumps(packet, ensure_ascii=True))
        self.assertEqual(
            packet["packet_kind"],
            transcript.CODEX_TRANSCRIPT_DELIVERY_OBSERVATION_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["handoff_proof_file_present"])
        self.assertTrue(packet["handoff_proof_file_read"])
        self.assertFalse(packet["handoff_proof_file_path_recorded"])
        self.assertTrue(packet["codex_exec_jsonl_file_present"])
        self.assertTrue(packet["codex_exec_jsonl_file_read"])
        self.assertFalse(packet["codex_exec_jsonl_file_path_recorded"])
        self.assertTrue(packet["codex_exec_transcript_sha256"])
        self.assertTrue(packet["codex_transcript_delivery_observed"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_blocks_invalid_jsonl_closed(self) -> None:
        handoff_packet, _events = _matching_handoff_and_events()
        with tempfile.TemporaryDirectory() as temp_dir:
            handoff_path = Path(temp_dir) / "handoff.json"
            jsonl_path = Path(temp_dir) / "codex.jsonl"
            handoff_path.write_text(json.dumps(handoff_packet) + "\n", encoding="utf-8")
            jsonl_path.write_text("{not-json}\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "transcript-observe",
                    "--handoff-proof-file",
                    str(handoff_path),
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
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            transcript.CODEX_TRANSCRIPT_DELIVERY_TRANSCRIPT_NOT_OBSERVED,
        )
        self.assertIn("codex_exec_jsonl_parse_error", packet["blocking_reasons"])
        self.assertFalse(packet["codex_transcript_delivery_observed"])
        _assert_no_product_or_native_claim(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])


if __name__ == "__main__":
    unittest.main()
