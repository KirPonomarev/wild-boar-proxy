# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import official_mcp_ledger_bound_dispatch_join as proof
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_official_mcp_admission_proof import (  # noqa: E402
    _natural_case_packet,
    _positive_case_packet,
)
from test_real_ledger_bound_api_dispatch_proof import (  # noqa: E402
    _prepare_paths,
    _run_dispatch_proof,
)
from test_user_prompt_submit_hook_producer import ROUTE_ID  # noqa: E402


PROMPT = "Worker, make a short verification plan."
OTHER_PROMPT = "Worker, make a different verification plan."
RAW_PROVIDER_TEXT = "raw provider text must not appear"


def _hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ledger_bound_dispatch_packet(prompt: str = PROMPT) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as temp_dir:
        paths = _prepare_paths(Path(temp_dir), prompt=prompt)
        result = _run_dispatch_proof(paths, prompt=prompt)
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    packet = json.loads(result.stdout)
    if not isinstance(packet, dict):
        raise AssertionError("dispatch proof did not return a JSON object")
    return packet


def _packet(
    *,
    official_packet: dict[str, object] | None = None,
    dispatch_packet: dict[str, object] | None = None,
) -> dict[str, object]:
    return proof.build_official_mcp_ledger_bound_dispatch_join_packet(
        official_mcp_case_packet=(
            _natural_case_packet("Worker", PROMPT)
            if official_packet is None
            else official_packet
        ),
        ledger_bound_dispatch_packet=(
            _ledger_bound_dispatch_packet()
            if dispatch_packet is None
            else dispatch_packet
        ),
        secret_values=[PROMPT, OTHER_PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
    )


def _assert_no_raw_prompt_route_or_provider(
    testcase: unittest.TestCase,
    packet: dict[str, object],
    *,
    prompts: list[str] | None = None,
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    testcase.assertNotIn(ROUTE_ID, serialized)
    testcase.assertNotIn(RAW_PROVIDER_TEXT, serialized)
    for prompt in prompts or [PROMPT]:
        testcase.assertNotIn(prompt, serialized)
        testcase.assertFalse(packet_contains_text(packet, prompt))
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


def _assert_no_ui_handoff_live_or_product_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["live_provider_proven"])
    testcase.assertFalse(packet["live_provider_response_proven"])
    testcase.assertFalse(packet["external_live_provider_response_proven"])
    testcase.assertEqual(packet["live_provider_status"], "not_attempted")
    testcase.assertFalse(packet["handoff_file_written"])
    testcase.assertFalse(packet["handoff_delivered"])
    testcase.assertFalse(packet["delivery_observed"])
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["codex_working_flow_delivery_proven"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["native_free_chat_router_product_ready"])
    testcase.assertFalse(packet["native_free_chat_router_delivery_proven"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_live_provider"])
    testcase.assertTrue(packet["does_not_prove_handoff"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_ui"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


class OfficialMcpLedgerBoundDispatchJoinTests(unittest.TestCase):
    def test_positive_binds_natural_mcp_case_to_real_ledger_bound_dispatch(self) -> None:
        official_packet = _natural_case_packet("Worker", PROMPT)
        dispatch_packet = _ledger_bound_dispatch_packet()
        packet = _packet(
            official_packet=official_packet,
            dispatch_packet=dispatch_packet,
        )

        self.assertEqual(official_packet["prompt_sha256"], _hex(PROMPT))
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            proof.OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["official_natural_mcp_case_proven"])
        self.assertTrue(packet["official_natural_alias_intent_routed"])
        self.assertTrue(packet["strict_natural_prompt"])
        self.assertFalse(packet["explicit_tool_instruction_used"])
        self.assertTrue(packet["prompt_to_mcp_call_bound"])
        self.assertTrue(packet["intent_claim_digest_bound"])
        self.assertTrue(packet["tool_call_task_matches_intent"])
        self.assertTrue(packet["prompt_digest_bound_to_official_mcp_case"])
        self.assertTrue(packet["prompt_digest_bound_to_ledger"])
        self.assertTrue(packet["prompt_digest_bound_to_dispatch"])
        self.assertTrue(packet["prompt_digest_bound_to_official_mcp_and_ledger_dispatch"])
        self.assertEqual(packet["selected_alias"], "Worker")
        self.assertTrue(packet["official_dispatch_alias_bound"])
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["real_user_prompt_submit_ledger_proven"])
        self.assertTrue(packet["custom_codex_origin_proven"])
        self.assertTrue(packet["native_router_hook_observed"])
        self.assertTrue(packet["ledger_bound_dispatch_admitted"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["api_lane_dispatch_admitted"])
        self.assertTrue(packet["api_lane_provider_called"])
        self.assertTrue(packet["provider_response_proven"])
        self.assertTrue(packet["controlled_provider_response_proven"])
        self.assertTrue(packet["real_ledger_bound_api_dispatch_proven"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_ui_handoff_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_prompt_digest_mismatch_blocks_join(self) -> None:
        dispatch = _ledger_bound_dispatch_packet()
        dispatch["prompt_digest"] = _hex(OTHER_PROMPT)
        packet = _packet(dispatch_packet=dispatch)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_DIGEST_MISMATCH,
        )
        self.assertIn(
            "official_dispatch_prompt_digest_mismatch",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["prompt_digest_bound_to_official_mcp_and_ledger_dispatch"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["real_ledger_bound_api_dispatch_proven"])
        _assert_no_ui_handoff_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet, prompts=[PROMPT, OTHER_PROMPT])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_tool_directed_official_case_does_not_count_as_natural_join(self) -> None:
        packet = _packet(official_packet=_positive_case_packet("DIP"))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_OFFICIAL_NOT_PROVEN,
        )
        self.assertIn("natural_prompt_not_used", packet["blocking_reasons"])
        self.assertIn("strict_natural_prompt_not_proven", packet["blocking_reasons"])
        self.assertFalse(packet["official_natural_mcp_case_proven"])
        self.assertFalse(packet["api_lane_called"])
        _assert_no_ui_handoff_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_alias_mismatch_blocks_join_after_both_sources_are_otherwise_green(self) -> None:
        dispatch = _ledger_bound_dispatch_packet()
        dispatch["selected_alias"] = "DIP"
        packet = _packet(dispatch_packet=dispatch)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_ALIAS_MISMATCH,
        )
        self.assertIn("official_dispatch_alias_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["official_dispatch_alias_bound"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["real_ledger_bound_api_dispatch_proven"])
        _assert_no_ui_handoff_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unsafe_overclaim_blocks_join(self) -> None:
        official = _natural_case_packet("Worker", PROMPT)
        official["product_ready"] = True
        packet = _packet(official_packet=official)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_UNSAFE_SOURCE,
        )
        self.assertIn("official_product_ready", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["api_lane_called"])
        _assert_no_ui_handoff_live_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_official_case_file_blocks_cli_join(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dispatch_file = root / "dispatch.json"
            dispatch_file.write_text(
                json.dumps(_ledger_bound_dispatch_packet(), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "official-mcp-ledger-bound-dispatch-join",
                        "--official-mcp-case-file",
                        str(root / "missing-official.json"),
                        "--ledger-bound-dispatch-proof-file",
                        str(dispatch_file),
                        "--json",
                    ]
                )

        packet = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_OFFICIAL_NOT_PROVEN,
        )
        self.assertFalse(packet["official_mcp_case_file_present"])
        self.assertEqual(packet["official_mcp_case_file_error_code"], "official_mcp_case_file_missing")
        self.assertIn("official_mcp_case_packet_kind_invalid", packet["blocking_reasons"])
        self.assertFalse(packet["api_lane_called"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_dispatch_file_blocks_cli_join(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            official_file = root / "official.json"
            official_file.write_text(
                json.dumps(_natural_case_packet("Worker", PROMPT), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "official-mcp-ledger-bound-dispatch-join",
                        "--official-mcp-case-file",
                        str(official_file),
                        "--ledger-bound-dispatch-proof-file",
                        str(root / "missing-dispatch.json"),
                        "--json",
                    ]
                )

        packet = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_DISPATCH_NOT_PROVEN,
        )
        self.assertFalse(packet["ledger_bound_dispatch_proof_file_present"])
        self.assertEqual(
            packet["ledger_bound_dispatch_proof_file_error_code"],
            "ledger_bound_dispatch_proof_file_missing",
        )
        self.assertIn("ledger_bound_dispatch_packet_kind_invalid", packet["blocking_reasons"])
        self.assertFalse(packet["api_lane_called"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_malformed_dispatch_file_blocks_cli_join(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            official_file = root / "official.json"
            dispatch_file = root / "dispatch.json"
            official_file.write_text(
                json.dumps(_natural_case_packet("Worker", PROMPT), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            dispatch_file.write_text("{not-json\n", encoding="utf-8")
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "official-mcp-ledger-bound-dispatch-join",
                        "--official-mcp-case-file",
                        str(official_file),
                        "--ledger-bound-dispatch-proof-file",
                        str(dispatch_file),
                        "--json",
                    ]
                )

        packet = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_DISPATCH_NOT_PROVEN,
        )
        self.assertFalse(packet["ledger_bound_dispatch_proof_file_valid_json"])
        self.assertEqual(
            packet["ledger_bound_dispatch_proof_file_error_code"],
            "ledger_bound_dispatch_proof_file_invalid",
        )
        self.assertIn("ledger_bound_dispatch_packet_kind_invalid", packet["blocking_reasons"])
        self.assertFalse(packet["api_lane_called"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_non_mapping_official_case_file_blocks_cli_join(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            official_file = root / "official.json"
            dispatch_file = root / "dispatch.json"
            official_file.write_text("[]\n", encoding="utf-8")
            dispatch_file.write_text(
                json.dumps(_ledger_bound_dispatch_packet(), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "official-mcp-ledger-bound-dispatch-join",
                        "--official-mcp-case-file",
                        str(official_file),
                        "--ledger-bound-dispatch-proof-file",
                        str(dispatch_file),
                        "--json",
                    ]
                )

        packet = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_OFFICIAL_NOT_PROVEN,
        )
        self.assertFalse(packet["official_mcp_case_file_mapping"])
        self.assertEqual(
            packet["official_mcp_case_file_error_code"],
            "official_mcp_case_file_not_mapping",
        )
        self.assertIn("official_mcp_case_packet_kind_invalid", packet["blocking_reasons"])
        self.assertFalse(packet["api_lane_called"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_join_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "official-mcp-ledger-bound-dispatch-join",
                "--official-mcp-case-file",
                "official.json",
                "--ledger-bound-dispatch-proof-file",
                "dispatch.json",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")

    def test_cli_emits_join_packet(self) -> None:
        expected = _packet()
        stdout = io.StringIO()

        with (
            mock.patch(
                "wild_boar_proxy.cli."
                "run_official_mcp_ledger_bound_dispatch_join_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "official-mcp-ledger-bound-dispatch-join",
                    "--official-mcp-case-file",
                    "official.json",
                    "--ledger-bound-dispatch-proof-file",
                    "dispatch.json",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertEqual(
            payload["packet_kind"],
            proof.OFFICIAL_MCP_LEDGER_BOUND_DISPATCH_JOIN_PACKET_KIND,
        )
        self.assertTrue(payload["api_lane_called"])
        self.assertTrue(payload["prompt_digest_bound_to_official_mcp_and_ledger_dispatch"])
        run_command.assert_called_once()
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()
