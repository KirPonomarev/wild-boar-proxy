# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wild_boar_proxy import codex_working_flow_delivery_proof as working_flow
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_custom_origin_bound_live_provider_join import (  # noqa: E402
    EXPECTED_TEXT,
    OTHER_PROMPT,
    OTHER_ROUTE_ID,
    PROMPT,
    RAW_PROVIDER_TEXT,
    ROUTE_ID,
    _packet as _custom_origin_live_provider_join_packet,
)

ROOT = Path(__file__).resolve().parents[1]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _file_metadata() -> dict[str, object]:
    return {
        "integrated_live_provider_proof_file_required": True,
        "integrated_live_provider_proof_file_present": True,
        "integrated_live_provider_proof_file_read": True,
        "integrated_live_provider_proof_file_valid_json": True,
        "integrated_live_provider_proof_file_mapping": True,
        "integrated_live_provider_proof_file_error_code": "",
        "integrated_live_provider_proof_file_path_recorded": False,
        "codex_exec_jsonl_file_required": True,
        "codex_exec_jsonl_file_present": True,
        "codex_exec_jsonl_file_read": True,
        "codex_exec_jsonl_file_valid_jsonl": True,
        "codex_exec_jsonl_file_error_code": "",
        "codex_exec_jsonl_file_path_recorded": False,
        "codex_exec_jsonl_parse_error_count": 0,
        "codex_exec_event_count": 5,
    }


def _delivery_payload(source: dict[str, object]) -> dict[str, object]:
    return working_flow._safe_working_flow_delivery_payload(source)


def _tool_result_event(structured_content: dict[str, object]) -> dict[str, object]:
    text = json.dumps(
        structured_content,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "type": "item.completed",
        "item": {
            "id": "item-custom-origin-live-provider-call",
            "type": "mcp_tool_call",
            "server": "wbp",
            "tool": "delegate_to_dip",
            "arguments": {
                "expected_alias": "DIP",
                "task_sha256": _sha256_text(PROMPT),
            },
            "status": "completed",
            "result": {
                "content": [{"type": "text", "text": text}],
                "structured_content": structured_content,
                "isError": False,
            },
        },
    }


def _assistant_event(handoff_digest: str) -> dict[str, object]:
    return {
        "type": "item.completed",
        "item": {
            "id": "item-custom-origin-live-provider-assistant",
            "type": "assistant_message",
            "role": "assistant",
            "status": "completed",
            "text": "WBP custom-origin live-provider handoff received.",
            "metadata": {"wbp_handoff_digest": handoff_digest},
        },
    }


def _events_for_source(
    source: dict[str, object],
    *,
    structured_content: dict[str, object] | None = None,
    assistant_digest: str | None = None,
) -> list[dict[str, object]]:
    structured = _delivery_payload(source) if structured_content is None else structured_content
    digest = str(
        structured["handoff_payload_sha256"] if assistant_digest is None else assistant_digest
    )
    return [
        {"type": "thread.started", "thread_id": "thread-custom-origin-live-provider"},
        {"type": "turn.started"},
        _tool_result_event(structured),
        _assistant_event(digest),
        {"type": "turn.completed"},
    ]


def _jsonl_from_events(events: list[dict[str, object]]) -> str:
    return "\n".join(json.dumps(event, ensure_ascii=True) for event in events)


def _assert_no_product_or_ui_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_ui"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


def _assert_no_raw_prompt_route_or_provider(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        PROMPT,
        OTHER_PROMPT,
        ROUTE_ID,
        OTHER_ROUTE_ID,
        EXPECTED_TEXT,
        RAW_PROVIDER_TEXT,
    ):
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["raw_jsonl_recorded"])
    testcase.assertFalse(packet["tool_call_arguments_recorded"])
    testcase.assertFalse(packet["route_candidate_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


class CustomOriginBoundWorkingFlowDeliveryProofTests(unittest.TestCase):
    def test_positive_accepts_custom_origin_bound_live_provider_join_source(
        self,
    ) -> None:
        source = _custom_origin_live_provider_join_packet()
        packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            _events_for_source(source),
            file_metadata=_file_metadata(),
            secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            working_flow.CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
        )
        self.assertTrue(packet["integrated_live_provider_proof_valid"])
        self.assertTrue(packet["custom_origin_bound_dispatch_proven"])
        self.assertTrue(packet["custom_origin_bound"])
        self.assertTrue(packet["custom_ui_origin_admitted"])
        self.assertTrue(packet["custom_codex_flow_origin_admitted"])
        self.assertTrue(packet["real_ledger_bound_api_dispatch_proven"])
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["live_provider_response_proven"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertTrue(packet["approved_handoff_ready"])
        self.assertTrue(packet["approved_handoff_payload_sanitized"])
        self.assertTrue(
            packet["approved_handoff_derived_from_custom_origin_live_provider_join"]
        )
        self.assertTrue(packet["handoff_delivered"])
        self.assertTrue(packet["delivery_observed"])
        self.assertTrue(packet["mcp_delivery_surface_proven"])
        self.assertTrue(packet["approved_delivery_surface_proven"])
        self.assertTrue(packet["live_provider_response_digest_bound_to_handoff"])
        self.assertTrue(packet["live_provider_response_digest_bound_to_delivery"])
        self.assertTrue(packet["controlled_provider_response_digest_bound_to_handoff"])
        self.assertTrue(packet["controlled_provider_response_digest_bound_to_delivery"])
        self.assertTrue(packet["assistant_response_bound_to_handoff_digest"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_custom_origin_live_provider_join_without_file_backed_metadata(
        self,
    ) -> None:
        source = _custom_origin_live_provider_join_packet()
        packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            _events_for_source(source),
            secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            working_flow.CODEX_WORKING_FLOW_INTEGRATED_PROOF_INVALID,
        )
        self.assertIn(
            "integrated_live_provider_proof_file_not_read",
            packet["blocking_reasons"],
        )
        self.assertIn("codex_exec_jsonl_file_not_read", packet["blocking_reasons"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_custom_origin_source_false_product_claim(self) -> None:
        source = _custom_origin_live_provider_join_packet()
        source["product_ready"] = True
        packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            _events_for_source(source),
            file_metadata=_file_metadata(),
            secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            working_flow.CODEX_WORKING_FLOW_INTEGRATED_PROOF_INVALID,
        )
        self.assertIn("product_ready_must_not_be_claimed", packet["blocking_reasons"])
        self.assertFalse(packet["approved_handoff_ready"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        _assert_no_product_or_ui_claim(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_missing_required_custom_origin_source_gates(self) -> None:
        cases = [
            ("custom_origin_bound_dispatch_proven", "custom_origin_bound_dispatch_not_proven"),
            ("same_allowed_route_binding", "allowed_route_binding_not_bound"),
            ("api_lane_provider_called", "api_lane_provider_not_called"),
            ("live_provider_cli_command_route_bound", "live_provider_cli_not_route_bound"),
            ("live_provider_response_bound_to_route", "live_provider_not_route_bound"),
            ("external_live_provider_response_proven", "external_live_provider_response_not_proven"),
        ]
        for field, reason in cases:
            with self.subTest(field=field):
                source = _custom_origin_live_provider_join_packet()
                source[field] = False
                packet = working_flow.build_codex_working_flow_delivery_proof_packet(
                    source,
                    _events_for_source(source),
                    file_metadata=_file_metadata(),
                    secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    working_flow.CODEX_WORKING_FLOW_INTEGRATED_PROOF_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["integrated_live_provider_proof_valid"])
                self.assertFalse(packet["codex_working_flow_delivery_proven"])
                _assert_no_product_or_ui_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_missing_required_custom_origin_source_digests(self) -> None:
        cases = [
            ("prompt_digest", "prompt_digest_missing"),
            ("selected_api_route_id_sha256", "selected_api_route_digest_missing"),
            ("controlled_provider_response_digest", "controlled_provider_response_digest_missing"),
            ("live_provider_response_digest", "live_provider_response_digest_missing"),
        ]
        for field, reason in cases:
            with self.subTest(field=field):
                source = _custom_origin_live_provider_join_packet()
                source[field] = ""
                packet = working_flow.build_codex_working_flow_delivery_proof_packet(
                    source,
                    _events_for_source(source),
                    file_metadata=_file_metadata(),
                    secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
                )

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    working_flow.CODEX_WORKING_FLOW_INTEGRATED_PROOF_INVALID,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["integrated_live_provider_proof_valid"])
                self.assertFalse(packet["codex_working_flow_delivery_proven"])
                _assert_no_product_or_ui_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_unbound_handoff_digest_from_custom_origin_source(self) -> None:
        source = _custom_origin_live_provider_join_packet()
        packet = working_flow.build_codex_working_flow_delivery_proof_packet(
            source,
            _events_for_source(source, assistant_digest="f" * 64),
            file_metadata=_file_metadata(),
            secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            working_flow.CODEX_WORKING_FLOW_DELIVERY_NOT_BOUND,
        )
        self.assertIn(
            "assistant_response_handoff_digest_mismatch",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["assistant_response_bound_to_handoff_digest"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_reads_custom_origin_live_provider_join_source(self) -> None:
        source = _custom_origin_live_provider_join_packet()
        events = _events_for_source(source)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "custom-origin-live-provider-join.json"
            jsonl_path = root / "codex-exec.jsonl"
            sentinel = root / "sentinel.txt"
            source_path.write_text(json.dumps(source) + "\n", encoding="utf-8")
            jsonl_path.write_text(_jsonl_from_events(events) + "\n", encoding="utf-8")
            sentinel.write_text("unchanged", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "working-flow-delivery-proof",
                    "--integrated-live-provider-proof-file",
                    str(source_path),
                    "--codex-exec-jsonl-file",
                    str(jsonl_path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            sentinel_text = sentinel.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sentinel_text, "unchanged")
        packet = json.loads(result.stdout)
        self.assertTrue(packet["integrated_live_provider_proof_file_read"])
        self.assertFalse(packet["integrated_live_provider_proof_file_path_recorded"])
        self.assertTrue(packet["codex_exec_jsonl_file_read"])
        self.assertFalse(packet["codex_exec_jsonl_file_path_recorded"])
        self.assertTrue(packet["custom_origin_bound_dispatch_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])


if __name__ == "__main__":
    unittest.main()
