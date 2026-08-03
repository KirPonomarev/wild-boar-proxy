# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Normalized evidence state machine (B03).

Implements the plan's evidence-level taxonomy and acceptance rules:

    DECLARED < SYNTHETIC_PROVEN < INTEGRATION_PROVEN < LIVE_PROVEN
    < PHYSICAL_VISIBLE_PROVEN

Lower levels never substitute for higher levels. Empty required-step
collections are never accepted (`all([])` is not evidence). One SHA cannot
stand for multiple independent milestones. Stale evidence (after code,
config, binding, binary, hook, or Codex-version changes) is invalid.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

EVIDENCE_DECLARED = "DECLARED"
EVIDENCE_SYNTHETIC_PROVEN = "SYNTHETIC_PROVEN"
EVIDENCE_INTEGRATION_PROVEN = "INTEGRATION_PROVEN"
EVIDENCE_LIVE_PROVEN = "LIVE_PROVEN"
EVIDENCE_PHYSICAL_VISIBLE_PROVEN = "PHYSICAL_VISIBLE_PROVEN"
EVIDENCE_LEVELS = (
    EVIDENCE_DECLARED,
    EVIDENCE_SYNTHETIC_PROVEN,
    EVIDENCE_INTEGRATION_PROVEN,
    EVIDENCE_LIVE_PROVEN,
    EVIDENCE_PHYSICAL_VISIBLE_PROVEN,
)
EVIDENCE_LEVEL_ORDER = {level: index for index, level in enumerate(EVIDENCE_LEVELS)}


def evidence_level_at_least(level: str, minimum: str) -> bool:
    return EVIDENCE_LEVEL_ORDER.get(level, -1) >= EVIDENCE_LEVEL_ORDER.get(minimum, 10**9)


@dataclasses.dataclass(frozen=True)
class EvidenceRecord:
    """One immutable evidence record bound to exact identities.

    Credentials and raw secrets never appear in an evidence record.
    """

    record_id: str
    stage_id: str
    plan_id: str
    project_identity_fingerprint: str
    candidate_sha: str
    artifact_digest: str
    binding_id: str
    binding_revision: int
    assignment_id: str
    assignment_revision: int
    adapter_id: str
    context_digest: str
    environment_policy_identity: str
    evidence_level: str
    observed_at_utc: str
    ttl_seconds: int | None = None
    invalidation_keys: tuple[str, ...] = ()
    # Honesty flags: any True value in a live claim is a false-green signal.
    secret_value_exposed: bool = False
    credential_presence_counts_as_live: bool = False
    bridge_proof_counts_as_direct_provider: bool = False

    def is_stale(self, *, now_utc_iso: str, invalidation_keys: Iterable[str] = ()) -> bool:
        if self.invalidation_keys and any(
            key in self.invalidation_keys for key in invalidation_keys
        ):
            return True
        if self.ttl_seconds is None:
            return False
        try:
            observed = datetime.fromisoformat(self.observed_at_utc.replace("Z", "+00:00"))
            now = datetime.fromisoformat(now_utc_iso.replace("Z", "+00:00"))
        except ValueError:
            return True
        return (now - observed).total_seconds() > self.ttl_seconds

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def validate_required_evidence(
    records: Iterable[Mapping[str, Any] | EvidenceRecord],
    *,
    required_step_ids: Iterable[str],
    minimum_evidence_level: str = EVIDENCE_DECLARED,
) -> dict[str, Any]:
    """Validate a required-step evidence collection; never accepts all([]).

    Returns a packet-shaped result: ``accepted`` False with machine-readable
    reasons when the required collection is empty, contains duplicates or
    missing ids, binds a wrong candidate SHA, or uses a level below the
    minimum required.
    """
    required = list(required_step_ids)
    record_list = list(records)
    reasons: list[str] = []

    # B00/B03: an empty required-step collection is never accepted.
    if not required:
        return {
            "accepted": False,
            "machine_error_code": "REQUIRED_STEP_SET_EMPTY",
            "reasons": ["required_step_set_empty"],
            "all_empty_acceptance": False,
        }
    seen_required: set[str] = set()
    for step_id in required:
        if step_id in seen_required:
            reasons.append(f"required_step_duplicate:{step_id}")
        seen_required.add(step_id)

    by_step: dict[str, list[Mapping[str, Any]]] = {}
    for record in record_list:
        mapping = record.as_dict() if isinstance(record, EvidenceRecord) else dict(record)
        step_id = str(mapping.get("record_id") or "")
        by_step.setdefault(step_id, []).append(mapping)

    missing = [step_id for step_id in required if step_id not in by_step]
    if missing:
        reasons.append(f"required_step_missing:{','.join(missing)}")
    candidate_shas = {
        str(mapping.get("candidate_sha") or "")
        for mappings in by_step.values()
        for mapping in mappings
    }
    if len(candidate_shas) > 1:
        reasons.append("candidate_sha_mixed")
    for step_id in required:
        mappings = by_step.get(step_id, [])
        for mapping in mappings:
            level = str(mapping.get("evidence_level") or "")
            if level not in EVIDENCE_LEVELS:
                reasons.append(f"evidence_level_unknown:{step_id}")
            elif not evidence_level_at_least(level, minimum_evidence_level):
                reasons.append(f"evidence_level_insufficient:{step_id}:{level}")
            if not mapping.get("observed_at_utc"):
                reasons.append(f"observed_at_missing:{step_id}")
            if not mapping.get("context_digest"):
                reasons.append(f"context_digest_missing:{step_id}")
            if mapping.get("secret_value_exposed") is True:
                reasons.append(f"secret_value_exposed:{step_id}")
            if mapping.get("credential_presence_counts_as_live") is True:
                reasons.append(f"credential_presence_as_live:{step_id}")
            if mapping.get("bridge_proof_counts_as_direct_provider") is True:
                reasons.append(f"bridge_proof_as_direct_provider:{step_id}")

    accepted = not reasons
    return {
        "accepted": accepted,
        "machine_error_code": "REQUIRED_EVIDENCE_ACCEPTED" if accepted else "REQUIRED_EVIDENCE_REJECTED",
        "reasons": reasons,
        "required_step_count": len(required),
        "provided_record_count": len(record_list),
        "missing_step_ids": missing,
        "all_empty_acceptance": False,
    }


def validate_milestone_distinctness(milestone_shas: Mapping[str, str]) -> dict[str, Any]:
    """One SHA must not stand for multiple independent milestones."""
    shas = [str(sha) for sha in milestone_shas.values() if str(sha)]
    if not shas:
        return {"distinct": False, "machine_error_code": "MILESTONE_IDENTITIES_EMPTY"}
    if len(set(shas)) != len(shas):
        return {"distinct": False, "machine_error_code": "MILESTONE_SHA_COLLISION"}
    return {"distinct": True, "machine_error_code": "OK"}


def evidence_claim_allowed(
    *,
    claimed_level: str,
    has_live_receipts: bool,
    has_physical_receipts: bool,
) -> dict[str, Any]:
    """Guard: a claim at LIVE_PROVEN or above requires the corresponding
    receipt class. Synthetic evidence never substitutes for live or physical
    proof."""
    reasons: list[str] = []
    if claimed_level in (EVIDENCE_LIVE_PROVEN, EVIDENCE_PHYSICAL_VISIBLE_PROVEN) and not has_live_receipts:
        reasons.append("live_claim_without_live_receipts")
    if claimed_level == EVIDENCE_PHYSICAL_VISIBLE_PROVEN and not has_physical_receipts:
        reasons.append("physical_claim_without_physical_receipts")
    return {
        "allowed": not reasons,
        "machine_error_code": "OK" if not reasons else "EVIDENCE_CLAIM_BLOCKED",
        "reasons": reasons,
    }


def invalidate_evidence(records: Iterable[EvidenceRecord], invalidation_keys: Iterable[str]) -> list[str]:
    """Return record ids invalidated by the given invalidation keys."""
    key_set = set(invalidation_keys)
    return [
        record.record_id
        for record in records
        if record.invalidation_keys and key_set & set(record.invalidation_keys)
    ]


__all__ = [
    "EVIDENCE_DECLARED",
    "EVIDENCE_SYNTHETIC_PROVEN",
    "EVIDENCE_INTEGRATION_PROVEN",
    "EVIDENCE_LIVE_PROVEN",
    "EVIDENCE_PHYSICAL_VISIBLE_PROVEN",
    "EVIDENCE_LEVELS",
    "EvidenceRecord",
    "validate_required_evidence",
    "validate_milestone_distinctness",
    "evidence_claim_allowed",
    "invalidate_evidence",
    "evidence_level_at_least",
]
