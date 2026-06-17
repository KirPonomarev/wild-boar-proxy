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
from wild_boar_proxy import controlled_dispatch_handoff_proof as handoff_proof
from wild_boar_proxy import controlled_ingress_api_dispatch_proof as dispatch_proof
from wild_boar_proxy import custom_codex_ingress_proof as ingress
from wild_boar_proxy import mcp_delegate
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy.approved_handoff import (
    HANDOFF_SURFACE_FILE_BRIDGE,
    HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
)
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, дай задачу DIP: prove dispatch handoff."
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
            json.dumps({"type": "thread.started", "thread_id": "thread-handoff"}),
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
    handoff_surface_kind: str = HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
) -> dict[str, object]:
    return handoff_proof.build_controlled_dispatch_handoff_proof_packet(
        _dispatch_packet() if dispatch_packet is None else dispatch_packet,
        handoff_surface_kind=handoff_surface_kind,
        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
    )


def _assert_no_product_or_native_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
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
    testcase.assertFalse(packet["machine_response_content_text_recorded"])
    testcase.assertFalse(packet["machine_response_raw_recorded"])


class ControlledDispatchHandoffProofTests(unittest.TestCase):
    def test_positive_dispatch_handoff_proves_approved_mcp_tool_response_delivery(self) -> None:
        packet = _handoff_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            handoff_proof.CONTROLLED_DISPATCH_HANDOFF_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(
            packet["dispatch_proof_kind"],
            dispatch_proof.CONTROLLED_INGRESS_API_DISPATCH_PACKET_KIND,
        )
        self.assertTrue(packet["dispatch_proof_valid"])
        self.assertTrue(packet["ingress_proven"])
        self.assertTrue(packet["controlled_ingress_proven"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["api_response_received"])
        self.assertTrue(packet["response_bound_to_proof"])
        self.assertTrue(packet["provider_like_response_only"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["forbidden_stale_route_ids_enforced"])
        self.assertEqual(packet["forbidden_stale_route_ids_count"], 1)
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["controlled_provider_response_proven"])
        self.assertEqual(packet["handoff_surface_kind"], HANDOFF_SURFACE_MCP_TOOL_RESPONSE)
        self.assertTrue(packet["handoff_surface_allowed"])
        self.assertTrue(packet["handoff_surface_supports_observed_delivery"])
        self.assertTrue(packet["approved_handoff_surface_used"])
        self.assertTrue(packet["approved_handoff_ready"])
        self.assertTrue(packet["approved_handoff_payload_sanitized"])
        self.assertTrue(packet["handoff_payload_digest"])
        self.assertTrue(packet["handoff_payload_prepared"])
        self.assertTrue(packet["handoff_envelope_built"])
        self.assertTrue(packet["handoff_observed"])
        self.assertTrue(packet["handoff_completed"])
        self.assertTrue(packet["delivery_surface_allowed"])
        self.assertTrue(packet["machine_response_envelope_observed"])
        self.assertTrue(packet["machine_response_envelope_sha256"])
        self.assertTrue(packet["machine_response_structured_content_present"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_wrong_negative_and_overclaiming_dispatch_proofs(self) -> None:
        negative = dict(_dispatch_packet())
        negative["status"] = "error"
        cases: list[tuple[str, dict[str, object], str]] = [
            (
                "wrong_kind",
                {"packet_kind": "wrong", "status": "ok", "machine_error_code": "OK"},
                handoff_proof.CONTROLLED_DISPATCH_HANDOFF_DISPATCH_PROOF_INVALID,
            ),
            (
                "negative_dispatch",
                negative,
                handoff_proof.CONTROLLED_DISPATCH_HANDOFF_DISPATCH_PROOF_INVALID,
            ),
        ]
        for field in (
            "fallback_used",
            "local_imitation_used",
            "native_codex_subagent_used_as_dip",
            "live_provider_proven",
            "live_provider_response_proven",
            "product_ready",
            "native_free_chat_router_proven",
            "raw_prompt_recorded",
            "raw_provider_response_recorded",
            "secret_value_exposed",
        ):
            unsafe = dict(_dispatch_packet())
            unsafe[field] = True
            cases.append(
                (
                    field,
                    unsafe,
                    handoff_proof.CONTROLLED_DISPATCH_HANDOFF_PAYLOAD_UNSAFE,
                )
            )

        for name, dispatch_packet, machine_error in cases:
            with self.subTest(name=name):
                packet = _handoff_packet(dispatch_packet=dispatch_packet)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_error)
                self.assertFalse(packet["handoff_completed"])
                self.assertFalse(packet["handoff_observed"])
                self.assertFalse(packet["handoff_envelope_built"])
                _assert_no_product_or_native_claim(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_missing_required_dispatch_evidence(self) -> None:
        cases = [
            ("ingress_proven", False, "ingress_not_proven"),
            ("controlled_ingress_proven", False, "controlled_ingress_not_proven"),
            ("dispatch_proven", False, "dispatch_not_proven"),
            ("api_lane_called", False, "api_lane_not_called"),
            ("api_response_received", False, "api_response_not_received"),
            ("response_bound_to_proof", False, "response_not_bound_to_proof"),
            ("provider_like_response_only", False, "provider_like_response_only_not_declared"),
            ("forbidden_stale_route_ids_enforced", False, "stale_route_guard_missing"),
            ("forbidden_stale_route_ids_count", 0, "stale_route_guard_missing"),
            ("selected_api_route_id_sha256", "", "selected_api_route_digest_missing"),
            ("provider_response_digest", "", "provider_response_digest_missing"),
        ]
        for field, value, reason in cases:
            with self.subTest(field=field):
                dispatch_packet = dict(_dispatch_packet())
                dispatch_packet[field] = value
                packet = _handoff_packet(dispatch_packet=dispatch_packet)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    handoff_proof.CONTROLLED_DISPATCH_HANDOFF_DISPATCH_PROOF_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["handoff_completed"])
                _assert_no_product_or_native_claim(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_approved_but_unobserved_handoff_surfaces(self) -> None:
        packet = _handoff_packet(handoff_surface_kind=HANDOFF_SURFACE_FILE_BRIDGE)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            handoff_proof.CONTROLLED_DISPATCH_HANDOFF_SURFACE_NOT_SUPPORTED,
        )
        self.assertTrue(packet["handoff_surface_allowed"])
        self.assertFalse(packet["handoff_surface_supports_observed_delivery"])
        self.assertIn(
            "handoff_surface_does_not_support_observed_delivery",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["handoff_completed"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_unapproved_handoff_surface(self) -> None:
        packet = handoff_proof.build_controlled_dispatch_handoff_proof_packet(
            _dispatch_packet(),
            handoff_surface_kind="browser_supplied_surface",
            secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            handoff_proof.CONTROLLED_DISPATCH_HANDOFF_SURFACE_NOT_ALLOWED,
        )
        self.assertFalse(packet["handoff_surface_allowed"])
        self.assertIn("handoff_surface_not_allowed", packet["blocking_reasons"])
        self.assertFalse(packet["handoff_completed"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_reads_dispatch_proof_file_and_emits_single_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dispatch_path = Path(temp_dir) / "dispatch.json"
            dispatch_path.write_text(
                json.dumps(_dispatch_packet()) + "\n",
                encoding="utf-8",
            )
            sentinel = Path(temp_dir) / "sentinel.txt"
            sentinel.write_text("unchanged", encoding="utf-8")
            env = os.environ.copy()
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "handoff-proof",
                    "--dispatch-proof-file",
                    str(dispatch_path),
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
            handoff_proof.CONTROLLED_DISPATCH_HANDOFF_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["dispatch_proof_file_present"])
        self.assertTrue(packet["dispatch_proof_file_read"])
        self.assertFalse(packet["dispatch_proof_file_path_recorded"])
        self.assertTrue(packet["handoff_completed"])
        _assert_no_product_or_native_claim(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_router_hook_handoff_proof_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "handoff-proof",
                "--dispatch-proof-file",
                "/tmp/wbp-dispatch.json",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")


if __name__ == "__main__":
    unittest.main()
