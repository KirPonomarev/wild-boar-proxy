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

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import custom_codex_ui_visibility_proof as ui_visibility
from wild_boar_proxy import custom_codex_visible_source_binding_proof as source_binding
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_DIGEST = "a" * 64
REQUEST_ID = "wbp-ui-visible-20260618-0219"
EXPECTED_VISIBLE_TEXT = f"WBP_UI_VISIBLE_{HANDOFF_DIGEST}_{REQUEST_ID}"


def _file_metadata() -> dict[str, object]:
    return {
        "visible_source_binding_proof_file_required": True,
        "visible_source_binding_proof_file_present": True,
        "visible_source_binding_proof_file_read": True,
        "visible_source_binding_proof_file_valid_json": True,
        "visible_source_binding_proof_file_mapping": True,
        "visible_source_binding_proof_file_error_code": "",
        "visible_source_binding_proof_file_path_recorded": False,
        "native_ui_observer_packet_file_required": True,
        "native_ui_observer_packet_file_present": True,
        "native_ui_observer_packet_file_read": True,
        "native_ui_observer_packet_file_valid_json": True,
        "native_ui_observer_packet_file_mapping": True,
        "native_ui_observer_packet_file_error_code": "",
        "native_ui_observer_packet_file_path_recorded": False,
    }


def _source_packet(overrides: dict[str, object] | None = None) -> dict[str, object]:
    packet: dict[str, object] = {
        "status": "ok",
        "exit_code": 0,
        "human_message": "visible source bound",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "not_applicable",
        "severity": "recoverable",
        "operator_action": "none",
        "effect": "probe",
        "schema_version": 1,
        "packet_kind": source_binding.CUSTOM_CODEX_VISIBLE_SOURCE_BINDING_PACKET_KIND,
        "visible_source_binding_proven": True,
        "custom_codex_visible_source_binding_proven": True,
        "visible_source_observed": True,
        "visible_source_bound_to_handoff": True,
        "visible_source_after_delivery": True,
        "visible_source_marker_digest": HANDOFF_DIGEST,
        "handoff_payload_digest": HANDOFF_DIGEST,
        "handoff_payload_digest_present": True,
        "working_flow_delivery_proven": True,
        "codex_working_flow_delivery_proven": True,
        "approved_delivery_surface_proven": True,
        "mcp_delivery_surface_proven": True,
        "approved_handoff_ready": True,
        "approved_handoff_payload_sanitized": True,
        "handoff_delivered": True,
        "delivery_observed": True,
        "codex_exec_assistant_continuation_proven": True,
        "assistant_response_bound_to_handoff_digest": True,
        "live_provider_response_digest_bound_to_handoff": True,
        "route_secret_screening_proven": True,
        "no_secret_exposed": True,
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
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "visible_source_secret_value_present": False,
        "visible_source_route_secret_value_present": False,
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "blocking_reasons": [],
        "working_flow_delivery_failures": [],
        "source_unsafe_claim_failures": [],
        "visible_source_event_unsafe_failures": [],
    }
    if overrides:
        packet.update(overrides)
    return packet


def _native_packet(
    *,
    expected_text: str = EXPECTED_VISIBLE_TEXT,
    request_id: str = REQUEST_ID,
    overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    packet: dict[str, object] = {
        "schema_version": 1,
        "packet_kind": ui_visibility.NATIVE_UI_SOURCE_CUSTOM_CODEX_NATIVE_PROMPT_SUBMIT,
        "status": "ok",
        "exit_code": 0,
        "human_message": "native prompt submitted",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "not_applicable",
        "severity": "recoverable",
        "operator_action": "none",
        "request_id": request_id,
        "cdp_port_owner_bound_to_custom_profile": True,
        "cdp_localhost_only": True,
        "cdp_endpoint_redacted": True,
        "cdp_target_bound_to_custom_launch": True,
        "native_window_observed": True,
        "input_capable_ui_observed": True,
        "native_app_usable": True,
        "input_text_insert_attempted": True,
        "input_text_insert_succeeded": True,
        "prompt_submitted": True,
        "assistant_turn_probe_attempted": True,
        "assistant_turn_probe_scan_performed": True,
        "assistant_turn_activity_observed": True,
        "assistant_turn_started_observed": True,
        "assistant_turn_completed_observed": True,
        "assistant_turn_activity_ended_observed": True,
        "assistant_turn_post_completion_scan_performed": True,
        "assistant_turn_last_scan_active": True,
        "assistant_turn_failed_observed": False,
        "assistant_turn_machine_error_code": "OK",
        "assistant_turn_progress_candidate_count": 0,
        "assistant_turn_stop_generating_candidate_count": 1,
        "auth_or_backend_blocker_observed": False,
        "model_or_runtime_blocker_observed": False,
        "response_surface_candidate_count": 1,
        "custom_response_observer_attempted": True,
        "custom_response_observer_scan_performed": True,
        "custom_response_text_read_without_storing": True,
        "custom_codex_response_text_read_proven": True,
        "custom_response_exact_token_observed": True,
        "custom_response_bound_to_request": True,
        "native_codex_subagent_absence_proven": True,
        "native_codex_subagent_used_as_dip": False,
        "native_free_text_observer_source": "bounded_cdp_response_token_scan",
        "native_free_text_observer_machine_error_code": "OK",
        "custom_response_expected_sha256": hashlib.sha256(
            expected_text.encode("utf-8")
        ).hexdigest(),
        "custom_response_exact_token_candidate_count": 1,
        "custom_response_like_candidate_count": 1,
        "custom_response_token_leaf_candidate_count": 1,
        "custom_response_prompt_echo_candidate_count": 0,
        "custom_response_prompt_suffix_echo_candidate_count": 0,
        "blocking_reasons": [],
        "raw_dom_exposed": False,
        "raw_ax_tree_exposed": False,
        "browser_cdp_authority_widened": False,
        "prompt_text_recorded": False,
        "raw_prompt_recorded": False,
        "text_value_captured": False,
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "fallback_used": False,
        "local_imitation_used": False,
    }
    if overrides:
        packet.update(overrides)
    return packet


class CustomCodexUiVisibilityProofTests(unittest.TestCase):
    def test_positive_binds_real_custom_ui_token_to_handoff(self) -> None:
        packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
            _source_packet(),
            _native_packet(),
            expected_visible_text=EXPECTED_VISIBLE_TEXT,
            request_id=REQUEST_ID,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["source_packet_file_backed"])
        self.assertTrue(packet["native_ui_observer_file_backed"])
        self.assertTrue(packet["custom_codex_process_bound"])
        self.assertTrue(packet["custom_codex_window_observed"])
        self.assertTrue(packet["custom_codex_profile_bound"])
        self.assertTrue(packet["visible_response_observed"])
        self.assertTrue(packet["visible_response_bound_to_handoff"])
        self.assertTrue(packet["visible_response_after_dispatch"])
        self.assertTrue(packet["stale_visibility_rejected"])
        self.assertTrue(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["expected_visible_text_recorded"])
        serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(EXPECTED_VISIBLE_TEXT, serialized)
        self.assertFalse(packet_contains_text(packet, EXPECTED_VISIBLE_TEXT))
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_token_leaf_without_exact_response_as_prompt_echo_diagnostic(self) -> None:
        packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
            _source_packet(),
            _native_packet(
                overrides={
                    "custom_codex_response_text_read_proven": False,
                    "custom_response_exact_token_observed": False,
                    "custom_response_bound_to_request": False,
                    "assistant_turn_activity_observed": False,
                    "assistant_turn_started_observed": False,
                    "assistant_turn_completed_observed": False,
                    "assistant_turn_activity_ended_observed": False,
                    "assistant_turn_post_completion_scan_performed": False,
                    "assistant_turn_last_scan_active": False,
                    "assistant_turn_failed_observed": False,
                    "assistant_turn_machine_error_code": (
                        "CUSTOM_NATIVE_ASSISTANT_TURN_PROMPT_ECHO_ONLY"
                    ),
                    "assistant_turn_progress_candidate_count": 0,
                    "assistant_turn_stop_generating_candidate_count": 0,
                    "response_surface_candidate_count": 0,
                    "native_codex_subagent_absence_proven": False,
                    "native_free_text_observer_machine_error_code": (
                        "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN"
                    ),
                    "custom_response_token_leaf_candidate_count": 1,
                    "custom_response_prompt_echo_candidate_count": 1,
                    "custom_response_prompt_suffix_echo_candidate_count": 1,
                    "custom_response_exact_token_candidate_count": 0,
                    "custom_response_like_candidate_count": 0,
                }
            ),
            expected_visible_text=EXPECTED_VISIBLE_TEXT,
            request_id=REQUEST_ID,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(
            packet["machine_error_code"],
            ui_visibility.CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_NOT_OBSERVED,
        )
        self.assertIn("custom_response_exact_token_not_observed", packet["blocking_reasons"])
        self.assertIn("custom_response_exact_token_candidate_missing", packet["blocking_reasons"])
        self.assertEqual(packet["custom_response_token_leaf_candidate_count"], 1)
        self.assertEqual(packet["custom_response_prompt_echo_candidate_count"], 1)
        self.assertEqual(packet["custom_response_prompt_suffix_echo_candidate_count"], 1)
        self.assertFalse(packet["assistant_turn_activity_observed"])
        self.assertFalse(packet["assistant_turn_started_observed"])
        self.assertFalse(packet["assistant_turn_completed_observed"])
        self.assertEqual(
            packet["assistant_turn_machine_error_code"],
            "CUSTOM_NATIVE_ASSISTANT_TURN_PROMPT_ECHO_ONLY",
        )
        self.assertEqual(packet["assistant_turn_progress_candidate_count"], 0)
        self.assertEqual(packet["assistant_turn_stop_generating_candidate_count"], 0)
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(EXPECTED_VISIBLE_TEXT, serialized)
        self.assertFalse(packet_contains_text(packet, EXPECTED_VISIBLE_TEXT))
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_turn_completion_without_exact_response_token(self) -> None:
        packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
            _source_packet(),
            _native_packet(
                overrides={
                    "custom_codex_response_text_read_proven": False,
                    "custom_response_exact_token_observed": False,
                    "custom_response_bound_to_request": False,
                    "assistant_turn_activity_observed": True,
                    "assistant_turn_started_observed": True,
                    "assistant_turn_completed_observed": True,
                    "assistant_turn_activity_ended_observed": True,
                    "assistant_turn_post_completion_scan_performed": True,
                    "assistant_turn_last_scan_active": False,
                    "assistant_turn_failed_observed": False,
                    "assistant_turn_machine_error_code": (
                        "CUSTOM_NATIVE_ASSISTANT_TURN_COMPLETED_WITHOUT_EXACT_TOKEN"
                    ),
                    "assistant_turn_progress_candidate_count": 0,
                    "assistant_turn_stop_generating_candidate_count": 1,
                    "response_surface_candidate_count": 3,
                    "native_codex_subagent_absence_proven": False,
                    "native_free_text_observer_machine_error_code": (
                        "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN"
                    ),
                    "custom_response_token_leaf_candidate_count": 0,
                    "custom_response_prompt_echo_candidate_count": 0,
                    "custom_response_prompt_suffix_echo_candidate_count": 0,
                    "custom_response_exact_token_candidate_count": 0,
                    "custom_response_like_candidate_count": 0,
                }
            ),
            expected_visible_text=EXPECTED_VISIBLE_TEXT,
            request_id=REQUEST_ID,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(
            packet["machine_error_code"],
            ui_visibility.CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_NOT_OBSERVED,
        )
        self.assertTrue(packet["assistant_turn_started_observed"])
        self.assertTrue(packet["assistant_turn_completed_observed"])
        self.assertFalse(packet["assistant_turn_last_scan_active"])
        self.assertEqual(
            packet["assistant_turn_machine_error_code"],
            "CUSTOM_NATIVE_ASSISTANT_TURN_COMPLETED_WITHOUT_EXACT_TOKEN",
        )
        self.assertIn("assistant_turn_machine_error_code_not_ok", packet["blocking_reasons"])
        self.assertIn("custom_response_exact_token_not_observed", packet["blocking_reasons"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(EXPECTED_VISIBLE_TEXT, serialized)
        self.assertFalse(packet_contains_text(packet, EXPECTED_VISIBLE_TEXT))
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_without_file_backed_inputs(self) -> None:
        packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
            _source_packet(),
            _native_packet(),
            expected_visible_text=EXPECTED_VISIBLE_TEXT,
            request_id=REQUEST_ID,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            ui_visibility.CUSTOM_CODEX_UI_VISIBILITY_SOURCE_INVALID,
        )
        self.assertIn(
            "visible_source_binding_proof_file_not_read",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_native_source_that_is_not_custom_codex_ui(self) -> None:
        packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
            _source_packet(),
            _native_packet(overrides={"packet_kind": "wbp_ui_screenshot_claim"}),
            expected_visible_text=EXPECTED_VISIBLE_TEXT,
            request_id=REQUEST_ID,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(
            packet["machine_error_code"],
            ui_visibility.CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_SOURCE_NOT_ALLOWED,
        )
        self.assertIn("native_ui_source_kind_not_allowed", packet["blocking_reasons"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_expected_text_not_bound_to_handoff_digest(self) -> None:
        unbound_text = f"WBP_UI_VISIBLE_{'b' * 64}_{REQUEST_ID}"
        packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
            _source_packet(),
            _native_packet(expected_text=unbound_text),
            expected_visible_text=unbound_text,
            request_id=REQUEST_ID,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(
            packet["machine_error_code"],
            ui_visibility.CUSTOM_CODEX_UI_VISIBILITY_NOT_BOUND,
        )
        self.assertIn(
            "expected_visible_text_not_bound_to_handoff_digest",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["visible_response_bound_to_handoff"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_native_hash_mismatch(self) -> None:
        packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
            _source_packet(),
            _native_packet(expected_text=f"{EXPECTED_VISIBLE_TEXT}_other"),
            expected_visible_text=EXPECTED_VISIBLE_TEXT,
            request_id=REQUEST_ID,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(
            packet["machine_error_code"],
            ui_visibility.CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_NOT_OBSERVED,
        )
        self.assertIn("custom_response_expected_sha256_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["visible_response_bound_to_handoff"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_stale_unbound_request(self) -> None:
        packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
            _source_packet(),
            _native_packet(overrides={"custom_response_bound_to_request": False}),
            expected_visible_text=EXPECTED_VISIBLE_TEXT,
            request_id=REQUEST_ID,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(
            packet["machine_error_code"],
            ui_visibility.CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_NOT_OBSERVED,
        )
        self.assertIn("custom_response_not_bound_to_request", packet["blocking_reasons"])
        self.assertFalse(packet["stale_visibility_rejected"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_overlong_request_id_without_prefix_truncation(self) -> None:
        long_request_id = "r" * 257
        long_expected_text = f"WBP_UI_VISIBLE_{HANDOFF_DIGEST}_{long_request_id}"
        packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
            _source_packet(),
            _native_packet(
                expected_text=long_expected_text,
                request_id=long_request_id,
            ),
            expected_visible_text=long_expected_text,
            request_id=long_request_id,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(
            packet["machine_error_code"],
            ui_visibility.CUSTOM_CODEX_UI_VISIBILITY_NOT_BOUND,
        )
        self.assertIn("request_id_invalid", packet["blocking_reasons"])
        self.assertEqual(packet["request_id"], "")
        self.assertTrue(packet["request_id_sha256"])
        self.assertFalse(packet["request_id_recorded"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(long_request_id, serialized)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_native_codex_subagent_substitution(self) -> None:
        packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
            _source_packet(),
            _native_packet(
                overrides={
                    "native_codex_subagent_absence_proven": False,
                    "native_codex_subagent_used_as_dip": True,
                }
            ),
            expected_visible_text=EXPECTED_VISIBLE_TEXT,
            request_id=REQUEST_ID,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(
            packet["machine_error_code"],
            ui_visibility.CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_NOT_OBSERVED,
        )
        self.assertIn("native_codex_subagent_used_as_dip", packet["blocking_reasons"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_raw_native_ui_capture_leak(self) -> None:
        packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
            _source_packet(),
            _native_packet(overrides={"raw_dom_exposed": True}),
            expected_visible_text=EXPECTED_VISIBLE_TEXT,
            request_id=REQUEST_ID,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(
            packet["machine_error_code"],
            ui_visibility.CUSTOM_CODEX_UI_VISIBILITY_PAYLOAD_UNSAFE,
        )
        self.assertIn("native_raw_dom_exposed", packet["blocking_reasons"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_native_ui_product_ready_preclaim_as_unsafe(self) -> None:
        packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
            _source_packet(),
            _native_packet(overrides={"product_ready": True}),
            expected_visible_text=EXPECTED_VISIBLE_TEXT,
            request_id=REQUEST_ID,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(
            packet["machine_error_code"],
            ui_visibility.CUSTOM_CODEX_UI_VISIBILITY_PAYLOAD_UNSAFE,
        )
        self.assertIn("native_preclaimed_product_ready", packet["blocking_reasons"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_source_product_ready_preclaim_as_unsafe(self) -> None:
        packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
            _source_packet(
                overrides={
                    "product_ready": True,
                    "custom_codex_ui_visibility_proven": True,
                }
            ),
            _native_packet(),
            expected_visible_text=EXPECTED_VISIBLE_TEXT,
            request_id=REQUEST_ID,
            file_metadata=_file_metadata(),
        )

        self.assertEqual(
            packet["machine_error_code"],
            ui_visibility.CUSTOM_CODEX_UI_VISIBILITY_PAYLOAD_UNSAFE,
        )
        self.assertIn("source_preclaimed_product_ready", packet["blocking_reasons"])
        self.assertIn("source_preclaimed_ui_visibility", packet["blocking_reasons"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_positive_keeps_files_private_and_packet_strict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "visible-source-binding.json"
            native_path = Path(temp_dir) / "native-ui.json"
            sentinel = Path(temp_dir) / "sentinel.txt"
            source_path.write_text(json.dumps(_source_packet()) + "\n", encoding="utf-8")
            native_path.write_text(json.dumps(_native_packet()) + "\n", encoding="utf-8")
            sentinel.write_text("unchanged", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "custom-codex-ui-visibility-proof",
                    "--visible-source-binding-proof-file",
                    str(source_path),
                    "--native-ui-observer-packet-file",
                    str(native_path),
                    "--expected-visible-text",
                    EXPECTED_VISIBLE_TEXT,
                    "--request-id",
                    REQUEST_ID,
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
        self.assertEqual(result.stdout.strip(), json.dumps(packet, ensure_ascii=True))
        self.assertTrue(packet["visible_source_binding_proof_file_read"])
        self.assertFalse(packet["visible_source_binding_proof_file_path_recorded"])
        self.assertTrue(packet["native_ui_observer_packet_file_read"])
        self.assertFalse(packet["native_ui_observer_packet_file_path_recorded"])
        self.assertTrue(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_blocks_non_utf8_source_packet_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "visible-source-binding.json"
            native_path = Path(temp_dir) / "native-ui.json"
            source_path.write_bytes(b"\xff\xfe\xff")
            native_path.write_text(json.dumps(_native_packet()) + "\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "custom-codex-ui-visibility-proof",
                    "--visible-source-binding-proof-file",
                    str(source_path),
                    "--native-ui-observer-packet-file",
                    str(native_path),
                    "--expected-visible-text",
                    EXPECTED_VISIBLE_TEXT,
                    "--request-id",
                    REQUEST_ID,
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        packet = json.loads(result.stdout)
        self.assertEqual(
            packet["machine_error_code"],
            ui_visibility.CUSTOM_CODEX_UI_VISIBILITY_SOURCE_INVALID,
        )
        self.assertEqual(
            packet["visible_source_binding_proof_file_error_code"],
            "visible_source_binding_proof_file_invalid",
        )
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_blocks_non_utf8_native_packet_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "visible-source-binding.json"
            native_path = Path(temp_dir) / "native-ui.json"
            source_path.write_text(json.dumps(_source_packet()) + "\n", encoding="utf-8")
            native_path.write_bytes(b"\xff\xfe\xff")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "custom-codex-ui-visibility-proof",
                    "--visible-source-binding-proof-file",
                    str(source_path),
                    "--native-ui-observer-packet-file",
                    str(native_path),
                    "--expected-visible-text",
                    EXPECTED_VISIBLE_TEXT,
                    "--request-id",
                    REQUEST_ID,
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        packet = json.loads(result.stdout)
        self.assertEqual(
            packet["machine_error_code"],
            ui_visibility.CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_NOT_OBSERVED,
        )
        self.assertEqual(
            packet["native_ui_observer_packet_file_error_code"],
            "native_ui_observer_packet_file_invalid",
        )
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_ui_visibility_proof_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "custom-codex-ui-visibility-proof",
                "--visible-source-binding-proof-file",
                "/tmp/wbp-visible-source-binding.json",
                "--native-ui-observer-packet-file",
                "/tmp/wbp-native-ui.json",
                "--expected-visible-text",
                EXPECTED_VISIBLE_TEXT,
                "--request-id",
                REQUEST_ID,
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")


if __name__ == "__main__":
    unittest.main()
