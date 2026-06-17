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

from wild_boar_proxy import codex_exec_assistant_continuation_proof as continuation
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
PROMPT = "Codex, дай задачу DIP: prove assistant continuation."
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
            json.dumps({"type": "thread.started", "thread_id": "thread-continuation"}),
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


def _tool_result_event(structured_content: dict[str, object]) -> dict[str, object]:
    text = json.dumps(
        structured_content,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "type": "item.completed",
        "item": {
            "id": "item-delegate-result",
            "type": "mcp_tool_result",
            "server_name": "wbp",
            "tool_name": "delegate_to_dip",
            "status": "completed",
            "result": {
                "content": [{"type": "text", "text": text}],
                "structuredContent": structured_content,
                "isError": False,
            },
        },
    }


def _assistant_event(
    digest: str,
    *,
    include_marker: bool = True,
    marker_digest: str | None = None,
    text: str = "WBP continuation receipt.",
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
            "text": "Local sub-agent Agent 2 produced a response.",
        },
    }


def _jsonl_from_events(events: list[dict[str, object]]) -> str:
    return "\n".join(json.dumps(event, ensure_ascii=True) for event in events)


def _matching_observation_and_events() -> tuple[dict[str, object], list[dict[str, object]]]:
    dispatch_packet = _dispatch_packet()
    handoff_packet = _handoff_packet(dispatch_packet=dispatch_packet)
    structured = _delivery_payload_for_dispatch(dispatch_packet)
    assert structured["handoff_payload_sha256"] == handoff_packet["handoff_payload_digest"]
    events = [
        {"type": "thread.started", "thread_id": "thread-continuation"},
        {"type": "turn.started"},
        _tool_result_event(structured),
        _assistant_event(str(handoff_packet["handoff_payload_digest"])),
        {"type": "turn.completed"},
    ]
    observation = transcript.build_codex_transcript_delivery_observation_packet(
        handoff_packet,
        events,
        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
    )
    assert observation["status"] == "ok"
    return observation, events


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


class CodexExecAssistantContinuationProofTests(unittest.TestCase):
    def test_positive_proves_assistant_continuation_after_digest_bound_tool_result(
        self,
    ) -> None:
        observation, events = _matching_observation_and_events()

        packet = continuation.build_codex_exec_assistant_continuation_proof_packet(
            observation,
            events,
            secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            continuation.CODEX_EXEC_ASSISTANT_CONTINUATION_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(
            packet["transcript_observation_kind"],
            transcript.CODEX_TRANSCRIPT_DELIVERY_OBSERVATION_PACKET_KIND,
        )
        self.assertTrue(packet["transcript_observation_valid"])
        self.assertTrue(packet["transcript_delivery_observed"])
        self.assertTrue(packet["mcp_tool_result_observed"])
        self.assertTrue(packet["mcp_tool_result_structured_content_present"])
        self.assertTrue(packet["structured_content_matches_handoff"])
        self.assertTrue(packet["handoff_payload_digest"])
        self.assertTrue(packet["codex_exec_json_events_observed"])
        self.assertTrue(packet["codex_exec_transcript_sha256"])
        self.assertTrue(packet["transcript_observation_codex_exec_transcript_sha256"])
        self.assertTrue(packet["same_codex_exec_jsonl_bound"])
        self.assertTrue(packet["same_codex_exec_jsonl_digest_matches"])
        self.assertTrue(packet["matching_mcp_tool_result_observed"])
        self.assertTrue(packet["matching_mcp_tool_result_event_index_present"])
        self.assertTrue(packet["assistant_response_observed"])
        self.assertTrue(packet["assistant_response_after_tool_result"])
        self.assertTrue(packet["assistant_response_event_index_present"])
        self.assertEqual(packet["assistant_response_event_type"], "item.completed")
        self.assertEqual(packet["assistant_response_item_type"], "assistant_message")
        self.assertEqual(packet["assistant_response_role"], "assistant")
        self.assertTrue(packet["assistant_machine_marker_observed"])
        self.assertFalse(packet["assistant_marker_digest_mismatch"])
        self.assertTrue(packet["assistant_response_bound_to_handoff_digest"])
        self.assertEqual(
            packet["binding_method"],
            continuation.BINDING_METHOD_SAFE_DIGEST_METADATA,
        )
        self.assertEqual(packet["assistant_binding_digest"], packet["handoff_payload_digest"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["transcript_secret_value_present"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_invalid_observation_and_missing_or_early_assistant_response(self) -> None:
        observation, events = _matching_observation_and_events()
        invalid_observation = dict(observation)
        invalid_observation["status"] = "error"
        early_assistant_events = [events[0], events[1], events[3], events[2], events[4]]
        cases = [
            (
                "invalid_observation",
                invalid_observation,
                events,
                continuation.CODEX_EXEC_ASSISTANT_CONTINUATION_OBSERVATION_INVALID,
                "transcript_observation_packet_not_ok",
            ),
            (
                "no_assistant",
                observation,
                [events[0], events[1], events[2], events[4]],
                continuation.CODEX_EXEC_ASSISTANT_CONTINUATION_TRANSCRIPT_NOT_OBSERVED,
                "assistant_response_after_tool_result_not_observed",
            ),
            (
                "assistant_before_tool_result",
                observation,
                early_assistant_events,
                continuation.CODEX_EXEC_ASSISTANT_CONTINUATION_TRANSCRIPT_NOT_OBSERVED,
                "assistant_response_after_tool_result_not_observed",
            ),
        ]
        for name, source, codex_events, machine_error, reason in cases:
            with self.subTest(name=name):
                packet = continuation.build_codex_exec_assistant_continuation_proof_packet(
                    source,
                    codex_events,
                    secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_error)
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["codex_exec_assistant_continuation_proven"])
                _assert_no_product_or_native_claim(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_unbound_or_mismatched_assistant_marker(self) -> None:
        observation, events = _matching_observation_and_events()
        no_marker_events = list(events)
        no_marker_events[3] = _assistant_event(
            str(observation["handoff_payload_digest"]),
            include_marker=False,
        )
        no_marker_observation = dict(observation)
        no_marker_observation["codex_exec_transcript_sha256"] = (
            transcript._codex_exec_transcript_digest(no_marker_events)
        )
        mismatch_events = list(events)
        mismatch_events[3] = _assistant_event(
            str(observation["handoff_payload_digest"]),
            marker_digest="f" * 64,
        )
        mismatch_observation = dict(observation)
        mismatch_observation["codex_exec_transcript_sha256"] = (
            transcript._codex_exec_transcript_digest(mismatch_events)
        )
        cases = [
            (
                "no_marker",
                no_marker_observation,
                no_marker_events,
                "assistant_response_machine_digest_marker_missing",
            ),
            (
                "mismatch",
                mismatch_observation,
                mismatch_events,
                "assistant_response_handoff_digest_mismatch",
            ),
        ]
        for name, source, codex_events, reason in cases:
            with self.subTest(name=name):
                packet = continuation.build_codex_exec_assistant_continuation_proof_packet(
                    source,
                    codex_events,
                    secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    continuation.CODEX_EXEC_ASSISTANT_CONTINUATION_NOT_BOUND,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["assistant_response_bound_to_handoff_digest"])
                self.assertFalse(packet["codex_exec_assistant_continuation_proven"])
                _assert_no_product_or_native_claim(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_transcript_digest_mismatch_and_broken_jsonl(self) -> None:
        observation, events = _matching_observation_and_events()
        different_jsonl_events = list(events)
        different_jsonl_events[3] = _assistant_event(
            str(observation["handoff_payload_digest"]),
            text="Different safe continuation text.",
        )
        digest_packet = continuation.build_codex_exec_assistant_continuation_proof_packet(
            observation,
            different_jsonl_events,
            secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(digest_packet["status"], "error")
        self.assertEqual(
            digest_packet["machine_error_code"],
            continuation.CODEX_EXEC_ASSISTANT_CONTINUATION_TRANSCRIPT_NOT_OBSERVED,
        )
        self.assertIn(
            "codex_exec_transcript_digest_mismatch",
            digest_packet["blocking_reasons"],
        )
        self.assertFalse(digest_packet["same_codex_exec_jsonl_bound"])
        self.assertFalse(digest_packet["codex_exec_assistant_continuation_proven"])
        _assert_no_product_or_native_claim(self, digest_packet)
        _assert_no_raw_payload_data(self, digest_packet)
        self.assertEqual(packets.inspect_command_packet_semantics(digest_packet), [])

        assistant_only_events = [events[0], events[1], events[3], events[4]]
        assistant_only_observation = dict(observation)
        assistant_only_observation["codex_exec_transcript_sha256"] = (
            transcript._codex_exec_transcript_digest(assistant_only_events)
        )
        assistant_only_packet = (
            continuation.build_codex_exec_assistant_continuation_proof_packet(
                assistant_only_observation,
                assistant_only_events,
                secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
            )
        )

        self.assertEqual(assistant_only_packet["status"], "error")
        self.assertEqual(
            assistant_only_packet["machine_error_code"],
            continuation.CODEX_EXEC_ASSISTANT_CONTINUATION_TRANSCRIPT_NOT_OBSERVED,
        )
        self.assertIn(
            "matching_mcp_tool_result_not_observed",
            assistant_only_packet["blocking_reasons"],
        )
        self.assertTrue(assistant_only_packet["same_codex_exec_jsonl_bound"])
        self.assertFalse(assistant_only_packet["matching_mcp_tool_result_observed"])
        self.assertFalse(assistant_only_packet["codex_exec_assistant_continuation_proven"])
        _assert_no_product_or_native_claim(self, assistant_only_packet)
        _assert_no_raw_payload_data(self, assistant_only_packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(assistant_only_packet),
            [],
        )

        mismatch_observation = dict(observation)
        mismatch_observation["handoff_payload_digest"] = "e" * 64
        packet = continuation.build_codex_exec_assistant_continuation_proof_packet(
            mismatch_observation,
            events,
            secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            continuation.CODEX_EXEC_ASSISTANT_CONTINUATION_TRANSCRIPT_NOT_OBSERVED,
        )
        self.assertIn("matching_mcp_tool_result_not_observed", packet["blocking_reasons"])
        self.assertFalse(packet["codex_exec_assistant_continuation_proven"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_unsafe_raw_overclaim_secret_and_subagent_cases(self) -> None:
        observation, events = _matching_observation_and_events()
        overclaim_events = list(events)
        overclaim_events[3] = _assistant_event(
            str(observation["handoff_payload_digest"]),
            extra={"product_ready": True},
        )
        raw_events = list(events)
        raw_events[3] = _assistant_event(
            str(observation["handoff_payload_digest"]),
            extra={"raw_provider_response_recorded": True},
        )
        secret_events = list(events)
        secret_events[3] = _assistant_event(
            str(observation["handoff_payload_digest"]),
            text=f"Unsafe raw prompt: {PROMPT}",
        )
        subagent_events = [events[0], events[1], events[2], _subagent_event(), events[3], events[4]]
        cases = [
            ("product_ready", overclaim_events, "product_ready_must_not_be_claimed"),
            (
                "raw_provider_response",
                raw_events,
                "raw_provider_response_recorded",
            ),
            (
                "secret_value_present",
                secret_events,
                "secret_value_present_in_transcript",
            ),
            (
                "subagent",
                subagent_events,
                "native_codex_subagent_used_as_dip",
            ),
        ]
        for name, codex_events, reason in cases:
            with self.subTest(name=name):
                packet = continuation.build_codex_exec_assistant_continuation_proof_packet(
                    observation,
                    codex_events,
                    secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    continuation.CODEX_EXEC_ASSISTANT_CONTINUATION_PAYLOAD_UNSAFE,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["codex_exec_assistant_continuation_proven"])
                _assert_no_product_or_native_claim(self, packet)
                if name != "secret_value_present":
                    _assert_no_raw_payload_data(self, packet)
                else:
                    self.assertTrue(packet["transcript_secret_value_present"])
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_reads_observation_and_jsonl_files_and_emits_single_json(self) -> None:
        observation, events = _matching_observation_and_events()
        with tempfile.TemporaryDirectory() as temp_dir:
            observation_path = Path(temp_dir) / "observation.json"
            jsonl_path = Path(temp_dir) / "codex.jsonl"
            observation_path.write_text(json.dumps(observation) + "\n", encoding="utf-8")
            jsonl_path.write_text(_jsonl_from_events(events) + "\n", encoding="utf-8")
            sentinel = Path(temp_dir) / "sentinel.txt"
            sentinel.write_text("unchanged", encoding="utf-8")
            env = os.environ.copy()
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "assistant-continuation-proof",
                    "--transcript-observation-file",
                    str(observation_path),
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
            continuation.CODEX_EXEC_ASSISTANT_CONTINUATION_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["transcript_observation_file_present"])
        self.assertTrue(packet["transcript_observation_file_read"])
        self.assertFalse(packet["transcript_observation_file_path_recorded"])
        self.assertTrue(packet["codex_exec_jsonl_file_present"])
        self.assertTrue(packet["codex_exec_jsonl_file_read"])
        self.assertFalse(packet["codex_exec_jsonl_file_path_recorded"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_blocks_invalid_jsonl_closed(self) -> None:
        observation, _events = _matching_observation_and_events()
        with tempfile.TemporaryDirectory() as temp_dir:
            observation_path = Path(temp_dir) / "observation.json"
            jsonl_path = Path(temp_dir) / "codex.jsonl"
            observation_path.write_text(json.dumps(observation) + "\n", encoding="utf-8")
            jsonl_path.write_text("{not-json}\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "assistant-continuation-proof",
                    "--transcript-observation-file",
                    str(observation_path),
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
            continuation.CODEX_EXEC_ASSISTANT_CONTINUATION_TRANSCRIPT_NOT_OBSERVED,
        )
        self.assertIn("codex_exec_jsonl_parse_error", packet["blocking_reasons"])
        self.assertFalse(packet["codex_exec_assistant_continuation_proven"])
        _assert_no_product_or_native_claim(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])


if __name__ == "__main__":
    unittest.main()
