# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Deterministic contract tests for persistent profile and update compat (W09)."""

from __future__ import annotations

import unittest

from wild_boar_proxy import persistent_profile_compat as ppc
from wild_boar_proxy.core import packets


def _assert_semantics(testcase, packet):
    missing = packets.missing_required_fields(packet, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    testcase.assertEqual(missing, [], f"missing: {missing}")
    violations = packets.inspect_command_packet_semantics(packet)
    testcase.assertEqual(violations, [], f"violations: {violations}")


class ClassifyUpdateCompatibilityTests(unittest.TestCase):
    def test_same_version_is_compatible(self) -> None:
        ident = ppc.build_official_identity(version="0.130.0", build="100")
        status, code = ppc.classify_update_compatibility(current=ident, last_proven=ident)
        self.assertEqual(status, ppc.COMPAT_STATUS_OK)
        self.assertEqual(code, "OK")

    def test_version_drift_requires_reproof(self) -> None:
        v1 = ppc.build_official_identity(version="0.130.0", build="100")
        v2 = ppc.build_official_identity(version="0.131.0", build="101")
        status, code = ppc.classify_update_compatibility(current=v2, last_proven=v1)
        self.assertEqual(status, ppc.COMPAT_STATUS_DRIFT)
        self.assertEqual(code, "OFFICIAL_CODEX_VERSION_DRIFT_REPROOF_REQUIRED")

    def test_no_prior_proof_requires_reproof(self) -> None:
        ident = ppc.build_official_identity(version="0.130.0", build="100")
        status, code = ppc.classify_update_compatibility(current=ident, last_proven=None)
        self.assertEqual(status, ppc.COMPAT_STATUS_DRIFT)
        self.assertEqual(code, "NO_PRIOR_COMPATIBILITY_PROOF")

    def test_unknown_version_is_unknown(self) -> None:
        unknown = ppc.build_official_identity(version="", build="", observed=False)
        status, code = ppc.classify_update_compatibility(
            current=unknown,
            last_proven=ppc.build_official_identity(version="0.130.0", build="100"),
        )
        self.assertEqual(status, ppc.COMPAT_STATUS_UNKNOWN)
        self.assertEqual(code, "OFFICIAL_CODEX_VERSION_UNKNOWN")


class ReceiptContractTests(unittest.TestCase):
    def _profile(self):
        return ppc.ProfilePersistenceProof(
            profile_id="p1",
            identity_digest="a" * 64,
            persisted_at="2026-07-27T00:00:00Z",
            history_classification="visible_owner_confirmed",
        )

    def test_compatible_receipt_ok(self) -> None:
        ident = ppc.build_official_identity(version="0.130.0", build="100")
        r = ppc.build_persistence_compat_receipt(
            profile=self._profile(), current_identity=ident, last_proven_identity=ident
        )
        _assert_semantics(self, r)
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["updater_restricted"])

    def test_drift_receipt_error(self) -> None:
        v1 = ppc.build_official_identity(version="0.130.0", build="100")
        v2 = ppc.build_official_identity(version="0.131.0", build="101")
        r = ppc.build_persistence_compat_receipt(
            profile=self._profile(), current_identity=v2, last_proven_identity=v1
        )
        _assert_semantics(self, r)
        self.assertEqual(r["status"], "error")

    def test_original_app_mutations_always_zero(self) -> None:
        ident = ppc.build_official_identity(version="0.130.0", build="100")
        r = ppc.build_persistence_compat_receipt(
            profile=self._profile(), current_identity=ident, last_proven_identity=ident
        )
        self.assertEqual(r["original_codex_app_mutations"], 0)


class SyntheticProofTests(unittest.TestCase):
    def test_summary_ok(self) -> None:
        s = ppc.run_persistent_profile_synthetic_proof_summary()
        _assert_semantics(self, s)
        self.assertEqual(s["status"], "ok")
        self.assertTrue(s["updater_always_restricted"])

    def test_covers_compatible_drift_noprior_unknown(self) -> None:
        s = ppc.run_persistent_profile_synthetic_proof_summary()
        statuses = set(s["statuses_covered"])
        self.assertIn(ppc.COMPAT_STATUS_OK, statuses)
        self.assertIn(ppc.COMPAT_STATUS_DRIFT, statuses)
        self.assertIn(ppc.COMPAT_STATUS_UNKNOWN, statuses)

    def test_receipts_contract_compliant(self) -> None:
        for r in ppc.run_persistent_profile_synthetic_proof():
            _assert_semantics(self, r)


if __name__ == "__main__":
    unittest.main()
