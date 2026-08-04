# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B13G: execution-core design gate tests."""

from __future__ import annotations

import unittest

from wild_boar_proxy import design_gate_accessibility as dga
from wild_boar_proxy import execution_core_design_gate as ecg

CLOSED_STAGES = [
    "B00_BASELINE_ADMISSION_REPAIR",
    "B01_ACTOR_ADR_AND_SPIKES",
    "B02_ACTOR_SCHEMA_V2_AND_MIGRATION",
    "B03_TRANSPORT_AND_EVIDENCE_STATE_MACHINE",
    "B04_THREAD_CONTEXT_LEDGER_V2",
    "B05_DISPATCHER_ASSIGNMENTS_PERMISSIONS_DIAGNOSTICS",
    "B06_LEGACY_SURFACE_AND_EVIDENCE_MATRIX_REGRESSION",
    "B07_CODE_MULTI_API_CORE",
    "B08_CODE_QWEN_API",
    "B09_ONE_SHOT_CLI_RUNTIME",
    "B10_CODE_QWEN_ONE_SHOT_CLI",
    "B11_CODE_KIMI_ONE_SHOT_CLI",
    "B12_ADMISSION_GLM_CLI_API_ONLY",
    "B13_SEQUENTIAL_WORKFLOW_RUNNER",
]

PASSING_CHECKS = [
    dga.AccessibilityCheck("aria_labels", "a11y", True, "ok"),
    dga.AccessibilityCheck("keyboard_nav", "keyboard", True, "ok"),
    dga.AccessibilityCheck("contrast_ratio", "contrast", True, "ok"),
    dga.AccessibilityCheck("focus_visible", "focus", True, "ok"),
    dga.AccessibilityCheck("responsive_layout", "responsive", True, "ok"),
]

FAILING_CHECKS = PASSING_CHECKS[:-1] + [
    dga.AccessibilityCheck("contrast_ratio_low", "contrast", False, "2.1:1"),
]


class ExecutionCoreDesignGateTests(unittest.TestCase):
    def test_gate_earns_exact_token_when_closed(self) -> None:
        packet = ecg.run_execution_core_design_gate(
            completed_stages=CLOSED_STAGES,
            evidence_index_references=14,
            full_suite_passed=4861,
            main_head="d6c414009f18211c0b1ab298d6f3a58dfebb28a2",
        )
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["design_gate_earned"])
        # The visible marker carries the exact earned token; the
        # token-shaped key is masked by the packet redaction contract.
        self.assertEqual(
            packet["design_gate_marker"],
            "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY",
        )
        self.assertEqual(packet["design_gate_token"], "<redacted>")
        self.assertTrue(packet["execution_core_repair_closed"])
        self.assertTrue(packet["input_evidence"]["recorded_not_asserted"])
        self.assertEqual(packet["input_evidence"]["evidence_index_references"], 14)
        self.assertEqual(packet["input_evidence"]["full_suite_passed"], 4861)

    def test_gate_blocked_when_core_open(self) -> None:
        packet = ecg.run_execution_core_design_gate(
            completed_stages=CLOSED_STAGES[:5],
            evidence_index_references=5,
            full_suite_passed=0,
            main_head="abc",
        )
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "DESIGN_GATE_NOT_EARNED")
        self.assertFalse(packet["design_gate_earned"])
        self.assertIsNone(packet["design_gate_token"])
        self.assertIsNone(packet["design_gate_marker"])
        self.assertIsNone(packet["design_gate_marker"])
        self.assertFalse(packet["execution_core_repair_closed"])

    def test_gate_blocked_when_check_fails(self) -> None:
        packet = ecg.run_execution_core_design_gate(
            completed_stages=CLOSED_STAGES,
            evidence_index_references=14,
            full_suite_passed=4861,
            main_head="d6c414009f18211c0b1ab298d6f3a58dfebb28a2",
            checks=FAILING_CHECKS,
        )
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "DESIGN_GATE_NOT_EARNED")
        self.assertFalse(packet["design_gate_earned"])
        self.assertIsNone(packet["design_gate_token"])
        self.assertIsNone(packet["design_gate_marker"])
        self.assertIsNone(packet["design_gate_marker"])
        self.assertEqual(len(packet["failed_checks"]), 1)

    def test_evidence_records_facts_verbatim(self) -> None:
        evidence = ecg.execution_core_repair_closed_evidence(
            completed_stages=CLOSED_STAGES,
            evidence_index_references=14,
            full_suite_passed=4861,
            main_head="abc123",
        )
        self.assertEqual(evidence["evidence_index_references"], 14)
        self.assertEqual(evidence["full_suite_passed"], 4861)
        self.assertEqual(evidence["main_head"], "abc123")
        self.assertEqual(len(evidence["completed_stages"]), 14)
        self.assertTrue(evidence["recorded_not_asserted"])

    def test_token_is_never_claimed_without_earned_gate(self) -> None:
        # Deterministic: a blocked gate packet never contains the token.
        packet = ecg.run_execution_core_design_gate(
            completed_stages=[],
            evidence_index_references=0,
            full_suite_passed=0,
            main_head="",
        )
        self.assertFalse(packet["design_gate_earned"])
        self.assertIsNone(packet["design_gate_token"])
        self.assertIsNone(packet["design_gate_marker"])

    def test_synthetic_repository_gate_still_green(self) -> None:
        proof = dga.run_design_gate_synthetic_proof()
        self.assertEqual(proof["status"], "ok")
        self.assertTrue(proof["gate_earned_when_core_closed"])
        self.assertTrue(proof["gate_blocked_when_core_open"])
        self.assertTrue(proof["gate_blocked_when_a11y_fail"])


if __name__ == "__main__":
    unittest.main()
