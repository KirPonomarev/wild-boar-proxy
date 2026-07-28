# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Deterministic contract tests for release E2E contract (W13/W14)."""

from __future__ import annotations

import unittest

from wild_boar_proxy import release_e2e_contract as re2e
from wild_boar_proxy.core import packets


def _assert_semantics(testcase, packet):
    missing = packets.missing_required_fields(packet, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    testcase.assertEqual(missing, [], f"missing: {missing}")
    violations = packets.inspect_command_packet_semantics(packet)
    testcase.assertEqual(violations, [], f"violations: {violations}")


class ReleaseE2EReceiptTests(unittest.TestCase):
    def _candidate(self):
        return re2e.ReleaseCandidateIdentity(
            version="0.1.0", source_sha="abc123", artifact_hashes={"wheel": "d1"}
        )

    def _steps(self):
        return [
            re2e.PhysicalMatrixStep("web_start", "start", True, True),
            re2e.PhysicalMatrixStep("failover", "A->B", True, True),
            re2e.PhysicalMatrixStep("routing", "alias", False, True),
        ]

    def _receipt(self, step_id):
        return re2e.LiveReceipt(
            step_id=step_id, provider="wbp", model="n/a",
            route_id="loopback", request_id=f"req-{step_id}",
            result="ok", evidence_level="PHYSICAL_PROVEN",
            observed_at_utc="2026-01-01T00:00:00Z", response_observed=True,
        )

    def test_accepted_with_full_live_receipts(self) -> None:
        r = re2e.build_release_e2e_receipt(
            candidate=self._candidate(), steps=self._steps(),
            live_receipts=[self._receipt("web_start"), self._receipt("failover")],
        )
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], "WEB_RELEASE_V0_1_0_ACCEPTED")

    def test_wait_without_live_receipts(self) -> None:
        r = re2e.build_release_e2e_receipt(
            candidate=self._candidate(), steps=self._steps(),
            live_receipts=None,
        )
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], "WAIT_EXTERNAL_PREREQUISITE")
        self.assertTrue(r["live_proof_deferred"])
        self.assertEqual(
            sorted(r["missing_live_step_ids"]), ["failover", "web_start"]
        )

    def test_partial_live_receipts_still_wait(self) -> None:
        # Only one of two live steps has a PHYSICAL_PROVEN receipt: a single
        # declared live step must not greenlight the whole release.
        r = re2e.build_release_e2e_receipt(
            candidate=self._candidate(), steps=self._steps(),
            live_receipts=[self._receipt("web_start")],
        )
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], "WAIT_EXTERNAL_PREREQUISITE")
        self.assertEqual(r["missing_live_step_ids"], ["failover"])

    def test_declared_evidence_receipt_not_counted(self) -> None:
        # A receipt without PHYSICAL_PROVEN evidence does not satisfy a step.
        weak = re2e.LiveReceipt(
            step_id="web_start", provider="wbp", model="n/a",
            route_id="loopback", request_id="req-weak",
            result="ok", evidence_level="DECLARED",
            observed_at_utc="2026-01-01T00:00:00Z", response_observed=True,
        )
        r = re2e.build_release_e2e_receipt(
            candidate=self._candidate(), steps=self._steps(),
            live_receipts=[weak, self._receipt("failover")],
        )
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], "WAIT_EXTERNAL_PREREQUISITE")
        self.assertEqual(r["live_receipts_provided"], 1)
        self.assertEqual(r["missing_live_step_ids"], ["web_start"])

    def test_synthetic_failure_blocks(self) -> None:
        steps = self._steps()[:-1] + [re2e.PhysicalMatrixStep("bad", "bad", False, False)]
        r = re2e.build_release_e2e_receipt(
            candidate=self._candidate(), steps=steps,
            live_receipts=[self._receipt("web_start"), self._receipt("failover")],
        )
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], "RELEASE_E2E_SYNTHETIC_FAILURE")


class SyntheticProofTests(unittest.TestCase):
    def test_summary_ok(self) -> None:
        s = re2e.run_release_e2e_synthetic_proof()
        _assert_semantics(self, s)
        self.assertEqual(s["status"], "ok")
        self.assertTrue(s["live_proof_deferred_without_credentials"])
        self.assertTrue(s["partial_receipts_not_enough"])


if __name__ == "__main__":
    unittest.main()
