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

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import controlled_ingress_api_dispatch_proof as proof
from wild_boar_proxy import custom_codex_ingress_proof as ingress
from wild_boar_proxy import mcp_delegate
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, дай задачу DIP: верни controlled dispatch proof."
RAW_PROVIDER_TEXT = "raw provider text must not be stored"


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


def _jsonl_for_tool_call(*, task: str = PROMPT) -> str:
    return "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "thread-dispatch"}),
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item-delegate",
                        "type": "mcp_tool_call",
                        "server_name": "wbp",
                        "tool_name": "delegate_to_dip",
                        "status": "completed",
                        "arguments": {"task": task},
                    },
                },
                ensure_ascii=True,
            ),
            json.dumps({"type": "turn.completed"}),
        ]
    )


def _ingress_packet(
    *,
    prompt: str = PROMPT,
    runtime_context: dict[str, object] | None = None,
) -> dict[str, object]:
    prompt_packet = mcp_delegate.build_prompt_observation_packet(
        prompt,
        source="codex_exec_json",
    )
    codex_packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
        _jsonl_for_tool_call(task=prompt),
        prompt_packet=prompt_packet,
    )
    router_packet = hook_entry.build_router_hook_entry_packet(
        prompt_text=prompt,
        runtime_context=_runtime_context() if runtime_context is None else runtime_context,
        hook_surface_kind=hook_entry.HOOK_SURFACE_PROMPT_PREPROCESSOR,
    )
    return ingress.build_custom_codex_ingress_proof_packet(
        prompt_packet=prompt_packet,
        codex_tool_call_packet=codex_packet,
        router_hook_entry_packet=router_packet,
        secret_values=[prompt, ROUTE_ID, RAW_PROVIDER_TEXT],
    )


def _dispatch_packet(
    *,
    ingress_packet: dict[str, object] | None = None,
    prompt: str = PROMPT,
    runtime_context: dict[str, object] | None = None,
    api_lane_adapter_available: bool = True,
    controlled_provider_available: bool = True,
    controlled_provider_error_code: str = "",
) -> dict[str, object]:
    return proof.build_controlled_ingress_api_dispatch_proof_packet(
        ingress_proof_packet=_ingress_packet()
        if ingress_packet is None
        else ingress_packet,
        prompt_text=prompt,
        runtime_context=_runtime_context() if runtime_context is None else runtime_context,
        hook_surface_kind=hook_entry.HOOK_SURFACE_PROMPT_PREPROCESSOR,
        api_lane_adapter_available=api_lane_adapter_available,
        controlled_provider_available=controlled_provider_available,
        controlled_provider_error_code=controlled_provider_error_code,
        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
    )


def _assert_no_product_or_native_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["live_provider_proven"])
    testcase.assertFalse(packet["live_provider_response_proven"])
    testcase.assertFalse(packet["external_live_provider_response_proven"])
    testcase.assertEqual(packet["live_provider_status"], "not_attempted")
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])
    testcase.assertTrue(packet["does_not_prove_live_provider"])


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


class ControlledIngressApiDispatchProofTests(unittest.TestCase):
    def test_positive_ingress_dispatch_proves_api_lane_response(self) -> None:
        packet = _dispatch_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            proof.CONTROLLED_INGRESS_API_DISPATCH_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(
            packet["ingress_proof_kind"],
            ingress.CUSTOM_CODEX_INGRESS_PROOF_PACKET_KIND,
        )
        self.assertTrue(packet["ingress_proven"])
        self.assertTrue(packet["controlled_ingress_proven"])
        self.assertEqual(
            packet["prompt_digest"],
            hashlib.sha256(PROMPT.encode("utf-8")).hexdigest(),
        )
        self.assertTrue(packet["prompt_digest_bound_to_ingress_proof"])
        self.assertTrue(packet["prompt_digest_bound_to_dispatch"])
        self.assertTrue(packet["prompt_digest_bound_to_proof"])
        self.assertEqual(packet["alias"], "DIP")
        self.assertEqual(packet["slot"], "dip")
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["alias_bound"])
        self.assertTrue(packet["route_id_allowed"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["ingress_forbidden_stale_route_ids_enforced"])
        self.assertEqual(packet["ingress_forbidden_stale_route_ids_count"], 1)
        self.assertTrue(packet["forbidden_stale_route_ids_enforced"])
        self.assertEqual(packet["forbidden_stale_route_ids_count"], 1)
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["api_lane_adapter_called"])
        self.assertTrue(packet["api_lane_dispatch_admitted"])
        self.assertTrue(packet["api_response_received"])
        self.assertTrue(packet["controlled_provider_called"])
        self.assertTrue(packet["controlled_provider_response_proven"])
        self.assertTrue(packet["response_bound_to_proof"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertEqual(packet["dispatch_status"], "proven")
        self.assertTrue(packet["route_bound_dispatch_attempted"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["route_bound_request_sha256"])
        self.assertTrue(packet["provider_response_digest"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertTrue(packet["provider_like_response_only"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_wrong_negative_and_overclaiming_ingress_packets(self) -> None:
        cases: list[tuple[str, dict[str, object], str]] = [
            (
                "wrong_kind",
                {"packet_kind": "wrong", "status": "ok", "machine_error_code": "OK"},
                proof.CONTROLLED_INGRESS_API_DISPATCH_INGRESS_NOT_PROVEN,
            ),
            (
                "negative_ingress",
                _ingress_packet(runtime_context=_runtime_context(allowed_routes=[])),
                proof.CONTROLLED_INGRESS_API_DISPATCH_INGRESS_NOT_PROVEN,
            ),
        ]
        for field in (
            "api_lane_called",
            "dispatch_proven",
            "product_ready",
            "native_free_chat_router_proven",
            "fallback_used",
            "local_imitation_used",
            "codex_native_subagent_used_as_dip",
            "raw_prompt_recorded",
        ):
            unsafe = dict(_ingress_packet())
            unsafe[field] = True
            cases.append(
                (
                    field,
                    unsafe,
                    proof.CONTROLLED_INGRESS_API_DISPATCH_UNSAFE_SOURCE,
                )
            )

        for name, ingress_packet, machine_error in cases:
            with self.subTest(name=name):
                packet = _dispatch_packet(ingress_packet=ingress_packet)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_error)
                self.assertFalse(packet["dispatch_proven"])
                self.assertEqual(packet["dispatch_status"], "blocked")
                self.assertFalse(packet["api_lane_called"])
                self.assertFalse(packet["api_response_received"])
                _assert_no_product_or_native_claim(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_prompt_digest_mismatch_before_dispatch(self) -> None:
        packet = _dispatch_packet(prompt="Codex, ask DIP a different task.")

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.CONTROLLED_INGRESS_API_DISPATCH_DIGEST_MISMATCH,
        )
        self.assertIn("prompt_digest_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["prompt_digest_bound_to_ingress_proof"])
        self.assertFalse(packet["dispatch_proven"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["api_response_received"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_rechecks_current_runtime_context_allowlist(self) -> None:
        packet = _dispatch_packet(
            ingress_packet=_ingress_packet(),
            runtime_context=_runtime_context(allowed_routes=["wbp-other-route"]),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "WBP_CONTROLLED_API_DISPATCH_HOOK_ENTRY_NOT_PROVEN",
        )
        self.assertIn("FAIL_ROUTE_NOT_ALLOWED", packet["blocking_reasons"])
        self.assertFalse(packet["route_id_allowed"])
        self.assertFalse(packet["api_lane_adapter_called"])
        self.assertFalse(packet["api_response_received"])
        self.assertFalse(packet["dispatch_proven"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_rechecks_current_runtime_context_stale_route_guard(self) -> None:
        runtime_context = _runtime_context()
        runtime_context["forbidden_stale_route_ids"] = []
        packet = _dispatch_packet(
            ingress_packet=_ingress_packet(),
            runtime_context=runtime_context,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "WBP_CONTROLLED_API_DISPATCH_HOOK_ENTRY_NOT_PROVEN",
        )
        self.assertIn("stale_route_guard_missing", packet["blocking_reasons"])
        self.assertFalse(packet["route_id_allowed"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertFalse(packet["forbidden_stale_route_ids_enforced"])
        self.assertEqual(packet["forbidden_stale_route_ids_count"], 0)
        self.assertFalse(packet["api_lane_adapter_called"])
        self.assertFalse(packet["api_response_received"])
        self.assertFalse(packet["dispatch_proven"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_api_lane_unavailable_and_provider_failures_do_not_false_green(self) -> None:
        cases = [
            (
                {"api_lane_adapter_available": False},
                "WBP_API_LANE_ADAPTER_NOT_AVAILABLE",
                False,
            ),
            (
                {"controlled_provider_available": False},
                "WBP_CONTROLLED_PROVIDER_UNAVAILABLE",
                True,
            ),
            (
                {"controlled_provider_error_code": "UPSTREAM_TIMEOUT"},
                "WBP_CONTROLLED_PROVIDER_ERROR",
                True,
            ),
        ]
        for kwargs, machine_error, api_lane_called in cases:
            with self.subTest(machine_error=machine_error):
                packet = _dispatch_packet(**kwargs)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_error)
                self.assertEqual(packet["api_lane_called"], api_lane_called)
                self.assertFalse(packet["api_response_received"])
                self.assertFalse(packet["response_bound_to_proof"])
                self.assertFalse(packet["dispatch_proven"])
                self.assertEqual(packet["dispatch_status"], "blocked")
                _assert_no_product_or_native_claim(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_reads_ingress_and_context_files_and_emits_single_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir) / "profile"
            profile_dir.mkdir()
            context_path = profile_dir / hook_entry.RUNTIME_CONTEXT_FILENAME
            context_path.write_text(
                json.dumps(_runtime_context()) + "\n",
                encoding="utf-8",
            )
            ingress_path = Path(temp_dir) / "ingress.json"
            ingress_path.write_text(
                json.dumps(_ingress_packet()) + "\n",
                encoding="utf-8",
            )
            sentinel = Path(temp_dir) / "sentinel.txt"
            sentinel.write_text("unchanged", encoding="utf-8")
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(profile_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "dispatch-proof",
                    "--ingress-proof-file",
                    str(ingress_path),
                    "--prompt",
                    PROMPT,
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
            proof.CONTROLLED_INGRESS_API_DISPATCH_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["ingress_proof_file_present"])
        self.assertTrue(packet["ingress_proof_file_read"])
        self.assertFalse(packet["ingress_proof_file_path_recorded"])
        self.assertTrue(packet["runtime_context_file_present"])
        self.assertTrue(packet["runtime_context_file_read"])
        self.assertFalse(packet["runtime_context_file_path_recorded"])
        self.assertTrue(packet["dispatch_proven"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_router_hook_dispatch_proof_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "dispatch-proof",
                "--ingress-proof-file",
                "/tmp/wbp-ingress.json",
                "--prompt",
                PROMPT,
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")


if __name__ == "__main__":
    unittest.main()
