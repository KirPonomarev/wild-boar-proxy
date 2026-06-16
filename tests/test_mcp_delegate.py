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
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "delegate_to_dip",
                        "arguments": {
                            "task": "Codex, дай задачу DIP: верни короткий план.",
                            "expected_alias": "DIP",
                        },
                    },
                },
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
        self.assertTrue(packet["delegate_to_dip_tool_called"])
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["forbidden_stale_route_ids_enforced"])
        self.assertTrue(packet["route_allowed"])
        self.assertEqual(packet["selected_route_id"], "wbp-deepseek-chat")
        self.assertTrue(packet["task_digest_preserved"])
        self.assertTrue(packet["task_sha256"])
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
            [initialized, listed, response]
        )
        self.assertEqual(proof["status"], "ok")
        self.assertEqual(proof["machine_error_code"], "OK")
        self.assertTrue(proof["mcp_server_visible"])
        self.assertTrue(proof["delegate_to_dip_tool_listed"])
        self.assertTrue(proof["delegate_to_dip_tool_called"])
        self.assertTrue(proof["alias_context_read"])
        self.assertTrue(proof["allowed_api_route_ids_enforced"])
        self.assertTrue(proof["forbidden_stale_route_ids_enforced"])
        self.assertTrue(proof["task_digest_preserved"])
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
            called = mcp_delegate.handle_jsonrpc_message(
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {
                        "name": "delegate_to_dip",
                        "arguments": {"task": "DIP: inspect this"},
                    },
                },
                env={"WBP_PROFILE_DIR": str(profile_dir)},
            )

        proof = mcp_delegate.build_reality_spike_proof_packet([called])
        self.assertEqual(proof["status"], "error")
        self.assertIn("mcp_server_not_visible", proof["blocking_reasons"])
        self.assertIn("delegate_to_dip_tool_not_listed", proof["blocking_reasons"])
        self.assertTrue(proof["delegate_to_dip_tool_called"])
        self.assertFalse(proof["product_ready"])


if __name__ == "__main__":
    unittest.main()
