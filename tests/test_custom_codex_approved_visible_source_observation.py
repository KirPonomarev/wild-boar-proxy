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
from wild_boar_proxy import custom_codex_approved_visible_source_observation as visible
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
PROMPT = "Codex, дай задачу DIP: prove approved visible source."
RAW_PROVIDER_TEXT = "raw provider response must not be stored"


def _runtime_context() -> dict[str, object]:
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
        "allowed_api_route_ids": [ROUTE_ID],
        "forbidden_stale_route_ids": ["wbp-deepseek-v3"],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _jsonl_for_tool_call() -> str:
    return "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "thread-visible"}),
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


def _handoff_packet(dispatch_packet: dict[str, object]) -> dict[str, object]:
    return handoff_proof.build_controlled_dispatch_handoff_proof_packet(
        dispatch_packet,
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
    return {
        "type": "item.completed",
        "item": {
            "id": "item-delegate-result",
            "type": "mcp_tool_result",
            "server_name": "wbp",
            "tool_name": "delegate_to_dip",
            "status": "completed",
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


def _assistant_event(
    digest: str,
    *,
    include_marker: bool = True,
    marker_digest: str | None = None,
    text: str = "WBP approved visible-source receipt.",
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
            "id": "item-assistant-visible",
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
            "name": "Agent 2",
            "status": "completed",
            "text": "Local sub-agent Agent 2 produced a response.",
        },
    }


def _jsonl_from_events(events: list[dict[str, object]]) -> str:
    return "\n".join(json.dumps(event, ensure_ascii=True) for event in events)


def _matching_continuation_and_events() -> tuple[dict[str, object], list[dict[str, object]]]:
    dispatch_packet = _dispatch_packet()
    handoff_packet = _handoff_packet(dispatch_packet)
    structured = _delivery_payload_for_dispatch(dispatch_packet)
    assert structured["handoff_payload_sha256"] == handoff_packet["handoff_payload_digest"]
    events = [
        {"type": "thread.started", "thread_id": "thread-visible"},
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
    continuation_packet = continuation.build_codex_exec_assistant_continuation_proof_packet(
        observation,
        events,
        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
    )
    assert continuation_packet["status"] == "ok"
    return continuation_packet, events


def _bind_source_digest(
    continuation_packet: dict[str, object],
    events: list[dict[str, object]],
) -> dict[str, object]:
    packet = dict(continuation_packet)
    packet["codex_exec_transcript_sha256"] = transcript._codex_exec_transcript_digest(events)
    return packet


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


class CustomCodexApprovedVisibleSourceObservationTests(unittest.TestCase):
    def test_positive_observes_approved_visible_source_assistant_output(self) -> None:
        continuation_packet, events = _matching_continuation_and_events()

        packet = visible.build_custom_codex_approved_visible_source_observation_packet(
            continuation_packet,
            events,
            visible_source_kind=visible.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
            secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            visible.CUSTOM_CODEX_APPROVED_VISIBLE_SOURCE_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(
            packet["assistant_continuation_proof_kind"],
            continuation.CODEX_EXEC_ASSISTANT_CONTINUATION_PACKET_KIND,
        )
        self.assertTrue(packet["assistant_continuation_proof_valid"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertTrue(packet["assistant_response_bound_to_handoff_digest"])
        self.assertTrue(packet["same_codex_exec_jsonl_bound"])
        self.assertTrue(packet["handoff_payload_digest"])
        self.assertEqual(
            packet["approved_visible_source_kind"],
            visible.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
        )
        self.assertTrue(packet["approved_visible_source_allowed"])
        self.assertEqual(packet["approved_visible_source_kinds_count"], 1)
        self.assertTrue(packet["visible_source_events_observed"])
        self.assertTrue(packet["visible_source_digest"])
        self.assertTrue(packet["assistant_continuation_source_digest"])
        self.assertTrue(packet["visible_source_digest_bound"])
        self.assertTrue(packet["visible_source_digest_matches_continuation"])
        self.assertTrue(packet["matching_mcp_tool_result_observed"])
        self.assertTrue(packet["visible_source_assistant_output_observed"])
        self.assertTrue(packet["visible_source_marker_observed"])
        self.assertFalse(packet["visible_source_marker_digest_mismatch"])
        self.assertTrue(packet["visible_source_marker_bound_to_handoff_digest"])
        self.assertEqual(packet["visible_source_marker_digest"], packet["handoff_payload_digest"])
        self.assertEqual(packet["visible_source_marker_binding_method"], "safe_digest_metadata")
        self.assertTrue(packet["custom_codex_approved_visible_source_observed"])
        self.assertTrue(packet["custom_codex_visible_flow_observed"])
        self.assertFalse(packet["visible_source_secret_value_present"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_positive_supports_safe_digest_marker_text_lane(self) -> None:
        dispatch_packet = _dispatch_packet()
        handoff_packet = _handoff_packet(dispatch_packet)
        structured = _delivery_payload_for_dispatch(dispatch_packet)
        digest = str(handoff_packet["handoff_payload_digest"])
        events = [
            {"type": "thread.started", "thread_id": "thread-visible-marker"},
            {"type": "turn.started"},
            _tool_result_event(structured),
            _assistant_event(
                digest,
                include_marker=False,
                text=f"safe receipt wbp_handoff_digest={digest}",
            ),
            {"type": "turn.completed"},
        ]
        observation = transcript.build_codex_transcript_delivery_observation_packet(
            handoff_packet,
            events,
            secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
        )
        continuation_packet = (
            continuation.build_codex_exec_assistant_continuation_proof_packet(
                observation,
                events,
                secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
            )
        )
        self.assertEqual(continuation_packet["status"], "ok")
        self.assertEqual(continuation_packet["binding_method"], "safe_digest_marker")

        packet = visible.build_custom_codex_approved_visible_source_observation_packet(
            continuation_packet,
            events,
            visible_source_kind=visible.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
            secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["custom_codex_approved_visible_source_observed"])
        self.assertTrue(packet["visible_source_marker_observed"])
        self.assertTrue(packet["visible_source_marker_bound_to_handoff_digest"])
        self.assertEqual(packet["visible_source_marker_binding_method"], "safe_digest_marker")
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_invalid_continuation_and_unapproved_source_kind(self) -> None:
        continuation_packet, events = _matching_continuation_and_events()
        invalid = dict(continuation_packet)
        invalid["status"] = "error"
        cases = [
            (
                "invalid_continuation",
                invalid,
                visible.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
                visible.VISIBLE_SOURCE_OBSERVATION_CONTINUATION_INVALID,
                "assistant_continuation_proof_packet_not_ok",
            ),
            (
                "unapproved_source",
                continuation_packet,
                "codex_native_observer_snapshot",
                visible.VISIBLE_SOURCE_OBSERVATION_SOURCE_NOT_ALLOWED,
                "approved_visible_source_kind_not_allowed",
            ),
        ]
        for name, source, source_kind, machine_error, reason in cases:
            with self.subTest(name=name):
                packet = visible.build_custom_codex_approved_visible_source_observation_packet(
                    source,
                    events,
                    visible_source_kind=source_kind,
                    secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_error)
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["custom_codex_approved_visible_source_observed"])
                _assert_no_product_or_native_claim(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_digest_source_and_marker_failures(self) -> None:
        continuation_packet, events = _matching_continuation_and_events()
        different_events = list(events)
        different_events[3] = _assistant_event(
            str(continuation_packet["handoff_payload_digest"]),
            text="Different safe visible-source text.",
        )
        no_assistant_events = [events[0], events[1], events[2], events[4]]
        no_assistant_source = _bind_source_digest(continuation_packet, no_assistant_events)
        no_marker_events = list(events)
        no_marker_events[3] = _assistant_event(
            str(continuation_packet["handoff_payload_digest"]),
            include_marker=False,
        )
        no_marker_source = _bind_source_digest(continuation_packet, no_marker_events)
        mismatch_events = list(events)
        mismatch_events[3] = _assistant_event(
            str(continuation_packet["handoff_payload_digest"]),
            marker_digest="f" * 64,
        )
        mismatch_source = _bind_source_digest(continuation_packet, mismatch_events)
        semantic_only_events = list(events)
        semantic_only_events[3] = _assistant_event(
            str(continuation_packet["handoff_payload_digest"]),
            include_marker=False,
            text=f"The handoff digest is {continuation_packet['handoff_payload_digest']}.",
        )
        semantic_only_source = _bind_source_digest(continuation_packet, semantic_only_events)
        cases = [
            (
                "source_digest_mismatch",
                continuation_packet,
                different_events,
                visible.VISIBLE_SOURCE_OBSERVATION_SOURCE_NOT_OBSERVED,
                "visible_source_digest_not_bound",
            ),
            (
                "tool_result_marker_only",
                no_assistant_source,
                no_assistant_events,
                visible.VISIBLE_SOURCE_OBSERVATION_SOURCE_NOT_OBSERVED,
                "visible_source_assistant_output_not_observed",
            ),
            (
                "no_marker",
                no_marker_source,
                no_marker_events,
                visible.VISIBLE_SOURCE_OBSERVATION_NOT_BOUND,
                "visible_source_marker_missing",
            ),
            (
                "marker_mismatch",
                mismatch_source,
                mismatch_events,
                visible.VISIBLE_SOURCE_OBSERVATION_NOT_BOUND,
                "visible_source_marker_digest_mismatch",
            ),
            (
                "semantic_only",
                semantic_only_source,
                semantic_only_events,
                visible.VISIBLE_SOURCE_OBSERVATION_NOT_BOUND,
                "visible_source_marker_missing",
            ),
        ]
        for name, source, source_events, machine_error, reason in cases:
            with self.subTest(name=name):
                packet = visible.build_custom_codex_approved_visible_source_observation_packet(
                    source,
                    source_events,
                    visible_source_kind=visible.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
                    secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_error)
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["custom_codex_approved_visible_source_observed"])
                _assert_no_product_or_native_claim(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_unsafe_raw_overclaim_secret_and_subagent_cases(self) -> None:
        continuation_packet, events = _matching_continuation_and_events()
        overclaim_events = list(events)
        overclaim_events[3] = _assistant_event(
            str(continuation_packet["handoff_payload_digest"]),
            extra={"custom_codex_ui_visibility_proven": True},
        )
        overclaim_source = _bind_source_digest(continuation_packet, overclaim_events)
        product_events = list(events)
        product_events[3] = _assistant_event(
            str(continuation_packet["handoff_payload_digest"]),
            extra={"product_ready": True},
        )
        product_source = _bind_source_digest(continuation_packet, product_events)
        raw_events = list(events)
        raw_events[3] = _assistant_event(
            str(continuation_packet["handoff_payload_digest"]),
            extra={"raw_provider_response_recorded": True},
        )
        raw_source = _bind_source_digest(continuation_packet, raw_events)
        secret_events = list(events)
        secret_events[3] = _assistant_event(
            str(continuation_packet["handoff_payload_digest"]),
            text=f"Unsafe raw prompt: {PROMPT}",
        )
        secret_source = _bind_source_digest(continuation_packet, secret_events)
        subagent_events = [events[0], events[1], events[2], _subagent_event(), events[3], events[4]]
        subagent_source = _bind_source_digest(continuation_packet, subagent_events)
        cases = [
            (
                "ui_visibility_overclaim",
                overclaim_source,
                overclaim_events,
                "custom_codex_ui_visibility_must_not_be_claimed",
            ),
            ("product_ready", product_source, product_events, "product_ready_must_not_be_claimed"),
            (
                "raw_provider_response",
                raw_source,
                raw_events,
                "raw_provider_response_recorded",
            ),
            (
                "secret_value",
                secret_source,
                secret_events,
                "secret_value_present_in_visible_source",
            ),
            (
                "subagent",
                subagent_source,
                subagent_events,
                "native_codex_subagent_used_as_dip",
            ),
        ]
        for name, source, source_events, reason in cases:
            with self.subTest(name=name):
                packet = visible.build_custom_codex_approved_visible_source_observation_packet(
                    source,
                    source_events,
                    visible_source_kind=visible.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
                    secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    visible.VISIBLE_SOURCE_OBSERVATION_PAYLOAD_UNSAFE,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["custom_codex_approved_visible_source_observed"])
                _assert_no_product_or_native_claim(self, packet)
                if name != "secret_value":
                    _assert_no_raw_payload_data(self, packet)
                else:
                    self.assertTrue(packet["visible_source_secret_value_present"])
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_reads_continuation_and_visible_source_files_and_emits_single_json(self) -> None:
        continuation_packet, events = _matching_continuation_and_events()
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_path = Path(temp_dir) / "continuation.json"
            jsonl_path = Path(temp_dir) / "codex.jsonl"
            proof_path.write_text(json.dumps(continuation_packet) + "\n", encoding="utf-8")
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
                    "visible-source-observe",
                    "--assistant-continuation-proof-file",
                    str(proof_path),
                    "--visible-source-kind",
                    visible.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
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
            visible.CUSTOM_CODEX_APPROVED_VISIBLE_SOURCE_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["assistant_continuation_proof_file_present"])
        self.assertTrue(packet["assistant_continuation_proof_file_read"])
        self.assertFalse(packet["assistant_continuation_proof_file_path_recorded"])
        self.assertTrue(packet["codex_exec_jsonl_file_present"])
        self.assertTrue(packet["codex_exec_jsonl_file_read"])
        self.assertFalse(packet["codex_exec_jsonl_file_path_recorded"])
        self.assertTrue(packet["custom_codex_approved_visible_source_observed"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_blocks_invalid_jsonl_closed(self) -> None:
        continuation_packet, _events = _matching_continuation_and_events()
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_path = Path(temp_dir) / "continuation.json"
            jsonl_path = Path(temp_dir) / "codex.jsonl"
            proof_path.write_text(json.dumps(continuation_packet) + "\n", encoding="utf-8")
            jsonl_path.write_text("{not-json}\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "visible-source-observe",
                    "--assistant-continuation-proof-file",
                    str(proof_path),
                    "--visible-source-kind",
                    visible.VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
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
            visible.VISIBLE_SOURCE_OBSERVATION_SOURCE_NOT_OBSERVED,
        )
        self.assertIn("visible_source_jsonl_parse_error", packet["blocking_reasons"])
        self.assertFalse(packet["custom_codex_approved_visible_source_observed"])
        _assert_no_product_or_native_claim(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])


if __name__ == "__main__":
    unittest.main()
