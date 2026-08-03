# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B03: normalized evidence state machine tests (false-green negatives)."""

from __future__ import annotations

import unittest

from wild_boar_proxy import evidence_state_machine as evm


def _record(record_id: str, *, level: str = evm.EVIDENCE_SYNTHETIC_PROVEN, **overrides) -> evm.EvidenceRecord:
    fields = {
        "record_id": record_id,
        "stage_id": "B03",
        "plan_id": "plan-1",
        "project_identity_fingerprint": "fp-1",
        "candidate_sha": "sha-1",
        "artifact_digest": "digest-1",
        "binding_id": "binding-agent_1",
        "binding_revision": 1,
        "assignment_id": "assignment-agent_1",
        "assignment_revision": 1,
        "adapter_id": "api",
        "context_digest": "ctx-1",
        "environment_policy_identity": "env-1",
        "evidence_level": level,
        "observed_at_utc": "2026-08-03T00:00:00Z",
        "ttl_seconds": None,
        "invalidation_keys": (),
    }
    fields.update(overrides)
    return evm.EvidenceRecord(**fields)


class RequiredEvidenceTests(unittest.TestCase):
    def test_non_empty_required_set_accepts(self) -> None:
        result = evm.validate_required_evidence(
            [_record("step-1"), _record("step-2")],
            required_step_ids=["step-1", "step-2"],
        )
        self.assertTrue(result["accepted"], result["reasons"])
        self.assertEqual(result["machine_error_code"], "REQUIRED_EVIDENCE_ACCEPTED")
        self.assertFalse(result["all_empty_acceptance"])

    def test_empty_required_set_never_accepted(self) -> None:
        # B00/B03 false-green negative: all([]) is not evidence.
        result = evm.validate_required_evidence([], required_step_ids=[])
        self.assertFalse(result["accepted"])
        self.assertEqual(result["machine_error_code"], "REQUIRED_STEP_SET_EMPTY")

    def test_missing_required_step_rejected(self) -> None:
        result = evm.validate_required_evidence(
            [_record("step-1")],
            required_step_ids=["step-1", "step-2"],
        )
        self.assertFalse(result["accepted"])
        self.assertIn("required_step_missing:step-2", result["reasons"])

    def test_duplicate_required_step_rejected(self) -> None:
        result = evm.validate_required_evidence(
            [_record("step-1")],
            required_step_ids=["step-1", "step-1"],
        )
        self.assertFalse(result["accepted"])
        self.assertTrue(any(r.startswith("required_step_duplicate:") for r in result["reasons"]))

    def test_insufficient_evidence_level_rejected(self) -> None:
        result = evm.validate_required_evidence(
            [_record("step-1", level=evm.EVIDENCE_DECLARED)],
            required_step_ids=["step-1"],
            minimum_evidence_level=evm.EVIDENCE_LIVE_PROVEN,
        )
        self.assertFalse(result["accepted"])
        self.assertTrue(any(r.startswith("evidence_level_insufficient:") for r in result["reasons"]))

    def test_mixed_candidate_sha_rejected(self) -> None:
        result = evm.validate_required_evidence(
            [_record("step-1"), _record("step-2", candidate_sha="sha-2")],
            required_step_ids=["step-1", "step-2"],
        )
        self.assertFalse(result["accepted"])
        self.assertIn("candidate_sha_mixed", result["reasons"])

    def test_credential_presence_as_live_rejected(self) -> None:
        result = evm.validate_required_evidence(
            [_record("step-1", credential_presence_counts_as_live=True)],
            required_step_ids=["step-1"],
        )
        self.assertFalse(result["accepted"])
        self.assertIn("credential_presence_as_live:step-1", result["reasons"])

    def test_bridge_proof_as_direct_provider_rejected(self) -> None:
        result = evm.validate_required_evidence(
            [_record("step-1", bridge_proof_counts_as_direct_provider=True)],
            required_step_ids=["step-1"],
        )
        self.assertFalse(result["accepted"])
        self.assertIn("bridge_proof_as_direct_provider:step-1", result["reasons"])

    def test_secret_exposure_rejected(self) -> None:
        result = evm.validate_required_evidence(
            [_record("step-1", secret_value_exposed=True)],
            required_step_ids=["step-1"],
        )
        self.assertFalse(result["accepted"])
        self.assertIn("secret_value_exposed:step-1", result["reasons"])


class MilestoneDistinctnessTests(unittest.TestCase):
    def test_distinct_shas_accepted(self) -> None:
        result = evm.validate_milestone_distinctness(
            {"web": "a" * 40, "provider": "b" * 40, "desktop": "c" * 40}
        )
        self.assertTrue(result["distinct"])

    def test_same_sha_rejected(self) -> None:
        result = evm.validate_milestone_distinctness(
            {"web": "a" * 40, "provider": "a" * 40, "desktop": "c" * 40}
        )
        self.assertFalse(result["distinct"])
        self.assertEqual(result["machine_error_code"], "MILESTONE_SHA_COLLISION")


class ClaimGuardTests(unittest.TestCase):
    def test_live_claim_requires_live_receipts(self) -> None:
        result = evm.evidence_claim_allowed(
            claimed_level=evm.EVIDENCE_LIVE_PROVEN,
            has_live_receipts=False,
            has_physical_receipts=False,
        )
        self.assertFalse(result["allowed"])
        self.assertIn("live_claim_without_live_receipts", result["reasons"])

    def test_physical_claim_requires_physical_receipts(self) -> None:
        result = evm.evidence_claim_allowed(
            claimed_level=evm.EVIDENCE_PHYSICAL_VISIBLE_PROVEN,
            has_live_receipts=True,
            has_physical_receipts=False,
        )
        self.assertFalse(result["allowed"])
        self.assertIn("physical_claim_without_physical_receipts", result["reasons"])

    def test_synthetic_claim_without_receipts_allowed(self) -> None:
        result = evm.evidence_claim_allowed(
            claimed_level=evm.EVIDENCE_SYNTHETIC_PROVEN,
            has_live_receipts=False,
            has_physical_receipts=False,
        )
        self.assertTrue(result["allowed"])


class InvalidationTests(unittest.TestCase):
    def test_invalidation_keys_invalidate(self) -> None:
        records = [
            _record("step-1", invalidation_keys=("code-change-1",)),
            _record("step-2", invalidation_keys=()),
        ]
        invalidated = evm.invalidate_evidence(records, ["code-change-1"])
        self.assertEqual(invalidated, ["step-1"])

    def test_ttl_expiry(self) -> None:
        record = _record("step-1", ttl_seconds=60, observed_at_utc="2026-01-01T00:00:00Z")
        self.assertTrue(record.is_stale(now_utc_iso="2026-01-01T00:02:00Z"))


if __name__ == "__main__":
    unittest.main()
