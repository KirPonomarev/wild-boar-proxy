# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import (
    DISPATCH_STATUS_NOT_ATTEMPTED,
    FAIL_ALIAS_CONTEXT_MISSING,
    FAIL_ALIAS_NOT_API_LANE,
    FAIL_PROMPT_EMPTY,
    FAIL_ROUTE_NOT_ALLOWED,
    INTENT_PASS,
    NATURAL_INTENT_CONTRACT_PACKET_KIND,
    NO_ALIAS_DETECTED,
    PREFLIGHT_PASS,
    packet_contains_text,
)


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"


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


def _assert_no_dispatch(testcase: unittest.TestCase, packet: dict[str, object]) -> None:
    testcase.assertEqual(packet["dispatch_status"], DISPATCH_STATUS_NOT_ATTEMPTED)
    testcase.assertFalse(packet["api_lane_called"])
    testcase.assertFalse(packet["dispatch_proven"])
    testcase.assertFalse(packet["fallback_used"])
    testcase.assertFalse(packet["local_imitation_used"])
    testcase.assertFalse(packet["native_codex_subagent_used"])
    testcase.assertFalse(packet["native_codex_subagent_used_as_dip"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertTrue(packet["does_not_prove_dispatch"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertFalse(packet["hook_dispatch_attempted"])
    testcase.assertFalse(packet["hook_surface_can_dispatch"])
    testcase.assertTrue(packet["hook_does_not_prove_dispatch"])
    testcase.assertTrue(packet["router_hook_entry_no_dispatch_enforced"])


class RouterHookEntryTests(unittest.TestCase):
    def test_router_hook_entry_positive_packet_wraps_parser_without_dispatch(self) -> None:
        prompt = "Codex, дай задачу DIP: верни короткий план."
        packet = hook_entry.build_router_hook_entry_packet(
            prompt_text=prompt,
            runtime_context=_runtime_context(),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["packet_kind"], hook_entry.ROUTER_HOOK_ENTRY_PACKET_KIND)
        self.assertEqual(packet["parser_packet_kind"], NATURAL_INTENT_CONTRACT_PACKET_KIND)
        self.assertEqual(packet["hook_surface_kind"], hook_entry.HOOK_SURFACE_LOCAL_PROOF_COMMAND)
        self.assertTrue(packet["hook_entry_observed"])
        self.assertTrue(packet["hook_entry_proven"])
        self.assertTrue(packet["hook_surface_admitted"])
        self.assertFalse(packet["custom_codex_origin_proven"])
        self.assertFalse(packet["native_custom_codex_flow_proven"])
        self.assertFalse(packet["native_router_hook_observed"])
        self.assertTrue(packet["parser_used"])
        self.assertEqual(packet["alias_candidate"], "DIP")
        self.assertEqual(packet["slot_candidate"], "dip")
        self.assertEqual(packet["lane_candidate"], "api_route")
        self.assertEqual(packet["intent_status"], INTENT_PASS)
        self.assertEqual(packet["contract_preflight_status"], PREFLIGHT_PASS)
        self.assertEqual(packet["source_surface"], "declared_custom_codex_flow")
        self.assertFalse(packet["source_surface_observed"])
        self.assertFalse(packet["command_origin_proven"])
        self.assertFalse(packet_contains_text(packet, prompt))
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["prompt_text_recorded"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_entry_blocks_without_alias_but_keeps_hook_observed(self) -> None:
        packet = hook_entry.build_router_hook_entry_packet(
            prompt_text="Просто составь план.",
            runtime_context=_runtime_context(),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], NO_ALIAS_DETECTED)
        self.assertTrue(packet["hook_entry_observed"])
        self.assertFalse(packet["hook_entry_proven"])
        self.assertEqual(packet["parser_machine_error_code"], NO_ALIAS_DETECTED)
        self.assertFalse(packet["router_hook_entry_preflight_passed"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_entry_primary_only_alias_is_not_api_lane(self) -> None:
        packet = hook_entry.build_router_hook_entry_packet(
            prompt_text="Codex, проверь план.",
            runtime_context=_runtime_context(),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], FAIL_ALIAS_NOT_API_LANE)
        self.assertTrue(packet["hook_entry_observed"])
        self.assertFalse(packet["hook_entry_proven"])
        self.assertEqual(packet["alias_candidate"], "Codex")
        self.assertEqual(packet["lane_candidate"], "primary_chatgpt")
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_entry_unadmitted_surface_blocks_even_with_parser_pass(self) -> None:
        packet = hook_entry.build_router_hook_entry_packet(
            prompt_text="Codex, дай задачу DIP.",
            runtime_context=_runtime_context(),
            hook_surface_kind="browser_supplied_hook",
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            hook_entry.ROUTER_HOOK_ENTRY_SURFACE_NOT_ADMITTED,
        )
        self.assertFalse(packet["hook_entry_observed"])
        self.assertFalse(packet["hook_entry_proven"])
        self.assertFalse(packet["hook_surface_admitted"])
        self.assertTrue(packet["parser_used"])
        self.assertEqual(packet["intent_status"], INTENT_PASS)
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_entry_empty_prompt_blocks_without_hook_proof(self) -> None:
        packet = hook_entry.build_router_hook_entry_packet(
            prompt_text="",
            runtime_context=_runtime_context(),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], FAIL_PROMPT_EMPTY)
        self.assertTrue(packet["hook_entry_observed"])
        self.assertFalse(packet["hook_entry_proven"])
        self.assertFalse(packet["router_hook_entry_preflight_passed"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_entry_route_not_allowed_fails_closed(self) -> None:
        packet = hook_entry.build_router_hook_entry_packet(
            prompt_text="Codex, дай задачу DIP.",
            runtime_context=_runtime_context(allowed_routes=["wbp-other-route"]),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], FAIL_ROUTE_NOT_ALLOWED)
        self.assertTrue(packet["hook_entry_observed"])
        self.assertFalse(packet["hook_entry_proven"])
        self.assertFalse(packet["route_id_allowed"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_entry_forbidden_stale_route_fails_closed(self) -> None:
        runtime_context = _runtime_context(allowed_routes=[ROUTE_ID])
        runtime_context["forbidden_stale_route_ids"] = [ROUTE_ID]
        packet = hook_entry.build_router_hook_entry_packet(
            prompt_text="Codex, дай задачу DIP.",
            runtime_context=runtime_context,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], FAIL_ROUTE_NOT_ALLOWED)
        self.assertTrue(packet["hook_entry_observed"])
        self.assertFalse(packet["hook_entry_proven"])
        self.assertFalse(packet["route_id_allowed"])
        self.assertEqual(packet["forbidden_stale_route_ids_count"], 1)
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_entry_missing_stale_route_guard_fails_closed(self) -> None:
        runtime_context = _runtime_context(allowed_routes=[ROUTE_ID])
        runtime_context["forbidden_stale_route_ids"] = []
        packet = hook_entry.build_router_hook_entry_packet(
            prompt_text="Codex, дай задачу DIP.",
            runtime_context=runtime_context,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], FAIL_ROUTE_NOT_ALLOWED)
        self.assertTrue(packet["hook_entry_observed"])
        self.assertFalse(packet["hook_entry_proven"])
        self.assertFalse(packet["route_id_allowed"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertFalse(packet["forbidden_stale_route_ids_enforced"])
        self.assertEqual(packet["forbidden_stale_route_ids_count"], 0)
        self.assertIn("stale_route_guard_missing", packet["blocking_reasons"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_entry_cli_reads_context_file_and_emits_single_json(self) -> None:
        prompt = "Codex, дай задачу DIP: верни короткий план."
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir) / "profile"
            profile_dir.mkdir()
            context_path = profile_dir / hook_entry.RUNTIME_CONTEXT_FILENAME
            context_path.write_text(
                json.dumps(_runtime_context()) + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(profile_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "entry",
                    "--prompt",
                    prompt,
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(result.stdout.strip(), json.dumps(packet, ensure_ascii=True))
        self.assertEqual(packet["packet_kind"], hook_entry.ROUTER_HOOK_ENTRY_PACKET_KIND)
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["runtime_context_file_present"])
        self.assertTrue(packet["runtime_context_file_read"])
        self.assertFalse(packet["runtime_context_file_path_recorded"])
        self.assertTrue(packet["hook_entry_observed"])
        self.assertTrue(packet["hook_entry_proven"])
        self.assertEqual(packet["alias_candidate"], "DIP")
        self.assertEqual(packet["intent_status"], INTENT_PASS)
        self.assertFalse(packet_contains_text(packet, prompt))
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_entry_cli_runtime_context_file_override_is_used(self) -> None:
        prompt = "Codex, дай задачу DIP."
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir = root / "profile"
            profile_dir.mkdir()
            context_path = root / "runtime-context.json"
            context_path.write_text(
                json.dumps(_runtime_context()) + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(profile_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "entry",
                    "--prompt",
                    prompt,
                    "--runtime-context-file",
                    str(context_path),
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        packet = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["runtime_context_file_read"])
        self.assertTrue(packet["hook_entry_proven"])
        self.assertEqual(packet["alias_candidate"], "DIP")
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_entry_cli_missing_context_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir) / "profile"
            profile_dir.mkdir()
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(profile_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "entry",
                    "--prompt",
                    "Codex, дай задачу DIP.",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        packet = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], FAIL_ALIAS_CONTEXT_MISSING)
        self.assertEqual(packet["runtime_context_file_error_code"], "runtime_context_file_missing")
        self.assertFalse(packet["runtime_context_file_read"])
        self.assertTrue(packet["hook_entry_observed"])
        self.assertFalse(packet["hook_entry_proven"])
        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_entry_cli_invalid_context_file_fails_closed(self) -> None:
        cases = [
            ("{not-json\n", "runtime_context_file_invalid"),
            (json.dumps(["not", "mapping"]) + "\n", "runtime_context_file_not_mapping"),
        ]

        for content, error_code in cases:
            with self.subTest(error_code=error_code):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    profile_dir = root / "profile"
                    profile_dir.mkdir()
                    context_path = root / "runtime-context.json"
                    context_path.write_text(content, encoding="utf-8")
                    env = os.environ.copy()
                    env["WBP_PROFILE_DIR"] = str(profile_dir)
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "wild_boar_proxy",
                            "router-hook",
                            "entry",
                            "--prompt",
                            "Codex, дай задачу DIP.",
                            "--runtime-context-file",
                            str(context_path),
                            "--json",
                        ],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                packet = json.loads(result.stdout)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], FAIL_ALIAS_CONTEXT_MISSING)
                self.assertEqual(packet["runtime_context_file_error_code"], error_code)
                self.assertFalse(packet["hook_entry_proven"])
                self.assertTrue(packet["hook_entry_observed"])
                self.assertFalse(packet["runtime_context_file_path_recorded"])
                _assert_no_dispatch(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_router_hook_entry_error_packets_do_not_claim_hook_proven(self) -> None:
        error_packets = [
            hook_entry.build_router_hook_entry_packet(
                prompt_text="Просто составь план.",
                runtime_context=_runtime_context(),
            ),
            hook_entry.build_router_hook_entry_packet(
                prompt_text="Codex, проверь план.",
                runtime_context=_runtime_context(),
            ),
            hook_entry.build_router_hook_entry_packet(
                prompt_text="Codex, дай задачу DIP.",
                runtime_context={},
            ),
        ]

        for packet in error_packets:
            with self.subTest(machine_error_code=packet["machine_error_code"]):
                self.assertEqual(packet["status"], "error")
                self.assertFalse(packet["hook_entry_proven"])
                self.assertFalse(packet["router_hook_entry_preflight_passed"])
                _assert_no_dispatch(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

        _assert_no_dispatch(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_router_hook_entry_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "entry",
                "--prompt",
                "Codex, дай задачу DIP.",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")


if __name__ == "__main__":
    unittest.main()
