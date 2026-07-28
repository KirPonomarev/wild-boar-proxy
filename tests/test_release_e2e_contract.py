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

    def test_accepted_with_credentials(self) -> None:
        r = re2e.build_release_e2e_receipt(
            candidate=self._candidate(), steps=self._steps(),
            dedicated_credentials_admitted=True,
        )
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], "WEB_RELEASE_V0_1_0_ACCEPTED")

    def test_wait_without_credentials(self) -> None:
        r = re2e.build_release_e2e_receipt(
            candidate=self._candidate(), steps=self._steps(),
            dedicated_credentials_admitted=False,
        )
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], "WAIT_EXTERNAL_PREREQUISITE")
        self.assertTrue(r["live_proof_deferred"])

    def test_synthetic_failure_blocks(self) -> None:
        steps = self._steps()[:-1] + [re2e.PhysicalMatrixStep("bad", "bad", False, False)]
        r = re2e.build_release_e2e_receipt(
            candidate=self._candidate(), steps=steps,
            dedicated_credentials_admitted=True,
        )
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], "RELEASE_E2E_SYNTHETIC_FAILURE")


class SyntheticProofTests(unittest.TestCase):
    def test_summary_ok(self) -> None:
        s = re2e.run_release_e2e_synthetic_proof()
        _assert_semantics(self, s)
        self.assertEqual(s["status"], "ok")
        self.assertTrue(s["live_proof_deferred_without_credentials"])
        self.assertTrue(s["accepted_with_credentials"])


if __name__ == "__main__":
    unittest.main()
