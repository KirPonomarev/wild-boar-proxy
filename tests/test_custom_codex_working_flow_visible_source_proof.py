# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wild_boar_proxy import custom_codex_operator_proof as operator
from wild_boar_proxy import custom_codex_working_flow_visible_source_proof as visible
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_custom_codex_admission import (  # noqa: E402
    EXPECTED_TEXT,
    PROMPT,
    ROOT,
    ROUTE_ID,
    _paths,
    _write_fake_codex,
    _write_profile,
)
from test_custom_codex_operator_proof import _admission_packet, _hex  # noqa: E402


def _write_packet(path: Path, packet: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _working_packet(
    *,
    transcript_digest: str,
    visible_digest: str = "",
    **overrides: object,
) -> dict[str, object]:
    extra: dict[str, object] = {
        "packet_kind": "wbp_codex_working_flow_delivery_proof",
        "codex_working_flow_delivery_proven": True,
        "codex_exec_assistant_continuation_proven": True,
        "codex_exec_json_events_observed": True,
        "codex_exec_jsonl_file_read": True,
        "approved_delivery_surface_proven": True,
        "api_lane_called": True,
        "external_live_provider_response_proven": True,
        "allowed_api_route_ids_enforced": True,
        "route_id_allowed": True,
        "hook_runtime_context_digest_bound": True,
        "blocking_reasons": [],
        "assistant_response_observed": True,
        "command_assistant_response_observed": True,
        "command_assistant_response_after_command": True,
        "command_assistant_response_bound_to_live_provider_digest": True,
        "command_assistant_binding_digest": visible_digest or _hex("5"),
        "codex_exec_transcript_sha256": transcript_digest,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "product_ready": False,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "route_candidate_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_expected_text_recorded": False,
        "expected_text_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }
    extra.update(overrides)
    return packets.build_command_packet(
        ok=True,
        human_message="working flow ok",
        machine_error_code="OK",
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        effect="probe",
        extra=extra,
    )


def _source_set(
    root: Path,
) -> tuple[
    dict[str, object],
    Path,
    list[dict[str, object]],
    list[Path],
    list[dict[str, object]],
    list[Path],
]:
    first = _admission_packet(
        run_id=_hex("1"),
        run_graph_digest=_hex("2"),
        transcript_digest=_hex("a"),
    )
    second = _admission_packet(
        run_id=_hex("3"),
        run_graph_digest=_hex("4"),
        transcript_digest=_hex("b"),
    )
    admissions = [first, second]
    admission_files = [
        _write_packet(root / "run_1" / "custom-codex-admission.packet.json", first),
        _write_packet(root / "run_2" / "custom-codex-admission.packet.json", second),
    ]
    operator_packet = operator.build_repeatable_operator_packet(
        admission_packets=admissions,
        admission_packet_files=admission_files,
        changed_files=[str(path) for path in admission_files],
        secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
    )
    operator_file = _write_packet(
        root / "repeatable-same-turn-operator-proof.packet.json",
        operator_packet,
    )
    working_flows = [
        _working_packet(transcript_digest=_hex("a"), visible_digest=_hex("c")),
        _working_packet(transcript_digest=_hex("b"), visible_digest=_hex("d")),
    ]
    working_files = [
        _write_packet(root / "run_1" / "working-flow-delivery-proof.packet.json", working_flows[0]),
        _write_packet(root / "run_2" / "working-flow-delivery-proof.packet.json", working_flows[1]),
    ]
    return operator_packet, operator_file, admissions, admission_files, working_flows, working_files


def _proof_packet(
    root: Path,
    *,
    operator_packet: dict[str, object] | None = None,
    admissions: list[dict[str, object]] | None = None,
    working_flows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    (
        source_operator,
        operator_file,
        source_admissions,
        admission_files,
        source_working_flows,
        working_files,
    ) = _source_set(root)
    if operator_packet is not None:
        source_operator = operator_packet
        _write_packet(operator_file, operator_packet)
    if admissions is not None:
        source_admissions = admissions
        for path, packet in zip(admission_files, admissions, strict=False):
            _write_packet(path, packet)
    if working_flows is not None:
        source_working_flows = working_flows
        for path, packet in zip(working_files, working_flows, strict=False):
            _write_packet(path, packet)
    return visible.build_working_flow_visible_source_proof_packet(
        operator_packet=source_operator,
        operator_packet_file=operator_file,
        admission_packets=source_admissions,
        admission_packet_files=admission_files,
        working_flow_packets=source_working_flows,
        working_flow_packet_files=working_files,
        changed_files=[str(operator_file), *(str(path) for path in admission_files), *(str(path) for path in working_files)],
        secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
    )


def _assert_no_product_or_ui_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["product_ready"])
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["fallback_used"])
    testcase.assertFalse(packet["local_imitation_used"])
    testcase.assertFalse(packet["native_codex_subagent_used_as_dip"])


def _assert_no_raw_sensitive_text(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in (PROMPT, ROUTE_ID, EXPECTED_TEXT):
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["raw_expected_text_recorded"])
    testcase.assertFalse(packet["secret_value_exposed"])


class CustomCodexWorkingFlowVisibleSourceProofTests(unittest.TestCase):
    def test_positive_binds_operator_admission_and_working_flow_visible_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = _proof_packet(Path(temp_dir))

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["packet_kind"], visible.WORKING_FLOW_VISIBLE_SOURCE_PACKET_KIND)
        self.assertTrue(packet["working_flow_visible_source_proven"])
        self.assertTrue(packet["custom_codex_working_flow_visible_source_proven"])
        self.assertTrue(packet["same_turn_custom_codex_flow_proven"])
        self.assertTrue(packet["repeatable_operator_proof_bound"])
        self.assertTrue(packet["operator_proof_valid"])
        self.assertEqual(packet["operator_run_count"], 2)
        self.assertEqual(packet["visible_source_run_count"], 2)
        self.assertEqual(packet["required_visible_source_run_count"], 2)
        self.assertEqual(packet["approved_visible_source_kind"], visible.APPROVED_VISIBLE_SOURCE_KIND)
        self.assertTrue(packet["approved_visible_source_observed"])
        self.assertTrue(packet["approved_visible_source_digest_bound"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["assistant_continuation_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )

    def test_blocks_invalid_operator_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            operator_packet, *_rest = _source_set(root)
            invalid = dict(operator_packet)
            invalid["status"] = "error"
            packet = _proof_packet(root, operator_packet=invalid)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            visible.VISIBLE_SOURCE_PROOF_OPERATOR_INVALID,
        )
        self.assertIn("operator_packet_not_ok", packet["blocking_reasons"])
        self.assertFalse(packet["working_flow_visible_source_proven"])
        _assert_no_product_or_ui_claim(self, packet)

    def test_blocks_working_flow_transcript_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            *_prefix, working_flows, _working_files = _source_set(root)
            changed = list(working_flows)
            changed[1] = _working_packet(transcript_digest=_hex("e"))
            packet = _proof_packet(root, working_flows=changed)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            visible.VISIBLE_SOURCE_PROOF_WORKING_FLOW_INVALID,
        )
        self.assertIn(
            "run_2_working_flow_transcript_not_operator_bound",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["working_flow_visible_source_proven"])
        _assert_no_product_or_ui_claim(self, packet)

    def test_blocks_working_flow_false_claim_and_secret_leak(self) -> None:
        cases = [
            (
                _working_packet(transcript_digest=_hex("b"), product_ready=True),
                visible.VISIBLE_SOURCE_PROOF_FALSE_CLAIM,
                "run_2_product_ready_not_false",
            ),
            (
                _working_packet(transcript_digest=_hex("b"), diagnostic_text=PROMPT),
                visible.VISIBLE_SOURCE_PROOF_UNSAFE_PACKET,
                "run_2_working_flow_packet_secret_leak",
            ),
            (
                _working_packet(
                    transcript_digest=_hex("b"),
                    command_assistant_response_bound_to_live_provider_digest=False,
                    assistant_response_bound_to_handoff_digest=False,
                ),
                visible.VISIBLE_SOURCE_PROOF_WORKING_FLOW_INVALID,
                "run_2_assistant_response_not_digest_bound",
            ),
        ]
        for working_packet, machine_error, reason in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                *_prefix, working_flows, _working_files = _source_set(root)
                changed = list(working_flows)
                changed[1] = working_packet
                packet = _proof_packet(root, working_flows=changed)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(packet["machine_error_code"], machine_error)
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["working_flow_visible_source_proven"])
                _assert_no_product_or_ui_claim(self, packet)

    def test_cli_runs_operator_and_emits_visible_source_proof_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            env = os.environ.copy()
            env.update(
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_PROFILE_DIR": str(paths.profile_dir),
                    "WBP_MANAGED_DIR": str(paths.managed_dir),
                    "WBP_CONFIG_TOML": str(paths.config_toml),
                    "WBP_RUNTIME_EFFECTIVE_MODE_FILE": str(
                        paths.runtime_effective_mode_file
                    ),
                    "WBP_MANAGED_CONFIG_FILE": str(paths.managed_config_file),
                    "WBP_STATE_FILE": str(paths.state_file),
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                }
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "codex-runner",
                    "working-flow-visible-source-proof",
                    "--prompt",
                    PROMPT,
                    "--codex-bin",
                    str(fake_codex),
                    "--proof-dir",
                    str(root / "proof"),
                    "--codex-cwd",
                    str(ROOT),
                    "--expected-text",
                    EXPECTED_TEXT,
                    "--timeout-seconds",
                    "20",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["packet_kind"], visible.WORKING_FLOW_VISIBLE_SOURCE_PACKET_KIND)
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["working_flow_visible_source_proven"])
        self.assertTrue(packet["approved_visible_source_observed"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["assistant_continuation_proven"])
        changed_names = {Path(path).name for path in packet["changed_files"]}
        self.assertIn("working-flow-visible-source-proof.packet.json", changed_names)
        self.assertIn("repeatable-same-turn-operator-proof.packet.json", changed_names)
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
