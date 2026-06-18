# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import official_mcp_handoff_source_proof as proof
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_official_mcp_ledger_bound_dispatch_join import (  # noqa: E402
    PROMPT,
    RAW_PROVIDER_TEXT,
    ROUTE_ID,
    _packet as _dispatch_join_packet,
)


def _packet(
    *,
    dispatch_join_packet: dict[str, object] | None = None,
) -> dict[str, object]:
    return proof.build_official_mcp_handoff_source_proof_packet(
        dispatch_join_packet=(
            _dispatch_join_packet()
            if dispatch_join_packet is None
            else dispatch_join_packet
        ),
        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
    )


def _assert_no_raw_prompt_route_or_provider(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in (PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT):
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["raw_task_recorded"])
    testcase.assertFalse(packet["tool_call_arguments_recorded"])
    testcase.assertFalse(packet["route_candidate_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


def _assert_no_delivery_ui_live_or_product_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["handoff_file_written"])
    testcase.assertFalse(packet["handoff_delivered"])
    testcase.assertFalse(packet["delivery_observed"])
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["codex_working_flow_delivery_proven"])
    testcase.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["native_free_chat_router_product_ready"])
    testcase.assertFalse(packet["native_free_chat_router_delivery_proven"])
    testcase.assertFalse(packet["live_provider_proven"])
    testcase.assertFalse(packet["live_provider_response_proven"])
    testcase.assertFalse(packet["external_live_provider_response_proven"])
    testcase.assertEqual(packet["live_provider_status"], "not_attempted")
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_handoff_delivery"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_ui"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_live_provider"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


class OfficialMcpHandoffSourceProofTests(unittest.TestCase):
    def test_positive_binds_dispatch_join_to_approved_handoff_source(self) -> None:
        packet = _packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            proof.OFFICIAL_MCP_HANDOFF_SOURCE_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["dispatch_join_valid"])
        self.assertTrue(packet["official_natural_mcp_case_proven"])
        self.assertTrue(packet["dispatch_join_proven"])
        self.assertTrue(packet["dispatch_join_prompt_digest_bound"])
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["route_id_allowed"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["api_lane_dispatch_admitted"])
        self.assertTrue(packet["api_lane_provider_called"])
        self.assertTrue(packet["provider_response_proven"])
        self.assertTrue(packet["controlled_provider_response_proven"])
        self.assertTrue(packet["result_bound_to_dispatch"])
        self.assertTrue(packet["dispatch_attempted"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["real_ledger_bound_api_dispatch_proven"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["selected_api_route_id_present"])
        self.assertTrue(packet["selected_api_route_id_sha256"])
        self.assertTrue(packet["route_bound_request_sha256"])
        self.assertTrue(packet["provider_response_digest"])
        self.assertTrue(packet["controlled_provider_response_sha256"])
        self.assertEqual(
            packet["provider_response_digest"],
            packet["controlled_provider_response_sha256"],
        )
        self.assertEqual(
            packet["normalized_dispatch_packet_kind"],
            "wbp_controlled_api_dispatch_proof",
        )
        self.assertEqual(
            packet["approved_handoff_packet_kind"],
            "wbp_approved_handoff_proof",
        )
        self.assertTrue(packet["approved_handoff_ready"])
        self.assertTrue(packet["approved_handoff_payload_sanitized"])
        self.assertTrue(packet["approved_handoff_surface_used"])
        self.assertEqual(packet["handoff_surface_kind"], "mcp_tool_response")
        self.assertTrue(packet["handoff_source_digest_bound"])
        self.assertTrue(packet["working_flow_source_bound"])
        self.assertTrue(packet["approved_working_flow_source_bound"])
        self.assertFalse(packet["approved_visible_source_bound"])
        self.assertEqual(
            packet["handoff_payload_digest"],
            packet["expected_handoff_payload_digest"],
        )
        self.assertTrue(packet["handoff_payload_prepared"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_delivery_ui_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_provider_response_digest_mismatch_blocks_handoff_source(self) -> None:
        source = _dispatch_join_packet()
        source["controlled_provider_response_sha256"] = "f" * 64
        packet = _packet(dispatch_join_packet=source)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_HANDOFF_SOURCE_DISPATCH_JOIN_INVALID,
        )
        self.assertIn("provider_response_digest_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["dispatch_join_proven"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["handoff_source_digest_bound"])
        _assert_no_delivery_ui_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_response_digest_not_bound_blocks_handoff_source(self) -> None:
        source = _dispatch_join_packet()
        source["response_digest_bound"] = False
        packet = _packet(dispatch_join_packet=source)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_HANDOFF_SOURCE_DISPATCH_JOIN_INVALID,
        )
        self.assertIn("response_digest_not_bound", packet["blocking_reasons"])
        self.assertFalse(packet["dispatch_join_proven"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["handoff_source_digest_bound"])
        _assert_no_delivery_ui_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_dispatch_join_packet_contract_regressions_block_handoff_source(self) -> None:
        cases = {
            "wrong_packet_kind": ("packet_kind", "wrong", "dispatch_join_packet_kind_invalid"),
            "status_not_ok": ("status", "error", "dispatch_join_packet_not_ok"),
            "machine_error_not_ok": (
                "machine_error_code",
                "BROKEN",
                "dispatch_join_machine_error_not_ok",
            ),
            "effect_not_probe": ("effect", "mutate", "dispatch_join_effect_not_probe"),
            "changed_files_not_empty": (
                "changed_files",
                ["unexpected.json"],
                "dispatch_join_changed_files_not_empty",
            ),
        }
        for name, (field, value, reason) in cases.items():
            with self.subTest(name=name):
                source = _dispatch_join_packet()
                source[field] = value
                packet = _packet(dispatch_join_packet=source)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.OFFICIAL_MCP_HANDOFF_SOURCE_DISPATCH_JOIN_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["dispatch_join_proven"])
                self.assertFalse(packet["api_lane_called"])
                self.assertFalse(packet["approved_handoff_ready"])
                _assert_no_delivery_ui_live_or_product_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unsafe_product_ready_claim_blocks_handoff_source(self) -> None:
        source = _dispatch_join_packet()
        source["product_ready"] = True
        packet = _packet(dispatch_join_packet=source)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_HANDOFF_SOURCE_UNSAFE_SOURCE,
        )
        self.assertIn("product_ready_must_not_be_claimed", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["approved_handoff_ready"])
        _assert_no_delivery_ui_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_preclaimed_delivery_blocks_handoff_source(self) -> None:
        source = _dispatch_join_packet()
        source["handoff_delivered"] = True
        packet = _packet(dispatch_join_packet=source)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_HANDOFF_SOURCE_UNSAFE_SOURCE,
        )
        self.assertIn("handoff_must_not_be_preclaimed", packet["blocking_reasons"])
        self.assertFalse(packet["handoff_delivered"])
        self.assertFalse(packet["delivery_observed"])
        _assert_no_delivery_ui_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_dispatch_join_file_blocks_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "official-mcp-handoff-source-proof",
                        "--dispatch-join-file",
                        str(Path(temp_dir) / "missing-dispatch-join.json"),
                        "--json",
                    ]
                )

        packet = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_HANDOFF_SOURCE_DISPATCH_JOIN_INVALID,
        )
        self.assertFalse(packet["dispatch_join_file_present"])
        self.assertEqual(
            packet["dispatch_join_file_error_code"],
            "dispatch_join_file_missing",
        )
        self.assertIn("dispatch_join_packet_kind_invalid", packet["blocking_reasons"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["approved_handoff_ready"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_malformed_dispatch_join_file_blocks_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dispatch_join_file = root / "dispatch-join.json"
            dispatch_join_file.write_text("{not-json\n", encoding="utf-8")
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "official-mcp-handoff-source-proof",
                        "--dispatch-join-file",
                        str(dispatch_join_file),
                        "--json",
                    ]
                )

        packet = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_HANDOFF_SOURCE_DISPATCH_JOIN_INVALID,
        )
        self.assertFalse(packet["dispatch_join_file_valid_json"])
        self.assertEqual(
            packet["dispatch_join_file_error_code"],
            "dispatch_join_file_invalid",
        )
        self.assertFalse(packet["approved_handoff_ready"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_non_mapping_dispatch_join_file_blocks_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dispatch_join_file = root / "dispatch-join.json"
            dispatch_join_file.write_text("[]\n", encoding="utf-8")
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "official-mcp-handoff-source-proof",
                        "--dispatch-join-file",
                        str(dispatch_join_file),
                        "--json",
                    ]
                )

        packet = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_HANDOFF_SOURCE_DISPATCH_JOIN_INVALID,
        )
        self.assertFalse(packet["dispatch_join_file_mapping"])
        self.assertEqual(
            packet["dispatch_join_file_error_code"],
            "dispatch_join_file_not_mapping",
        )
        self.assertFalse(packet["approved_handoff_ready"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_handoff_source_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "official-mcp-handoff-source-proof",
                "--dispatch-join-file",
                "dispatch-join.json",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")

    def test_cli_emits_handoff_source_packet(self) -> None:
        expected = _packet()
        stdout = io.StringIO()

        with (
            mock.patch(
                "wild_boar_proxy.cli."
                "run_official_mcp_handoff_source_proof_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "official-mcp-handoff-source-proof",
                    "--dispatch-join-file",
                    "dispatch-join.json",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertEqual(
            payload["packet_kind"],
            proof.OFFICIAL_MCP_HANDOFF_SOURCE_PACKET_KIND,
        )
        self.assertTrue(payload["handoff_source_digest_bound"])
        self.assertFalse(payload["codex_working_flow_delivery_proven"])
        self.assertFalse(payload["product_ready"])
        run_command.assert_called_once()
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()
