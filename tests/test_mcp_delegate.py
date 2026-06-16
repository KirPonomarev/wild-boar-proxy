# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
from io import BytesIO
from io import StringIO
import json
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import mcp_delegate
from wild_boar_proxy.core import packets
from wild_boar_proxy.custom_agent_bindings import API_ROUTE_LANE, PRIMARY_CHATGPT_LANE


def _context_payload(
    *,
    route_id: str = "wbp-deepseek-chat",
    allowed_api_route_ids: list[str] | None = None,
    coding_aliases: list[str] | None = None,
) -> dict[str, object]:
    aliases = coding_aliases or ["DIP", "Agent 2"]
    allowed = allowed_api_route_ids if allowed_api_route_ids is not None else [route_id]
    return {
        "schema_version": 1,
        "packet_kind": "codex_custom_native_agent_runtime_context",
        "execution_mode": "chatgpt_plus_api",
        "agent_bindings_status": "ok",
        "primary_aliases": ["Codex", "Agent 1"],
        "coding_aliases": aliases,
        "allowed_api_route_ids": allowed,
        "forbidden_stale_route_ids": ["wbp-deepseek-v3"],
        "agent_bindings": [
            {
                "agent_id": "codex",
                "display_name": "Codex",
                "role": "orchestrator",
                "aliases": ["Codex", "Agent 1"],
                "lane": PRIMARY_CHATGPT_LANE,
                "enabled": True,
                "model_id": "gpt-5.4",
                "allowed_actions": ["plan", "inspect"],
            },
            {
                "agent_id": "dip",
                "display_name": "DIP",
                "role": "coding_agent",
                "aliases": aliases,
                "lane": API_ROUTE_LANE,
                "enabled": True,
                "route_id": route_id,
                "allowed_actions": ["implementation_help"],
            },
        ],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _write_context(profile_dir: Path, payload: dict[str, object]) -> None:
    (profile_dir / "wbp-agent-runtime-context.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _tool_packet(response: dict[str, object]) -> dict[str, object]:
    result = response["result"]
    assert isinstance(result, dict)
    structured = result["structuredContent"]
    assert isinstance(structured, dict)
    text_packet = json.loads(result["content"][0]["text"])
    assert text_packet == structured
    return structured


def _config_probe(*, loaded: bool = True) -> dict[str, object]:
    return {
        "packet_kind": "wbp_codex_mcp_config_probe",
        "config_loaded": loaded,
    }


CODEX_MCP_LIST_OUTPUT = """\
Name  Command  Args                             Env                    Cwd  Status   Auth
wbp   python3  -m wild_boar_proxy.mcp_delegate  WBP_PROFILE_DIR=*****  -    enabled  Unsupported
"""

CODEX_MCP_GET_OUTPUT = """\
wbp
  enabled: true
  transport: stdio
  command: python3
  args: -m wild_boar_proxy.mcp_delegate
  cwd: -
  env: WBP_PROFILE_DIR=*****
  remove: codex mcp remove wbp
"""


PROMPT_TEXT = "Codex, дай задачу DIP: верни короткий план."
PROMPT_DELEGATE_ARGUMENTS = {
    "task": "Codex, дай задачу DIP: верни короткий план.",
    "expected_alias": "DIP",
}
ROUTER_HOOK_PACKET = {
    "hook_observed_prompt": True,
    "hook_can_enforce_router": True,
    "hook_can_route_delegate_to_dip": True,
}


def _direct_mcp_reality_packet(
    config_packet: dict[str, object] | None = None,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as temp_dir:
        profile_dir = Path(temp_dir)
        _write_context(profile_dir, _context_payload())
        initialized = mcp_delegate.handle_jsonrpc_message(
            {
                "jsonrpc": "2.0",
                "id": 21,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            }
        )
        listed = mcp_delegate.handle_jsonrpc_message(
            {"jsonrpc": "2.0", "id": 22, "method": "tools/list"}
        )
        call_request = {
            "jsonrpc": "2.0",
            "id": 23,
            "method": "tools/call",
            "params": {
                "name": "delegate_to_dip",
                "arguments": PROMPT_DELEGATE_ARGUMENTS,
            },
        }
        called = mcp_delegate.handle_jsonrpc_message(
            call_request,
            env={"WBP_PROFILE_DIR": str(profile_dir)},
        )
    return mcp_delegate.build_reality_spike_proof_packet(
        [config_packet or _config_probe(), initialized, listed, call_request, called]
    )


def _live_smoke_packet(
    *,
    context_payload: dict[str, object] | None = None,
    arguments: dict[str, object] | None = None,
    **kwargs: object,
) -> dict[str, object]:
    args = arguments or PROMPT_DELEGATE_ARGUMENTS
    if context_payload is None:
        return mcp_delegate.build_live_route_bound_api_smoke_packet(
            args,
            env={},
            **kwargs,
        )
    with tempfile.TemporaryDirectory() as temp_dir:
        profile_dir = Path(temp_dir)
        _write_context(profile_dir, context_payload)
        return mcp_delegate.build_live_route_bound_api_smoke_packet(
            args,
            env={"WBP_PROFILE_DIR": str(profile_dir)},
            **kwargs,
        )


def _prompt_bound_codex_tool_call_packet(
    *,
    arguments: dict[str, object] | None = None,
    expected_arguments: dict[str, object] | None = None,
    jsonl_events: list[dict[str, object]] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    args = arguments or PROMPT_DELEGATE_ARGUMENTS
    expected = expected_arguments or args
    prompt_packet = mcp_delegate.build_prompt_observation_packet(
        PROMPT_TEXT,
        source="codex_exec_json",
        expected_delegate_arguments=expected,
    )
    events = jsonl_events or [
        {"type": "thread.started", "thread_id": "t1"},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {
                "id": "item_router_1",
                "type": "mcp_tool_call",
                "server_name": "wild-boar-proxy",
                "tool_name": "delegate_to_dip",
                "status": "completed",
                "arguments": args,
            },
        },
        {"type": "turn.completed"},
    ]
    codex_packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events),
        prompt_packet=prompt_packet,
    )
    return prompt_packet, codex_packet


def _router_hook_source_event(
    prompt_packet: dict[str, object],
    **overrides: object,
) -> dict[str, object]:
    event: dict[str, object] = {
        "packet_kind": "wbp_router_hook_source_event",
        "source_wbp_owned": True,
        "source_kind": "wbp_codex_exec_jsonl_observer",
        "effect": "probe",
        "changed_files": [],
        "source_run_sha256": hashlib.sha256(b"codex-exec-run-1").hexdigest(),
        "source_prompt_sha256": prompt_packet["prompt_sha256"],
        "hook_observed_prompt": True,
        "hook_can_enforce_router": True,
        "hook_can_route_delegate_to_dip": True,
        "manual_hook_packet_used": False,
        "synthetic_hook_packet_used": False,
        "prompt_supplied_hook_flags": False,
        "browser_supplied_hook_flags": False,
        "state_written": False,
        "profile_written": False,
        "config_written": False,
        "route_registry_written": False,
        "credential_written": False,
        "runtime_state_written": False,
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "product_ready": False,
        "native_free_chat_router_proven": False,
    }
    event.update(overrides)
    return event


def _router_hook_source_packet(
    prompt_packet: dict[str, object],
    **overrides: object,
) -> dict[str, object]:
    return mcp_delegate.build_router_hook_source_admission_packet(
        prompt_packet=prompt_packet,
        source_event_packet=_router_hook_source_event(prompt_packet, **overrides),
    )


def _delegate_packet(
    *,
    arguments: dict[str, object] | None = None,
    context_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    args = arguments or PROMPT_DELEGATE_ARGUMENTS
    if context_payload is None:
        return mcp_delegate.build_delegate_to_dip_packet(
            args,
            env={},
            mcp_tool_called=True,
        )
    with tempfile.TemporaryDirectory() as temp_dir:
        profile_dir = Path(temp_dir)
        _write_context(profile_dir, context_payload)
        return mcp_delegate.build_delegate_to_dip_packet(
            args,
            env={"WBP_PROFILE_DIR": str(profile_dir)},
            mcp_tool_called=True,
        )


class McpDelegateToDipTests(unittest.TestCase):
    def test_initialize_and_tools_list_expose_delegate_to_dip(self) -> None:
        initialized = mcp_delegate.handle_jsonrpc_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            }
        )
        listed = mcp_delegate.handle_jsonrpc_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        )

        self.assertEqual(initialized["result"]["serverInfo"]["name"], "wild-boar-proxy")
        self.assertIn("delegate_to_dip", initialized["result"]["instructions"])
        tools = listed["result"]["tools"]
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "delegate_to_dip")
        self.assertEqual(tools[0]["inputSchema"]["required"], ["task"])
        self.assertFalse(tools[0]["inputSchema"]["additionalProperties"])

    def test_describe_cli_emits_tool_catalog(self) -> None:
        stdout = StringIO()

        self.assertEqual(mcp_delegate.main(["--describe"], stdout=stdout), 0)

        packet = json.loads(stdout.getvalue())
        self.assertEqual(packet["tools"][0]["name"], "delegate_to_dip")

    def test_delegate_to_dip_call_returns_route_bound_controlled_dispatch_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            _write_context(profile_dir, _context_payload())
            call_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "delegate_to_dip",
                    "arguments": PROMPT_DELEGATE_ARGUMENTS,
                },
            }
            initialized = mcp_delegate.handle_jsonrpc_message(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05"},
                }
            )
            listed = mcp_delegate.handle_jsonrpc_message(
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
            )
            response = mcp_delegate.handle_jsonrpc_message(
                call_request,
                env={"WBP_PROFILE_DIR": str(profile_dir)},
            )

        packet = _tool_packet(response)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["packet_kind"], "wbp_mcp_delegate_to_dip_reality")
        self.assertEqual(packet["result_status"], "with_limits")
        self.assertEqual(
            packet["final_status"],
            "WBP_MCP_DELEGATE_TO_DIP_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(packet["mcp_server_visible"])
        self.assertTrue(packet["delegate_to_dip_tool_listed"])
        self.assertTrue(packet["delegate_to_dip_tool_visible"])
        self.assertTrue(packet["delegate_to_dip_tool_called"])
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["forbidden_stale_route_ids_enforced"])
        self.assertTrue(packet["route_allowed"])
        self.assertEqual(packet["selected_alias"], "DIP")
        self.assertEqual(packet["selected_alias_lane"], API_ROUTE_LANE)
        self.assertNotIn("selected_route_id", packet)
        self.assertNotIn("allowed_api_route_ids", packet)
        self.assertNotIn("wbp-deepseek-chat", json.dumps(packet, sort_keys=True))
        self.assertTrue(packet["selected_api_route_id_present"])
        self.assertEqual(
            packet["selected_api_route_id_sha256"],
            hashlib.sha256(b"wbp-deepseek-chat").hexdigest(),
        )
        self.assertFalse(packet["selected_api_route_id_recorded"])
        self.assertTrue(packet["task_digest_preserved"])
        self.assertTrue(packet["task_sha256"])
        self.assertTrue(packet["tool_call_digest_present"])
        self.assertTrue(packet["tool_call_sha256"])
        self.assertFalse(packet["prompt_text_recorded"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertTrue(packet["api_lane_adapter_called"])
        self.assertTrue(packet["api_lane_dispatch_admitted"])
        self.assertEqual(
            packet["api_lane_adapter_packet_kind"],
            "wbp_api_lane_adapter_admission",
        )
        self.assertEqual(packet["api_lane_adapter_machine_error_code"], "OK")
        self.assertEqual(
            packet["route_bound_dispatch_packet_kind"],
            "wbp_route_bound_controlled_dispatch",
        )
        self.assertEqual(packet["route_bound_dispatch_machine_error_code"], "OK")
        self.assertTrue(packet["route_bound_dispatch_attempted"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["route_bound_request_sent"])
        self.assertTrue(packet["route_bound_request_sha256"])
        self.assertEqual(
            packet["dispatch_truth_source"],
            "server_owned_controlled_provider_no_live_network",
        )
        self.assertTrue(packet["controlled_provider_called"])
        self.assertTrue(packet["controlled_provider_response_digest_present"])
        self.assertTrue(packet["controlled_provider_response_sha256"])
        self.assertTrue(packet["controlled_provider_response_proven"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["api_lane_provider_called"])
        self.assertTrue(packet["provider_response_proven"])
        self.assertFalse(packet["live_provider_response_proven"])
        self.assertFalse(packet["bounded_api_lane_mock_used"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertTrue(packet["does_not_prove_native_free_chat_router"])
        self.assertFalse(packet["does_not_prove_api_lane_provider_dispatch"])
        self.assertTrue(packet["does_not_prove_live_provider_dispatch"])
        self.assertFalse(packet["raw_provider_response_recorded"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(
            packets.inspect_command_packet_semantics(packet),
            [],
        )
        proof = mcp_delegate.build_reality_spike_proof_packet(
            [_config_probe(), initialized, listed, call_request, response]
        )
        self.assertEqual(proof["status"], "ok")
        self.assertEqual(proof["machine_error_code"], "OK")
        self.assertTrue(proof["codex_mcp_config_loaded"])
        self.assertTrue(proof["mcp_server_visible"])
        self.assertTrue(proof["delegate_to_dip_tool_listed"])
        self.assertTrue(proof["delegate_to_dip_tool_visible"])
        self.assertTrue(proof["delegate_to_dip_tool_called"])
        self.assertTrue(proof["alias_context_read"])
        self.assertTrue(proof["allowed_api_route_ids_enforced"])
        self.assertTrue(proof["forbidden_stale_route_ids_enforced"])
        self.assertTrue(proof["task_digest_preserved"])
        self.assertTrue(proof["prompt_digest_available"])
        self.assertTrue(proof["prompt_digest_bound_to_tool_packet"])
        self.assertTrue(proof["call_digest_available"])
        self.assertTrue(proof["call_digest_bound_to_tool_packet"])
        self.assertFalse(proof["bounded_api_lane_mock_used"])
        self.assertTrue(proof["api_lane_adapter_called"])
        self.assertTrue(proof["api_lane_dispatch_admitted"])
        self.assertTrue(proof["route_bound_dispatch_attempted"])
        self.assertTrue(proof["route_bound_dispatch_proven"])
        self.assertTrue(proof["route_bound_request_sent"])
        self.assertTrue(proof["route_bound_request_sha256"])
        self.assertEqual(
            proof["dispatch_truth_source"],
            "server_owned_controlled_provider_no_live_network",
        )
        self.assertTrue(proof["controlled_provider_called"])
        self.assertTrue(proof["controlled_provider_response_digest_present"])
        self.assertTrue(proof["controlled_provider_response_sha256"])
        self.assertTrue(proof["controlled_provider_response_proven"])
        self.assertEqual(
            proof["selected_api_route_id_sha256"],
            hashlib.sha256(b"wbp-deepseek-chat").hexdigest(),
        )
        self.assertNotIn("wbp-deepseek-chat", json.dumps(proof, sort_keys=True))
        self.assertFalse(proof["selected_api_route_id_recorded"])
        self.assertTrue(proof["api_lane_called"])
        self.assertTrue(proof["api_lane_provider_called"])
        self.assertTrue(proof["provider_response_proven"])
        self.assertFalse(proof["live_provider_response_proven"])
        self.assertFalse(proof["fallback_used"])
        self.assertFalse(proof["local_imitation_used"])
        self.assertFalse(proof["product_ready"])
        self.assertFalse(proof["raw_transcript_recorded"])
        self.assertFalse(proof["raw_provider_response_recorded"])
        self.assertEqual(
            packets.inspect_command_packet_semantics(proof),
            [],
        )

    def test_live_route_bound_api_smoke_accepts_fake_transport_contract(self) -> None:
        packet = _live_smoke_packet(context_payload=_context_payload())

        serialized = json.dumps(packet, sort_keys=True)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["packet_kind"], "wbp_live_route_bound_api_smoke")
        self.assertEqual(packet["result_status"], "admitted")
        self.assertTrue(packet["live_smoke_contract_proven"])
        self.assertTrue(packet["controlled_dispatch_evidence_proven"])
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["forbidden_stale_route_ids_enforced"])
        self.assertTrue(packet["route_allowed"])
        self.assertEqual(
            packet["route_bound_dispatch_packet_kind"],
            "wbp_route_bound_controlled_dispatch",
        )
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["route_bound_request_sent"])
        self.assertTrue(packet["route_bound_request_sha256"])
        self.assertTrue(packet["selected_api_route_id_present"])
        self.assertEqual(
            packet["selected_api_route_id_sha256"],
            hashlib.sha256(b"wbp-deepseek-chat").hexdigest(),
        )
        self.assertFalse(packet["selected_api_route_id_recorded"])
        self.assertNotIn("wbp-deepseek-chat", serialized)
        self.assertTrue(packet["live_credential_present"])
        self.assertFalse(packet["live_credential_value_recorded"])
        self.assertTrue(packet["live_transport_available"])
        self.assertEqual(packet["live_transport_kind"], "fake")
        self.assertEqual(
            packet["live_transport_truth_source"],
            "fake_transport_no_external_network",
        )
        self.assertFalse(packet["external_provider_network_used"])
        self.assertTrue(packet["live_provider_smoke_attempted"])
        self.assertTrue(packet["live_smoke_attempted"])
        self.assertTrue(packet["smoke_route_bound"])
        self.assertTrue(packet["fake_transport_called"])
        self.assertTrue(packet["fake_transport_response_digest_present"])
        self.assertTrue(packet["fake_transport_response_sha256"])
        self.assertTrue(packet["fake_transport_response_proven"])
        self.assertFalse(packet["live_provider_called"])
        self.assertFalse(packet["live_provider_route_bound"])
        self.assertTrue(packet["live_request_digest_present"])
        self.assertTrue(packet["live_request_sha256"])
        self.assertFalse(packet["live_response_digest_present"])
        self.assertEqual(packet["live_response_sha256"], "")
        self.assertFalse(packet["live_provider_response_proven"])
        self.assertFalse(packet["external_live_provider_response_proven"])
        self.assertFalse(packet["state_written"])
        self.assertFalse(packet["evidence_written"])
        self.assertFalse(packet["file_mutation_attempted"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["raw_provider_response_recorded"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

        proof = mcp_delegate.build_live_route_bound_api_smoke_proof_packet(packet)
        self.assertEqual(proof["status"], "ok")
        self.assertEqual(proof["machine_error_code"], "OK")
        self.assertEqual(
            proof["packet_kind"],
            "wbp_live_route_bound_api_smoke_proof",
        )
        self.assertTrue(proof["live_smoke_contract_proven"])
        self.assertTrue(proof["live_provider_smoke_attempted"])
        self.assertTrue(proof["live_smoke_attempted"])
        self.assertTrue(proof["smoke_route_bound"])
        self.assertTrue(proof["fake_transport_response_proven"])
        self.assertFalse(proof["live_provider_called"])
        self.assertFalse(proof["live_provider_route_bound"])
        self.assertFalse(proof["live_provider_response_proven"])
        self.assertFalse(proof["external_provider_network_used"])
        self.assertFalse(proof["product_ready"])
        self.assertFalse(proof["native_free_chat_router_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(proof), [])

    def test_delegate_to_dip_remains_no_live_smoke_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            _write_context(profile_dir, _context_payload())
            packet = mcp_delegate.build_delegate_to_dip_packet(
                PROMPT_DELEGATE_ARGUMENTS,
                env={"WBP_PROFILE_DIR": str(profile_dir)},
                mcp_tool_called=True,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["live_provider_response_proven"])
        self.assertNotIn("live_provider_smoke_attempted", packet)
        self.assertNotIn("live_request_sha256", packet)
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_live_route_bound_api_smoke_blocks_context_and_route_failures(self) -> None:
        outside_allowlist = _context_payload(
            route_id="wbp-deepseek-chat",
            allowed_api_route_ids=["wbp-other-route"],
        )
        missing_route = _context_payload(route_id="", allowed_api_route_ids=[])
        missing_stale_guard = _context_payload()
        missing_stale_guard["forbidden_stale_route_ids"] = []
        cases = [
            (None, "FAIL_ALIAS_CONTEXT_MISSING", "FAIL_ALIAS_CONTEXT_MISSING"),
            (
                outside_allowlist,
                "WBP_LIVE_ROUTE_BOUND_API_SMOKE_NOT_PROVEN",
                "coding_route_not_allowed",
            ),
            (
                missing_route,
                "WBP_LIVE_ROUTE_BOUND_API_SMOKE_NOT_PROVEN",
                "coding_route_id_missing",
            ),
            (
                missing_stale_guard,
                "WBP_LIVE_ROUTE_BOUND_API_SMOKE_NOT_PROVEN",
                "stale_route_guard_missing",
            ),
        ]
        for payload, machine_code, expected_reason in cases:
            with self.subTest(expected_reason=expected_reason):
                packet = _live_smoke_packet(context_payload=payload)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_code)
                self.assertIn(expected_reason, packet["blocking_reasons"])
                self.assertFalse(packet["controlled_dispatch_evidence_proven"])
                self.assertFalse(packet["live_provider_smoke_attempted"])
                self.assertFalse(packet["live_provider_response_proven"])
                self.assertFalse(packet["fallback_used"])
                self.assertFalse(packet["local_imitation_used"])
                self.assertFalse(packet["product_ready"])
                self.assertFalse(packet["raw_provider_response_recorded"])
                self.assertFalse(packet["secret_value_exposed"])
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_live_route_bound_api_smoke_blocks_provider_failures_without_leak(self) -> None:
        cases = [
            (
                {"live_credential_present": False},
                "WBP_LIVE_PROVIDER_CREDENTIAL_MISSING",
                "live_provider_credential_missing",
                False,
            ),
            (
                {"live_transport_available": False},
                "WBP_LIVE_PROVIDER_TRANSPORT_UNAVAILABLE",
                "live_provider_transport_unavailable",
                False,
            ),
            (
                {"live_provider_error_code": "fixture-secret-upstream-error"},
                "WBP_LIVE_PROVIDER_ERROR",
                "live_provider_error",
                True,
            ),
        ]
        for kwargs, machine_code, expected_reason, attempted in cases:
            with self.subTest(expected_reason=expected_reason):
                packet = _live_smoke_packet(
                    context_payload=_context_payload(),
                    **kwargs,
                )
                serialized = json.dumps(packet, sort_keys=True)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_code)
                self.assertIn(expected_reason, packet["blocking_reasons"])
                self.assertTrue(packet["controlled_dispatch_evidence_proven"])
                self.assertEqual(packet["live_provider_smoke_attempted"], attempted)
                self.assertFalse(packet["live_provider_response_proven"])
                self.assertFalse(packet["live_response_digest_present"])
                self.assertFalse(packet["fallback_used"])
                self.assertFalse(packet["local_imitation_used"])
                self.assertFalse(packet["raw_provider_response_recorded"])
                self.assertFalse(packet["secret_value_exposed"])
                self.assertNotIn("fixture-secret-upstream-error", serialized)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_live_route_bound_api_smoke_rejects_browser_authority_fields(self) -> None:
        packet = _live_smoke_packet(
            context_payload=_context_payload(),
            arguments={
                "task": "DIP: implement this",
                "expected_alias": "DIP",
                "route_id": "evil-route-id",
                "backend": "https://evil.invalid",
                "secret": "secret-from-browser",
                "model": "evil-model",
            },
        )

        serialized = json.dumps(packet, sort_keys=True)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "WBP_LIVE_ROUTE_BROWSER_AUTHORITY_REJECTED",
        )
        self.assertIn("forbidden_field:route_id", packet["blocking_reasons"])
        self.assertIn("forbidden_field:backend", packet["blocking_reasons"])
        self.assertIn("forbidden_field:secret", packet["blocking_reasons"])
        self.assertIn("forbidden_field:model", packet["blocking_reasons"])
        self.assertFalse(packet["controlled_dispatch_evidence_proven"])
        self.assertFalse(packet["live_provider_smoke_attempted"])
        self.assertFalse(packet["live_provider_response_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertNotIn("evil-route-id", serialized)
        self.assertNotIn("https://evil.invalid", serialized)
        self.assertNotIn("secret-from-browser", serialized)
        self.assertNotIn("evil-model", serialized)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_live_route_bound_api_smoke_requires_controlled_dispatch_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            _write_context(profile_dir, _context_payload())
            delegate_packet = mcp_delegate.build_delegate_to_dip_packet(
                PROMPT_DELEGATE_ARGUMENTS,
                env={"WBP_PROFILE_DIR": str(profile_dir)},
                mcp_tool_called=True,
            )
        mutated_packet = dict(delegate_packet)
        mutated_packet["route_bound_dispatch_proven"] = False

        packet = mcp_delegate.build_live_route_bound_api_smoke_packet(
            PROMPT_DELEGATE_ARGUMENTS,
            env={},
            route_bound_dispatch_evidence_packet=mutated_packet,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "WBP_LIVE_ROUTE_BOUND_API_SMOKE_NOT_PROVEN",
        )
        self.assertIn("route_bound_dispatch_not_proven", packet["blocking_reasons"])
        self.assertFalse(packet["controlled_dispatch_evidence_proven"])
        self.assertFalse(packet["live_provider_smoke_attempted"])
        self.assertFalse(packet["live_provider_response_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_live_smoke_proof_rejects_claim_without_digest_or_route_bound_evidence(self) -> None:
        packet = _live_smoke_packet(context_payload=_context_payload())
        mutated_packet = dict(packet)
        mutated_packet["smoke_route_bound"] = False
        mutated_packet["fake_transport_response_digest_present"] = False
        mutated_packet["fake_transport_response_sha256"] = ""
        mutated_packet["live_provider_response_proven"] = True

        proof = mcp_delegate.build_live_route_bound_api_smoke_proof_packet(mutated_packet)

        self.assertEqual(proof["status"], "error")
        self.assertIn("smoke_not_route_bound", proof["blocking_reasons"])
        self.assertIn(
            "fake_transport_response_digest_missing",
            proof["blocking_reasons"],
        )
        self.assertIn(
            "fake_transport_response_digest_invalid",
            proof["blocking_reasons"],
        )
        self.assertIn(
            "live_provider_response_must_not_be_claimed",
            proof["blocking_reasons"],
        )
        self.assertTrue(proof["live_provider_response_proven"])
        self.assertFalse(proof["smoke_route_bound"])
        self.assertFalse(proof["product_ready"])
        self.assertEqual(packets.inspect_command_packet_semantics(proof), [])

    def test_reality_spike_rejects_live_provider_response_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            _write_context(profile_dir, _context_payload())
            call_request = {
                "jsonrpc": "2.0",
                "id": 31,
                "method": "tools/call",
                "params": {
                    "name": "delegate_to_dip",
                    "arguments": PROMPT_DELEGATE_ARGUMENTS,
                },
            }
            initialized = mcp_delegate.handle_jsonrpc_message(
                {
                    "jsonrpc": "2.0",
                    "id": 29,
                    "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05"},
                }
            )
            listed = mcp_delegate.handle_jsonrpc_message(
                {"jsonrpc": "2.0", "id": 30, "method": "tools/list"}
            )
            response = mcp_delegate.handle_jsonrpc_message(
                call_request,
                env={"WBP_PROFILE_DIR": str(profile_dir)},
            )

        assert response is not None
        structured = dict(response["result"]["structuredContent"])
        structured["live_provider_response_proven"] = True
        response["result"]["structuredContent"] = structured
        response["result"]["content"][0]["text"] = json.dumps(structured, sort_keys=True)

        proof = mcp_delegate.build_reality_spike_proof_packet(
            [_config_probe(), initialized, listed, call_request, response]
        )

        self.assertEqual(proof["status"], "error")
        self.assertIn(
            "live_provider_response_must_not_be_claimed",
            proof["blocking_reasons"],
        )
        self.assertFalse(proof["product_ready"])
        self.assertTrue(proof["provider_response_proven"])
        self.assertTrue(proof["live_provider_response_proven"])
        self.assertEqual(
            packets.inspect_command_packet_semantics(proof),
            [],
        )

    def test_reality_spike_rejects_mutated_controlled_dispatch_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            _write_context(profile_dir, _context_payload())
            call_request = {
                "jsonrpc": "2.0",
                "id": 41,
                "method": "tools/call",
                "params": {
                    "name": "delegate_to_dip",
                    "arguments": PROMPT_DELEGATE_ARGUMENTS,
                },
            }
            initialized = mcp_delegate.handle_jsonrpc_message(
                {
                    "jsonrpc": "2.0",
                    "id": 39,
                    "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05"},
                }
            )
            listed = mcp_delegate.handle_jsonrpc_message(
                {"jsonrpc": "2.0", "id": 40, "method": "tools/list"}
            )
            response = mcp_delegate.handle_jsonrpc_message(
                call_request,
                env={"WBP_PROFILE_DIR": str(profile_dir)},
            )

        assert response is not None
        mutations = [
            (
                "route_bound_dispatch_packet_kind",
                "wrong_packet_kind",
                "route_bound_dispatch_packet_kind_invalid",
            ),
            (
                "dispatch_truth_source",
                "not_the_controlled_truth_source",
                "dispatch_truth_source_invalid",
            ),
            ("route_bound_request_sent", False, "route_bound_request_not_sent"),
            ("route_bound_request_sha256", "", "route_bound_request_digest_missing"),
            ("controlled_provider_called", False, "controlled_provider_not_called"),
            (
                "controlled_provider_response_digest_present",
                False,
                "controlled_provider_response_digest_missing",
            ),
            (
                "controlled_provider_response_sha256",
                "",
                "controlled_provider_response_digest_invalid",
            ),
        ]
        for field, value, expected_reason in mutations:
            with self.subTest(field=field):
                mutated_response = json.loads(json.dumps(response))
                structured = dict(mutated_response["result"]["structuredContent"])
                structured[field] = value
                mutated_response["result"]["structuredContent"] = structured
                mutated_response["result"]["content"][0]["text"] = json.dumps(
                    structured,
                    sort_keys=True,
                )

                proof = mcp_delegate.build_reality_spike_proof_packet(
                    [_config_probe(), initialized, listed, call_request, mutated_response]
                )

                self.assertEqual(proof["status"], "error")
                self.assertIn(expected_reason, proof["blocking_reasons"])
                self.assertFalse(proof["product_ready"])
                self.assertEqual(
                    packets.inspect_command_packet_semantics(proof),
                    [],
                )

    def test_missing_runtime_context_fails_closed_with_alias_context_code(self) -> None:
        packet = mcp_delegate.build_delegate_to_dip_packet(
            {"task": "DIP: inspect this"},
            env={},
            mcp_tool_called=True,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "FAIL_ALIAS_CONTEXT_MISSING")
        self.assertFalse(packet["alias_context_read"])
        self.assertTrue(packet["delegate_to_dip_tool_called"])
        self.assertIn("FAIL_ALIAS_CONTEXT_MISSING", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["bounded_api_lane_mock_used"])
        self.assertFalse(packet["api_lane_adapter_called"])
        self.assertFalse(packet["route_bound_dispatch_attempted"])
        self.assertFalse(packet["route_bound_dispatch_proven"])

    def test_route_outside_runtime_allowlist_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            _write_context(
                profile_dir,
                _context_payload(
                    route_id="wbp-deepseek-chat",
                    allowed_api_route_ids=["wbp-other-route"],
                ),
            )
            packet = mcp_delegate.build_delegate_to_dip_packet(
                {"task": "DIP: implement this", "expected_alias": "DIP"},
                env={"WBP_PROFILE_DIR": str(profile_dir)},
                mcp_tool_called=True,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WBP_MCP_DELEGATE_TO_DIP_NOT_PROVEN")
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertFalse(packet["route_allowed"])
        self.assertNotIn("selected_route_id", packet)
        self.assertNotIn("allowed_api_route_ids", packet)
        self.assertNotIn("wbp-deepseek-chat", json.dumps(packet, sort_keys=True))
        self.assertTrue(packet["selected_api_route_id_present"])
        self.assertEqual(
            packet["selected_api_route_id_sha256"],
            hashlib.sha256(b"wbp-deepseek-chat").hexdigest(),
        )
        self.assertFalse(packet["selected_api_route_id_recorded"])
        self.assertFalse(packet["api_lane_adapter_called"])
        self.assertFalse(packet["api_lane_dispatch_admitted"])
        self.assertFalse(packet["route_bound_dispatch_attempted"])
        self.assertFalse(packet["route_bound_dispatch_proven"])
        self.assertIn("coding_route_not_allowed", packet["blocking_reasons"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])

    def test_primary_chatgpt_alias_is_rejected_before_api_lane_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            _write_context(profile_dir, _context_payload())
            packet = mcp_delegate.build_delegate_to_dip_packet(
                {"task": "Codex: inspect this", "expected_alias": "Codex"},
                env={"WBP_PROFILE_DIR": str(profile_dir)},
                mcp_tool_called=True,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "WBP_MCP_DELEGATE_TO_DIP_NOT_PROVEN",
        )
        self.assertEqual(packet["selected_alias"], "Codex")
        self.assertEqual(packet["selected_alias_lane"], PRIMARY_CHATGPT_LANE)
        self.assertFalse(packet["coding_alias_bound_to_api_lane"])
        self.assertFalse(packet["api_lane_adapter_called"])
        self.assertFalse(packet["api_lane_dispatch_admitted"])
        self.assertFalse(packet["route_bound_dispatch_attempted"])
        self.assertFalse(packet["route_bound_dispatch_proven"])
        self.assertIn("coding_alias_binding_invalid", packet["blocking_reasons"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])

    def test_missing_api_route_id_is_rejected_before_api_lane_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            context = _context_payload(route_id="", allowed_api_route_ids=[])
            _write_context(profile_dir, context)
            packet = mcp_delegate.build_delegate_to_dip_packet(
                {"task": "DIP: implement this", "expected_alias": "DIP"},
                env={"WBP_PROFILE_DIR": str(profile_dir)},
                mcp_tool_called=True,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "WBP_MCP_DELEGATE_TO_DIP_NOT_PROVEN",
        )
        self.assertEqual(packet["selected_alias"], "DIP")
        self.assertEqual(packet["selected_alias_lane"], API_ROUTE_LANE)
        self.assertFalse(packet["selected_api_route_id_present"])
        self.assertEqual(packet["selected_api_route_id_sha256"], "")
        self.assertFalse(packet["selected_api_route_id_recorded"])
        self.assertFalse(packet["api_lane_adapter_called"])
        self.assertFalse(packet["api_lane_dispatch_admitted"])
        self.assertFalse(packet["route_bound_dispatch_attempted"])
        self.assertFalse(packet["route_bound_dispatch_proven"])
        self.assertIn("coding_route_id_missing", packet["blocking_reasons"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])

    def test_api_lane_adapter_unavailable_rejects_without_local_imitation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            _write_context(profile_dir, _context_payload())
            packet = mcp_delegate.build_delegate_to_dip_packet(
                {"task": "DIP: implement this", "expected_alias": "DIP"},
                env={"WBP_PROFILE_DIR": str(profile_dir)},
                mcp_tool_called=True,
                api_lane_adapter_available=False,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WBP_API_LANE_ADAPTER_NOT_AVAILABLE")
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["route_allowed"])
        self.assertTrue(packet["api_lane_adapter_called"])
        self.assertFalse(packet["api_lane_dispatch_admitted"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["route_bound_dispatch_attempted"])
        self.assertFalse(packet["route_bound_dispatch_proven"])
        self.assertFalse(packet["api_lane_provider_called"])
        self.assertFalse(packet["provider_response_proven"])
        self.assertFalse(packet["live_provider_response_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertIn("api_lane_adapter_unavailable", packet["blocking_reasons"])

    def test_controlled_provider_unavailable_rejects_without_local_imitation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            _write_context(profile_dir, _context_payload())
            packet = mcp_delegate.build_delegate_to_dip_packet(
                {"task": "DIP: implement this", "expected_alias": "DIP"},
                env={"WBP_PROFILE_DIR": str(profile_dir)},
                mcp_tool_called=True,
                controlled_provider_available=False,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WBP_CONTROLLED_PROVIDER_UNAVAILABLE")
        self.assertTrue(packet["api_lane_adapter_called"])
        self.assertTrue(packet["api_lane_dispatch_admitted"])
        self.assertTrue(packet["route_bound_dispatch_attempted"])
        self.assertFalse(packet["route_bound_dispatch_proven"])
        self.assertFalse(packet["route_bound_request_sent"])
        self.assertFalse(packet["controlled_provider_called"])
        self.assertFalse(packet["controlled_provider_response_proven"])
        self.assertFalse(packet["api_lane_provider_called"])
        self.assertFalse(packet["provider_response_proven"])
        self.assertFalse(packet["live_provider_response_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertIn("controlled_provider_unavailable", packet["blocking_reasons"])
        self.assertEqual(
            packets.inspect_command_packet_semantics(packet),
            [],
        )

    def test_controlled_provider_error_rejects_without_raw_error_or_imitation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            _write_context(profile_dir, _context_payload())
            packet = mcp_delegate.build_delegate_to_dip_packet(
                {"task": "DIP: implement this", "expected_alias": "DIP"},
                env={"WBP_PROFILE_DIR": str(profile_dir)},
                mcp_tool_called=True,
                controlled_provider_error_code="fixture-secret-upstream-error",
            )

        serialized = json.dumps(packet, sort_keys=True)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WBP_CONTROLLED_PROVIDER_ERROR")
        self.assertTrue(packet["api_lane_adapter_called"])
        self.assertTrue(packet["api_lane_dispatch_admitted"])
        self.assertTrue(packet["route_bound_dispatch_attempted"])
        self.assertFalse(packet["route_bound_dispatch_proven"])
        self.assertFalse(packet["route_bound_request_sent"])
        self.assertTrue(packet["controlled_provider_called"])
        self.assertTrue(packet["controlled_provider_error_observed"])
        self.assertTrue(packet["controlled_provider_error_code_recorded"])
        self.assertFalse(packet["controlled_provider_response_proven"])
        self.assertFalse(packet["provider_response_proven"])
        self.assertFalse(packet["live_provider_response_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertIn("controlled_provider_error", packet["blocking_reasons"])
        self.assertNotIn("fixture-secret-upstream-error", serialized)
        self.assertEqual(
            packets.inspect_command_packet_semantics(packet),
            [],
        )

    def test_browser_supplied_route_backend_or_secret_fields_reject_before_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            _write_context(profile_dir, _context_payload())
            packet = mcp_delegate.build_delegate_to_dip_packet(
                {
                    "task": "DIP: implement this",
                    "expected_alias": "DIP",
                    "route_id": "evil-route-id",
                    "backend": "https://evil.invalid",
                    "secret": "secret-from-browser",
                },
                env={"WBP_PROFILE_DIR": str(profile_dir)},
                mcp_tool_called=True,
            )

        serialized = json.dumps(packet, sort_keys=True)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "WBP_MCP_DELEGATE_BROWSER_AUTHORITY_REJECTED",
        )
        self.assertFalse(packet["api_lane_adapter_called"])
        self.assertFalse(packet["api_lane_dispatch_admitted"])
        self.assertFalse(packet["route_bound_dispatch_attempted"])
        self.assertFalse(packet["route_bound_dispatch_proven"])
        self.assertFalse(packet["provider_response_proven"])
        self.assertFalse(packet["live_provider_response_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertIn("forbidden_field:route_id", packet["blocking_reasons"])
        self.assertIn("forbidden_field:backend", packet["blocking_reasons"])
        self.assertIn("forbidden_field:secret", packet["blocking_reasons"])
        self.assertNotIn("evil-route-id", serialized)
        self.assertNotIn("https://evil.invalid", serialized)
        self.assertNotIn("secret-from-browser", serialized)
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertEqual(
            packets.inspect_command_packet_semantics(packet),
            [],
        )

    def test_missing_stale_route_guard_blocks_delegate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            context = _context_payload()
            context["forbidden_stale_route_ids"] = []
            _write_context(profile_dir, context)
            packet = mcp_delegate.build_delegate_to_dip_packet(
                {"task": "DIP: implement this", "expected_alias": "DIP"},
                env={"WBP_PROFILE_DIR": str(profile_dir)},
                mcp_tool_called=True,
            )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["route_allowed"])
        self.assertFalse(packet["forbidden_stale_route_ids_enforced"])
        self.assertFalse(packet["api_lane_adapter_called"])
        self.assertFalse(packet["route_bound_dispatch_attempted"])
        self.assertFalse(packet["route_bound_dispatch_proven"])
        self.assertIn("stale_route_guard_missing", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])

    def test_malformed_agent_bindings_block_without_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            context = _context_payload()
            context["agent_bindings"] = ["not-an-object"]
            _write_context(profile_dir, context)
            packet = mcp_delegate.build_delegate_to_dip_packet(
                {"task": "DIP: implement this", "expected_alias": "DIP"},
                env={"WBP_PROFILE_DIR": str(profile_dir)},
                mcp_tool_called=True,
            )

        self.assertEqual(packet["status"], "error")
        self.assertIn("coding_alias_binding_invalid", packet["blocking_reasons"])
        self.assertFalse(packet["coding_alias_bound_to_api_lane"])
        self.assertFalse(packet["product_ready"])

    def test_without_real_mcp_tool_call_cannot_turn_green(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            _write_context(profile_dir, _context_payload(coding_aliases=["DIP"]))
            packet = mcp_delegate.build_delegate_to_dip_packet(
                {"task": "DIP: inspect this"},
                env={"WBP_PROFILE_DIR": str(profile_dir)},
                mcp_tool_called=False,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WBP_MCP_DELEGATE_TO_DIP_NOT_PROVEN")
        self.assertFalse(packet["delegate_to_dip_tool_called"])
        self.assertIn("mcp_tool_call_not_observed", packet["blocking_reasons"])
        self.assertFalse(packet["bounded_api_lane_mock_used"])
        self.assertFalse(packet["route_bound_dispatch_attempted"])
        self.assertFalse(packet["route_bound_dispatch_proven"])
        self.assertFalse(packet["product_ready"])

    def test_content_length_stdio_roundtrip_handles_tools_list(self) -> None:
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/list",
        }
        body = json.dumps(request).encode("utf-8")
        stdin = BytesIO(
            b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body
        )
        stdout = BytesIO()

        self.assertEqual(
            mcp_delegate.run_stdio(stdin=stdin, stdout=stdout, env={}),
            0,
        )
        raw = stdout.getvalue()
        self.assertTrue(raw.startswith(b"Content-Length: "))
        response_body = raw.split(b"\r\n\r\n", 1)[1]
        response = json.loads(response_body.decode("utf-8"))
        self.assertEqual(response["id"], 4)
        self.assertEqual(response["result"]["tools"][0]["name"], "delegate_to_dip")

    def test_reality_spike_summary_blocks_without_tools_list_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            _write_context(profile_dir, _context_payload())
            call_request = {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "delegate_to_dip",
                    "arguments": {"task": "DIP: inspect this"},
                },
            }
            called = mcp_delegate.handle_jsonrpc_message(
                call_request,
                env={"WBP_PROFILE_DIR": str(profile_dir)},
            )

        proof = mcp_delegate.build_reality_spike_proof_packet(
            [_config_probe(), call_request, called]
        )
        self.assertEqual(proof["status"], "error")
        self.assertIn("mcp_server_not_visible", proof["blocking_reasons"])
        self.assertIn("delegate_to_dip_tool_not_listed", proof["blocking_reasons"])
        self.assertTrue(proof["delegate_to_dip_tool_called"])
        self.assertFalse(proof["product_ready"])

    def test_reality_spike_summary_blocks_without_config_loaded_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            _write_context(profile_dir, _context_payload())
            initialized = mcp_delegate.handle_jsonrpc_message(
                {
                    "jsonrpc": "2.0",
                    "id": 11,
                    "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05"},
                }
            )
            listed = mcp_delegate.handle_jsonrpc_message(
                {"jsonrpc": "2.0", "id": 12, "method": "tools/list"}
            )
            call_request = {
                "jsonrpc": "2.0",
                "id": 13,
                "method": "tools/call",
                "params": {
                    "name": "delegate_to_dip",
                    "arguments": {"task": "DIP: inspect this", "expected_alias": "DIP"},
                },
            }
            called = mcp_delegate.handle_jsonrpc_message(
                call_request,
                env={"WBP_PROFILE_DIR": str(profile_dir)},
            )

        proof = mcp_delegate.build_reality_spike_proof_packet(
            [initialized, listed, call_request, called]
        )
        self.assertEqual(proof["status"], "error")
        self.assertFalse(proof["codex_mcp_config_loaded"])
        self.assertIn("codex_mcp_config_not_loaded", proof["blocking_reasons"])
        self.assertFalse(proof["product_ready"])

    def test_codex_mcp_config_probe_parses_temp_codex_registration(self) -> None:
        packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["packet_kind"], "wbp_codex_mcp_config_probe")
        self.assertEqual(packet["result_status"], "loaded")
        self.assertTrue(packet["config_loaded"])
        self.assertTrue(packet["codex_mcp_config_loaded"])
        self.assertEqual(packet["codex_mcp_server_name"], "wbp")
        self.assertTrue(packet["codex_mcp_server_enabled"])
        self.assertTrue(packet["codex_mcp_command_present"])
        self.assertEqual(packet["codex_mcp_command"], "python3")
        self.assertTrue(packet["codex_mcp_args_match"])
        self.assertTrue(packet["codex_mcp_env_redacted"])
        self.assertFalse(packet["codex_mcp_original_profile_touched"])
        self.assertFalse(packet["original_profile_touched"])
        self.assertFalse(packet["raw_config_stdout_recorded"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertEqual(
            packets.inspect_command_packet_semantics(packet),
            [],
        )

    def test_codex_mcp_config_probe_blocks_global_config_error(self) -> None:
        packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            "failed to load configuration\nunknown variant default",
            "",
            list_exit_code=1,
            get_exit_code=1,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["result_status"], "blocked")
        self.assertFalse(packet["config_loaded"])
        self.assertTrue(packet["global_config_error_observed"])
        self.assertIn("codex_global_config_error_observed", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(
            packets.inspect_command_packet_semantics(packet),
            [],
        )

    def test_router_hook_source_admission_accepts_wbp_owned_probe(self) -> None:
        prompt_packet, _codex_packet = _prompt_bound_codex_tool_call_packet()

        packet = _router_hook_source_packet(prompt_packet)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["packet_kind"], "wbp_router_hook_source_admission")
        self.assertEqual(packet["result_status"], "admitted")
        self.assertEqual(packet["source_status"], "ok")
        self.assertTrue(packet["source_wbp_owned"])
        self.assertEqual(packet["source_effect"], "probe")
        self.assertTrue(packet["source_run_digest_present"])
        self.assertTrue(packet["source_prompt_digest_present"])
        self.assertTrue(packet["source_prompt_digest_bound"])
        self.assertTrue(packet["hook_observed_prompt"])
        self.assertTrue(packet["hook_can_enforce_router"])
        self.assertTrue(packet["hook_can_route_delegate_to_dip"])
        self.assertFalse(packet["manual_hook_packet_used"])
        self.assertFalse(packet["synthetic_hook_packet_used"])
        self.assertFalse(packet["prompt_supplied_hook_flags"])
        self.assertFalse(packet["browser_supplied_hook_flags"])
        self.assertFalse(packet["write_side_effect_observed"])
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(packet["effect"], "probe")
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["raw_route_id_recorded"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_source_admission_rejects_manual_and_authority_sources(self) -> None:
        prompt_packet, _codex_packet = _prompt_bound_codex_tool_call_packet()
        cases = [
            (
                "manual",
                {"manual_hook_packet_used": True},
                "manual_hook_packet_not_admitted",
                "WBP_ROUTER_HOOK_SOURCE_NOT_ADMITTED",
            ),
            (
                "synthetic",
                {"synthetic_hook_packet_used": True},
                "synthetic_hook_packet_not_admitted",
                "WBP_ROUTER_HOOK_SOURCE_NOT_ADMITTED",
            ),
            (
                "prompt_flags",
                {"prompt_supplied_hook_flags": True},
                "prompt_supplied_hook_flags",
                "WBP_ROUTER_HOOK_SOURCE_AUTHORITY_REJECTED",
            ),
            (
                "browser_flags",
                {"browser_supplied_hook_flags": True},
                "browser_supplied_hook_flags",
                "WBP_ROUTER_HOOK_SOURCE_AUTHORITY_REJECTED",
            ),
        ]

        for name, overrides, reason, error_code in cases:
            with self.subTest(name=name):
                packet = _router_hook_source_packet(prompt_packet, **overrides)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], error_code)
                self.assertEqual(packet["result_status"], "blocked")
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["product_ready"])
                self.assertFalse(packet["native_free_chat_router_proven"])
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_source_admission_rejects_digest_and_side_effect_drift(self) -> None:
        prompt_packet, _codex_packet = _prompt_bound_codex_tool_call_packet()
        cases = [
            (
                "missing_run_digest",
                {"source_run_sha256": ""},
                "router_hook_source_run_digest_missing",
                "WBP_ROUTER_HOOK_SOURCE_DIGEST_NOT_BOUND",
            ),
            (
                "prompt_digest_mismatch",
                {"source_prompt_sha256": hashlib.sha256(b"wrong").hexdigest()},
                "router_hook_source_prompt_digest_not_bound",
                "WBP_ROUTER_HOOK_SOURCE_DIGEST_NOT_BOUND",
            ),
            (
                "profile_write",
                {"profile_written": True},
                "router_hook_source_write_side_effect",
                "WBP_ROUTER_HOOK_SOURCE_SIDE_EFFECT_REJECTED",
            ),
            (
                "changed_files",
                {"changed_files": ["config.toml"]},
                "router_hook_source_write_side_effect",
                "WBP_ROUTER_HOOK_SOURCE_SIDE_EFFECT_REJECTED",
            ),
        ]

        for name, overrides, reason, error_code in cases:
            with self.subTest(name=name):
                packet = _router_hook_source_packet(prompt_packet, **overrides)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], error_code)
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["product_ready"])
                self.assertFalse(packet["native_free_chat_router_proven"])
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_source_admission_rejects_logging_only_source(self) -> None:
        prompt_packet, _codex_packet = _prompt_bound_codex_tool_call_packet()

        packet = _router_hook_source_packet(
            prompt_packet,
            hook_can_enforce_router=False,
            hook_can_route_delegate_to_dip=False,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "WBP_ROUTER_HOOK_SOURCE_NOT_ADMITTED",
        )
        self.assertTrue(packet["hook_observed_prompt"])
        self.assertFalse(packet["hook_can_enforce_router"])
        self.assertFalse(packet["hook_can_route_delegate_to_dip"])
        self.assertTrue(packet["hook_logging_only"])
        self.assertIn("router_hook_source_logging_only", packet["blocking_reasons"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_native_router_hook_observation_accepts_prompt_bound_wbp_tool_call(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        prompt_packet, codex_packet = _prompt_bound_codex_tool_call_packet()
        hook_source_packet = _router_hook_source_packet(prompt_packet)
        delegate_packet = _delegate_packet(context_payload=_context_payload())

        packet = mcp_delegate.build_native_router_hook_observation_packet(
            config_packet=config_packet,
            prompt_packet=prompt_packet,
            codex_tool_call_packet=codex_packet,
            delegate_packet=delegate_packet,
            hook_source_packet=hook_source_packet,
        )

        serialized = json.dumps(packet, sort_keys=True)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["packet_kind"], "wbp_native_router_hook_observation")
        self.assertEqual(packet["result_status"], "observed")
        self.assertTrue(packet["router_hook_observed"])
        self.assertTrue(packet["native_router_hook_observed"])
        self.assertTrue(packet["explicit_router_hook_evidence"])
        self.assertEqual(packet["source_packet_kind"], "wbp_router_hook_source_admission")
        self.assertEqual(packet["source_status"], "ok")
        self.assertTrue(packet["source_wbp_owned"])
        self.assertEqual(packet["source_effect"], "probe")
        self.assertTrue(packet["source_run_digest_present"])
        self.assertTrue(packet["source_prompt_digest_present"])
        self.assertTrue(packet["source_prompt_digest_bound"])
        self.assertFalse(packet["manual_hook_packet_used"])
        self.assertFalse(packet["prompt_supplied_hook_flags"])
        self.assertFalse(packet["browser_supplied_hook_flags"])
        self.assertTrue(packet["wbp_owned_surface_called"])
        self.assertEqual(packet["wbp_owned_surface_kind"], "mcp_tool_call:delegate_to_dip")
        self.assertTrue(packet["delegate_to_dip_called"])
        self.assertTrue(packet["codex_mcp_config_loaded"])
        self.assertTrue(packet["codex_tool_call_observation_packet_ok"])
        self.assertTrue(packet["real_codex_prompt_executed"])
        self.assertTrue(packet["prompt_digest_present"])
        self.assertTrue(packet["prompt_digest_bound"])
        self.assertTrue(packet["prompt_to_mcp_call_bound"])
        self.assertTrue(packet["tool_call_digest_bound"])
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["runtime_context_file_proven"])
        self.assertTrue(packet["custom_codex_agent_runtime_context_proven"])
        self.assertTrue(packet["coding_alias_bound_to_api_lane"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["forbidden_stale_route_ids_enforced"])
        self.assertTrue(packet["route_allowed"])
        self.assertEqual(
            packet["selected_api_route_id_sha256"],
            hashlib.sha256(b"wbp-deepseek-chat").hexdigest(),
        )
        self.assertFalse(packet["selected_api_route_id_recorded"])
        self.assertNotIn("wbp-deepseek-chat", serialized)
        self.assertFalse(packet["local_codex_subagent_used"])
        self.assertFalse(packet["local_codex_subagent_used_as_dip"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["browser_authority_rejected"])
        self.assertTrue(packet["hook_observed_prompt"])
        self.assertTrue(packet["hook_can_enforce_router"])
        self.assertTrue(packet["hook_can_route_delegate_to_dip"])
        self.assertFalse(packet["browser_can_supply_route_authority"])
        self.assertFalse(packet["browser_can_supply_model_authority"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["raw_provider_response_recorded"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertTrue(packet["does_not_prove_native_free_chat_router"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_native_router_hook_observation_requires_explicit_hook_evidence(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        prompt_packet, codex_packet = _prompt_bound_codex_tool_call_packet()
        delegate_packet = _delegate_packet(context_payload=_context_payload())

        packet = mcp_delegate.build_native_router_hook_observation_packet(
            config_packet=config_packet,
            prompt_packet=prompt_packet,
            codex_tool_call_packet=codex_packet,
            delegate_packet=delegate_packet,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WBP_NATIVE_ROUTER_HOOK_NOT_OBSERVED")
        self.assertFalse(packet["router_hook_observed"])
        self.assertFalse(packet["explicit_router_hook_evidence"])
        self.assertEqual(packet["source_packet_kind"], "")
        self.assertEqual(packet["source_status"], "")
        self.assertFalse(packet["source_wbp_owned"])
        self.assertIn("router_hook_source_packet_missing", packet["blocking_reasons"])
        self.assertTrue(packet["wbp_owned_surface_called"])
        self.assertIn("hook_prompt_not_observed", packet["blocking_reasons"])
        self.assertIn("hook_cannot_enforce_router", packet["blocking_reasons"])
        self.assertIn("hook_cannot_route_delegate_to_dip", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_native_router_hook_observation_rejects_manual_truthy_hook_packet(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        prompt_packet, codex_packet = _prompt_bound_codex_tool_call_packet()
        delegate_packet = _delegate_packet(context_payload=_context_payload())

        packet = mcp_delegate.build_native_router_hook_observation_packet(
            config_packet=config_packet,
            prompt_packet=prompt_packet,
            codex_tool_call_packet=codex_packet,
            delegate_packet=delegate_packet,
            hook_packet={**ROUTER_HOOK_PACKET, "source_kind": "manual"},
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "WBP_NATIVE_ROUTER_HOOK_NOT_OBSERVED",
        )
        self.assertFalse(packet["router_hook_observed"])
        self.assertFalse(packet["explicit_router_hook_evidence"])
        self.assertTrue(packet["manual_hook_packet_used"])
        self.assertIn("manual_hook_packet_not_admitted", packet["blocking_reasons"])
        self.assertIn("router_hook_source_packet_missing", packet["blocking_reasons"])
        self.assertFalse(packet["hook_observed_prompt"])
        self.assertFalse(packet["hook_can_enforce_router"])
        self.assertFalse(packet["hook_can_route_delegate_to_dip"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_native_router_hook_observation_rejects_hook_logging_only(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        prompt_packet, codex_packet = _prompt_bound_codex_tool_call_packet()
        hook_source_packet = _router_hook_source_packet(
            prompt_packet,
            hook_can_enforce_router=False,
            hook_can_route_delegate_to_dip=False,
        )
        delegate_packet = _delegate_packet(context_payload=_context_payload())

        packet = mcp_delegate.build_native_router_hook_observation_packet(
            config_packet=config_packet,
            prompt_packet=prompt_packet,
            codex_tool_call_packet=codex_packet,
            delegate_packet=delegate_packet,
            hook_source_packet=hook_source_packet,
        )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["router_hook_observed"])
        self.assertEqual(packet["source_packet_kind"], "wbp_router_hook_source_admission")
        self.assertEqual(packet["source_status"], "blocked")
        self.assertIn("router_hook_source_packet_not_admitted", packet["blocking_reasons"])
        self.assertFalse(packet["hook_observed_prompt"])
        self.assertFalse(packet["hook_can_enforce_router"])
        self.assertFalse(packet["hook_can_route_delegate_to_dip"])
        self.assertIn("hook_prompt_not_observed", packet["blocking_reasons"])
        self.assertIn("hook_cannot_enforce_router", packet["blocking_reasons"])
        self.assertIn("hook_cannot_route_delegate_to_dip", packet["blocking_reasons"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_native_router_hook_observation_rejects_text_imitation_without_tool_call(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        prompt_packet, codex_packet = _prompt_bound_codex_tool_call_packet(
            jsonl_events=[
                {"type": "thread.started", "thread_id": "t1"},
                {"type": "turn.started"},
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item_text_1",
                        "type": "agent_message",
                        "text": "DIP says the answer is ready without a tool call.",
                    },
                },
                {"type": "turn.completed"},
            ],
        )
        hook_source_packet = _router_hook_source_packet(prompt_packet)
        delegate_packet = _delegate_packet(context_payload=_context_payload())

        packet = mcp_delegate.build_native_router_hook_observation_packet(
            config_packet=config_packet,
            prompt_packet=prompt_packet,
            codex_tool_call_packet=codex_packet,
            delegate_packet=delegate_packet,
            hook_source_packet=hook_source_packet,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WBP_NATIVE_ROUTER_HOOK_NOT_OBSERVED")
        self.assertFalse(packet["router_hook_observed"])
        self.assertFalse(packet["wbp_owned_surface_called"])
        self.assertIn("router_hook_not_observed", packet["blocking_reasons"])
        self.assertIn("codex_tool_call_observation_packet_not_ok", packet["blocking_reasons"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_codex_exec_jsonl_observation_marks_subagent_substitution(self) -> None:
        prompt_packet, packet = _prompt_bound_codex_tool_call_packet(
            jsonl_events=[
                {"type": "thread.started", "thread_id": "t1"},
                {"type": "turn.started"},
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item_subagent_1",
                        "type": "codex_subagent",
                        "name": "DIP",
                        "status": "completed",
                        "text": "Subagent DIP completed locally.",
                    },
                },
                {"type": "turn.completed"},
            ],
        )

        self.assertTrue(prompt_packet["prompt_digest_present"])
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WBP_CODEX_EXEC_SUBAGENT_USED_AS_DIP")
        self.assertTrue(packet["local_codex_subagent_used_as_dip"])
        self.assertTrue(packet["codex_subagent_used_as_dip"])
        self.assertTrue(packet["local_imitation_used"])
        self.assertFalse(packet["delegate_to_dip_tool_called"])
        self.assertIn("codex_subagent_used_as_dip", packet["blocking_reasons"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_native_router_hook_observation_rejects_codex_subagent_as_dip(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        prompt_packet, codex_packet = _prompt_bound_codex_tool_call_packet(
            jsonl_events=[
                {"type": "thread.started", "thread_id": "t1"},
                {"type": "turn.started"},
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item_subagent_2",
                        "type": "codex_subagent",
                        "name": "Agent 2",
                        "status": "completed",
                        "text": "Local sub-agent Agent 2 produced a response.",
                    },
                },
                {"type": "turn.completed"},
            ],
        )
        hook_source_packet = _router_hook_source_packet(prompt_packet)
        delegate_packet = _delegate_packet(context_payload=_context_payload())

        packet = mcp_delegate.build_native_router_hook_observation_packet(
            config_packet=config_packet,
            prompt_packet=prompt_packet,
            codex_tool_call_packet=codex_packet,
            delegate_packet=delegate_packet,
            hook_source_packet=hook_source_packet,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "WBP_NATIVE_ROUTER_HOOK_CODEX_SUBAGENT_USED",
        )
        self.assertTrue(packet["local_codex_subagent_used_as_dip"])
        self.assertTrue(packet["local_imitation_used"])
        self.assertIn("local_codex_subagent_used_as_dip", packet["blocking_reasons"])
        self.assertFalse(packet["router_hook_observed"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_native_router_hook_observation_blocks_without_codex_tool_call_packet(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        prompt_packet = mcp_delegate.build_prompt_observation_packet(
            PROMPT_TEXT,
            source="codex_exec_json",
            expected_delegate_arguments=PROMPT_DELEGATE_ARGUMENTS,
        )
        hook_source_packet = _router_hook_source_packet(prompt_packet)
        delegate_packet = _delegate_packet(context_payload=_context_payload())

        packet = mcp_delegate.build_native_router_hook_observation_packet(
            config_packet=config_packet,
            prompt_packet=prompt_packet,
            delegate_packet=delegate_packet,
            hook_source_packet=hook_source_packet,
        )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["router_hook_observed"])
        self.assertIn("codex_tool_call_observation_missing", packet["blocking_reasons"])
        self.assertIn("router_hook_not_observed", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_native_router_hook_observation_blocks_unbound_tool_call(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        prompt_packet, codex_packet = _prompt_bound_codex_tool_call_packet(
            arguments={"task": "Different task", "expected_alias": "DIP"},
            expected_arguments=PROMPT_DELEGATE_ARGUMENTS,
        )
        hook_source_packet = _router_hook_source_packet(prompt_packet)
        delegate_packet = _delegate_packet(context_payload=_context_payload())

        packet = mcp_delegate.build_native_router_hook_observation_packet(
            config_packet=config_packet,
            prompt_packet=prompt_packet,
            codex_tool_call_packet=codex_packet,
            delegate_packet=delegate_packet,
            hook_source_packet=hook_source_packet,
        )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["prompt_digest_bound"])
        self.assertFalse(packet["tool_call_digest_bound"])
        self.assertIn("prompt_digest_not_bound_to_router_hook", packet["blocking_reasons"])
        self.assertIn(
            "tool_call_digest_not_bound_to_delegate_packet",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["router_hook_observed"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_native_router_hook_observation_rejects_prompt_supplied_authority(self) -> None:
        forbidden_arguments = {
            "task": "DIP: implement this",
            "expected_alias": "DIP",
            "route_id": "evil-route-id",
            "backend": "https://evil.invalid",
            "secret": "secret-from-browser",
            "model": "evil-model",
        }
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        prompt_packet, codex_packet = _prompt_bound_codex_tool_call_packet(
            arguments=forbidden_arguments,
            expected_arguments=forbidden_arguments,
        )
        hook_source_packet = _router_hook_source_packet(prompt_packet)
        delegate_packet = _delegate_packet(
            arguments=forbidden_arguments,
            context_payload=_context_payload(),
        )

        packet = mcp_delegate.build_native_router_hook_observation_packet(
            config_packet=config_packet,
            prompt_packet=prompt_packet,
            codex_tool_call_packet=codex_packet,
            delegate_packet=delegate_packet,
            hook_source_packet=hook_source_packet,
        )

        serialized = json.dumps(packet, sort_keys=True)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "WBP_NATIVE_ROUTER_HOOK_BROWSER_AUTHORITY_REJECTED",
        )
        self.assertTrue(codex_packet["browser_authority_fields_rejected"])
        self.assertTrue(packet["browser_authority_rejected"])
        self.assertIn("browser_authority_rejected", packet["blocking_reasons"])
        self.assertFalse(packet["router_hook_observed"])
        self.assertNotIn("evil-route-id", serialized)
        self.assertNotIn("https://evil.invalid", serialized)
        self.assertNotIn("secret-from-browser", serialized)
        self.assertNotIn("evil-model", serialized)
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_native_router_hook_observation_requires_runtime_context(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        prompt_packet, codex_packet = _prompt_bound_codex_tool_call_packet()
        hook_source_packet = _router_hook_source_packet(prompt_packet)
        delegate_packet = _delegate_packet()

        packet = mcp_delegate.build_native_router_hook_observation_packet(
            config_packet=config_packet,
            prompt_packet=prompt_packet,
            codex_tool_call_packet=codex_packet,
            delegate_packet=delegate_packet,
            hook_source_packet=hook_source_packet,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "FAIL_ALIAS_CONTEXT_MISSING")
        self.assertFalse(packet["alias_context_read"])
        self.assertIn("alias_context_not_read", packet["blocking_reasons"])
        self.assertFalse(packet["router_hook_observed"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_native_router_hook_observation_rejects_product_ready_claims(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        prompt_packet, codex_packet = _prompt_bound_codex_tool_call_packet()
        hook_source_packet = _router_hook_source_packet(prompt_packet)
        codex_packet = dict(codex_packet)
        codex_packet["native_free_chat_router_proven"] = True
        codex_packet["product_ready"] = True
        delegate_packet = _delegate_packet(context_payload=_context_payload())

        packet = mcp_delegate.build_native_router_hook_observation_packet(
            config_packet=config_packet,
            prompt_packet=prompt_packet,
            codex_tool_call_packet=codex_packet,
            delegate_packet=delegate_packet,
            hook_source_packet=hook_source_packet,
        )

        self.assertEqual(packet["status"], "error")
        self.assertIn(
            "native_free_chat_router_must_not_be_claimed",
            packet["blocking_reasons"],
        )
        self.assertIn("product_ready_must_not_be_claimed", packet["blocking_reasons"])
        self.assertFalse(packet["router_hook_observed"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_codex_mcp_wiring_is_with_limits_without_codex_prompt_call(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        direct_proof = _direct_mcp_reality_packet(config_packet)

        packet = mcp_delegate.build_codex_mcp_wiring_reality_packet(
            config_packet=config_packet,
            mcp_reality_packet=direct_proof,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["packet_kind"], "wbp_codex_mcp_wiring_reality")
        self.assertEqual(packet["result_status"], "works_with_limits")
        self.assertEqual(
            packet["final_status"],
            "WBP_CODEX_MCP_WIRING_WORKS_WITH_LIMITS",
        )
        self.assertTrue(packet["codex_mcp_config_loaded"])
        self.assertTrue(packet["wbp_mcp_server_visible_to_codex"])
        self.assertTrue(packet["delegate_to_dip_tool_visible_to_codex"])
        self.assertTrue(packet["direct_mcp_proven_with_limits"])
        self.assertTrue(packet["direct_delegate_to_dip_tool_called"])
        self.assertFalse(packet["real_codex_prompt_executed"])
        self.assertFalse(packet["codex_delegate_to_dip_tool_called"])
        self.assertFalse(packet["prompt_to_mcp_call_bound"])
        self.assertFalse(packet["codex_mcp_wiring_proven"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertTrue(packet["does_not_prove_native_free_chat_router"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertIn("real_codex_prompt_not_executed", packet["limiting_reasons"])
        self.assertIn(
            "codex_delegate_to_dip_tool_call_not_observed",
            packet["limiting_reasons"],
        )
        self.assertEqual(
            packets.inspect_command_packet_semantics(packet),
            [],
        )

    def test_codex_mcp_wiring_blocks_without_codex_config(self) -> None:
        packet = mcp_delegate.build_codex_mcp_wiring_reality_packet()

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["result_status"], "blocked")
        self.assertFalse(packet["codex_mcp_config_loaded"])
        self.assertFalse(packet["wbp_mcp_server_visible_to_codex"])
        self.assertFalse(packet["delegate_to_dip_tool_visible_to_codex"])
        self.assertIn("codex_mcp_config_not_loaded", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(
            packets.inspect_command_packet_semantics(packet),
            [],
        )

    def test_codex_mcp_wiring_proven_requires_prompt_bound_tool_call(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        direct_proof = _direct_mcp_reality_packet(config_packet)
        prompt_packet = mcp_delegate.build_prompt_observation_packet(
            PROMPT_TEXT,
            source="codex_exec_json",
            expected_delegate_arguments=PROMPT_DELEGATE_ARGUMENTS,
        )
        codex_tool_call_packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
            "\n".join(
                [
                    json.dumps({"type": "thread.started", "thread_id": "t1"}),
                    json.dumps({"type": "turn.started"}),
                    json.dumps(
                        {
                            "type": "item.completed",
                            "item": {
                                "id": "item_1",
                                "type": "mcp_tool_call",
                                "server_name": "wild-boar-proxy",
                                "tool_name": "delegate_to_dip",
                                "status": "completed",
                                "arguments": PROMPT_DELEGATE_ARGUMENTS,
                            },
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps({"type": "turn.completed"}),
                ]
            ),
            prompt_packet=prompt_packet,
        )

        packet = mcp_delegate.build_codex_mcp_wiring_reality_packet(
            config_packet=config_packet,
            mcp_reality_packet=direct_proof,
            prompt_packet=prompt_packet,
            codex_tool_call_packet=codex_tool_call_packet,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["result_status"], "proven")
        self.assertEqual(packet["final_status"], "WBP_CODEX_MCP_WIRING_PROVEN")
        self.assertTrue(packet["codex_mcp_wiring_proven"])
        self.assertTrue(packet["codex_cli_prompt_mcp_tool_call_proven"])
        self.assertTrue(packet["codex_tool_call_observation_packet_ok"])
        self.assertTrue(packet["codex_exec_json_events_observed"])
        self.assertTrue(packet["real_codex_prompt_executed"])
        self.assertTrue(packet["codex_delegate_to_dip_tool_called"])
        self.assertTrue(packet["prompt_digest_present"])
        self.assertTrue(packet["prompt_to_mcp_call_bound"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertTrue(packet["does_not_prove_api_lane_provider_dispatch"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertEqual(
            packets.inspect_command_packet_semantics(packet),
            [],
        )

    def test_codex_exec_jsonl_observation_parses_prompt_bound_mcp_call(self) -> None:
        prompt_packet = mcp_delegate.build_prompt_observation_packet(
            PROMPT_TEXT,
            source="codex_exec_json",
            expected_delegate_arguments=PROMPT_DELEGATE_ARGUMENTS,
        )
        packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
            "\n".join(
                [
                    json.dumps({"type": "thread.started", "thread_id": "t1"}),
                    json.dumps({"type": "turn.started"}),
                    json.dumps(
                        {
                            "type": "item.completed",
                            "item": {
                                "id": "item_2",
                                "type": "mcp_tool_call",
                                "server": "wbp",
                                "name": "delegate_to_dip",
                                "status": "completed",
                                "arguments": PROMPT_DELEGATE_ARGUMENTS,
                            },
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps({"type": "turn.completed"}),
                ]
            ),
            prompt_packet=prompt_packet,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["packet_kind"], "wbp_codex_exec_tool_call_observation")
        self.assertEqual(packet["result_status"], "observed")
        self.assertTrue(packet["codex_exec_json_events_observed"])
        self.assertTrue(packet["real_codex_prompt_executed"])
        self.assertTrue(packet["delegate_to_dip_tool_called"])
        self.assertTrue(packet["codex_delegate_to_dip_tool_called"])
        self.assertTrue(packet["expected_delegate_tool_call_matched"])
        self.assertTrue(packet["prompt_to_mcp_call_bound"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["raw_jsonl_recorded"])
        self.assertFalse(packet["tool_call_arguments_recorded"])
        self.assertEqual(
            packets.inspect_command_packet_semantics(packet),
            [],
        )

    def test_codex_exec_jsonl_observation_ignores_agent_message_mentions(self) -> None:
        prompt_packet = mcp_delegate.build_prompt_observation_packet(
            PROMPT_TEXT,
            source="codex_exec_json",
            expected_delegate_arguments=PROMPT_DELEGATE_ARGUMENTS,
        )
        packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
            "\n".join(
                [
                    json.dumps({"type": "thread.started", "thread_id": "t1"}),
                    json.dumps({"type": "turn.started"}),
                    json.dumps(
                        {
                            "type": "item.completed",
                            "item": {
                                "id": "item_3",
                                "type": "agent_message",
                                "text": "I should call delegate_to_dip for DIP.",
                            },
                        }
                    ),
                    json.dumps({"type": "turn.completed"}),
                ]
            ),
            prompt_packet=prompt_packet,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["result_status"], "blocked")
        self.assertFalse(packet["delegate_to_dip_tool_called"])
        self.assertFalse(packet["prompt_to_mcp_call_bound"])
        self.assertIn(
            "codex_delegate_to_dip_tool_call_not_observed",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["product_ready"])

    def test_codex_exec_jsonl_observation_requires_expected_call_digest(self) -> None:
        prompt_packet = mcp_delegate.build_prompt_observation_packet(
            PROMPT_TEXT,
            source="codex_exec_json",
            expected_delegate_arguments=PROMPT_DELEGATE_ARGUMENTS,
        )
        packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
            "\n".join(
                [
                    json.dumps({"type": "thread.started", "thread_id": "t1"}),
                    json.dumps({"type": "turn.started"}),
                    json.dumps(
                        {
                            "type": "item.completed",
                            "item": {
                                "type": "mcp_tool_call",
                                "server": "wbp",
                                "name": "delegate_to_dip",
                                "status": "completed",
                                "arguments": {
                                    "task": PROMPT_TEXT,
                                    "expected_alias": "Agent 2",
                                },
                            },
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps({"type": "turn.completed"}),
                ]
            ),
            prompt_packet=prompt_packet,
        )

        self.assertEqual(packet["status"], "error")
        self.assertTrue(packet["delegate_to_dip_tool_called"])
        self.assertFalse(packet["expected_delegate_tool_call_matched"])
        self.assertTrue(packet["prompt_task_digest_matched"])
        self.assertFalse(packet["prompt_to_mcp_call_bound"])
        self.assertIn(
            "prompt_not_bound_to_codex_mcp_tool_call",
            packet["blocking_reasons"],
        )

    def test_codex_exec_jsonl_observation_rejects_agent_message_metadata(self) -> None:
        prompt_packet = mcp_delegate.build_prompt_observation_packet(
            PROMPT_TEXT,
            source="codex_exec_json",
            expected_delegate_arguments=PROMPT_DELEGATE_ARGUMENTS,
        )
        packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
            "\n".join(
                [
                    json.dumps({"type": "thread.started", "thread_id": "t1"}),
                    json.dumps({"type": "turn.started"}),
                    json.dumps(
                        {
                            "type": "item.completed",
                            "item": {
                                "id": "item_4",
                                "type": "agent_message",
                                "metadata": {
                                    "server": "wbp",
                                    "name": "delegate_to_dip",
                                    "arguments": PROMPT_DELEGATE_ARGUMENTS,
                                },
                            },
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps({"type": "turn.completed"}),
                ]
            ),
            prompt_packet=prompt_packet,
        )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["delegate_to_dip_tool_called"])
        self.assertIn(
            "codex_delegate_to_dip_tool_call_not_observed",
            packet["blocking_reasons"],
        )

    def test_codex_exec_jsonl_observation_blocks_prompt_digest_mismatch(self) -> None:
        prompt_packet = mcp_delegate.build_prompt_observation_packet(
            PROMPT_TEXT,
            source="codex_exec_json",
            expected_delegate_arguments=PROMPT_DELEGATE_ARGUMENTS,
        )
        packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
            "\n".join(
                [
                    json.dumps({"type": "thread.started", "thread_id": "t1"}),
                    json.dumps({"type": "turn.started"}),
                    json.dumps(
                        {
                            "type": "item.completed",
                            "item": {
                                "type": "mcp_tool_call",
                                "server_name": "wild-boar-proxy",
                                "tool_name": "delegate_to_dip",
                                "status": "completed",
                                "arguments": {
                                    "task": "Different task",
                                    "expected_alias": "DIP",
                                },
                            },
                        }
                    ),
                    json.dumps({"type": "turn.completed"}),
                ]
            ),
            prompt_packet=prompt_packet,
        )

        self.assertEqual(packet["status"], "error")
        self.assertTrue(packet["delegate_to_dip_tool_called"])
        self.assertFalse(packet["prompt_to_mcp_call_bound"])
        self.assertIn(
            "prompt_not_bound_to_codex_mcp_tool_call",
            packet["blocking_reasons"],
        )

    def test_codex_exec_jsonl_observation_reports_auth_admission_blocker(self) -> None:
        prompt_packet = mcp_delegate.build_prompt_observation_packet(
            PROMPT_TEXT,
            source="codex_exec_json",
            expected_delegate_arguments=PROMPT_DELEGATE_ARGUMENTS,
        )
        packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
            "",
            prompt_packet=prompt_packet,
            exec_exit_code=1,
            stderr_text="not authenticated; run codex login",
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "WBP_CODEX_EXEC_AUTHORIZATION_REQUIRED",
        )
        self.assertTrue(packet["codex_exec_auth_blocker_observed"])
        self.assertIn(
            "codex_exec_auth_or_model_admission_required",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["raw_stderr_recorded"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_codex_exec_jsonl_observation_reports_auth_from_error_events(self) -> None:
        prompt_packet = mcp_delegate.build_prompt_observation_packet(
            PROMPT_TEXT,
            source="codex_exec_json",
            expected_delegate_arguments=PROMPT_DELEGATE_ARGUMENTS,
        )
        auth_messages = [
            "Authentication required; run codex login.",
            "User is not currently authenticated.",
            "OAuth session expired.",
            "Sign in required before running Codex.",
            "Subscription plan required for this model.",
            "Account access required for this model.",
            "401 Unauthorized",
            "Bearer token missing",
        ]

        for message in auth_messages:
            with self.subTest(message=message):
                packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
                    "\n".join(
                        [
                            json.dumps({"type": "thread.started", "thread_id": "t1"}),
                            json.dumps({"type": "turn.started"}),
                            json.dumps({"type": "error", "message": message}),
                            json.dumps({"type": "turn.failed"}),
                        ]
                    ),
                    prompt_packet=prompt_packet,
                    exec_exit_code=1,
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    "WBP_CODEX_EXEC_AUTHORIZATION_REQUIRED",
                )
                self.assertTrue(packet["codex_exec_auth_blocker_observed"])
                self.assertIn(
                    "codex_exec_auth_or_model_admission_required",
                    packet["blocking_reasons"],
                )
                self.assertFalse(packet["raw_jsonl_recorded"])
                self.assertFalse(packet["secret_value_exposed"])

    def test_codex_exec_jsonl_observation_does_not_report_auth_on_success(self) -> None:
        packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
            "\n".join(
                [
                    json.dumps({"type": "thread.started", "thread_id": "t1"}),
                    json.dumps({"type": "turn.started"}),
                    json.dumps(
                        {
                            "type": "item.completed",
                            "item": {
                                "type": "message",
                                "text": "OK for this ChatGPT account.",
                            },
                        }
                    ),
                    json.dumps({"type": "turn.completed"}),
                ]
            ),
            exec_exit_code=0,
        )

        self.assertFalse(packet["codex_exec_auth_blocker_observed"])
        self.assertNotEqual(
            packet["machine_error_code"],
            "WBP_CODEX_EXEC_AUTHORIZATION_REQUIRED",
        )

    def test_codex_exec_model_guard_overrides_absent_or_unsafe_default(self) -> None:
        for requested_model in ("", "gpt-5.3-codex"):
            with self.subTest(requested_model=requested_model):
                packet = mcp_delegate.build_codex_exec_model_admission_guard_packet(
                    requested_model,
                    explicit_model_requested=False,
                    auth_mode_hint="chatgpt_login_status",
                )

                self.assertEqual(packet["status"], "ok")
                self.assertEqual(packet["machine_error_code"], "OK")
                self.assertEqual(packet["requested_model"], requested_model)
                self.assertEqual(packet["effective_model"], "gpt-5.4")
                self.assertTrue(packet["model_override_used"])
                self.assertEqual(
                    packet["model_override_reason"],
                    "chatgpt_account_default_model_not_admitted",
                )
                self.assertTrue(packet["model_admission_checked"])
                self.assertTrue(packet["model_admitted"])
                self.assertEqual(packet["auth_mode_hint"], "chatgpt_login_status")
                self.assertFalse(packet["raw_error_recorded"])
                self.assertFalse(packet["secret_value_exposed"])

    def test_codex_exec_model_guard_blocks_explicit_unsupported_model(self) -> None:
        packet = mcp_delegate.build_codex_exec_model_admission_guard_packet(
            "gpt-5.3-codex",
            explicit_model_requested=True,
            auth_mode_hint="chatgpt_login_status",
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "CODEX_MODEL_NOT_ADMITTED")
        self.assertEqual(packet["requested_model"], "gpt-5.3-codex")
        self.assertEqual(packet["effective_model"], "")
        self.assertFalse(packet["model_override_used"])
        self.assertFalse(packet["model_admitted"])
        self.assertIn("codex_model_not_admitted", packet["blocking_reasons"])
        self.assertFalse(packet["raw_error_recorded"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_codex_exec_model_guard_passes_explicit_admitted_model(self) -> None:
        packet = mcp_delegate.build_codex_exec_model_admission_guard_packet(
            "gpt-5.4",
            explicit_model_requested=True,
            auth_mode_hint="chatgpt_login_status",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["requested_model"], "gpt-5.4")
        self.assertEqual(packet["effective_model"], "gpt-5.4")
        self.assertFalse(packet["model_override_used"])
        self.assertTrue(packet["model_admission_checked"])
        self.assertTrue(packet["model_admitted"])

    def test_codex_exec_jsonl_observation_reports_unsupported_model(self) -> None:
        prompt_packet = mcp_delegate.build_prompt_observation_packet(
            PROMPT_TEXT,
            source="codex_exec_json",
            expected_delegate_arguments=PROMPT_DELEGATE_ARGUMENTS,
        )
        packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
            "\n".join(
                [
                    json.dumps({"type": "thread.started", "thread_id": "t1"}),
                    json.dumps({"type": "turn.started"}),
                    json.dumps(
                        {
                            "type": "error",
                            "message": (
                                "The 'gpt-5.3-codex' model is not supported "
                                "when using Codex with a ChatGPT account."
                            ),
                        }
                    ),
                    json.dumps({"type": "turn.failed"}),
                ]
            ),
            prompt_packet=prompt_packet,
            exec_exit_code=1,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "CODEX_MODEL_NOT_ADMITTED")
        self.assertTrue(packet["codex_exec_unsupported_model_observed"])
        self.assertFalse(packet["codex_exec_auth_blocker_observed"])
        self.assertIn("codex_model_not_admitted", packet["blocking_reasons"])
        self.assertFalse(packet["raw_jsonl_recorded"])
        self.assertFalse(packet["secret_value_exposed"])

    def test_codex_mcp_wiring_does_not_promote_blocked_codex_observation(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        direct_proof = _direct_mcp_reality_packet(config_packet)
        prompt_packet = mcp_delegate.build_prompt_observation_packet(
            PROMPT_TEXT,
            source="codex_exec_json",
            expected_delegate_arguments=PROMPT_DELEGATE_ARGUMENTS,
        )
        codex_tool_call_packet = (
            mcp_delegate.build_codex_exec_tool_call_observation_packet(
                "\n".join(
                    [
                        "{not-json",
                        json.dumps({"type": "thread.started", "thread_id": "t1"}),
                        json.dumps({"type": "turn.started"}),
                        json.dumps(
                            {
                                "type": "item.completed",
                                "item": {
                                    "type": "mcp_tool_call",
                                    "server": "wbp",
                                    "name": "delegate_to_dip",
                                    "status": "completed",
                                    "arguments": PROMPT_DELEGATE_ARGUMENTS,
                                },
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps({"type": "turn.completed"}),
                    ]
                ),
                prompt_packet=prompt_packet,
            )
        )

        self.assertEqual(codex_tool_call_packet["status"], "error")
        self.assertTrue(codex_tool_call_packet["delegate_to_dip_tool_called"])
        packet = mcp_delegate.build_codex_mcp_wiring_reality_packet(
            config_packet=config_packet,
            mcp_reality_packet=direct_proof,
            prompt_packet=prompt_packet,
            codex_tool_call_packet=codex_tool_call_packet,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["result_status"], "works_with_limits")
        self.assertFalse(packet["codex_mcp_wiring_proven"])
        self.assertFalse(packet["codex_cli_prompt_mcp_tool_call_proven"])
        self.assertFalse(packet["codex_tool_call_observation_packet_ok"])
        self.assertIn(
            "codex_tool_call_observation_packet_not_ok",
            packet["limiting_reasons"],
        )

    def test_codex_mcp_wiring_blocks_original_profile_touch(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        config_packet["codex_mcp_original_profile_touched"] = True
        direct_proof = _direct_mcp_reality_packet(config_packet)

        packet = mcp_delegate.build_codex_mcp_wiring_reality_packet(
            config_packet=config_packet,
            mcp_reality_packet=direct_proof,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["result_status"], "blocked")
        self.assertTrue(packet["codex_mcp_original_profile_touched"])
        self.assertFalse(packet["direct_mcp_proven_with_limits"])
        self.assertFalse(packet["codex_cli_prompt_mcp_tool_call_proven"])
        self.assertIn(
            "codex_mcp_original_profile_touched",
            packet["blocking_reasons"],
        )

    def test_codex_mcp_wiring_does_not_count_hook_logging_as_router(self) -> None:
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            CODEX_MCP_LIST_OUTPUT,
            CODEX_MCP_GET_OUTPUT,
        )
        direct_proof = _direct_mcp_reality_packet(config_packet)
        prompt_packet = mcp_delegate.build_prompt_observation_packet(
            PROMPT_TEXT,
            source="user_prompt_submit_hook",
            expected_delegate_arguments=PROMPT_DELEGATE_ARGUMENTS,
        )

        packet = mcp_delegate.build_codex_mcp_wiring_reality_packet(
            config_packet=config_packet,
            mcp_reality_packet=direct_proof,
            prompt_packet=prompt_packet,
            hook_packet={
                "hook_observed_prompt": True,
                "hook_can_enforce_router": False,
                "hook_can_route_delegate_to_dip": False,
            },
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["result_status"], "works_with_limits")
        self.assertTrue(packet["hook_observed_prompt"])
        self.assertFalse(packet["hook_can_enforce_router"])
        self.assertFalse(packet["hook_can_route_delegate_to_dip"])
        self.assertFalse(packet["codex_mcp_wiring_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertIn(
            "codex_delegate_to_dip_tool_call_not_observed",
            packet["limiting_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
