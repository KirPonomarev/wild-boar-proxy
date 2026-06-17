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

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import custom_codex_ingress_proof as ingress
from wild_boar_proxy import mcp_delegate
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy.core import packets


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, ask DIP to inspect ingress proof."
RAW_JSONL = "raw jsonl must not be stored"


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


def _jsonl_for_tool_call(
    *,
    task: str = PROMPT,
    status: str = "completed",
    item_type: str = "mcp_tool_call",
    tool_name: str = "delegate_to_dip",
) -> str:
    return "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "thread-ingress"}),
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item-delegate",
                        "type": item_type,
                        "server_name": "wbp",
                        "tool_name": tool_name,
                        "status": status,
                        "arguments": {"task": task},
                    },
                },
                ensure_ascii=True,
            ),
            json.dumps({"type": "turn.completed"}),
        ]
    )


def _jsonl_for_no_tool_call() -> str:
    return "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "thread-ingress"}),
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item-message",
                        "type": "agent_message",
                        "text": "I should ask DIP locally.",
                    },
                },
                ensure_ascii=True,
            ),
            json.dumps({"type": "turn.completed"}),
        ]
    )


def _jsonl_for_subagent() -> str:
    return "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "thread-ingress"}),
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item-subagent",
                        "type": "codex_subagent",
                        "name": "DIP",
                        "status": "completed",
                        "text": "Subagent DIP completed locally.",
                    },
                },
                ensure_ascii=True,
            ),
            json.dumps({"type": "turn.completed"}),
        ]
    )


def _prompt_packet() -> dict[str, object]:
    return mcp_delegate.build_prompt_observation_packet(
        PROMPT,
        source="codex_exec_json",
    )


def _codex_packet(jsonl_text: str | None = None) -> dict[str, object]:
    return mcp_delegate.build_codex_exec_tool_call_observation_packet(
        _jsonl_for_tool_call() if jsonl_text is None else jsonl_text,
        prompt_packet=_prompt_packet(),
    )


def _router_packet(
    *,
    runtime_context: dict[str, object] | None = None,
) -> dict[str, object]:
    return hook_entry.build_router_hook_entry_packet(
        prompt_text=PROMPT,
        runtime_context=_runtime_context() if runtime_context is None else runtime_context,
        hook_surface_kind=hook_entry.HOOK_SURFACE_PROMPT_PREPROCESSOR,
    )


def _ingress_packet(
    *,
    prompt_packet: dict[str, object] | None = None,
    codex_packet: dict[str, object] | None = None,
    router_packet: dict[str, object] | None = None,
) -> dict[str, object]:
    return ingress.build_custom_codex_ingress_proof_packet(
        prompt_packet=_prompt_packet() if prompt_packet is None else prompt_packet,
        codex_tool_call_packet=_codex_packet() if codex_packet is None else codex_packet,
        router_hook_entry_packet=_router_packet() if router_packet is None else router_packet,
        secret_values=[PROMPT, ROUTE_ID, RAW_JSONL],
    )


def _assert_no_false_product_claims(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["custom_codex_origin_proven"])
    testcase.assertFalse(packet["dispatch_proven"])
    testcase.assertEqual(packet["dispatch_status"], "not_attempted")
    testcase.assertFalse(packet["api_lane_called"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_dispatch"])
    testcase.assertTrue(packet["does_not_prove_api_lane_provider_dispatch"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_origin"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


def _assert_no_raw_payload_data(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    testcase.assertNotIn(PROMPT, serialized)
    testcase.assertNotIn(ROUTE_ID, serialized)
    testcase.assertNotIn(RAW_JSONL, serialized)
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["raw_jsonl_recorded"])
    testcase.assertFalse(packet["tool_call_arguments_recorded"])
    testcase.assertFalse(packet["route_candidate_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


class CustomCodexIngressProofTests(unittest.TestCase):
    def test_ingress_proves_prompt_bound_codex_tool_call_and_router_entry(self) -> None:
        packet = _ingress_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            ingress.CUSTOM_CODEX_INGRESS_PROOF_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["ingress_proven"])
        self.assertTrue(packet["controlled_ingress_proven"])
        self.assertFalse(packet["custom_codex_origin_proven"])
        self.assertTrue(packet["codex_tool_call_transcript_observed"])
        self.assertTrue(packet["mcp_tool_call_observed"])
        self.assertTrue(packet["mcp_tool_call_completed"])
        self.assertTrue(packet["prompt_digest"])
        self.assertTrue(packet["prompt_digest_bound_to_codex_tool_call"])
        self.assertTrue(packet["prompt_digest_bound_to_router_entry"])
        self.assertTrue(packet["prompt_digest_bound_to_ingress"])
        self.assertTrue(packet["tool_call_digest_present"])
        self.assertTrue(packet["tool_call_sha256"])
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["alias_bound"])
        self.assertEqual(packet["alias_candidate"], "DIP")
        self.assertEqual(packet["slot_candidate"], "dip")
        self.assertTrue(packet["route_id_allowed"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["forbidden_stale_route_ids_enforced"])
        self.assertEqual(packet["forbidden_stale_route_ids_count"], 1)
        self.assertTrue(packet["wbp_controlled_entry_called"])
        self.assertTrue(packet["router_hook_entry_preflight_passed"])
        self.assertFalse(packet["codex_native_subagent_used_as_dip"])
        self.assertFalse(packet["local_codex_subagent_used_as_dip"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertEqual(
            packet["ingress_truth_source"],
            ingress.INGRESS_TRUTH_SOURCE_PROVEN,
        )
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_false_product_claims(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, RAW_JSONL],
            ),
            [],
        )

    def test_ingress_blocks_missing_transcript_or_missing_tool_call(self) -> None:
        cases = [
            ("missing_transcript", ""),
            ("no_tool_call", _jsonl_for_no_tool_call()),
            (
                "failed_tool_call",
                _jsonl_for_tool_call(status="failed"),
            ),
        ]

        for name, jsonl_text in cases:
            with self.subTest(name=name):
                packet = _ingress_packet(codex_packet=_codex_packet(jsonl_text))

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    ingress.CUSTOM_CODEX_INGRESS_CODEX_TOOL_CALL_NOT_PROVEN,
                )
                self.assertFalse(packet["ingress_proven"])
                self.assertFalse(packet["wbp_controlled_entry_called"])
                self.assertIn(
                    "prompt_digest_not_bound_to_ingress",
                    packet["blocking_reasons"],
                )
                _assert_no_false_product_claims(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_ingress_blocks_prompt_digest_mismatch(self) -> None:
        packet = _ingress_packet(
            codex_packet=_codex_packet(_jsonl_for_tool_call(task="Different task")),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            ingress.CUSTOM_CODEX_INGRESS_CODEX_TOOL_CALL_NOT_PROVEN,
        )
        self.assertFalse(packet["prompt_digest_bound_to_codex_tool_call"])
        self.assertFalse(packet["prompt_digest_bound_to_ingress"])
        self.assertIn(
            "prompt_not_bound_to_codex_mcp_tool_call",
            packet["blocking_reasons"],
        )
        _assert_no_false_product_claims(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_ingress_blocks_alias_context_and_route_failures(self) -> None:
        cases = [
            ("missing_context", {}, "alias_context_not_read"),
            (
                "route_not_allowed",
                _runtime_context(allowed_routes=["other-route"]),
                "route_id_not_allowed",
            ),
            (
                "missing_stale_guard",
                {
                    **_runtime_context(),
                    "forbidden_stale_route_ids": [],
                },
                "stale_route_guard_missing",
            ),
            (
                "no_alias",
                _runtime_context(),
                "alias_not_bound",
            ),
        ]

        for name, context, reason in cases:
            with self.subTest(name=name):
                prompt_packet = _prompt_packet()
                router_prompt = "Summarize this note without a coding alias." if name == "no_alias" else PROMPT
                router_packet = hook_entry.build_router_hook_entry_packet(
                    prompt_text=router_prompt,
                    runtime_context=context,
                    hook_surface_kind=hook_entry.HOOK_SURFACE_PROMPT_PREPROCESSOR,
                )
                packet = ingress.build_custom_codex_ingress_proof_packet(
                    prompt_packet=prompt_packet,
                    codex_tool_call_packet=_codex_packet(),
                    router_hook_entry_packet=router_packet,
                    secret_values=[PROMPT, ROUTE_ID],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    ingress.CUSTOM_CODEX_INGRESS_ROUTER_ENTRY_NOT_PROVEN,
                )
                self.assertFalse(packet["ingress_proven"])
                self.assertFalse(packet["wbp_controlled_entry_called"])
                self.assertIn(reason, packet["blocking_reasons"])
                _assert_no_false_product_claims(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_ingress_blocks_codex_subagent_substitution(self) -> None:
        packet = _ingress_packet(codex_packet=_codex_packet(_jsonl_for_subagent()))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            ingress.CUSTOM_CODEX_INGRESS_CODEX_SUBAGENT_USED_AS_DIP,
        )
        self.assertTrue(packet["codex_native_subagent_used_as_dip"])
        self.assertTrue(packet["local_codex_subagent_used_as_dip"])
        self.assertTrue(packet["local_imitation_used"])
        self.assertFalse(packet["mcp_tool_call_observed"])
        self.assertFalse(packet["ingress_proven"])
        self.assertIn("codex_native_subagent_used_as_dip", packet["blocking_reasons"])
        _assert_no_false_product_claims(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_ingress_blocks_unsafe_source_claims_without_recording_raw_values(self) -> None:
        cases = [
            ({"raw_prompt_recorded": True, "prompt_text": PROMPT}, "raw_prompt_recorded"),
            ({"fallback_used": True}, "fallback_used"),
            ({"product_ready": True}, "product_ready_must_not_be_claimed"),
            (
                {"native_free_chat_router_proven": True},
                "native_free_chat_router_must_not_be_claimed",
            ),
            ({"api_lane_called": True}, "api_lane_call_must_not_be_claimed"),
        ]

        for mutation, reason in cases:
            with self.subTest(reason=reason):
                codex_packet = _codex_packet()
                codex_packet.update(mutation)
                packet = _ingress_packet(codex_packet=codex_packet)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    ingress.CUSTOM_CODEX_INGRESS_UNSAFE_SOURCE,
                )
                self.assertFalse(packet["ingress_proven"])
                self.assertFalse(packet["wbp_controlled_entry_called"])
                self.assertIn(reason, packet["blocking_reasons"])
                _assert_no_false_product_claims(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(
                    packets.inspect_command_packet_semantics(
                        packet,
                        secret_values=[PROMPT, ROUTE_ID, RAW_JSONL],
                    ),
                    [],
                )

    def test_ingress_cli_reads_context_and_jsonl_and_emits_single_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            profile_dir = temp / "profile"
            profile_dir.mkdir()
            context_path = profile_dir / hook_entry.RUNTIME_CONTEXT_FILENAME
            context_path.write_text(
                json.dumps(_runtime_context()) + "\n",
                encoding="utf-8",
            )
            jsonl_path = temp / "codex.jsonl"
            jsonl_path.write_text(_jsonl_for_tool_call() + "\n", encoding="utf-8")
            sentinel_path = temp / "sentinel.txt"
            sentinel_path.write_text("unchanged\n", encoding="utf-8")
            before = sentinel_path.read_text(encoding="utf-8")
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(profile_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "ingress",
                    "--prompt",
                    PROMPT,
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
            after = sentinel_path.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(result.stdout.strip(), json.dumps(packet, ensure_ascii=True))
        self.assertEqual(packet["packet_kind"], ingress.CUSTOM_CODEX_INGRESS_PROOF_PACKET_KIND)
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["ingress_proven"])
        self.assertTrue(packet["controlled_ingress_proven"])
        self.assertTrue(packet["codex_exec_jsonl_file_read"])
        self.assertFalse(packet["codex_exec_jsonl_file_path_recorded"])
        self.assertEqual(before, after)
        _assert_no_false_product_claims(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_router_hook_ingress_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "ingress",
                "--prompt",
                PROMPT,
                "--codex-exec-jsonl-file",
                "/tmp/wbp-codex.jsonl",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")


if __name__ == "__main__":
    unittest.main()
