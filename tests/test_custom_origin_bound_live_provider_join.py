# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import custom_origin_bound_api_dispatch_proof as dispatch_proof
from wild_boar_proxy import custom_origin_bound_live_provider_join as proof
from wild_boar_proxy import router_hook_entry
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


PROMPT = "Codex, дай задачу DIP: prove custom-origin-bound live provider join."
OTHER_PROMPT = "Codex, дай задачу DIP: different prompt."
ROUTE_ID = "wbp-deepseek-chat"
OTHER_ROUTE_ID = "wbp-other-route"
EXPECTED_TEXT = "WBP_LIVE_PROVIDER_JOIN_OK"
RAW_PROVIDER_TEXT = "raw provider response must never leak"


def _hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
        "deepseek_live_format_check_cli_command": [
            sys.executable,
            "-m",
            "wild_boar_proxy",
            "external-models",
            "live-format-check",
            "--route",
            ROUTE_ID,
            "--json",
        ],
        "forbidden_stale_route_ids": ["wbp-deepseek-v3"],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _prompt_digest(prompt: str = PROMPT) -> str:
    return _hex(prompt)


def _dispatch_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "status": "ok",
        "exit_code": 0,
        "human_message": "custom origin bound dispatch",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "not_applicable",
        "severity": "recoverable",
        "operator_action": "none",
        "effect": "probe",
        "packet_kind": dispatch_proof.CUSTOM_ORIGIN_BOUND_API_DISPATCH_PACKET_KIND,
        "custom_origin_bound": True,
        "custom_ui_origin_admitted": True,
        "custom_codex_flow_origin_admitted": True,
        "real_ledger_bound_api_dispatch_proven": True,
        "prompt_digest": _prompt_digest(),
        "prompt_digest_bound_to_custom_origin_and_dispatch": True,
        "alias_context_read": True,
        "alias_bound": True,
        "alias_resolved": True,
        "selected_alias": "DIP",
        "selected_alias_lane": "api_route",
        "selected_slot": "dip",
        "route_id_allowed": True,
        "allowed_api_route_ids_enforced": True,
        "selected_api_route_id_present": True,
        "selected_api_route_id_sha256": _hex(ROUTE_ID),
        "api_lane_called": True,
        "api_lane_dispatch_admitted": True,
        "api_lane_provider_called": True,
        "provider_response_proven": True,
        "controlled_provider_response_proven": True,
        "provider_response_digest": _hex("controlled provider response"),
        "dispatch_attempted": True,
        "dispatch_proven": True,
        "dispatch_status": "proven",
        "route_bound_dispatch_proven": True,
        "route_bound_request_sha256": _hex("route-bound request"),
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


def _live_provider_packet(
    *,
    route_id: str = ROUTE_ID,
    expected_text: str = EXPECTED_TEXT,
    expected_text_observed: bool = True,
    response_preview_bounded: str | None = None,
    fallback_used: bool = False,
    raw_provider_response_recorded: bool = False,
) -> dict[str, object]:
    response_preview = (
        expected_text if response_preview_bounded is None else response_preview_bounded
    )
    return packets.build_command_packet(
        ok=True,
        human_message=(
            "External-models route live format check captured one provider response "
            "without writing state or evidence."
        ),
        machine_error_code="OK",
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        effect="probe",
        extra={
            "data": {
                "check_kind": "api_only_live_route_format",
                "network_dependent": True,
                "verification_scope": "route_provider_only_no_write",
                "route_state": "live_response_observed_no_write",
                "requested_model": route_id,
                "effective_model": "deepseek-test",
                "provider": "deepseek",
                "fallback_used": fallback_used,
                "fallback_chain": [route_id],
                "cost_class": "free_or_limited",
                "latency_ms": 12,
                "request_count": 1,
                "retry_count": 0,
                "parallel_fanout_attempted": False,
                "expected_text": expected_text,
                "expected_text_observed": expected_text_observed,
                "response_preview_bounded": response_preview,
                "response_text_length": len(response_preview),
                "changed_files": [],
                "state_written": False,
                "evidence_written": False,
                "file_mutation_attempted": False,
                "commands_started_by_provider": False,
                "codex_history_sent": False,
                "repo_context_sent": False,
                "request_shape": "openai_chat_messages",
                "response_shape": "choices_message",
            },
            "raw_provider_response_recorded": raw_provider_response_recorded,
        },
    )


def _packet(
    *,
    prompt: str = PROMPT,
    runtime_context: dict[str, object] | None = None,
    dispatch_packet: dict[str, object] | None = None,
    live_provider_packet: dict[str, object] | None = None,
    expected_text: str = EXPECTED_TEXT,
) -> dict[str, object]:
    context = _runtime_context() if runtime_context is None else runtime_context
    return proof.build_custom_origin_bound_live_provider_join_packet(
        prompt_text=prompt,
        runtime_context=context,
        custom_origin_bound_dispatch_packet=(
            _dispatch_packet() if dispatch_packet is None else dispatch_packet
        ),
        live_provider_packet=(
            _live_provider_packet() if live_provider_packet is None else live_provider_packet
        ),
        live_provider_expected_text=expected_text,
        context_file_metadata={
            "runtime_context_file_read": True,
            "runtime_context_file_valid_json": True,
            "runtime_context_file_mapping": True,
        },
        dispatch_file_metadata={
            "custom_origin_bound_dispatch_proof_file_read": True,
            "custom_origin_bound_dispatch_proof_file_valid_json": True,
            "custom_origin_bound_dispatch_proof_file_mapping": True,
        },
        live_provider_file_metadata={
            "live_provider_proof_file_read": True,
            "live_provider_proof_file_valid_json": True,
            "live_provider_proof_file_mapping": True,
        },
        secret_values=[PROMPT, OTHER_PROMPT, ROUTE_ID, OTHER_ROUTE_ID, RAW_PROVIDER_TEXT],
    )


def _write_packet(path: Path, packet: dict[str, object]) -> None:
    path.write_text(json.dumps(packet) + "\n", encoding="utf-8")


def _assert_no_raw_prompt_route_or_provider(
    testcase: unittest.TestCase,
    packet: dict[str, object],
    *,
    expected_text: str = EXPECTED_TEXT,
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    testcase.assertNotIn(PROMPT, serialized)
    testcase.assertNotIn(OTHER_PROMPT, serialized)
    testcase.assertNotIn(ROUTE_ID, serialized)
    testcase.assertNotIn(OTHER_ROUTE_ID, serialized)
    testcase.assertNotIn(expected_text, serialized)
    testcase.assertNotIn(RAW_PROVIDER_TEXT, serialized)
    testcase.assertFalse(packet_contains_text(packet, PROMPT))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["route_candidate_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["live_provider_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


def _assert_no_product_handoff_or_visibility(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["handoff_file_written"])
    testcase.assertFalse(packet["handoff_delivered"])
    testcase.assertFalse(packet["delivery_observed"])
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["codex_working_flow_delivery_proven"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["native_free_chat_router_product_ready"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_handoff"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_ui"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


class CustomOriginBoundLiveProviderJoinTests(unittest.TestCase):
    def test_positive_packet_joins_custom_origin_dispatch_to_live_provider(self) -> None:
        packet = _packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            proof.CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["custom_origin_bound_dispatch_proven"])
        self.assertTrue(packet["custom_origin_bound"])
        self.assertTrue(packet["same_prompt_digest"])
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["alias_resolved"])
        self.assertTrue(packet["same_allowed_route_binding"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["live_provider_called"])
        self.assertTrue(packet["live_provider_proven"])
        self.assertTrue(packet["live_provider_response_proven"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertTrue(packet["response_digest_bound"])
        self.assertTrue(packet["response_digest_bound_to_expected_text"])
        self.assertEqual(packet["expected_text_digest"], _hex(EXPECTED_TEXT))
        self.assertEqual(packet["live_provider_response_digest"], _hex(EXPECTED_TEXT))
        self.assertEqual(packet["selected_api_route_id_sha256"], _hex(ROUTE_ID))
        self.assertEqual(packet["live_provider_route_id_sha256"], _hex(ROUTE_ID))
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        _assert_no_product_handoff_or_visibility(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_prompt_digest_mismatch_blocks_join(self) -> None:
        packet = _packet(
            prompt=OTHER_PROMPT,
            dispatch_packet=_dispatch_packet(prompt_digest=_prompt_digest(PROMPT)),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_DIGEST_MISMATCH,
        )
        self.assertIn("prompt_digest_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["same_prompt_digest"])
        self.assertFalse(packet["live_provider_called"])
        self.assertFalse(packet["live_provider_proven"])
        _assert_no_product_handoff_or_visibility(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_dispatch_without_route_digest_blocks_join(self) -> None:
        packet = _packet(
            dispatch_packet=_dispatch_packet(
                selected_api_route_id_present=False,
                selected_api_route_id_sha256="",
            )
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_DISPATCH_NOT_PROVEN,
        )
        self.assertIn("selected_api_route_id_digest_missing", packet["blocking_reasons"])
        self.assertFalse(packet["same_allowed_route_binding"])
        self.assertFalse(packet["live_provider_proven"])
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_live_provider_route_mismatch_blocks_join(self) -> None:
        packet = _packet(live_provider_packet=_live_provider_packet(route_id=OTHER_ROUTE_ID))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_ROUTE_MISMATCH,
        )
        self.assertIn("live_provider_route_digest_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["same_allowed_route_binding"])
        self.assertFalse(packet["live_provider_called"])
        self.assertFalse(packet["live_provider_proven"])
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_route_outside_allowlist_blocks_join(self) -> None:
        packet = _packet(runtime_context=_runtime_context(allowed_routes=[OTHER_ROUTE_ID]))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_ROUTE_MISMATCH,
        )
        self.assertIn("selected_route_not_allowed", packet["blocking_reasons"])
        self.assertFalse(packet["same_allowed_route_binding"])
        self.assertFalse(packet["live_provider_proven"])
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_live_provider_expected_text_not_observed_blocks_join(self) -> None:
        packet = _packet(
            live_provider_packet=_live_provider_packet(expected_text_observed=False)
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_LIVE_PROVIDER_NOT_PROVEN,
        )
        self.assertIn(
            "live_provider_expected_text_not_observed",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["live_provider_called"])
        self.assertFalse(packet["live_provider_proven"])
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_live_provider_response_preview_mismatch_blocks_join(self) -> None:
        packet = _packet(
            live_provider_packet=_live_provider_packet(
                response_preview_bounded="DIFFERENT_MARKER"
            )
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_LIVE_PROVIDER_NOT_PROVEN,
        )
        self.assertIn(
            "live_provider_response_preview_mismatch",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["response_digest_bound"])
        self.assertFalse(packet["live_provider_proven"])
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_live_provider_fallback_blocks_join(self) -> None:
        packet = _packet(live_provider_packet=_live_provider_packet(fallback_used=True))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_LIVE_PROVIDER_NOT_PROVEN,
        )
        self.assertIn("live_provider_fallback_used", packet["blocking_reasons"])
        self.assertFalse(packet["live_provider_proven"])
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unsafe_live_provider_overclaim_blocks_join(self) -> None:
        packet = _packet(
            live_provider_packet=_live_provider_packet(
                raw_provider_response_recorded=True,
                response_preview_bounded=RAW_PROVIDER_TEXT,
            )
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_UNSAFE_SOURCE,
        )
        self.assertIn("live_provider_raw_response_recorded", packet["blocking_reasons"])
        self.assertFalse(packet["live_provider_proven"])
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_command_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "custom-origin-bound-live-provider-join",
                "--prompt",
                PROMPT,
                "--runtime-context-file",
                "/tmp/context.json",
                "--custom-origin-bound-dispatch-proof-file",
                "/tmp/dispatch.json",
                "--live-provider-proof-file",
                "/tmp/live.json",
                "--live-provider-expected-text",
                EXPECTED_TEXT,
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")

    def test_cli_dispatch_emits_join_packet(self) -> None:
        expected = _packet()
        stdout = io.StringIO()

        with (
            mock.patch(
                "wild_boar_proxy.cli."
                "run_custom_origin_bound_live_provider_join_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "custom-origin-bound-live-provider-join",
                    "--prompt",
                    PROMPT,
                    "--runtime-context-file",
                    "/tmp/context.json",
                    "--custom-origin-bound-dispatch-proof-file",
                    "/tmp/dispatch.json",
                    "--live-provider-proof-file",
                    "/tmp/live.json",
                    "--live-provider-expected-text",
                    EXPECTED_TEXT,
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertEqual(
            payload["packet_kind"],
            proof.CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_PACKET_KIND,
        )
        self.assertTrue(payload["custom_origin_bound_dispatch_proven"])
        self.assertTrue(payload["live_provider_response_proven"])
        run_command.assert_called_once()
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])

    def test_file_backed_command_reads_context_and_packets_without_path_leak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context_path = root / router_hook_entry.RUNTIME_CONTEXT_FILENAME
            dispatch_path = root / "dispatch-proof.json"
            live_path = root / "live-proof.json"
            context_path.write_text(json.dumps(_runtime_context()) + "\n", encoding="utf-8")
            _write_packet(dispatch_path, _dispatch_packet())
            _write_packet(live_path, _live_provider_packet())

            packet = proof.run_custom_origin_bound_live_provider_join_command(
                paths=mock.Mock(profile_dir=root),
                prompt_text=PROMPT,
                runtime_context_file=str(context_path),
                custom_origin_bound_dispatch_proof_file=str(dispatch_path),
                live_provider_proof_file=str(live_path),
                live_provider_expected_text=EXPECTED_TEXT,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["runtime_context_file_read"])
        self.assertTrue(packet["custom_origin_bound_dispatch_proof_file_read"])
        self.assertTrue(packet["live_provider_proof_file_read"])
        self.assertFalse(packet["runtime_context_file_path_recorded"])
        self.assertFalse(packet["custom_origin_bound_dispatch_proof_file_path_recorded"])
        self.assertFalse(packet["live_provider_proof_file_path_recorded"])
        self.assertTrue(packet["live_provider_response_proven"])
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])


if __name__ == "__main__":
    unittest.main()
