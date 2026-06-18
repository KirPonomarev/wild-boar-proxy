# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from wild_boar_proxy import codex_working_flow_delivery_proof as working_flow
from wild_boar_proxy import real_custom_codex_hook_proof as integrated
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, дай задачу DIP: prove working flow delivery."
EXPECTED_TEXT = "WBP_DIP_DISPATCH_OK"
RAW_PROVIDER_TEXT = "raw provider response must not be stored"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _runtime_context(*, route_id: str = ROUTE_ID) -> dict[str, object]:
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
                "route_id": route_id,
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
        "agent_id_to_route": {"dip": route_id},
        "agent_id_to_model": {"codex": "gpt-5.4"},
        "allowed_api_route_ids": [route_id],
        "deepseek_live_format_check_cli_command": [
            sys.executable,
            "-m",
            "wild_boar_proxy",
            "external-models",
            "live-format-check",
            "--route",
            route_id,
            "--json",
        ],
        "forbidden_stale_route_ids": ["wbp-deepseek-v3"],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _prompt_digest(prompt: str, context: dict[str, object]) -> str:
    packet = hook_entry.build_router_hook_entry_packet(
        prompt_text=prompt,
        runtime_context=context,
        hook_surface_kind=hook_entry.HOOK_SURFACE_USER_PROMPT_SUBMIT,
    )
    return str(packet["prompt_digest"])


def _ledger(prompt: str, context: dict[str, object]) -> dict[str, object]:
    hook_hash = _sha256("wbp-user-prompt-submit-hook-v1")
    return integrated.build_user_prompt_submit_hook_ledger(
        prompt_digest=_prompt_digest(prompt, context),
        runtime_context_digest_value=integrated.runtime_context_digest(context),
        thread_digest=_sha256("custom-codex-thread"),
        turn_digest=_sha256("custom-codex-turn"),
        trusted_hook_config_sha256=hook_hash,
        loaded_hook_config_sha256=hook_hash,
        hook_producer_state="HOOK_RAN_CUSTOM_CODEX_PROVEN",
        hook_event_digest=_sha256("custom-codex-user-prompt-submit-event"),
        session_digest=_sha256("custom-codex-session"),
        cwd_digest=_sha256(str(ROOT)),
        hook_trust_source="codex_non_managed_hook_execution",
    )


def _live_provider_packet(
    *,
    route_id: str = ROUTE_ID,
    expected_text: str = EXPECTED_TEXT,
) -> dict[str, object]:
    return packets.build_command_packet(
        ok=True,
        human_message="External-models route live format check captured one provider response without writing state or evidence.",
        machine_error_code="OK",
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        effect="probe",
        extra={
            "data": {
                "check_kind": "api_only_live_route_format",
                "network_dependent": True,
                "verification_scope": "route_provider_only_no_write",
                "route_state": "live_response_observed_no_write",
                "requested_model": route_id,
                "effective_model": "deepseek-test",
                "provider": "deepseek",
                "fallback_used": False,
                "fallback_chain": [route_id],
                "cost_class": "free_or_limited",
                "latency_ms": 12,
                "request_count": 1,
                "retry_count": 0,
                "parallel_fanout_attempted": False,
                "expected_text": expected_text,
                "expected_text_observed": True,
                "response_preview_bounded": expected_text,
                "response_text_length": len(expected_text),
                "changed_files": [],
                "state_written": False,
                "evidence_written": False,
                "file_mutation_attempted": False,
                "commands_started_by_provider": False,
                "codex_history_sent": False,
                "repo_context_sent": False,
                "request_shape": "openai_chat_messages",
                "response_shape": "choices_message",
            },
            "raw_provider_response_recorded": False,
        },
    )


def _file_metadata() -> dict[str, object]:
    return {
        "integrated_live_provider_proof_file_required": True,
        "integrated_live_provider_proof_file_present": True,
        "integrated_live_provider_proof_file_read": True,
        "integrated_live_provider_proof_file_valid_json": True,
        "integrated_live_provider_proof_file_mapping": True,
        "integrated_live_provider_proof_file_error_code": "",
        "integrated_live_provider_proof_file_path_recorded": False,
        "codex_exec_jsonl_file_required": True,
        "codex_exec_jsonl_file_present": True,
        "codex_exec_jsonl_file_read": True,
        "codex_exec_jsonl_file_valid_jsonl": True,
        "codex_exec_jsonl_file_error_code": "",
        "codex_exec_jsonl_file_path_recorded": False,
        "codex_exec_jsonl_parse_error_count": 0,
        "codex_exec_event_count": 5,
    }


def _integrated_packet(
    *,
    context: dict[str, object] | None = None,
    prompt: str = PROMPT,
    expected_text: str = EXPECTED_TEXT,
) -> dict[str, object]:
    context = _runtime_context() if context is None else context
    source = integrated.build_real_custom_codex_hook_proof_packet(
        prompt_text=prompt,
        runtime_context=context,
        hook_ledger=_ledger(prompt, context),
        context_file_metadata={
            "runtime_context_file_read": True,
            "runtime_context_file_valid_json": True,
            "runtime_context_file_mapping": True,
        },
        hook_ledger_file_metadata={
            "hook_ledger_file_read": True,
            "hook_ledger_file_valid_json": True,
            "hook_ledger_file_mapping": True,
        },
        live_provider_packet=_live_provider_packet(
            route_id=str(context["agent_id_to_route"]["dip"]),
            expected_text=expected_text,
        ),
        live_provider_file_metadata={
            "live_provider_proof_file_read": True,
            "live_provider_proof_file_valid_json": True,
            "live_provider_proof_file_mapping": True,
        },
        live_provider_expected_text=expected_text,
        live_provider_source_kind="file_backed_external_models_live_format_check",
        secret_values=[prompt, ROUTE_ID, RAW_PROVIDER_TEXT, expected_text],
    )
    assert source["status"] == "ok"
    return source


def _delivery_payload(
    *,
    source: dict[str, object],
) -> dict[str, object]:
    return working_flow._safe_working_flow_delivery_payload(source)


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


def _assistant_event(
    digest: str,
    *,
    include_marker: bool = True,
    marker_digest: str | None = None,
    text: str = "WBP working-flow receipt.",
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


def _command_execution_event(
    source: dict[str, object],
    *,
    expected_text: str = EXPECTED_TEXT,
    exit_code: int = 0,
    status: str = "completed",
) -> dict[str, object]:
    provider_packet = _live_provider_packet(expected_text=expected_text)
    return {
        "type": "item.completed",
        "item": {
            "id": "item-live-format-check",
            "type": "command_execution",
            "command": (
                "/bin/zsh -lc "
                + json.dumps(
                    f"{sys.executable} -m wild_boar_proxy external-models "
                    f"live-format-check --route {ROUTE_ID} --json"
                )
            ),
            "aggregated_output": json.dumps(provider_packet),
            "exit_code": exit_code,
            "status": status,
        },
    }


def _codex_wrapped_command_execution_event(source: dict[str, object]) -> dict[str, object]:
    event = _command_execution_event(source)
    original_command = str(event["item"]["command"])
    event["item"]["command"] = "/bin/zsh -c " + json.dumps(original_command)
    return event


def _command_assistant_event(text: str = EXPECTED_TEXT) -> dict[str, object]:
    return {
        "type": "item.completed",
        "item": {
            "id": "item-command-assistant",
            "type": "agent_message",
            "text": text,
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


def _events_for_packet(
    source: dict[str, object],
    *,
    assistant: dict[str, object] | None = None,
    structured_content: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    structured = _delivery_payload(source=source)
    if structured_content is not None:
        structured = structured_content
    else:
        assert structured["handoff_payload_sha256"] != source["handoff_payload_digest"]
    assistant_event = (
        _assistant_event(str(structured["handoff_payload_sha256"]))
        if assistant is None
        else assistant
    )
    return [
        {"type": "thread.started", "thread_id": "thread-working-flow"},
        {"type": "turn.started"},
        _tool_result_event(structured),
        assistant_event,
        {"type": "turn.completed"},
    ]


def _jsonl_from_events(events: list[dict[str, object]]) -> str:
    return "\n".join(json.dumps(event, ensure_ascii=True) for event in events)


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


def _assert_no_secret_or_raw_text(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in (PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT):
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


class CodexWorkingFlowDeliveryProofTests(unittest.TestCase):
    def test_positive_proves_live_provider_delivery_into_digest_bound_codex_flow(self) -> None:
        source = _integrated_packet()
        events = _events_for_packet(source)

        packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            events,
            file_metadata=_file_metadata(),
            secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            working_flow.CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["integrated_live_provider_proof_valid"])
        self.assertTrue(packet["hook_producer_ledger_proven"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["live_provider_response_proven"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertFalse(packet["does_not_prove_live_provider"])
        self.assertTrue(packet["approved_handoff_ready"])
        self.assertTrue(packet["approved_handoff_payload_sanitized"])
        self.assertTrue(packet["handoff_delivered"])
        self.assertTrue(packet["delivery_observed"])
        self.assertNotEqual(
            packet["source_handoff_payload_digest"],
            packet["working_flow_handoff_payload_digest"],
        )
        self.assertEqual(
            packet["handoff_payload_digest"],
            packet["working_flow_handoff_payload_digest"],
        )
        self.assertTrue(packet["live_provider_response_digest"])
        self.assertTrue(packet["controlled_provider_response_digest"])
        self.assertNotEqual(
            packet["live_provider_response_digest"],
            packet["controlled_provider_response_digest"],
        )
        self.assertTrue(packet["live_provider_response_digest_bound_to_handoff"])
        self.assertTrue(packet["controlled_provider_response_digest_bound_to_handoff"])
        self.assertTrue(packet["matching_mcp_tool_result_observed"])
        self.assertTrue(packet["mcp_tool_result_structured_content_present"])
        self.assertTrue(packet["structured_content_matches_handoff"])
        self.assertEqual(
            packet["declared_handoff_payload_digest"],
            packet["handoff_payload_digest"],
        )
        self.assertEqual(
            packet["observed_handoff_payload_digest"],
            packet["handoff_payload_digest"],
        )
        self.assertTrue(packet["assistant_response_observed"])
        self.assertTrue(packet["assistant_response_after_tool_result"])
        self.assertTrue(packet["assistant_machine_marker_observed"])
        self.assertFalse(packet["assistant_marker_digest_mismatch"])
        self.assertTrue(packet["assistant_response_bound_to_handoff_digest"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertEqual(
            packet["working_flow_delivery_truth_source"],
            working_flow.WORKING_FLOW_DELIVERY_TRUTH_SOURCE,
        )
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["transcript_secret_value_present"])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_secret_or_raw_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_positive_proves_command_execution_live_format_delivery_into_codex_flow(self) -> None:
        source = _integrated_packet()
        events = [
            {"type": "thread.started", "thread_id": "thread-command-flow"},
            {"type": "turn.started"},
            _command_execution_event(source),
            _command_assistant_event(),
            {"type": "turn.completed"},
        ]

        packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            events,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["integrated_live_provider_proof_valid"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertEqual(
            packet["working_flow_delivery_surface_kind"],
            working_flow.DELIVERY_SURFACE_CODEX_COMMAND_EXECUTION_LIVE_FORMAT_CHECK,
        )
        self.assertTrue(packet["approved_delivery_surface_proven"])
        self.assertFalse(packet["mcp_delivery_surface_proven"])
        self.assertTrue(packet["command_execution_delivery_surface_proven"])
        self.assertTrue(packet["command_execution_live_format_observed"])
        self.assertTrue(packet["command_execution_live_format_event_index_present"])
        self.assertTrue(packet["command_execution_live_format_cli_command_digest_bound"])
        self.assertTrue(packet["command_execution_live_format_route_digest_bound"])
        self.assertTrue(packet["command_execution_live_format_extra_args_allowed"])
        self.assertTrue(packet["command_execution_live_format_exit_code_zero"])
        self.assertTrue(packet["command_execution_live_format_status_completed"])
        self.assertEqual(packet["command_execution_live_format_packet_status"], "ok")
        self.assertEqual(packet["command_execution_live_format_machine_error_code"], "OK")
        self.assertTrue(packet["command_execution_live_format_route_digest"])
        self.assertEqual(
            packet["command_execution_live_format_response_digest"],
            packet["live_provider_response_digest"],
        )
        self.assertTrue(packet["command_execution_live_format_expected_text_observed"])
        self.assertFalse(packet["command_execution_live_format_fallback_used"])
        self.assertTrue(packet["command_assistant_response_observed"])
        self.assertTrue(packet["command_assistant_response_after_command"])
        self.assertTrue(packet["command_assistant_response_bound_to_live_provider_digest"])
        self.assertEqual(
            packet["command_assistant_binding_digest"],
            packet["live_provider_response_digest"],
        )
        self.assertTrue(packet["live_provider_response_digest_bound_to_delivery"])
        self.assertTrue(packet["controlled_provider_response_digest_bound_to_delivery"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertEqual(packet["transcript_delivery_failures"], [])
        self.assertEqual(packet["assistant_binding_failures"], [])
        self.assertEqual(packet["command_execution_delivery_failures"], [])
        self.assertEqual(packet["command_assistant_binding_failures"], [])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_secret_or_raw_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_positive_accepts_current_codex_shell_c_wrapped_live_format_command(
        self,
    ) -> None:
        source = _integrated_packet()
        events = [
            {"type": "thread.started", "thread_id": "thread-command-flow"},
            {"type": "turn.started"},
            _codex_wrapped_command_execution_event(source),
            _command_assistant_event(),
            {"type": "turn.completed"},
        ]

        packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            events,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["command_execution_delivery_surface_proven"])
        self.assertTrue(packet["command_execution_live_format_cli_command_digest_bound"])
        self.assertTrue(packet["command_execution_live_format_route_digest_bound"])
        self.assertTrue(packet["command_execution_live_format_extra_args_allowed"])
        self.assertTrue(packet["command_assistant_response_bound_to_live_provider_digest"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        _assert_no_product_or_ui_claim(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_command_execution_not_bound_to_server_issued_cli(self) -> None:
        source = _integrated_packet()
        forged_event = _command_execution_event(source)
        forged_event["item"]["command"] = (
            f"/bin/echo external-models live-format-check --route {ROUTE_ID} --json"
        )
        events = [
            {"type": "thread.started", "thread_id": "thread-command-flow"},
            {"type": "turn.started"},
            forged_event,
            _command_assistant_event(),
            {"type": "turn.completed"},
        ]

        packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            events,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["command_execution_delivery_surface_proven"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["command_execution_live_format_cli_command_digest_bound"])
        self.assertIn(
            "live_format_command_execution_not_bound",
            packet["blocking_reasons"],
        )
        _assert_no_product_or_ui_claim(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_command_execution_reordered_or_unwrapped_cli_shape(self) -> None:
        source = _integrated_packet()
        cases = {
            "reordered_json_before_route": (
                "/bin/zsh -lc "
                + json.dumps(
                    f"{sys.executable} -m wild_boar_proxy external-models "
                    f"live-format-check --json --route {ROUTE_ID}"
                )
            ),
            "direct_unwrapped_cli": (
                f"{sys.executable} -m wild_boar_proxy external-models "
                f"live-format-check --route {ROUTE_ID} --json"
            ),
        }
        for name, command in cases.items():
            with self.subTest(name=name):
                event = _command_execution_event(source)
                event["item"]["command"] = command
                packet = working_flow.build_codex_working_flow_delivery_proof_packet(
                    source,
                    [
                        {"type": "thread.started", "thread_id": "thread-command-flow"},
                        {"type": "turn.started"},
                        event,
                        _command_assistant_event(),
                        {"type": "turn.completed"},
                    ],
                    file_metadata=_file_metadata(),
                )

                self.assertEqual(packet["status"], "error")
                self.assertFalse(packet["command_execution_delivery_surface_proven"])
                self.assertFalse(packet["codex_working_flow_delivery_proven"])
                self.assertFalse(
                    packet["command_execution_live_format_cli_command_digest_bound"]
                )
                self.assertIn(
                    "live_format_command_execution_not_bound",
                    packet["blocking_reasons"],
                )
                _assert_no_product_or_ui_claim(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_codex_shell_c_wrapper_with_extra_shell_chain(self) -> None:
        source = _integrated_packet()
        event = _codex_wrapped_command_execution_event(source)
        nested_command = str(event["item"]["command"])
        event["item"]["command"] = "/bin/zsh -c " + json.dumps(
            f"echo unsafe && {nested_command}"
        )

        packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            [
                {"type": "thread.started", "thread_id": "thread-command-flow"},
                {"type": "turn.started"},
                event,
                _command_assistant_event(),
                {"type": "turn.completed"},
            ],
            file_metadata=_file_metadata(),
        )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["command_execution_delivery_surface_proven"])
        self.assertFalse(packet["command_execution_live_format_cli_command_digest_bound"])
        self.assertIn(
            "live_format_command_execution_not_bound",
            packet["blocking_reasons"],
        )
        _assert_no_product_or_ui_claim(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_command_execution_without_bound_assistant_response(self) -> None:
        source = _integrated_packet()
        events = [
            {"type": "thread.started", "thread_id": "thread-command-flow"},
            {"type": "turn.started"},
            _command_execution_event(source),
            _command_assistant_event(text="WRONG_OUTPUT"),
            {"type": "turn.completed"},
        ]

        packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            events,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["command_execution_delivery_surface_proven"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertIn(
            "command_assistant_response_not_bound_to_live_provider_digest",
            packet["blocking_reasons"],
        )
        _assert_no_product_or_ui_claim(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_in_memory_source_without_file_backed_metadata(self) -> None:
        source = _integrated_packet()
        packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            _events_for_packet(source),
            secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            working_flow.CODEX_WORKING_FLOW_INTEGRATED_PROOF_INVALID,
        )
        self.assertIn(
            "integrated_live_provider_proof_file_not_read",
            packet["blocking_reasons"],
        )
        self.assertIn("codex_exec_jsonl_file_not_read", packet["blocking_reasons"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["source_live_provider_response_proven"])
        self.assertTrue(packet["source_external_live_provider_response_proven"])
        self.assertFalse(packet["live_provider_response_proven"])
        self.assertFalse(packet["external_live_provider_response_proven"])
        self.assertTrue(packet["does_not_prove_live_provider"])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_secret_or_raw_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_integrated_proof_without_external_live_provider(self) -> None:
        source = _integrated_packet()
        source["external_live_provider_response_proven"] = False
        packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            _events_for_packet(source),
            file_metadata=_file_metadata(),
            secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            working_flow.CODEX_WORKING_FLOW_INTEGRATED_PROOF_INVALID,
        )
        self.assertIn(
            "external_live_provider_response_not_proven",
            packet["blocking_reasons"],
        )
        self.assertTrue(packet["source_live_provider_response_proven"])
        self.assertFalse(packet["source_external_live_provider_response_proven"])
        self.assertFalse(packet["live_provider_response_proven"])
        self.assertFalse(packet["external_live_provider_response_proven"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_secret_or_raw_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_unbound_or_missing_assistant_marker(self) -> None:
        source = _integrated_packet()
        cases = [
            (
                _assistant_event(str(source["handoff_payload_digest"]), include_marker=False),
                "assistant_response_machine_digest_marker_missing",
            ),
            (
                _assistant_event(
                    str(source["handoff_payload_digest"]),
                    marker_digest="f" * 64,
                ),
                "assistant_response_handoff_digest_mismatch",
            ),
        ]
        for assistant, reason in cases:
            with self.subTest(reason=reason):
                packet = working_flow.build_codex_working_flow_delivery_proof_packet(
                    source,
                    _events_for_packet(source, assistant=assistant),
                    file_metadata=_file_metadata(),
                    secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    working_flow.CODEX_WORKING_FLOW_DELIVERY_NOT_BOUND,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["codex_working_flow_delivery_proven"])
                _assert_no_product_or_ui_claim(self, packet)
                _assert_no_secret_or_raw_text(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_transcript_digest_mismatch_and_unsafe_subagent_claim(self) -> None:
        source = _integrated_packet()
        structured = _delivery_payload(source=source)
        structured["handoff_payload"]["provider_response_digest"] = source[
            "provider_response_digest"
        ]
        structured["handoff_payload_sha256"] = "e" * 64
        structured_mismatch_packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            _events_for_packet(source, structured_content=structured),
            file_metadata=_file_metadata(),
            secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(structured_mismatch_packet["status"], "error")
        self.assertEqual(
            structured_mismatch_packet["machine_error_code"],
            working_flow.CODEX_WORKING_FLOW_TRANSCRIPT_NOT_OBSERVED,
        )
        self.assertIn(
            "matching_mcp_tool_result_not_observed",
            structured_mismatch_packet["blocking_reasons"],
        )
        self.assertIn(
            "structured_content_not_bound_to_integrated_handoff",
            structured_mismatch_packet["blocking_reasons"],
        )
        self.assertFalse(
            structured_mismatch_packet["codex_working_flow_delivery_proven"]
        )
        _assert_no_product_or_ui_claim(self, structured_mismatch_packet)
        _assert_no_secret_or_raw_text(self, structured_mismatch_packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(structured_mismatch_packet),
            [],
        )

        events = _events_for_packet(source)
        events.insert(3, _subagent_event())
        subagent_packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            events,
            file_metadata=_file_metadata(),
            secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(subagent_packet["status"], "error")
        self.assertEqual(
            subagent_packet["machine_error_code"],
            working_flow.CODEX_WORKING_FLOW_PAYLOAD_UNSAFE,
        )
        self.assertIn("native_codex_subagent_used_as_dip", subagent_packet["blocking_reasons"])
        self.assertTrue(subagent_packet["native_codex_subagent_used_as_dip"])
        self.assertTrue(subagent_packet["codex_native_subagent_used_as_dip"])
        self.assertTrue(subagent_packet["local_imitation_used"])
        self.assertFalse(subagent_packet["codex_working_flow_delivery_proven"])
        _assert_no_product_or_ui_claim(self, subagent_packet)
        _assert_no_secret_or_raw_text(self, subagent_packet)
        self.assertEqual(packets.inspect_command_packet_semantics(subagent_packet), [])

    def test_blocks_unsafe_source_or_transcript_secret_claims(self) -> None:
        source = _integrated_packet()
        source["product_ready"] = True
        source_packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            _events_for_packet(source),
            file_metadata=_file_metadata(),
            secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(source_packet["status"], "error")
        self.assertEqual(
            source_packet["machine_error_code"],
            working_flow.CODEX_WORKING_FLOW_INTEGRATED_PROOF_INVALID,
        )
        self.assertIn("product_ready_must_not_be_claimed", source_packet["blocking_reasons"])
        self.assertFalse(source_packet["codex_working_flow_delivery_proven"])
        _assert_no_product_or_ui_claim(self, source_packet)

        source = _integrated_packet()
        events = _events_for_packet(
            source,
            assistant=_assistant_event(
                str(source["handoff_payload_digest"]),
                text=f"Unsafe raw prompt: {PROMPT}",
            ),
        )
        transcript_packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            events,
            file_metadata=_file_metadata(),
            secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(transcript_packet["status"], "error")
        self.assertEqual(
            transcript_packet["machine_error_code"],
            working_flow.CODEX_WORKING_FLOW_PAYLOAD_UNSAFE,
        )
        self.assertIn(
            "secret_value_present_in_codex_exec_transcript",
            transcript_packet["blocking_reasons"],
        )
        self.assertTrue(transcript_packet["transcript_secret_value_present"])
        self.assertFalse(transcript_packet["codex_working_flow_delivery_proven"])
        _assert_no_product_or_ui_claim(self, transcript_packet)
        self.assertEqual(packets.inspect_command_packet_semantics(transcript_packet), [])

    def test_cli_reads_files_and_emits_single_json(self) -> None:
        source = _integrated_packet()
        events = _events_for_packet(source)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "integrated-live-provider.json"
            jsonl_path = root / "codex-exec.jsonl"
            source_path.write_text(json.dumps(source) + "\n", encoding="utf-8")
            jsonl_path.write_text(_jsonl_from_events(events) + "\n", encoding="utf-8")
            sentinel = root / "sentinel.txt"
            sentinel.write_text("unchanged", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "working-flow-delivery-proof",
                    "--integrated-live-provider-proof-file",
                    str(source_path),
                    "--codex-exec-jsonl-file",
                    str(jsonl_path),
                    "--json",
                ],
                cwd=ROOT,
                env=os.environ.copy(),
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
            working_flow.CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
        )
        self.assertTrue(packet["integrated_live_provider_proof_file_read"])
        self.assertFalse(packet["integrated_live_provider_proof_file_path_recorded"])
        self.assertTrue(packet["codex_exec_jsonl_file_read"])
        self.assertFalse(packet["codex_exec_jsonl_file_path_recorded"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        _assert_no_product_or_ui_claim(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_blocks_invalid_jsonl_closed(self) -> None:
        source = _integrated_packet()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "integrated-live-provider.json"
            jsonl_path = root / "codex-exec.jsonl"
            source_path.write_text(json.dumps(source) + "\n", encoding="utf-8")
            jsonl_path.write_text("{not-json}\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "working-flow-delivery-proof",
                    "--integrated-live-provider-proof-file",
                    str(source_path),
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
            working_flow.CODEX_WORKING_FLOW_TRANSCRIPT_NOT_OBSERVED,
        )
        self.assertIn("codex_exec_jsonl_parse_error", packet["blocking_reasons"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        _assert_no_product_or_ui_claim(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])


if __name__ == "__main__":
    unittest.main()
