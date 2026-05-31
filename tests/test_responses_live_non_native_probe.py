# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "responses_live_non_native_probe.py"


def _load_tool_module():
    spec = importlib.util.spec_from_file_location("responses_live_non_native_probe", TOOL_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _clean_git_status(tool):
    original_run_text = tool.run_text

    def runner(repo_root: Path, command: list[str]) -> str:
        if command == ["git", "status", "--short"]:
            return ""
        return original_run_text(repo_root, command)

    return runner


class ResponsesLiveNonNativeProbeTests(unittest.TestCase):
    def test_owner_authorization_phrase_present_requires_exact_phrase(self) -> None:
        tool = _load_tool_module()

        self.assertTrue(
            tool.owner_authorization_phrase_present(tool.OWNER_STANDING_AUTHORIZATION_PHRASE)
        )
        self.assertTrue(
            tool.owner_authorization_phrase_present(
                f" {tool.OWNER_STANDING_AUTHORIZATION_PHRASE} "
            )
        )
        self.assertFalse(tool.owner_authorization_phrase_present("начинай работу"))
        self.assertFalse(
            tool.owner_authorization_phrase_present("начинай работу по данному контуру")
        )

    def test_probe_blocks_before_live_request_without_owner_authorization(self) -> None:
        tool = _load_tool_module()
        with tempfile.TemporaryDirectory(dir=ROOT / "audit_results") as tmp:
            packets = tool.build_packets(ROOT, Path(tmp))

        auth = packets["live_authorization_packet.json"]
        attempt = packets["direct_request_attempt_packet.json"]
        route = packets["route_selection_observation_packet.json"]
        response = packets["direct_non_stream_response_shape_packet.json"]
        stream = packets["direct_stream_response_shape_packet.json"]
        tool_loop = packets["responses_tool_loop_packet.json"]
        failure_semantics = packets["failure_semantics_packet.json"]
        summary = packets["responses_live_non_native_summary_packet.json"]
        false_green = packets["responses_live_non_native_false_green_audit.json"]
        independent = packets["independent_responses_live_non_native_audit.json"]
        redaction = packets["secret_redaction_audit.json"]

        self.assertEqual(auth["status"], "blocked")
        self.assertFalse(auth["owner_authorization_phrase_present"])
        self.assertFalse(auth["generic_start_phrase_accepted"])
        self.assertFalse(attempt["request_attempted"])
        self.assertFalse(attempt["request_reaches_wbp"])
        self.assertFalse(route["route_selected"])
        self.assertFalse(response["response_shape_accepted"])
        self.assertFalse(stream["stream_shape_accepted"])
        self.assertFalse(tool_loop["tool_loop_shape_accepted"])
        self.assertEqual(failure_semantics["failure_cause"], "unknown")
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["final_status"], tool.BLOCKED_NO_OWNER_AUTHORIZATION)
        self.assertFalse(summary["live_request_attempted"])
        self.assertFalse(summary["request_reaches_wbp"])
        self.assertFalse(summary["model_availability_proven"])
        self.assertEqual(false_green["status"], "ok")
        self.assertEqual(independent["status"], "ok")
        self.assertEqual(redaction["status"], "ok")
        self.assertEqual(redaction["secret_marker_findings"], [])

    def test_probe_can_classify_bounded_direct_success_without_promoting_other_layers(self) -> None:
        tool = _load_tool_module()

        def runner(request_spec: dict[str, object]) -> dict[str, object]:
            self.assertEqual(request_spec["endpoint_path"], "/v1/responses")
            surface = request_spec.get("surface")
            self.assertIn(surface, {"non_stream", "stream", "tool_loop", "failure_semantics"})
            if surface == "stream":
                self.assertTrue(request_spec["stream"])
                return {
                    "request_attempted": True,
                    "request_reaches_wbp": True,
                    "path": "/v1/responses",
                    "response_observed": True,
                    "route_selected": True,
                    "upstream_status_code": 200,
                    "upstream_accepts": True,
                    "stream_shape_accepted": True,
                    "stream_sse_envelope_observed": True,
                    "event_count": 9,
                    "observed_events": [
                        "response.created",
                        "response.in_progress",
                        "response.output_item.added",
                        "response.content_part.added",
                        "response.output_text.delta",
                        "response.output_text.done",
                        "response.content_part.done",
                        "response.output_item.done",
                        "response.completed",
                    ],
                    "expected_events": [
                        "response.created",
                        "response.in_progress",
                        "response.output_item.added",
                        "response.content_part.added",
                        "response.output_text.delta",
                        "response.output_text.done",
                        "response.content_part.done",
                        "response.output_item.done",
                        "response.completed",
                    ],
                    "data_type_sequence": [
                        "response.created",
                        "response.in_progress",
                        "response.output_item.added",
                        "response.content_part.added",
                        "response.output_text.delta",
                        "response.output_text.done",
                        "response.content_part.done",
                        "response.output_item.done",
                        "response.completed",
                    ],
                    "data_type_matches_event": True,
                    "data_parse_errors": [],
                    "terminal_response_status": "completed",
                    "completed_event_observed": True,
                    "failure_cause": "none",
                }
            if surface == "tool_loop":
                self.assertFalse(request_spec["stream"])
                return {
                    "request_attempted": True,
                    "request_reaches_wbp": True,
                    "path": "/v1/responses",
                    "response_observed": True,
                    "route_selected": True,
                    "upstream_status_code": 200,
                    "upstream_accepts": True,
                    "response_shape_accepted": True,
                    "tool_call_observed": True,
                    "tool_result_roundtrip_observed": True,
                    "assistant_followup_after_tool_observed": True,
                    "failure_cause": "none",
                }
            if surface == "failure_semantics":
                return {
                    "request_attempted": True,
                    "request_reaches_wbp": True,
                    "path": "/v1/responses",
                    "response_observed": True,
                    "route_selected": True,
                    "upstream_status_code": 429,
                    "upstream_accepts": False,
                    "response_shape_accepted": False,
                    "failure_cause": "quota_or_rate_limit",
                }
            self.assertFalse(request_spec["stream"])
            return {
                "request_attempted": True,
                "request_reaches_wbp": True,
                "path": "/v1/responses",
                "response_observed": True,
                "route_selected": True,
                "upstream_status_code": 200,
                "upstream_accepts": True,
                "response_shape_accepted": True,
                "response_status": "completed",
                "failure_cause": "none",
            }

        with mock.patch.object(tool, "run_text", side_effect=_clean_git_status(tool)):
            with tempfile.TemporaryDirectory(dir=ROOT / "audit_results") as tmp:
                packets = tool.build_packets(
                    ROOT,
                    Path(tmp),
                    owner_authorization_phrase=tool.OWNER_STANDING_AUTHORIZATION_PHRASE,
                    request_runner=runner,
                )

        summary = packets["responses_live_non_native_summary_packet.json"]
        false_green = packets["responses_live_non_native_false_green_audit.json"]
        independent = packets["independent_responses_live_non_native_audit.json"]
        response = packets["direct_non_stream_response_shape_packet.json"]
        stream = packets["direct_stream_response_shape_packet.json"]
        tool_loop = packets["responses_tool_loop_packet.json"]
        failure_semantics = packets["failure_semantics_packet.json"]
        upstream = packets["upstream_acceptance_or_failure_packet.json"]

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], tool.TARGET_STATUS)
        self.assertTrue(summary["live_request_attempted"])
        self.assertTrue(summary["request_reaches_wbp"])
        self.assertTrue(summary["route_selected"])
        self.assertTrue(summary["upstream_accepts"])
        self.assertTrue(summary["direct_non_stream_response_shape_accepted"])
        self.assertFalse(summary["native_codex_acceptance_proven"])
        self.assertFalse(summary["model_availability_proven"])
        self.assertTrue(summary["streaming_compatibility_proven"])
        self.assertTrue(summary["tool_loop_compatibility_proven"])
        self.assertTrue(summary["failure_semantics_compatibility_proven"])
        self.assertEqual(response["status"], "ok")
        self.assertEqual(stream["status"], "ok")
        self.assertEqual(tool_loop["status"], "ok")
        self.assertEqual(failure_semantics["failure_cause"], "quota_or_rate_limit")
        self.assertTrue(response["response_shape_accepted"])
        self.assertEqual(upstream["failure_cause"], "none")
        self.assertEqual(false_green["status"], "ok")
        self.assertEqual(independent["status"], "ok")

    def test_shape_only_tool_loop_must_not_count_as_tool_loop_compatibility_proven(self) -> None:
        tool = _load_tool_module()

        def runner(request_spec: dict[str, object]) -> dict[str, object]:
            surface = request_spec.get("surface")
            if surface == "stream":
                return {
                    "request_attempted": True,
                    "request_reaches_wbp": True,
                    "path": "/v1/responses",
                    "response_observed": True,
                    "route_selected": True,
                    "upstream_status_code": 200,
                    "upstream_accepts": True,
                    "stream_shape_accepted": True,
                    "stream_sse_envelope_observed": True,
                    "event_count": 9,
                    "observed_events": [
                        "response.created",
                        "response.in_progress",
                        "response.output_item.added",
                        "response.content_part.added",
                        "response.output_text.delta",
                        "response.output_text.done",
                        "response.content_part.done",
                        "response.output_item.done",
                        "response.completed",
                    ],
                    "expected_events": [
                        "response.created",
                        "response.in_progress",
                        "response.output_item.added",
                        "response.content_part.added",
                        "response.output_text.delta",
                        "response.output_text.done",
                        "response.content_part.done",
                        "response.output_item.done",
                        "response.completed",
                    ],
                    "data_type_sequence": [
                        "response.created",
                        "response.in_progress",
                        "response.output_item.added",
                        "response.content_part.added",
                        "response.output_text.delta",
                        "response.output_text.done",
                        "response.content_part.done",
                        "response.output_item.done",
                        "response.completed",
                    ],
                    "data_type_matches_event": True,
                    "data_parse_errors": [],
                    "terminal_response_status": "completed",
                    "completed_event_observed": True,
                    "failure_cause": "none",
                }
            if surface == "failure_semantics":
                return {
                    "request_attempted": True,
                    "request_reaches_wbp": True,
                    "path": "/v1/responses",
                    "response_observed": True,
                    "route_selected": True,
                    "upstream_status_code": 400,
                    "upstream_accepts": False,
                    "response_shape_accepted": False,
                    "failure_cause": "provider_error",
                }
            return {
                "request_attempted": True,
                "request_reaches_wbp": True,
                "path": "/v1/responses",
                "response_observed": True,
                "route_selected": True,
                "upstream_status_code": 200,
                "upstream_accepts": True,
                "response_shape_accepted": True,
                "response_status": "completed",
                "failure_cause": "none",
            }

        with mock.patch.object(tool, "run_text", side_effect=_clean_git_status(tool)):
            with tempfile.TemporaryDirectory(dir=ROOT / "audit_results") as tmp:
                packets = tool.build_packets(
                    ROOT,
                    Path(tmp),
                    owner_authorization_phrase=tool.OWNER_STANDING_AUTHORIZATION_PHRASE,
                    request_runner=runner,
                )

        summary = packets["responses_live_non_native_summary_packet.json"]
        tool_loop = packets["responses_tool_loop_packet.json"]
        self.assertFalse(tool_loop.get("tool_result_roundtrip_observed", False))
        self.assertFalse(tool_loop.get("assistant_followup_after_tool_observed", False))
        self.assertFalse(summary["tool_loop_compatibility_proven"])

    def test_partial_surface_is_classified_with_limits_not_false_full_pass_or_generic_blocked(
        self,
    ) -> None:
        tool = _load_tool_module()

        def runner(request_spec: dict[str, object]) -> dict[str, object]:
            surface = request_spec.get("surface")
            if surface == "stream":
                return {
                    "request_attempted": True,
                    "request_reaches_wbp": True,
                    "path": "/v1/responses",
                    "response_observed": True,
                    "route_selected": True,
                    "upstream_status_code": 400,
                    "upstream_accepts": False,
                    "stream_shape_accepted": False,
                    "failure_cause": "model_rejected",
                }
            if surface == "tool_loop":
                return {
                    "request_attempted": True,
                    "request_reaches_wbp": True,
                    "path": "/v1/responses",
                    "response_observed": True,
                    "route_selected": True,
                    "upstream_status_code": 400,
                    "upstream_accepts": False,
                    "response_shape_accepted": False,
                    "failure_cause": "model_rejected",
                }
            if surface == "failure_semantics":
                return {
                    "request_attempted": True,
                    "request_reaches_wbp": True,
                    "path": "/v1/responses",
                    "response_observed": True,
                    "route_selected": True,
                    "upstream_status_code": 400,
                    "upstream_accepts": False,
                    "response_shape_accepted": False,
                    "failure_cause": "provider_error",
                }
            return {
                "request_attempted": True,
                "request_reaches_wbp": True,
                "path": "/v1/responses",
                "response_observed": True,
                "route_selected": True,
                "upstream_status_code": 200,
                "upstream_accepts": True,
                "response_shape_accepted": True,
                "response_status": "completed",
                "failure_cause": "none",
            }

        with mock.patch.object(tool, "run_text", side_effect=_clean_git_status(tool)):
            with tempfile.TemporaryDirectory(dir=ROOT / "audit_results") as tmp:
                packets = tool.build_packets(
                    ROOT,
                    Path(tmp),
                    owner_authorization_phrase=tool.OWNER_STANDING_AUTHORIZATION_PHRASE,
                    request_runner=runner,
                )

        summary = packets["responses_live_non_native_summary_packet.json"]
        self.assertNotEqual(summary["final_status"], tool.TARGET_STATUS)
        self.assertNotEqual(summary["status"], "blocked")
        self.assertIn("CLASSIFIED_WITH_LIMITS", summary["final_status"])

    def test_stream_success_requires_packetized_sse_grammar_and_classification_fields(self) -> None:
        tool = _load_tool_module()

        def runner(request_spec: dict[str, object]) -> dict[str, object]:
            surface = request_spec.get("surface")
            if surface == "stream":
                return {
                    "request_attempted": True,
                    "request_reaches_wbp": True,
                    "path": "/v1/responses",
                    "response_observed": True,
                    "route_selected": True,
                    "upstream_status_code": 200,
                    "upstream_accepts": True,
                    "stream_shape_accepted": True,
                    "failure_cause": "none",
                }
            if surface == "failure_semantics":
                return {
                    "request_attempted": True,
                    "request_reaches_wbp": True,
                    "path": "/v1/responses",
                    "response_observed": True,
                    "route_selected": True,
                    "upstream_status_code": 400,
                    "upstream_accepts": False,
                    "response_shape_accepted": False,
                    "failure_cause": "provider_error",
                }
            return {
                "request_attempted": True,
                "request_reaches_wbp": True,
                "path": "/v1/responses",
                "response_observed": True,
                "route_selected": True,
                "upstream_status_code": 200,
                "upstream_accepts": True,
                "response_shape_accepted": True,
                "response_status": "completed",
                "failure_cause": "none",
            }

        with tempfile.TemporaryDirectory(dir=ROOT / "audit_results") as tmp:
            packets = tool.build_packets(
                ROOT,
                Path(tmp),
                owner_authorization_phrase=tool.OWNER_STANDING_AUTHORIZATION_PHRASE,
                request_runner=runner,
            )

        stream = packets["direct_stream_response_shape_packet.json"]
        summary = packets["responses_live_non_native_summary_packet.json"]
        self.assertFalse(stream.get("stream_sse_envelope_observed", False))
        self.assertFalse(stream.get("stream_classification_fields_observed", False))
        self.assertFalse(summary["streaming_compatibility_proven"])

    def test_required_packets_are_present(self) -> None:
        tool = _load_tool_module()
        with tempfile.TemporaryDirectory(dir=ROOT / "audit_results") as tmp:
            packets = tool.build_packets(ROOT, Path(tmp))

        required = {
            "sync_gate_packet.json",
            "historical_dirt_quarantine_packet.json",
            "declared_write_surfaces_packet.json",
            "live_authorization_packet.json",
            "runtime_readiness_packet.json",
            "direct_request_shape_packet.json",
            "direct_stream_request_shape_packet.json",
            "direct_tool_loop_request_shape_packet.json",
            "direct_request_attempt_packet.json",
            "route_selection_observation_packet.json",
            "upstream_acceptance_or_failure_packet.json",
            "direct_non_stream_response_shape_packet.json",
            "direct_stream_response_shape_packet.json",
            "responses_tool_loop_packet.json",
            "responses_tool_loop_followup_request_packet.json",
            "responses_tool_loop_followup_response_packet.json",
            "responses_tool_loop_followup_failure_packet.json",
            "responses_tool_loop_followup_root_cause_classification_packet.json",
            "responses_tool_loop_followup_false_green_audit.json",
            "failure_semantics_packet.json",
            "failure_taxonomy_packet.json",
            "responses_live_compatibility_matrix.json",
            "secret_redaction_audit.json",
            "responses_live_non_native_false_green_audit.json",
            "independent_responses_live_non_native_audit.json",
            "responses_live_non_native_summary_packet.json",
        }
        self.assertFalse(required - set(packets))

    def test_probe_allows_evidence_dir_outside_repo(self) -> None:
        tool = _load_tool_module()
        with tempfile.TemporaryDirectory() as tmp:
            packets = tool.build_packets(ROOT, Path(tmp))

        summary = packets["responses_live_non_native_summary_packet.json"]
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["final_status"], tool.BLOCKED_NO_OWNER_AUTHORIZATION)


if __name__ == "__main__":
    unittest.main()
