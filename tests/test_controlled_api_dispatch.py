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
from wild_boar_proxy import controlled_api_dispatch as dispatch
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, дай задачу DIP: верни route-bound proof."


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


def _assert_no_live_or_product_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["live_provider_proven"])
    testcase.assertFalse(packet["live_provider_response_proven"])
    testcase.assertFalse(packet["external_live_provider_response_proven"])
    testcase.assertEqual(packet["live_provider_status"], "not_attempted")
    testcase.assertFalse(packet["product_ready"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_live_provider"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


def _assert_no_raw_prompt_route_or_provider_text(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    testcase.assertNotIn(PROMPT, serialized)
    testcase.assertNotIn(ROUTE_ID, serialized)
    testcase.assertFalse(packet_contains_text(packet, PROMPT))
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["route_candidate_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


class ControlledApiDispatchTests(unittest.TestCase):
    def test_controlled_dispatch_proves_route_bound_bridge_backed_api_lane(self) -> None:
        packet = dispatch.build_controlled_api_dispatch_packet(
            prompt_text=PROMPT,
            runtime_context=_runtime_context(),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            dispatch.CONTROLLED_API_DISPATCH_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["hook_entry_proven"])
        self.assertTrue(packet["alias_context_read"])
        self.assertEqual(packet["selected_alias"], "DIP")
        self.assertEqual(packet["selected_alias_lane"], "api_route")
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["route_id_allowed"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["api_lane_adapter_called"])
        self.assertTrue(packet["api_lane_dispatch_admitted"])
        self.assertTrue(packet["route_bound_dispatch_attempted"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["route_bound_request_sent"])
        self.assertTrue(packet["route_bound_request_sha256"])
        self.assertEqual(
            packet["dispatch_truth_source"],
            "server_owned_controlled_provider_no_live_network",
        )
        self.assertEqual(
            packet["api_lane_truth_source"],
            "server_owned_controlled_route_bound_dispatch",
        )
        self.assertTrue(packet["controlled_provider_called"])
        self.assertTrue(packet["controlled_provider_response_digest_present"])
        self.assertTrue(packet["controlled_provider_response_sha256"])
        self.assertTrue(packet["controlled_provider_response_proven"])
        self.assertTrue(packet["provider_response_proven"])
        self.assertFalse(packet["bridge_backed_hook_surface"])
        self.assertFalse(packet["bridge_backed_provider_proof"])
        self.assertFalse(packet["bridge_backed_provider_response_proven"])
        self.assertTrue(packet["local_proof_command_dispatch_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertEqual(
            packet["selected_api_route_id_sha256"],
            hashlib.sha256(ROUTE_ID.encode("utf-8")).hexdigest(),
        )
        _assert_no_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_route_digest_is_not_computed_from_redacted_route_placeholder(self) -> None:
        packet = dispatch.build_controlled_api_dispatch_packet(
            prompt_text=PROMPT,
            runtime_context=_runtime_context(),
            secret_values=[PROMPT, ROUTE_ID],
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["selected_api_route_id_sha256"],
            hashlib.sha256(ROUTE_ID.encode("utf-8")).hexdigest(),
        )
        self.assertNotEqual(
            packet["selected_api_route_id_sha256"],
            hashlib.sha256("<redacted>".encode("utf-8")).hexdigest(),
        )
        _assert_no_raw_prompt_route_or_provider_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_controlled_dispatch_blocks_without_alias_context(self) -> None:
        packet = dispatch.build_controlled_api_dispatch_packet(
            prompt_text=PROMPT,
            runtime_context={},
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            dispatch.CONTROLLED_API_DISPATCH_HOOK_ENTRY_NOT_PROVEN,
        )
        self.assertIn("FAIL_ALIAS_CONTEXT_MISSING", packet["blocking_reasons"])
        self.assertFalse(packet["hook_entry_proven"])
        self.assertFalse(packet["api_lane_adapter_called"])
        self.assertFalse(packet["route_bound_dispatch_attempted"])
        self.assertFalse(packet["controlled_provider_called"])
        self.assertFalse(packet["dispatch_proven"])
        _assert_no_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_controlled_dispatch_blocks_non_api_and_missing_aliases_before_adapter(self) -> None:
        cases = [
            ("Просто составь план.", "NO_ALIAS_DETECTED"),
            ("Codex, проверь план.", "FAIL_ALIAS_NOT_API_LANE"),
        ]

        for prompt, hook_error in cases:
            with self.subTest(hook_error=hook_error):
                packet = dispatch.build_controlled_api_dispatch_packet(
                    prompt_text=prompt,
                    runtime_context=_runtime_context(),
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    dispatch.CONTROLLED_API_DISPATCH_HOOK_ENTRY_NOT_PROVEN,
                )
                self.assertIn(hook_error, packet["blocking_reasons"])
                self.assertFalse(packet["hook_entry_proven"])
                self.assertFalse(packet["api_lane_adapter_called"])
                self.assertFalse(packet["route_bound_dispatch_attempted"])
                self.assertFalse(packet["controlled_provider_called"])
                self.assertFalse(packet["dispatch_proven"])
                _assert_no_live_or_product_claim(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_controlled_dispatch_rejects_route_outside_allowlist(self) -> None:
        packet = dispatch.build_controlled_api_dispatch_packet(
            prompt_text=PROMPT,
            runtime_context=_runtime_context(allowed_routes=["wbp-other-route"]),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            dispatch.CONTROLLED_API_DISPATCH_HOOK_ENTRY_NOT_PROVEN,
        )
        self.assertIn("FAIL_ROUTE_NOT_ALLOWED", packet["blocking_reasons"])
        self.assertFalse(packet["route_id_allowed"])
        self.assertFalse(packet["api_lane_adapter_called"])
        self.assertFalse(packet["controlled_provider_called"])
        _assert_no_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_controlled_dispatch_rejects_missing_stale_route_guard(self) -> None:
        runtime_context = _runtime_context()
        runtime_context["forbidden_stale_route_ids"] = []
        packet = dispatch.build_controlled_api_dispatch_packet(
            prompt_text=PROMPT,
            runtime_context=runtime_context,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            dispatch.CONTROLLED_API_DISPATCH_HOOK_ENTRY_NOT_PROVEN,
        )
        self.assertIn("stale_route_guard_missing", packet["blocking_reasons"])
        self.assertFalse(packet["route_id_allowed"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertEqual(packet["forbidden_stale_route_ids_count"], 0)
        self.assertFalse(packet["api_lane_adapter_called"])
        self.assertFalse(packet["controlled_provider_called"])
        self.assertFalse(packet["dispatch_proven"])
        _assert_no_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_controlled_dispatch_rejects_adapter_unavailable(self) -> None:
        packet = dispatch.build_controlled_api_dispatch_packet(
            prompt_text=PROMPT,
            runtime_context=_runtime_context(),
            api_lane_adapter_available=False,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WBP_API_LANE_ADAPTER_NOT_AVAILABLE")
        self.assertTrue(packet["hook_entry_proven"])
        self.assertTrue(packet["api_lane_adapter_called"])
        self.assertFalse(packet["api_lane_dispatch_admitted"])
        self.assertFalse(packet["route_bound_dispatch_attempted"])
        self.assertFalse(packet["controlled_provider_called"])
        self.assertFalse(packet["dispatch_proven"])
        _assert_no_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_controlled_dispatch_rejects_controlled_provider_failures(self) -> None:
        cases = [
            (False, "", "WBP_CONTROLLED_PROVIDER_UNAVAILABLE"),
            (True, "UPSTREAM_TIMEOUT", "WBP_CONTROLLED_PROVIDER_ERROR"),
        ]

        for available, error_code, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                packet = dispatch.build_controlled_api_dispatch_packet(
                    prompt_text=PROMPT,
                    runtime_context=_runtime_context(),
                    controlled_provider_available=available,
                    controlled_provider_error_code=error_code,
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], expected_error)
                self.assertTrue(packet["hook_entry_proven"])
                self.assertTrue(packet["api_lane_adapter_called"])
                self.assertTrue(packet["api_lane_dispatch_admitted"])
                self.assertTrue(packet["route_bound_dispatch_attempted"])
                self.assertFalse(packet["route_bound_dispatch_proven"])
                self.assertFalse(packet["dispatch_proven"])
                self.assertFalse(packet["provider_response_proven"])
                _assert_no_live_or_product_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider_text(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_controlled_dispatch_accepts_admitted_bridge_surfaces_without_native_claim(self) -> None:
        surfaces = [
            hook_entry.HOOK_SURFACE_LAUNCHER_OWNED_BRIDGE,
            hook_entry.HOOK_SURFACE_FILE_BRIDGE,
        ]

        for surface in surfaces:
            with self.subTest(surface=surface):
                packet = dispatch.build_controlled_api_dispatch_packet(
                    prompt_text=PROMPT,
                    runtime_context=_runtime_context(),
                    hook_surface_kind=surface,
                )

                self.assertEqual(packet["status"], "ok")
                self.assertTrue(packet["hook_surface_admitted"])
                self.assertTrue(packet["bridge_backed_hook_surface"])
                self.assertTrue(packet["hook_entry_proven"])
                self.assertTrue(packet["route_bound_dispatch_proven"])
                self.assertTrue(packet["bridge_backed_provider_proof"])
                self.assertTrue(packet["bridge_backed_provider_response_proven"])
                self.assertFalse(packet["local_proof_command_dispatch_proven"])
                self.assertFalse(packet["native_custom_codex_flow_proven"])
                self.assertFalse(packet["native_router_hook_observed"])
                _assert_no_live_or_product_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider_text(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_controlled_dispatch_cli_reads_context_file_and_emits_single_json(self) -> None:
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
                    "dispatch",
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

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(result.stdout.strip(), json.dumps(packet, ensure_ascii=True))
        self.assertEqual(
            packet["packet_kind"],
            dispatch.CONTROLLED_API_DISPATCH_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["runtime_context_file_present"])
        self.assertTrue(packet["runtime_context_file_read"])
        self.assertFalse(packet["runtime_context_file_path_recorded"])
        self.assertTrue(packet["hook_entry_proven"])
        self.assertTrue(packet["dispatch_proven"])
        _assert_no_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_router_hook_dispatch_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "dispatch",
                "--prompt",
                PROMPT,
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")


if __name__ == "__main__":
    unittest.main()
