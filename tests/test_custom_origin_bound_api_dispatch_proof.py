# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import io
import json
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import custom_origin_bound_api_dispatch_proof as proof
from wild_boar_proxy import custom_ui_origin_admission as origin_admission
from wild_boar_proxy import real_ledger_bound_api_dispatch_proof as dispatch_proof
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


PROMPT = "Codex, дай задачу DIP: prove custom-origin-bound API dispatch."
OTHER_PROMPT = "Codex, дай задачу DIP: different prompt."
ROUTE_ID = "wbp-deepseek-chat"
RAW_PROVIDER_TEXT = "raw provider text must never appear"


def _hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _origin_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "status": "ok",
        "exit_code": 0,
        "human_message": "custom origin",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "not_applicable",
        "severity": "recoverable",
        "operator_action": "none",
        "effect": "probe",
        "packet_kind": origin_admission.CUSTOM_UI_ORIGIN_ADMISSION_PACKET_KIND,
        "custom_ui_origin_admitted": True,
        "custom_codex_flow_origin_admitted": True,
        "fresh_user_prompt_submit_ledger_proven": True,
        "real_custom_app_submit_ledger_proven": True,
        "real_user_prompt_submit_ledger_proven": True,
        "hook_prompt_digest_bound": True,
        "hook_runtime_context_digest_bound": True,
        "thread_or_turn_digest_bound": True,
        "process_inventory_live": True,
        "wbp_clean_app_process_observed": True,
        "wbp_clean_app_server_process_observed": True,
        "prompt_digest": _hex(PROMPT),
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
        "native_free_chat_router_product_ready": False,
        "live_provider_proven": False,
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "blocking_reasons": [],
    }
    packet.update(overrides)
    return packet


def _dispatch_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "status": "ok",
        "exit_code": 0,
        "human_message": "ledger bound dispatch",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "not_applicable",
        "severity": "recoverable",
        "operator_action": "none",
        "effect": "probe",
        "packet_kind": dispatch_proof.REAL_LEDGER_BOUND_API_DISPATCH_PACKET_KIND,
        "real_ledger_bound_api_dispatch_proven": True,
        "ledger_bound_dispatch_admitted": True,
        "real_user_prompt_submit_ledger_proven": True,
        "custom_codex_origin_proven": True,
        "native_custom_codex_flow_proven": True,
        "native_router_hook_observed": True,
        "user_prompt_submit_hook_observed": True,
        "user_prompt_submit_hook_ran": True,
        "hook_ledger_written": True,
        "hook_prompt_digest_bound": True,
        "hook_runtime_context_digest_bound": True,
        "thread_or_turn_digest_bound": True,
        "prompt_digest": _hex(PROMPT),
        "prompt_digest_bound_to_ledger": True,
        "prompt_digest_bound_to_dispatch": True,
        "alias_context_read": True,
        "alias_bound": True,
        "selected_alias": "DIP",
        "selected_alias_lane": "api_route",
        "selected_slot": "dip",
        "route_id_allowed": True,
        "allowed_api_route_ids_enforced": True,
        "forbidden_stale_route_ids_count": 1,
        "api_lane_called": True,
        "api_lane_adapter_called": True,
        "api_lane_dispatch_admitted": True,
        "api_lane_provider_called": True,
        "api_response_received": True,
        "provider_response_proven": True,
        "controlled_provider_called": True,
        "controlled_provider_response_proven": True,
        "provider_like_response_only": True,
        "response_digest_bound": True,
        "response_bound_to_proof": True,
        "provider_response_digest": _hex("controlled provider response"),
        "controlled_provider_response_sha256": _hex("controlled provider response"),
        "dispatch_attempted": True,
        "dispatch_proven": True,
        "dispatch_status": "proven",
        "route_bound_dispatch_attempted": True,
        "route_bound_dispatch_proven": True,
        "route_bound_request_sent": True,
        "route_bound_request_sha256": _hex("route-bound request"),
        "dispatch_truth_source": "server_owned_controlled_provider_no_live_network",
        "api_lane_truth_source": "server_owned_controlled_route_bound_dispatch",
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "handoff_file_written": False,
        "handoff_delivered": False,
        "delivery_observed": False,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "blocking_reasons": [],
    }
    packet.update(overrides)
    return packet


def _packet(
    *,
    origin_packet: dict[str, object] | None = None,
    dispatch_packet: dict[str, object] | None = None,
    prompt: str = PROMPT,
    launch_surface: str = proof.LAUNCH_SURFACE_LAUNCHSERVICES_PROOF_HARNESS,
) -> dict[str, object]:
    return proof.build_custom_origin_bound_api_dispatch_proof_packet(
        custom_origin_packet=_origin_packet() if origin_packet is None else origin_packet,
        ledger_bound_dispatch_packet=(
            _dispatch_packet() if dispatch_packet is None else dispatch_packet
        ),
        prompt_text=prompt,
        launch_surface=launch_surface,
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
    testcase.assertFalse(packet["route_candidate_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


def _assert_no_product_handoff_or_live_claim(
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
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_live_provider"])
    testcase.assertTrue(packet["does_not_prove_handoff"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_ui"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


class CustomOriginBoundApiDispatchProofTests(unittest.TestCase):
    def test_positive_packet_binds_custom_origin_to_api_dispatch(self) -> None:
        packet = _packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            proof.CUSTOM_ORIGIN_BOUND_API_DISPATCH_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(
            packet["launch_surface"],
            proof.LAUNCH_SURFACE_LAUNCHSERVICES_PROOF_HARNESS,
        )
        self.assertTrue(packet["launch_surface_explicit"])
        self.assertTrue(packet["custom_ui_origin_admitted"])
        self.assertTrue(packet["fresh_user_prompt_submit_ledger_proven"])
        self.assertTrue(packet["custom_origin_bound"])
        self.assertTrue(packet["real_ledger_bound_api_dispatch_proven"])
        self.assertTrue(packet["prompt_digest_bound_to_custom_origin_and_dispatch"])
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["alias_resolved"])
        self.assertTrue(packet["alias_bound"])
        self.assertEqual(packet["selected_alias"], "DIP")
        self.assertEqual(packet["selected_alias_lane"], "api_route")
        self.assertEqual(packet["selected_slot"], "dip")
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["route_id_allowed"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["api_lane_dispatch_admitted"])
        self.assertTrue(packet["api_lane_provider_called"])
        self.assertTrue(packet["dispatch_attempted"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertEqual(packet["dispatch_status"], "proven")
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["provider_response_proven"])
        self.assertTrue(packet["controlled_provider_response_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        _assert_no_product_handoff_or_live_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_custom_origin_not_admitted_blocks_even_with_dispatch_packet(self) -> None:
        packet = _packet(
            origin_packet=_origin_packet(
                status="error",
                machine_error_code=(
                    origin_admission.CUSTOM_UI_ORIGIN_ADMISSION_LEDGER_NOT_PROVEN
                ),
                custom_ui_origin_admitted=False,
                custom_codex_flow_origin_admitted=False,
                fresh_user_prompt_submit_ledger_proven=False,
                blocking_reasons=["fresh_ledger_not_proven"],
            )
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.CUSTOM_ORIGIN_BOUND_API_DISPATCH_ORIGIN_NOT_PROVEN,
        )
        self.assertIn("custom_origin_packet_not_ok", packet["blocking_reasons"])
        self.assertFalse(packet["custom_origin_bound"])
        self.assertFalse(packet["custom_ui_origin_admitted"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["dispatch_attempted"])
        self.assertFalse(packet["dispatch_proven"])
        _assert_no_product_handoff_or_live_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_digest_mismatch_blocks_custom_origin_dispatch_join(self) -> None:
        packet = _packet(
            dispatch_packet=_dispatch_packet(prompt_digest=_hex(OTHER_PROMPT)),
            prompt=OTHER_PROMPT,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.CUSTOM_ORIGIN_BOUND_API_DISPATCH_DIGEST_MISMATCH,
        )
        self.assertIn(
            "custom_origin_dispatch_digest_mismatch",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["custom_origin_bound"])
        self.assertFalse(packet["prompt_digest_bound_to_custom_origin_and_dispatch"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["dispatch_proven"])
        _assert_no_product_handoff_or_live_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(
            self,
            packet,
            prompts=[PROMPT, OTHER_PROMPT],
        )
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unsafe_source_overclaim_blocks_join(self) -> None:
        packet = _packet(origin_packet=_origin_packet(product_ready=True))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.CUSTOM_ORIGIN_BOUND_API_DISPATCH_UNSAFE_SOURCE,
        )
        self.assertIn("source_must_not_claim_product_ready", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["custom_origin_bound"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["dispatch_proven"])
        _assert_no_product_handoff_or_live_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_invalid_launch_surface_blocks_join(self) -> None:
        packet = _packet(launch_surface="synthetic_app_server")

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.CUSTOM_ORIGIN_BOUND_API_DISPATCH_INVALID,
        )
        self.assertIn("launch_surface_not_admitted", packet["blocking_reasons"])
        self.assertFalse(packet["launch_surface_explicit"])
        self.assertFalse(packet["custom_origin_bound"])
        self.assertFalse(packet["api_lane_called"])
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_command_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "custom-origin-bound-dispatch-proof",
                "--prompt",
                PROMPT,
                "--ledger-mtime-before-ns",
                "1",
                "--launch-surface",
                proof.LAUNCH_SURFACE_LAUNCHSERVICES_PROOF_HARNESS,
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")

    def test_cli_dispatch_emits_custom_origin_bound_packet(self) -> None:
        expected = _packet()
        stdout = io.StringIO()

        with (
            mock.patch(
                "wild_boar_proxy.cli."
                "run_custom_origin_bound_api_dispatch_proof_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "custom-origin-bound-dispatch-proof",
                    "--prompt",
                    PROMPT,
                    "--ledger-mtime-before-ns",
                    "1",
                    "--launch-surface",
                    proof.LAUNCH_SURFACE_LAUNCHSERVICES_PROOF_HARNESS,
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertEqual(
            payload["packet_kind"],
            proof.CUSTOM_ORIGIN_BOUND_API_DISPATCH_PACKET_KIND,
        )
        self.assertTrue(payload["custom_origin_bound"])
        self.assertTrue(payload["api_lane_called"])
        run_command.assert_called_once()
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()
