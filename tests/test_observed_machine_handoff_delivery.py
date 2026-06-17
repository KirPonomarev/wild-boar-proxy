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

from wild_boar_proxy import approved_handoff as handoff
from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import controlled_api_dispatch as dispatch
from wild_boar_proxy import observed_machine_handoff_delivery as delivery
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy.core import packets


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, дай задачу DIP: deliver the approved handoff."
RAW_PROVIDER_RESPONSE = "raw provider response must not be stored"


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


def _dispatch_packet() -> dict[str, object]:
    return dispatch.build_controlled_api_dispatch_packet(
        prompt_text=PROMPT,
        runtime_context=_runtime_context(),
    )


def _approved_packet(
    *,
    surface: str = handoff.HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
) -> dict[str, object]:
    return handoff.build_approved_handoff_packet(
        _dispatch_packet(),
        handoff_surface_kind=surface,
    )


def _handoff_payload(
    *,
    surface: str = handoff.HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
) -> dict[str, object]:
    return handoff._safe_handoff_payload(_dispatch_packet(), surface)


def _assert_no_false_product_claims(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["command_origin_proven"])
    testcase.assertFalse(packet["custom_codex_origin_proven"])
    testcase.assertFalse(packet["native_custom_codex_flow_proven"])
    testcase.assertFalse(packet["native_router_hook_observed"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["live_provider_proven"])
    testcase.assertFalse(packet["live_provider_response_proven"])
    testcase.assertFalse(packet["external_live_provider_response_proven"])
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
    testcase.assertNotIn(RAW_PROVIDER_RESPONSE, serialized)
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["route_candidate_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])
    testcase.assertFalse(packet["delivery_payload_text_recorded"])
    testcase.assertFalse(packet["delivery_payload_raw_recorded"])
    testcase.assertFalse(packet["machine_response_content_text_recorded"])
    testcase.assertFalse(packet["machine_response_raw_recorded"])


class ObservedMachineHandoffDeliveryTests(unittest.TestCase):
    def test_observed_delivery_prepares_mcp_tool_response_envelope(self) -> None:
        packet = delivery.build_observed_machine_handoff_delivery_packet(
            _approved_packet(),
            handoff_payload=_handoff_payload(),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            delivery.OBSERVED_MACHINE_HANDOFF_DELIVERY_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["approved_handoff_packet_valid"])
        self.assertTrue(packet["handoff_ready"])
        self.assertTrue(packet["handoff_payload_sanitized"])
        self.assertEqual(
            packet["delivery_surface_kind"],
            delivery.DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
        )
        self.assertTrue(packet["delivery_surface_allowed"])
        self.assertTrue(packet["delivery_surface_allowlist_enforced"])
        self.assertTrue(packet["delivery_attempted"])
        self.assertTrue(packet["delivery_surface_observed"])
        self.assertTrue(packet["machine_response_envelope_observed"])
        self.assertTrue(packet["machine_response_envelope_sha256"])
        self.assertTrue(packet["machine_response_structured_content_present"])
        self.assertTrue(packet["machine_response_structured_content_sha256"])
        self.assertTrue(packet["machine_response_content_text_present"])
        self.assertFalse(packet["mcp_tool_response_is_error"])
        self.assertEqual(
            packet["delivery_payload_kind"],
            delivery.MACHINE_HANDOFF_DELIVERY_PAYLOAD_KIND,
        )
        self.assertTrue(packet["delivery_payload_prepared"])
        self.assertTrue(packet["delivery_payload_sanitized"])
        self.assertTrue(packet["delivery_payload_sha256"])
        self.assertEqual(
            packet["delivery_payload_sha256"],
            packet["approved_handoff_payload_sha256"],
        )
        self.assertTrue(packet["delivery_payload_digest_matches_approved_handoff"])
        self.assertTrue(packet["handoff_delivered"])
        self.assertTrue(packet["delivery_observed"])
        self.assertEqual(
            packet["delivery_truth_source"],
            delivery.DELIVERY_TRUTH_SOURCE_PROVEN,
        )
        self.assertTrue(packet["delivery_counts_as_machine_handoff"])
        self.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
        self.assertFalse(packet["delivery_counts_as_native_free_chat_router"])
        self.assertFalse(packet["delivery_counts_as_live_provider_proof"])
        self.assertFalse(packet["delivery_counts_as_product_ready"])
        _assert_no_false_product_claims(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_RESPONSE],
            ),
            [],
        )

    def test_mcp_tool_response_envelope_shape_is_structured_and_no_error(self) -> None:
        handoff_payload = _handoff_payload()
        delivery_payload = delivery._safe_delivery_payload(
            handoff_payload,
            delivery_surface_kind=delivery.DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
        )
        envelope = delivery.build_mcp_tool_response_handoff_envelope(delivery_payload)

        self.assertEqual(envelope["isError"], False)
        self.assertEqual(envelope["structuredContent"], delivery_payload)
        self.assertEqual(envelope["content"][0]["type"], "text")
        self.assertEqual(json.loads(envelope["content"][0]["text"]), delivery_payload)

    def test_observed_delivery_blocks_missing_or_failed_approved_handoff(self) -> None:
        failed_source = _approved_packet()
        failed_source["status"] = "error"
        cases = [
            ({}, "approved_handoff_packet_kind_invalid"),
            (failed_source, "approved_handoff_packet_not_ok"),
        ]

        for source_packet, reason in cases:
            with self.subTest(reason=reason):
                packet = delivery.build_observed_machine_handoff_delivery_packet(
                    source_packet,
                    handoff_payload=_handoff_payload(),
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    delivery.OBSERVED_MACHINE_HANDOFF_APPROVED_HANDOFF_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["approved_handoff_packet_valid"])
                self.assertFalse(packet["delivery_attempted"])
                self.assertFalse(packet["delivery_payload_prepared"])
                self.assertFalse(packet["delivery_payload_sanitized"])
                self.assertFalse(packet["machine_response_structured_content_sha256"])
                self.assertFalse(packet["machine_response_envelope_observed"])
                self.assertFalse(packet["handoff_delivered"])
                self.assertFalse(packet["delivery_observed"])
                _assert_no_false_product_claims(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_observed_delivery_requires_mcp_tool_response_handoff_surface(self) -> None:
        packet = delivery.build_observed_machine_handoff_delivery_packet(
            _approved_packet(surface=handoff.HANDOFF_SURFACE_LOCAL_PROOF_COMMAND),
            handoff_payload=_handoff_payload(
                surface=handoff.HANDOFF_SURFACE_LOCAL_PROOF_COMMAND,
            ),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            delivery.OBSERVED_MACHINE_HANDOFF_APPROVED_HANDOFF_INVALID,
        )
        self.assertIn(
            "handoff_surface_must_be_mcp_tool_response",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["delivery_attempted"])
        self.assertFalse(packet["delivery_payload_prepared"])
        self.assertFalse(packet["delivery_payload_sanitized"])
        self.assertFalse(packet["machine_response_structured_content_sha256"])
        self.assertFalse(packet["machine_response_envelope_observed"])
        self.assertFalse(packet["handoff_delivered"])
        self.assertFalse(packet["delivery_observed"])
        _assert_no_false_product_claims(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_observed_delivery_blocks_unapproved_delivery_surface(self) -> None:
        packet = delivery.build_observed_machine_handoff_delivery_packet(
            _approved_packet(),
            handoff_payload=_handoff_payload(),
            delivery_surface_kind=handoff.HANDOFF_SURFACE_FILE_BRIDGE,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            delivery.OBSERVED_MACHINE_HANDOFF_SURFACE_NOT_ALLOWED,
        )
        self.assertFalse(packet["delivery_surface_allowed"])
        self.assertIn("delivery_surface_not_allowed", packet["blocking_reasons"])
        self.assertFalse(packet["delivery_attempted"])
        self.assertFalse(packet["delivery_payload_prepared"])
        self.assertFalse(packet["delivery_payload_sanitized"])
        self.assertFalse(packet["machine_response_structured_content_sha256"])
        self.assertFalse(packet["machine_response_envelope_observed"])
        self.assertFalse(packet["handoff_delivered"])
        self.assertFalse(packet["delivery_observed"])
        _assert_no_false_product_claims(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_observed_delivery_blocks_without_observed_surface_or_payload(self) -> None:
        cases = [
            (
                {"handoff_payload": _handoff_payload(), "delivery_surface_observed": False},
                delivery.OBSERVED_MACHINE_HANDOFF_NOT_OBSERVED,
                "delivery_surface_not_observed",
            ),
            (
                {"handoff_payload": None, "delivery_surface_observed": True},
                delivery.OBSERVED_MACHINE_HANDOFF_NOT_OBSERVED,
                "handoff_payload_missing",
            ),
        ]

        for kwargs, error_code, reason in cases:
            with self.subTest(reason=reason):
                packet = delivery.build_observed_machine_handoff_delivery_packet(
                    _approved_packet(),
                    **kwargs,
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], error_code)
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertEqual(
                    packet["delivery_attempted"],
                    reason == "delivery_surface_not_observed",
                )
                self.assertEqual(
                    packet["delivery_payload_prepared"],
                    reason == "delivery_surface_not_observed",
                )
                self.assertEqual(
                    packet["delivery_payload_sanitized"],
                    reason == "delivery_surface_not_observed",
                )
                self.assertFalse(packet["machine_response_structured_content_sha256"])
                self.assertFalse(packet["machine_response_envelope_observed"])
                self.assertFalse(packet["handoff_delivered"])
                self.assertFalse(packet["delivery_observed"])
                _assert_no_false_product_claims(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_observed_delivery_blocks_payload_digest_mismatch(self) -> None:
        bad_payload = _handoff_payload()
        bad_payload["selected_alias"] = "Worker"
        packet = delivery.build_observed_machine_handoff_delivery_packet(
            _approved_packet(),
            handoff_payload=bad_payload,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            delivery.OBSERVED_MACHINE_HANDOFF_DIGEST_MISMATCH,
        )
        self.assertIn("handoff_payload_digest_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["delivery_payload_digest_matches_approved_handoff"])
        self.assertFalse(packet["delivery_attempted"])
        self.assertFalse(packet["delivery_payload_prepared"])
        self.assertFalse(packet["delivery_payload_sanitized"])
        self.assertFalse(packet["machine_response_structured_content_sha256"])
        self.assertFalse(packet["machine_response_envelope_observed"])
        self.assertFalse(packet["handoff_delivered"])
        self.assertFalse(packet["delivery_observed"])
        _assert_no_false_product_claims(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_observed_delivery_blocks_raw_leaks_or_overclaims_in_source(self) -> None:
        cases = [
            ({"raw_prompt_recorded": True, "prompt_text": PROMPT}, "raw_prompt_recorded"),
            (
                {"selected_api_route_id_recorded": True, "selected_api_route_id": ROUTE_ID},
                "selected_api_route_id_recorded",
            ),
            (
                {
                    "raw_provider_response_recorded": True,
                    "provider_response_text": RAW_PROVIDER_RESPONSE,
                },
                "raw_provider_response_recorded",
            ),
            ("product_ready", "product_ready_must_not_be_claimed"),
            (
                "native_free_chat_router_proven",
                "native_free_chat_router_must_not_be_claimed",
            ),
            ("custom_codex_origin_proven", "custom_codex_origin_must_not_be_claimed"),
            ("live_provider_response_proven", "live_provider_response_must_not_be_claimed"),
        ]

        for mutation, reason in cases:
            with self.subTest(reason=reason):
                source_packet = _approved_packet()
                if isinstance(mutation, dict):
                    source_packet.update(mutation)
                else:
                    source_packet[mutation] = True
                packet = delivery.build_observed_machine_handoff_delivery_packet(
                    source_packet,
                    handoff_payload=_handoff_payload(),
                    secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_RESPONSE],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    delivery.OBSERVED_MACHINE_HANDOFF_PAYLOAD_UNSAFE,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["delivery_attempted"])
                self.assertFalse(packet["delivery_payload_prepared"])
                self.assertFalse(packet["delivery_payload_sanitized"])
                self.assertFalse(packet["machine_response_structured_content_sha256"])
                self.assertFalse(packet["machine_response_envelope_observed"])
                self.assertFalse(packet["handoff_delivered"])
                self.assertFalse(packet["delivery_observed"])
                _assert_no_false_product_claims(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(
                    packets.inspect_command_packet_semantics(
                        packet,
                        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_RESPONSE],
                    ),
                    [],
                )

    def test_observed_delivery_cli_reads_context_file_and_emits_single_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir) / "profile"
            profile_dir.mkdir()
            context_path = profile_dir / hook_entry.RUNTIME_CONTEXT_FILENAME
            context_path.write_text(
                json.dumps(_runtime_context()) + "\n",
                encoding="utf-8",
            )
            sentinel_path = Path(temp_dir) / "sentinel.txt"
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
                    "deliver",
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
            after = sentinel_path.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(result.stdout.strip(), json.dumps(packet, ensure_ascii=True))
        self.assertEqual(
            packet["packet_kind"],
            delivery.OBSERVED_MACHINE_HANDOFF_DELIVERY_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["handoff_delivered"])
        self.assertTrue(packet["delivery_observed"])
        self.assertEqual(before, after)
        _assert_no_false_product_claims(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_router_hook_deliver_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "deliver",
                "--prompt",
                PROMPT,
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")


if __name__ == "__main__":
    unittest.main()
