# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

from wild_boar_proxy import native_custom_codex_visible_flow_proof as proof
from wild_boar_proxy.codex_working_flow_delivery_proof import (
    CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
)
from wild_boar_proxy.natural_intent_contract import packet_contains_text

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_custom_codex_ui_visibility_proof import _native_packet


HANDOFF_DIGEST = "a" * 64
REQUEST_ID = "fresh-sealed-20260622070000"
EXPECTED_VISIBLE_TEXT = f"WBP_FRESH_SEALED_VISIBLE_{HANDOFF_DIGEST}_{REQUEST_ID}"


def _metadata() -> dict[str, object]:
    return {
        "working_flow_delivery_proof_file_required": True,
        "working_flow_delivery_proof_file_present": True,
        "working_flow_delivery_proof_file_read": True,
        "working_flow_delivery_proof_file_valid_json": True,
        "working_flow_delivery_proof_file_mapping": True,
        "working_flow_delivery_proof_file_error_code": "",
        "working_flow_delivery_proof_file_path_recorded": False,
        "native_ui_observer_packet_file_required": True,
        "native_ui_observer_packet_file_present": True,
        "native_ui_observer_packet_file_read": True,
        "native_ui_observer_packet_file_valid_json": True,
        "native_ui_observer_packet_file_mapping": True,
        "native_ui_observer_packet_file_error_code": "",
        "native_ui_observer_packet_file_path_recorded": False,
    }


def _working_flow_packet(overrides: dict[str, object] | None = None) -> dict[str, object]:
    packet: dict[str, object] = {
        "status": "ok",
        "exit_code": 0,
        "human_message": "working flow delivered",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "not_applicable",
        "severity": "recoverable",
        "operator_action": "none",
        "effect": "probe",
        "packet_kind": CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
        "codex_working_flow_delivery_proven": True,
        "approved_delivery_surface_proven": True,
        "approved_handoff_ready": True,
        "approved_handoff_payload_sanitized": True,
        "handoff_delivered": True,
        "delivery_observed": True,
        "live_provider_response_digest_bound_to_handoff": True,
        "codex_exec_assistant_continuation_proven": True,
        "mcp_delivery_surface_proven": False,
        "command_execution_delivery_surface_proven": True,
        "working_flow_delivery_surface_kind": (
            "codex_command_execution_external_models_live_format_check"
        ),
        "handoff_payload_digest": HANDOFF_DIGEST,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }
    if overrides:
        packet.update(overrides)
    return packet


class NativeCustomCodexVisibleFlowProofTests(unittest.TestCase):
    def test_positive_binds_native_visible_response_to_core_handoff(self) -> None:
        packet = proof.build_native_custom_codex_visible_flow_proof_packet(
            _working_flow_packet(),
            _native_packet(
                expected_text=EXPECTED_VISIBLE_TEXT,
                request_id=REQUEST_ID,
            ),
            expected_visible_text=EXPECTED_VISIBLE_TEXT,
            request_id=REQUEST_ID,
            file_metadata=_metadata(),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["native_custom_codex_visible_flow_proven"])
        self.assertTrue(packet["custom_codex_ui_visibility_proven"])
        self.assertTrue(packet["command_execution_delivery_surface_accepted"])
        self.assertTrue(packet["visible_response_bound_to_handoff"])
        self.assertTrue(packet["visible_response_after_dispatch"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["expected_visible_text_recorded"])
        self.assertFalse(packet_contains_text(packet, EXPECTED_VISIBLE_TEXT))

    def test_rejects_visible_text_not_bound_to_handoff_digest(self) -> None:
        packet = proof.build_native_custom_codex_visible_flow_proof_packet(
            _working_flow_packet(),
            _native_packet(
                expected_text="WBP_FRESH_SEALED_VISIBLE_wrong",
                request_id=REQUEST_ID,
            ),
            expected_visible_text="WBP_FRESH_SEALED_VISIBLE_wrong",
            request_id=REQUEST_ID,
            file_metadata=_metadata(),
        )

        self.assertEqual(
            packet["machine_error_code"],
            proof.NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_NOT_BOUND,
        )
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertIn(
            "expected_visible_text_not_bound_to_handoff",
            packet["binding_failures"],
        )

    def test_rejects_native_unsafe_claims(self) -> None:
        packet = proof.build_native_custom_codex_visible_flow_proof_packet(
            _working_flow_packet(),
            _native_packet(
                expected_text=EXPECTED_VISIBLE_TEXT,
                request_id=REQUEST_ID,
                overrides={"product_ready": True},
            ),
            expected_visible_text=EXPECTED_VISIBLE_TEXT,
            request_id=REQUEST_ID,
            file_metadata=_metadata(),
        )

        self.assertEqual(
            packet["machine_error_code"],
            proof.NATIVE_CUSTOM_CODEX_VISIBLE_FLOW_PAYLOAD_UNSAFE,
        )
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertIn("native_preclaimed_product_ready", packet["unsafe_failures"])

    def test_command_reads_file_backed_packets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            working_file = root / "working.json"
            native_file = root / "native.json"
            working_file.write_text(
                json.dumps(_working_flow_packet()),
                encoding="utf-8",
            )
            native_file.write_text(
                json.dumps(
                    _native_packet(
                        expected_text=EXPECTED_VISIBLE_TEXT,
                        request_id=REQUEST_ID,
                    )
                ),
                encoding="utf-8",
            )

            packet = proof.run_native_custom_codex_visible_flow_proof_command(
                working_flow_delivery_proof_file=str(working_file),
                native_ui_observer_packet_file=str(native_file),
                expected_visible_text=EXPECTED_VISIBLE_TEXT,
                request_id=REQUEST_ID,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["working_flow_delivery_file_backed"])
        self.assertTrue(packet["native_ui_observer_file_backed"])


if __name__ == "__main__":
    unittest.main()
