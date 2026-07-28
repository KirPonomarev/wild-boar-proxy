# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Deterministic contract tests for design gate accessibility (W11)."""

from __future__ import annotations

import unittest

from wild_boar_proxy import design_gate_accessibility as dg
from wild_boar_proxy.core import packets


def _assert_semantics(testcase, packet):
    missing = packets.missing_required_fields(packet, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    testcase.assertEqual(missing, [], f"missing: {missing}")
    violations = packets.inspect_command_packet_semantics(packet)
    testcase.assertEqual(violations, [], f"violations: {violations}")


class DesignGateReceiptTests(unittest.TestCase):
    def _passing(self):
        return [
            dg.AccessibilityCheck("aria", "a11y", True, "ok"),
            dg.AccessibilityCheck("keyboard", "keyboard", True, "ok"),
            dg.AccessibilityCheck("contrast", "contrast", True, "ok"),
        ]

    def test_earned_when_core_closed_all_pass(self) -> None:
        r = dg.build_design_gate_receipt(execution_core_closed=True, checks=self._passing())
        _assert_semantics(self, r)
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["gate_earned"])
        self.assertTrue(r["design_gate_earned"])

    def test_blocked_when_core_open(self) -> None:
        r = dg.build_design_gate_receipt(execution_core_closed=False, checks=self._passing())
        _assert_semantics(self, r)
        self.assertFalse(r["gate_earned"])
        self.assertEqual(r["machine_error_code"], "DESIGN_GATE_NOT_EARNED")

    def test_blocked_when_a11y_fails(self) -> None:
        checks = self._passing()[:-1] + [dg.AccessibilityCheck("contrast", "contrast", False, "2:1")]
        r = dg.build_design_gate_receipt(execution_core_closed=True, checks=checks)
        _assert_semantics(self, r)
        self.assertFalse(r["gate_earned"])
        self.assertEqual(len(r["failed_checks"]), 1)


class SyntheticProofTests(unittest.TestCase):
    def test_summary_ok(self) -> None:
        s = dg.run_design_gate_synthetic_proof()
        _assert_semantics(self, s)
        self.assertEqual(s["status"], "ok")
        self.assertTrue(s["gate_earned_when_core_closed"])
        self.assertTrue(s["gate_blocked_when_core_open"])
        self.assertTrue(s["gate_blocked_when_a11y_fail"])


if __name__ == "__main__":
    unittest.main()
