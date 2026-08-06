# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B13G/R54: execution-core design gate tests (self-verified V2)."""

from __future__ import annotations

import unittest

from wild_boar_proxy import execution_core_design_gate as ecg
from wild_boar_proxy import gate_evidence_bundle_v2 as gebv

TYPED_FAILURE_CODES = {
    gebv.EVIDENCE_SCHEMA_INVALID,
    gebv.EVIDENCE_DIGEST_MISMATCH,
    gebv.EVIDENCE_COMMIT_UNREACHABLE,
    gebv.EVIDENCE_STAGE_INVALIDATED,
    gebv.EVIDENCE_CANDIDATE_MISMATCH,
    ecg.DESIGN_GATE_NOT_EARNED,
}


class ExecutionCoreDesignGateTests(unittest.TestCase):
    def test_main_head_argument_rejected_as_forged_input(self) -> None:
        """R54: the production gate takes no main_head argument."""
        with self.assertRaises(TypeError):
            ecg.run_execution_core_design_gate(main_head="a" * 40)  # type: ignore[call-arg]

    def test_completed_stages_argument_rejected_as_forged_input(self) -> None:
        """R54: the production gate takes no completed_stages argument."""
        with self.assertRaises(TypeError):
            ecg.run_execution_core_design_gate(  # type: ignore[call-arg]
                completed_stages=["B00", "B01"]
            )

    def test_no_hardcoded_true_checks(self) -> None:
        """The gate must not use default True accessibility checks."""
        packet = ecg.run_execution_core_design_gate()
        self.assertNotIn("check_count", packet)
        self.assertNotIn("passed_count", packet)

    def test_token_format(self) -> None:
        self.assertEqual(
            ecg.DESIGN_GATE_TOKEN,
            "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY",
        )

    def test_gate_earns_only_with_typed_evidence(self) -> None:
        """Structural contract: earned implies zero failures; not earned
        implies a typed failure code. Never a bare boolean."""
        packet = ecg.run_execution_core_design_gate()
        self.assertIn("design_gate_earned", packet)
        self.assertIn("evidence_failures", packet)
        self.assertIn("findings", packet)
        self.assertIn("origin_main_sha", packet["findings"])
        if packet["design_gate_earned"]:
            self.assertEqual(packet["evidence_failures"], [])
            self.assertEqual(packet["machine_error_code"], "OK")
            self.assertEqual(packet["design_gate_marker"], ecg.DESIGN_GATE_TOKEN)
        else:
            self.assertIsNone(packet["design_gate_marker"])
            self.assertIn(packet["machine_error_code"], TYPED_FAILURE_CODES)
            self.assertNotEqual(packet["evidence_failures"], [])

    def test_synthetic_repository_gate_still_green(self) -> None:
        from wild_boar_proxy import design_gate_accessibility as dga
        proof = dga.run_design_gate_synthetic_proof()
        self.assertEqual(proof["status"], "ok")


if __name__ == "__main__":
    unittest.main()
