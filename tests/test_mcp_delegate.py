# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

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

    def test_delegate_to_dip_call_returns_bounded_with_limits_packet(self) -> None:
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
        self.assertEqual(packet["selected_route_id"], "wbp-deepseek-chat")
        self.assertTrue(packet["task_digest_preserved"])
        self.assertTrue(packet["task_sha256"])
        self.assertTrue(packet["tool_call_digest_present"])
        self.assertTrue(packet["tool_call_sha256"])
        self.assertFalse(packet["prompt_text_recorded"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["api_lane_called"])
        self.assertTrue(packet["bounded_api_lane_mock_used"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertTrue(packet["does_not_prove_native_free_chat_router"])
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
        self.assertTrue(proof["bounded_api_lane_mock_used"])
        self.assertFalse(proof["api_lane_called"])
        self.assertFalse(proof["fallback_used"])
        self.assertFalse(proof["local_imitation_used"])
        self.assertFalse(proof["product_ready"])
        self.assertFalse(proof["raw_transcript_recorded"])
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
        self.assertEqual(packet["selected_route_id"], "")
        self.assertIn("coding_route_not_allowed", packet["blocking_reasons"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])

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
