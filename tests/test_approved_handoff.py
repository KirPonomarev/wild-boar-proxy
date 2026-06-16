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
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy.core import packets


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, дай задачу DIP: подготовь handoff proof."
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


class ApprovedHandoffTests(unittest.TestCase):
    def test_approved_handoff_prepares_sanitized_payload_from_dispatch_proof(self) -> None:
        packet = handoff.build_approved_handoff_packet(_dispatch_packet())

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["packet_kind"], handoff.APPROVED_HANDOFF_PACKET_KIND)
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["source_dispatch_packet_valid"])
        self.assertTrue(packet["hook_entry_proven"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["provider_response_proven"])
        self.assertTrue(packet["controlled_provider_response_proven"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertEqual(
            packet["handoff_surface_kind"],
            handoff.HANDOFF_SURFACE_LOCAL_PROOF_COMMAND,
        )
        self.assertTrue(packet["handoff_surface_allowed"])
        self.assertTrue(packet["handoff_surface_allowlist_enforced"])
        self.assertTrue(packet["handoff_payload_prepared"])
        self.assertTrue(packet["handoff_ready"])
        self.assertTrue(packet["handoff_payload_sanitized"])
        self.assertTrue(packet["handoff_payload_sha256"])
        self.assertGreater(packet["handoff_payload_field_count"], 0)
        self.assertEqual(
            packet["handoff_truth_source"],
            handoff.HANDOFF_TRUTH_SOURCE_PROVEN,
        )
        self.assertFalse(packet["handoff_delivered"])
        self.assertFalse(packet["handoff_delivered_requested"])
        self.assertFalse(packet["handoff_delivery_observed"])
        self.assertFalse(packet["handoff_counts_as_native_free_chat_router"])
        self.assertFalse(packet["handoff_counts_as_live_provider_proof"])
        self.assertFalse(packet["handoff_counts_as_product_ready"])
        _assert_no_false_product_claims(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_approved_handoff_accepts_each_allowed_surface(self) -> None:
        for surface in sorted(handoff.APPROVED_HANDOFF_SURFACES):
            with self.subTest(surface=surface):
                packet = handoff.build_approved_handoff_packet(
                    _dispatch_packet(),
                    handoff_surface_kind=surface,
                )

                self.assertEqual(packet["status"], "ok")
                self.assertEqual(packet["handoff_surface_kind"], surface)
                self.assertTrue(packet["handoff_surface_allowed"])
                self.assertTrue(packet["handoff_ready"])
                self.assertFalse(packet["handoff_delivered"])
                _assert_no_false_product_claims(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_approved_handoff_blocks_missing_or_failed_dispatch_proof(self) -> None:
        failed_dispatch = dispatch.build_controlled_api_dispatch_packet(
            prompt_text=PROMPT,
            runtime_context={},
        )
        cases = [
            ({}, "dispatch_packet_kind_invalid"),
            (failed_dispatch, "dispatch_packet_not_ok"),
        ]

        for source_packet, reason in cases:
            with self.subTest(reason=reason):
                packet = handoff.build_approved_handoff_packet(source_packet)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    handoff.APPROVED_HANDOFF_DISPATCH_PROOF_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["handoff_payload_prepared"])
                self.assertFalse(packet["handoff_ready"])
                self.assertFalse(packet["handoff_payload_sanitized"])
                self.assertFalse(packet["handoff_delivered"])
                _assert_no_false_product_claims(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_approved_handoff_blocks_missing_digest_or_spoofed_truth_source(self) -> None:
        cases = [
            ("selected_api_route_id_sha256", "", "selected_api_route_digest_missing"),
            ("selected_api_route_id_present", False, "selected_api_route_id_missing"),
            ("route_bound_request_sent", False, "route_bound_request_not_sent"),
            ("route_bound_request_sha256", "", "route_bound_request_digest_missing"),
            ("provider_response_digest", "", "provider_response_digest_missing"),
            ("provider_response_digest", "0" * 64, "provider_response_digest_not_bound"),
            (
                "controlled_provider_response_sha256",
                "",
                "controlled_provider_response_digest_missing",
            ),
            (
                "controlled_provider_response_sha256",
                "0" * 64,
                "provider_response_digest_not_bound",
            ),
            (
                "dispatch_truth_source",
                "browser_supplied_dispatch",
                "dispatch_truth_source_invalid",
            ),
            (
                "api_lane_truth_source",
                "browser_supplied_api_lane",
                "api_lane_truth_source_invalid",
            ),
        ]

        for field, value, reason in cases:
            with self.subTest(field=field):
                source_packet = _dispatch_packet()
                source_packet[field] = value
                packet = handoff.build_approved_handoff_packet(source_packet)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    handoff.APPROVED_HANDOFF_DISPATCH_PROOF_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["source_dispatch_packet_valid"])
                self.assertFalse(packet["handoff_payload_prepared"])
                self.assertFalse(packet["handoff_ready"])
                self.assertFalse(packet["handoff_payload_sanitized"])
                _assert_no_false_product_claims(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_approved_handoff_blocks_self_consistent_forged_provider_digest(self) -> None:
        source_packet = _dispatch_packet()
        source_packet["provider_response_digest"] = "0" * 64
        source_packet["controlled_provider_response_sha256"] = "0" * 64

        packet = handoff.build_approved_handoff_packet(source_packet)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            handoff.APPROVED_HANDOFF_DISPATCH_PROOF_INVALID,
        )
        self.assertIn(
            "controlled_provider_response_digest_invalid",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["handoff_ready"])
        _assert_no_false_product_claims(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_approved_handoff_blocks_unapproved_surface(self) -> None:
        packet = handoff.build_approved_handoff_packet(
            _dispatch_packet(),
            handoff_surface_kind="browser_supplied_handoff",
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            handoff.APPROVED_HANDOFF_SURFACE_NOT_ALLOWED,
        )
        self.assertFalse(packet["handoff_surface_allowed"])
        self.assertIn("handoff_surface_not_allowed", packet["blocking_reasons"])
        self.assertFalse(packet["handoff_ready"])
        _assert_no_false_product_claims(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_approved_handoff_blocks_raw_prompt_route_and_provider_response_leaks(self) -> None:
        cases = [
            ({"raw_prompt_recorded": True, "prompt_text": PROMPT}, "raw_prompt_recorded"),
            (
                {"selected_api_route_id_recorded": True, "selected_api_route_id": ROUTE_ID},
                "selected_api_route_id_must_not_be_recorded",
            ),
            (
                {
                    "raw_provider_response_recorded": True,
                    "provider_response_text_recorded": True,
                    "provider_response_text": RAW_PROVIDER_RESPONSE,
                },
                "raw_provider_response_recorded",
            ),
        ]

        for mutation, reason in cases:
            with self.subTest(reason=reason):
                source_packet = _dispatch_packet()
                source_packet.update(mutation)
                packet = handoff.build_approved_handoff_packet(
                    source_packet,
                    secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_RESPONSE],
                )

                self.assertEqual(packet["status"], "error")
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["handoff_payload_prepared"])
                self.assertFalse(packet["handoff_ready"])
                _assert_no_false_product_claims(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(
                    packets.inspect_command_packet_semantics(
                        packet,
                        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_RESPONSE],
                    ),
                    [],
                )

    def test_approved_handoff_blocks_live_native_or_product_overclaim(self) -> None:
        cases = [
            ("live_provider_response_proven", "live_provider_response_must_not_be_claimed"),
            ("product_ready", "product_ready_must_not_be_claimed"),
            ("native_free_chat_router_proven", "native_free_chat_router_must_not_be_claimed"),
            ("custom_codex_origin_proven", "custom_codex_origin_must_not_be_claimed"),
        ]

        for field, reason in cases:
            with self.subTest(field=field):
                source_packet = _dispatch_packet()
                source_packet[field] = True
                packet = handoff.build_approved_handoff_packet(source_packet)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    handoff.APPROVED_HANDOFF_PAYLOAD_UNSAFE,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["handoff_ready"])
                _assert_no_false_product_claims(self, packet)
                _assert_no_raw_payload_data(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_approved_handoff_blocks_delivery_claim_without_observation(self) -> None:
        packet = handoff.build_approved_handoff_packet(
            _dispatch_packet(),
            handoff_delivered=True,
            handoff_delivery_observed=False,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            handoff.APPROVED_HANDOFF_DELIVERY_NOT_OBSERVED,
        )
        self.assertTrue(packet["handoff_delivered_requested"])
        self.assertFalse(packet["handoff_delivery_observed"])
        self.assertFalse(packet["handoff_delivered"])
        self.assertFalse(packet["handoff_ready"])
        self.assertIn("handoff_delivery_not_observed", packet["blocking_reasons"])
        _assert_no_false_product_claims(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_approved_handoff_cli_reads_context_file_and_emits_single_json(self) -> None:
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
                    "handoff",
                    "--prompt",
                    PROMPT,
                    "--handoff-surface-kind",
                    handoff.HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
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
        self.assertEqual(packet["packet_kind"], handoff.APPROVED_HANDOFF_PACKET_KIND)
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(
            packet["handoff_surface_kind"],
            handoff.HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
        )
        self.assertTrue(packet["handoff_ready"])
        self.assertFalse(packet["handoff_delivered"])
        _assert_no_false_product_claims(self, packet)
        _assert_no_raw_payload_data(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_router_hook_handoff_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "handoff",
                "--prompt",
                PROMPT,
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")


if __name__ == "__main__":
    unittest.main()
