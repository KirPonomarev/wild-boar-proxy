# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import real_custom_app_submit_ledger_proof as proof
from wild_boar_proxy import real_user_prompt_submit_ledger_proof as ledger_proof
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_user_prompt_submit_hook_producer import PROMPT, ROUTE_ID  # noqa: E402


def _hex(seed: str) -> str:
    return (seed * 64)[:64]


def _ledger_proof(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "status": "ok",
        "exit_code": 0,
        "human_message": "ledger proof",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "not_applicable",
        "severity": "recoverable",
        "operator_action": "none",
        "effect": "probe",
        "packet_kind": ledger_proof.REAL_USER_PROMPT_SUBMIT_LEDGER_PROOF_PACKET_KIND,
        "real_user_prompt_submit_ledger_proven": True,
        "custom_codex_origin_proven": True,
        "native_custom_codex_flow_proven": True,
        "user_prompt_submit_hook_ran": True,
        "hook_ledger_written": True,
        "hook_event_transport_stdin": True,
        "hook_prompt_digest_bound": True,
        "hook_runtime_context_digest_bound": True,
        "thread_or_turn_digest_bound": True,
        "hook_ledger_file_profile_owned": True,
        "codex_hook_trusted_by_profile_state": True,
        "prompt_digest": _hex("a"),
        "hook_parent_process_chain_observed": True,
        "hook_parent_process_chain_path_proven": True,
        "hook_parent_process_chain_exact_path_classified": True,
        "hook_parent_process_chain_digest": _hex("b"),
        "hook_parent_process_chain_length": 5,
        "hook_parent_process_chain_custom_wbp_clean_app": True,
        "hook_parent_process_chain_app_server": True,
        "hook_parent_process_chain_clean_root": True,
        "hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound": True,
        "hook_parent_process_chain_app_server_executable_path_bound": True,
        "hook_parent_process_chain_clean_root_executable_path_bound": True,
        "hook_parent_process_chain_stock_codex_app": False,
        "hook_parent_process_chain_command_text_substring_only": False,
        "hook_parent_process_raw_lines_recorded": False,
        "api_lane_called": False,
        "api_response_received": False,
        "dispatch_attempted": False,
        "dispatch_proven": False,
        "route_bound_dispatch_proven": False,
        "provider_response_proven": False,
        "handoff_file_written": False,
        "handoff_delivered": False,
        "delivery_observed": False,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "native_free_chat_router_proven": False,
        "live_provider_proven": False,
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }
    packet.update(overrides)
    return packet


def _process_inventory(*, stock_only: bool = False, missing_server: bool = False) -> dict[str, object]:
    if stock_only:
        return {
            "sample": [
                "111 /Applications/Codex.app/Contents/MacOS/Codex",
                "112 /Applications/Codex.app/Contents/Resources/codex app-server",
            ],
            "custom_process_lines": [],
            "default_process_lines": [
                "111 /Applications/Codex.app/Contents/MacOS/Codex",
            ],
        }
    sample = [
        "222 /Users/kirillponomarev/Applications/Codex WBP Clean.app/Contents/MacOS/Codex --user-data-dir=/profile/electron-user-data",
    ]
    if not missing_server:
        sample.append(
            "333 /Users/kirillponomarev/Applications/Codex WBP Clean.app/Contents/Resources/codex app-server --analytics-default-enabled"
        )
    return {
        "sample": sample,
        "custom_process_lines": sample,
        "default_process_lines": [],
    }


def _packet(
    *,
    ledger: dict[str, object] | None = None,
    process_inventory: dict[str, object] | None = None,
    before: int = 100,
    after: int = 200,
) -> dict[str, object]:
    return proof.build_real_custom_app_submit_ledger_proof_packet(
        ledger_proof_packet=_ledger_proof() if ledger is None else ledger,
        prompt_text=PROMPT,
        process_inventory=_process_inventory()
        if process_inventory is None
        else process_inventory,
        ledger_mtime_before_ns=before,
        ledger_mtime_after_ns=after,
        ledger_file_sha256=_hex("c"),
    )


def _assert_no_raw_prompt_route_or_product(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    testcase.assertNotIn(PROMPT, serialized)
    testcase.assertNotIn(ROUTE_ID, serialized)
    testcase.assertFalse(packet_contains_text(packet, PROMPT))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])
    testcase.assertFalse(packet["product_ready"])


class RealCustomAppSubmitLedgerProofTests(unittest.TestCase):
    def test_positive_clean_app_parent_chain_and_fresh_ledger_proves_gate_only(self) -> None:
        packet = _packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(
            packet["packet_kind"],
            proof.REAL_CUSTOM_APP_SUBMIT_LEDGER_PROOF_PACKET_KIND,
        )
        self.assertTrue(packet["real_custom_app_submit_ledger_proven"])
        self.assertTrue(packet["custom_app_submit_proven"])
        self.assertTrue(packet["custom_app_submit_ledger_gate_proven"])
        self.assertTrue(packet["real_user_prompt_submit_ledger_proven"])
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["thread_or_turn_digest_bound"])
        self.assertTrue(packet["hook_parent_process_chain_observed"])
        self.assertTrue(packet["hook_parent_process_chain_path_proven"])
        self.assertTrue(packet["hook_parent_process_chain_exact_path_classified"])
        self.assertTrue(packet["hook_parent_process_chain_custom_wbp_clean_app"])
        self.assertTrue(packet["hook_parent_process_chain_app_server"])
        self.assertTrue(packet["hook_parent_process_chain_clean_root"])
        self.assertTrue(
            packet[
                "hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound"
            ]
        )
        self.assertTrue(
            packet["hook_parent_process_chain_app_server_executable_path_bound"]
        )
        self.assertTrue(
            packet["hook_parent_process_chain_clean_root_executable_path_bound"]
        )
        self.assertFalse(packet["hook_parent_process_chain_stock_codex_app"])
        self.assertFalse(packet["hook_parent_process_chain_command_text_substring_only"])
        self.assertTrue(packet["wbp_clean_app_process_observed"])
        self.assertTrue(packet["wbp_clean_app_server_process_observed"])
        self.assertTrue(packet["ledger_newer_than_pre_submit_snapshot"])
        self.assertFalse(packet["source_file_unforgeable"])
        self.assertFalse(packet["cryptographic_app_submit_proven"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["dispatch_attempted"])
        self.assertEqual(packet["dispatch_status"], "not_attempted")
        self.assertFalse(packet["handoff_file_written"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertEqual(packet["changed_files"], [])
        _assert_no_raw_prompt_route_or_product(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_or_tui_ledger_without_clean_parent_chain_cannot_claim_app_submit(self) -> None:
        packet = _packet(
            ledger=_ledger_proof(
                hook_parent_process_chain_custom_wbp_clean_app=False,
                hook_parent_process_chain_app_server=False,
                hook_parent_process_chain_clean_root=False,
                hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound=False,
                hook_parent_process_chain_app_server_executable_path_bound=False,
                hook_parent_process_chain_clean_root_executable_path_bound=False,
            )
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.REAL_CUSTOM_APP_SUBMIT_LEDGER_APP_NOT_PROVEN,
        )
        self.assertFalse(packet["custom_app_submit_proven"])
        self.assertIn(
            "hook_parent_process_chain_not_wbp_clean_app",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "hook_parent_process_chain_app_server_not_observed",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "hook_parent_process_chain_app_server_path_not_bound",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["api_lane_called"])
        _assert_no_raw_prompt_route_or_product(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_substring_only_parent_chain_cannot_claim_app_submit(self) -> None:
        packet = _packet(
            ledger=_ledger_proof(
                hook_parent_process_chain_path_proven=False,
                hook_parent_process_chain_exact_path_classified=False,
                hook_parent_process_chain_custom_wbp_clean_app=True,
                hook_parent_process_chain_app_server=True,
                hook_parent_process_chain_clean_root=True,
                hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound=False,
                hook_parent_process_chain_app_server_executable_path_bound=False,
                hook_parent_process_chain_clean_root_executable_path_bound=False,
                hook_parent_process_chain_command_text_substring_only=True,
            )
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.REAL_CUSTOM_APP_SUBMIT_LEDGER_APP_NOT_PROVEN,
        )
        self.assertFalse(packet["custom_app_submit_proven"])
        self.assertIn(
            "hook_parent_process_chain_command_text_substring_only",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "hook_parent_process_chain_exact_path_not_classified",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "hook_parent_process_chain_app_server_path_not_bound",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_product(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_stock_app_process_inventory_is_rejected(self) -> None:
        packet = _packet(process_inventory=_process_inventory(stock_only=True))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.REAL_CUSTOM_APP_SUBMIT_LEDGER_APP_NOT_PROVEN,
        )
        self.assertFalse(packet["custom_app_submit_proven"])
        self.assertFalse(packet["wbp_clean_app_process_observed"])
        self.assertTrue(packet["stock_codex_app_process_observed"])
        self.assertIn("wbp_clean_app_process_not_observed", packet["blocking_reasons"])
        self.assertIn(
            "wbp_clean_app_server_process_not_observed",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "stock_codex_app_without_wbp_clean_rejected",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_product(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_clean_app_server_process_blocks_gate(self) -> None:
        packet = _packet(process_inventory=_process_inventory(missing_server=True))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.REAL_CUSTOM_APP_SUBMIT_LEDGER_APP_NOT_PROVEN,
        )
        self.assertTrue(packet["wbp_clean_app_process_observed"])
        self.assertFalse(packet["wbp_clean_app_server_process_observed"])
        self.assertIn(
            "wbp_clean_app_server_process_not_observed",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_product(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_stale_ledger_mtime_blocks_gate(self) -> None:
        packet = _packet(before=200, after=200)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.REAL_CUSTOM_APP_SUBMIT_LEDGER_STALE,
        )
        self.assertFalse(packet["custom_app_submit_proven"])
        self.assertFalse(packet["ledger_newer_than_pre_submit_snapshot"])
        self.assertIn(
            "hook_ledger_not_newer_than_pre_submit_snapshot",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_product(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_provided_process_inventory_file_cannot_green_live_app_claim(self) -> None:
        packet = proof.build_real_custom_app_submit_ledger_proof_packet(
            ledger_proof_packet=_ledger_proof(),
            prompt_text=PROMPT,
            process_inventory=_process_inventory(),
            ledger_mtime_before_ns=100,
            ledger_mtime_after_ns=200,
            ledger_file_sha256=_hex("c"),
            process_inventory_live=False,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.REAL_CUSTOM_APP_SUBMIT_LEDGER_APP_NOT_PROVEN,
        )
        self.assertFalse(packet["custom_app_submit_proven"])
        self.assertEqual(packet["process_inventory_source_kind"], "provided_file")
        self.assertFalse(packet["process_inventory_live"])
        self.assertIn("process_inventory_not_live", packet["blocking_reasons"])
        _assert_no_raw_prompt_route_or_product(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unsafe_ledger_overclaim_blocks_before_app_green(self) -> None:
        packet = _packet(ledger=_ledger_proof(product_ready=True))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.REAL_CUSTOM_APP_SUBMIT_LEDGER_UNSAFE_SOURCE,
        )
        self.assertFalse(packet["custom_app_submit_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertIn(
            "ledger_must_not_claim_product_ready",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_product(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_custom_app_submit_ledger_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "custom-app-submit-ledger-proof",
                "--prompt",
                PROMPT,
                "--ledger-mtime-before-ns",
                "1",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")

    def test_command_uses_explicit_custom_user_data_dir_for_live_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ledger = Path(tmp_dir) / "ledger.json"
            ledger.write_text("{}", encoding="utf-8")
            with (
                mock.patch(
                    "wild_boar_proxy.real_custom_app_submit_ledger_proof."
                    "run_real_user_prompt_submit_ledger_proof_command",
                    return_value=_ledger_proof(),
                ),
                mock.patch(
                    "wild_boar_proxy.real_custom_app_submit_ledger_proof."
                    "collect_codex_process_inventory",
                    return_value=_process_inventory(),
                ) as collect,
            ):
                packet = proof.run_real_custom_app_submit_ledger_proof_command(
                    paths=cli_mod.RuntimePaths.from_env(),
                    prompt_text=PROMPT,
                    ledger_mtime_before_ns=0,
                    hook_ledger_file=str(ledger),
                    custom_user_data_dir="/custom/profile/electron-user-data",
                )

        collect.assert_called_once_with(
            custom_user_data_dir="/custom/profile/electron-user-data"
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])


if __name__ == "__main__":
    unittest.main()
