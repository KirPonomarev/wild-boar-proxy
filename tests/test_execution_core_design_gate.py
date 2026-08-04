# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B13G: execution-core design gate tests (self-verified)."""

from __future__ import annotations

import unittest

from wild_boar_proxy import execution_core_design_gate as ecg


class ExecutionCoreDesignGateTests(unittest.TestCase):
    def test_fake_sha_rejected(self) -> None:
        """A 40-hex SHA that does not exist in git must not earn the token."""
        packet = ecg.run_execution_core_design_gate(main_head="a" * 40)
        self.assertFalse(packet["design_gate_earned"])
        self.assertIsNone(packet["design_gate_marker"])
        self.assertFalse(packet["findings"]["sha_exists"])

    def test_gate_self_verifies_not_caller_provided(self) -> None:
        """The gate reads git state directly; it does not accept
        caller-provided completed_stages or counts."""
        packet = ecg.run_execution_core_design_gate(
            completed_stages=["B00", "B01", "B02"],
            main_head="a" * 40,
        )
        self.assertFalse(packet["design_gate_earned"])
        self.assertIn("sha_exists", packet["findings"])
        self.assertIn("origin_main_matches", packet["findings"])

    def test_no_hardcoded_true_checks(self) -> None:
        """The gate must not use default True accessibility checks."""
        packet = ecg.run_execution_core_design_gate(main_head="a" * 40)
        self.assertNotIn("check_count", packet)
        self.assertNotIn("passed_count", packet)

    def test_token_format(self) -> None:
        self.assertEqual(
            ecg.DESIGN_GATE_TOKEN,
            "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY",
        )

    def test_evidence_index_findings_reported(self) -> None:
        packet = ecg.run_execution_core_design_gate(main_head="a" * 40)
        self.assertIn("evidence_index", packet["findings"])
        ev = packet["findings"]["evidence_index"]
        self.assertIn("receipt_count", ev)

    def test_synthetic_repository_gate_still_green(self) -> None:
        from wild_boar_proxy import design_gate_accessibility as dga
        proof = dga.run_design_gate_synthetic_proof()
        self.assertEqual(proof["status"], "ok")


if __name__ == "__main__":
    unittest.main()
