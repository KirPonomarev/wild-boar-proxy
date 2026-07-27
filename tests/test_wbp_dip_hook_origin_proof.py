# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import real_user_prompt_submit_ledger_proof as ledger_proof
from wild_boar_proxy import wbp_dip_hook_origin_proof as proof
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text
from wild_boar_proxy.wbp_dip_tool import WBP_DIP_TOOL_OK, WBP_DIP_TOOL_PACKET_KIND


PROMPT = "Codex, дай задачу DIP: WBP hook-origin live dispatch proof."
OTHER_PROMPT = "Codex, дай задачу DIP: другой prompt."
ROUTE_ID = "wbp-deepseek-chat"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ledger_packet(
    *,
    prompt: str = PROMPT,
    custom_origin: bool = True,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    digest = _sha256(prompt)
    packet: dict[str, object] = {
        "packet_kind": ledger_proof.REAL_USER_PROMPT_SUBMIT_LEDGER_PROOF_PACKET_KIND,
        "status": "ok",
        "machine_error_code": ledger_proof.REAL_USER_PROMPT_SUBMIT_LEDGER_OK,
        "effect": "probe",
        "changed_files": [],
        "real_user_prompt_submit_ledger_proven": custom_origin,
        "custom_codex_flow_proven": custom_origin,
        "custom_codex_origin_proven": custom_origin,
        "user_prompt_submit_hook_ran": True,
        "hook_ledger_written": True,
        "hook_prompt_digest_bound": True,
        "hook_runtime_context_digest_bound": True,
        "thread_or_turn_digest_bound": True,
        "hook_config_digest_bound": True,
        "hook_event_transport_stdin": True,
        "prompt_digest": digest,
        "hook_prompt_digest": digest,
        "blocking_reasons": [],
        "custom_codex_ui_visibility_proven": False,
        "product_ready": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
    }
    packet.update(extra or {})
    return packet


def _wbp_dip_packet(
    *,
    prompt: str = PROMPT,
    alias: str = "DIP",
    ok: bool = True,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    packet: dict[str, object] = {
        "packet_kind": WBP_DIP_TOOL_PACKET_KIND,
        "status": "ok" if ok else "error",
        "machine_error_code": WBP_DIP_TOOL_OK if ok else "WBP_DIP_TOOL_FAILED",
        "effect": "mutate",
        "changed_files": ["proof/wbp-dip-tool.packet.json"],
        "expected_alias": alias,
        "task_sha256": _sha256(prompt),
        "delegate_to_dip_proven": True,
        "api_lane_called": True,
        "route_bound_dispatch_proven": True,
        "live_result_required": True,
        "live_result_available": True,
        "live_result_provider_called": True,
        "live_result_route_allowed": True,
        "live_result_machine_error_code": "OK",
        "live_result_text_sha256": _sha256("live answer"),
        "live_result_text_length": len("live answer"),
        "live_result_text_recorded": True,
        "live_result_route_id_recorded": False,
        "live_result_bridge_or_file_bridge_used": False,
        "live_result_runtime_context_bridge_used": False,
        "live_result_runtime_context_file_bridge_used": False,
        "direct_provider_auth_proven": True,
        "direct_provider_response_observed": True,
        "provider_auth_ok": True,
        "bridge_green_counts_as_provider_proof": False,
        "provider_auth_smoke_required_before_full_runner": True,
        "positive_provider_proof_gate_satisfied": True,
        "blocking_reasons": [],
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_task_recorded": False,
        "tool_call_arguments_recorded": False,
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "live_result_raw_backend_details_exposed": False,
        "live_result_secret_value_exposed": False,
        "command_argv_recorded": False,
        "codex_stdout_recorded": False,
        "codex_stderr_recorded": False,
    }
    packet.update(extra or {})
    return packet


def _metadata(prefix: str) -> dict[str, object]:
    return {
        f"{prefix}_file_read": True,
        f"{prefix}_file_valid_json": True,
        f"{prefix}_file_mapping": True,
        f"{prefix}_file_path_recorded": False,
    }


def _packet(
    *,
    prompt: str = PROMPT,
    ledger: dict[str, object] | None = None,
    dip: dict[str, object] | None = None,
    expected_alias: str = "DIP",
) -> dict[str, object]:
    return proof.build_wbp_dip_hook_origin_proof_packet(
        prompt_text=prompt,
        expected_alias=expected_alias,
        ledger_proof_packet=_ledger_packet() if ledger is None else ledger,
        wbp_dip_packet=_wbp_dip_packet() if dip is None else dip,
        ledger_proof_file_metadata=_metadata("ledger_proof"),
        wbp_dip_file_metadata=_metadata("wbp_dip_proof"),
        secret_values=[PROMPT, OTHER_PROMPT, ROUTE_ID],
    )


def _assert_no_prompt_or_route(testcase: unittest.TestCase, packet: dict[str, object]) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    testcase.assertNotIn(PROMPT, serialized)
    testcase.assertNotIn(OTHER_PROMPT, serialized)
    testcase.assertNotIn(ROUTE_ID, serialized)
    testcase.assertFalse(packet_contains_text(packet, PROMPT))
    testcase.assertFalse(packet_contains_text(packet, OTHER_PROMPT))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["live_result_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


class WbpDipHookOriginProofTests(unittest.TestCase):
    def test_positive_joins_real_hook_ledger_to_wbp_dip_live_dispatch(self) -> None:
        packet = _packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["packet_kind"], proof.WBP_DIP_HOOK_ORIGIN_PROOF_PACKET_KIND)
        self.assertTrue(packet["custom_codex_flow_proven"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["prompt_digest_bound_to_hook_ledger"])
        self.assertTrue(packet["prompt_digest_bound_to_wbp_dip_task"])
        self.assertTrue(packet["delegate_to_dip_proven"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["live_result_available"])
        self.assertTrue(packet["direct_provider_auth_proven"])
        self.assertTrue(packet["direct_provider_response_observed"])
        self.assertTrue(packet["positive_provider_proof_gate_satisfied"])
        self.assertTrue(packet["api_route_live_response_proven"])
        self.assertTrue(packet["positive_api_route_response_gate_satisfied"])
        self.assertFalse(packet["server_owned_bridge_or_file_bridge_response_proven"])
        self.assertFalse(packet["live_result_bridge_or_file_bridge_used"])
        self.assertTrue(packet["live_result_digest_bound"])
        self.assertFalse(packet["source_file_unforgeable"])
        self.assertFalse(packet["cryptographic_origin_proven"])
        self.assertTrue(packet["does_not_prove_source_file_unforgeable"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_prompt_or_route(self, packet)
        self.assertFalse(packet["live_result_text_recorded"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_bridge_backed_live_result_proves_api_route_response_not_direct_provider(
        self,
    ) -> None:
        packet = _packet(
            dip=_wbp_dip_packet(
                extra={
                    "live_result_bridge_or_file_bridge_used": True,
                    "live_result_runtime_context_file_bridge_used": True,
                    "direct_provider_auth_proven": False,
                    "direct_provider_response_observed": False,
                    "provider_auth_ok": False,
                    "positive_provider_proof_gate_satisfied": False,
                }
            )
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["live_result_available"])
        self.assertTrue(packet["server_owned_bridge_or_file_bridge_response_proven"])
        self.assertTrue(packet["api_route_live_response_proven"])
        self.assertTrue(packet["positive_api_route_response_gate_satisfied"])
        self.assertTrue(packet["live_result_bridge_or_file_bridge_used"])
        self.assertFalse(packet["direct_provider_auth_proven"])
        self.assertFalse(packet["direct_provider_response_observed"])
        self.assertFalse(packet["positive_provider_proof_gate_satisfied"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_prompt_or_route(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_digest_mismatch_blocks_join(self) -> None:
        packet = _packet(prompt=OTHER_PROMPT)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.WBP_DIP_HOOK_ORIGIN_DIGEST_MISMATCH,
        )
        self.assertIn("ledger_prompt_digest_not_bound_to_prompt", packet["blocking_reasons"])
        self.assertIn("wbp_dip_task_digest_not_bound_to_prompt", packet["blocking_reasons"])
        self.assertFalse(packet["custom_codex_flow_proven"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["live_result_available"])
        _assert_no_prompt_or_route(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_alias_mismatch_blocks_join_after_sources_are_green(self) -> None:
        packet = _packet(dip=_wbp_dip_packet(alias="Agent 2"), expected_alias="DIP")

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.WBP_DIP_HOOK_ORIGIN_ALIAS_MISMATCH,
        )
        self.assertIn("wbp_dip_expected_alias_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["expected_alias_bound"])
        self.assertFalse(packet["api_lane_called"])
        _assert_no_prompt_or_route(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unsafe_source_blocks_join_without_echoing_secret(self) -> None:
        packet = _packet(dip=_wbp_dip_packet(extra={"raw_prompt_recorded": True}))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.WBP_DIP_HOOK_ORIGIN_UNSAFE_SOURCE,
        )
        self.assertIn("wbp_dip_raw_prompt_recorded", packet["blocking_reasons"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["api_lane_called"])
        _assert_no_prompt_or_route(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unproven_ledger_blocks_before_dispatch_claim(self) -> None:
        packet = _packet(ledger=_ledger_packet(custom_origin=False))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.WBP_DIP_HOOK_ORIGIN_LEDGER_NOT_PROVEN,
        )
        self.assertIn("real_user_prompt_submit_ledger_not_proven", packet["blocking_reasons"])
        self.assertFalse(packet["custom_codex_flow_proven"])
        self.assertFalse(packet["delegate_to_dip_proven"])
        self.assertFalse(packet["api_lane_called"])
        _assert_no_prompt_or_route(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_reads_file_backed_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger_file = root / "ledger-proof.json"
            dip_file = root / "wbp-dip.json"
            ledger_file.write_text(json.dumps(_ledger_packet()) + "\n", encoding="utf-8")
            dip_file.write_text(json.dumps(_wbp_dip_packet()) + "\n", encoding="utf-8")
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "wbp-dip-hook-origin-proof",
                        "--prompt",
                        PROMPT,
                        "--ledger-proof-file",
                        str(ledger_file),
                        "--wbp-dip-proof-file",
                        str(dip_file),
                        "--json",
                    ]
                )

        self.assertEqual(exit_code, 0)
        packet = json.loads(stdout.getvalue())
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["ledger_proof_file_read"])
        self.assertTrue(packet["wbp_dip_proof_file_read"])
        self.assertTrue(packet["prompt_digest_bound_to_wbp_dip_task"])
        _assert_no_prompt_or_route(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])


if __name__ == "__main__":
    unittest.main()
