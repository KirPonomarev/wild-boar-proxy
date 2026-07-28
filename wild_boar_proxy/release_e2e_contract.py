# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Web release candidate physical E2E contract (W13).

Defines the deterministic synthetic contract for the complete web daily-use
journey on the exact release candidate. Live physical proof (with dedicated
accounts and DeepSeek credential) is reserved for the final physical gate;
absence of those credentials is non-blocking for the contract layer and
results in EARLY_LIVE_SMOKE_DEFERRED_NOT_BLOCKING / WAIT_EXTERNAL_PREREQUISITE
on the final physical gate.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from .core import packets as command_packets
from .runtime import build_command_payload

E2E_EFFECT_READ = "read"

WEB_RELEASE_VERSION = "0.1.0"


@dataclasses.dataclass(frozen=True)
class ReleaseCandidateIdentity:
    version: str
    source_sha: str
    artifact_hashes: dict[str, str]


@dataclasses.dataclass(frozen=True)
class PhysicalMatrixStep:
    step_id: str
    description: str
    requires_live_credentials: bool
    synthetic_pass: bool


@dataclasses.dataclass(frozen=True)
class LiveReceipt:
    """A real live proof receipt for one physical step. NOT synthetic.

    Each live step must carry provider/model/route/request identity,
    timestamp, result and evidence level. A boolean credentials_admitted
    flag is NOT sufficient — this receipt proves the step was actually
    executed against a live provider.
    """
    step_id: str
    provider: str
    model: str
    route_id: str
    request_id: str
    result: str  # "ok" | "error"
    evidence_level: str  # "PHYSICAL_PROVEN"
    observed_at_utc: str
    response_observed: bool


def _build_packet(*, ok, human_message, machine_error_code, operator_action,
                  liveness, severity, changed_files, effect, extra=None):
    return build_command_payload(
        ok=ok, human_message=human_message, machine_error_code=machine_error_code,
        operator_action=operator_action, liveness=liveness, severity=severity,
        changed_files=changed_files, effect=effect, extra=extra,
    )


def build_release_e2e_receipt(
    *,
    candidate: ReleaseCandidateIdentity,
    steps: list[PhysicalMatrixStep],
    live_receipts: list[LiveReceipt] | None = None,
) -> dict[str, Any]:
    """Build the W13 release candidate E2E receipt.

    A live step (``requires_live_credentials=True``) is only satisfied by a
    matching ``LiveReceipt`` whose ``evidence_level == "PHYSICAL_PROVEN"`` and
    ``response_observed`` is True and whose ``step_id`` equals the step's id.
    A bare ``dedicated_credentials_admitted`` boolean is NOT accepted: that is
    exactly the false-green the old API permitted.

    If any live step lacks such a receipt, the receipt honestly reports
    WAIT_EXTERNAL_PREREQUISITE for the live steps while the synthetic contract
    remains proven.
    """
    synthetic_all_pass = all(s.synthetic_pass for s in steps)
    live_steps = [s for s in steps if s.requires_live_credentials]

    valid_receipts = [
        r for r in (live_receipts or [])
        if r.evidence_level == "PHYSICAL_PROVEN" and r.response_observed
    ]
    proven_step_ids = {r.step_id for r in valid_receipts}
    missing_live = [s for s in live_steps if s.step_id not in proven_step_ids]
    live_blocked = bool(missing_live)

    extra: dict[str, Any] = {
        "version": candidate.version,
        "source_sha": candidate.source_sha,
        "artifact_hashes": candidate.artifact_hashes,
        "total_steps": len(steps),
        "synthetic_all_pass": synthetic_all_pass,
        "live_credential_steps": len(live_steps),
        "live_receipts_provided": len(valid_receipts),
        "live_receipt_step_ids": sorted(proven_step_ids),
        "missing_live_step_ids": sorted(s.step_id for s in missing_live),
        "live_proof_deferred": bool(live_blocked),
    }

    if live_blocked:
        return _build_packet(
            ok=False,
            human_message=(
                "Release candidate synthetic contract proven, but live physical "
                "steps require PHYSICAL_PROVEN receipts that are not provided."
            ),
            machine_error_code="WAIT_EXTERNAL_PREREQUISITE",
            operator_action="user_action",
            liveness="degraded",
            severity="recoverable",
            changed_files=[],
            effect=E2E_EFFECT_READ,
            extra=extra,
        )
    if not synthetic_all_pass:
        return _build_packet(
            ok=False,
            human_message="Release candidate synthetic contract has failing steps.",
            machine_error_code="RELEASE_E2E_SYNTHETIC_FAILURE",
            operator_action="stop",
            liveness="down",
            severity="high",
            changed_files=[],
            effect=E2E_EFFECT_READ,
            extra=extra,
        )
    return _build_packet(
        ok=True,
        human_message="Release candidate E2E contract fully proven.",
        machine_error_code="WEB_RELEASE_V0_1_0_ACCEPTED",
        operator_action="none",
        liveness="healthy",
        severity="recoverable",
        changed_files=[],
        effect=E2E_EFFECT_READ,
        extra=extra,
    )


def run_release_e2e_synthetic_proof() -> dict[str, Any]:
    """Deterministic synthetic proof of the release E2E contract."""
    candidate = ReleaseCandidateIdentity(
        version=WEB_RELEASE_VERSION,
        source_sha="e24b0f89",
        artifact_hashes={"wheel": "synthetic-digest-wheel", "sdist": "synthetic-digest-sdist"},
    )
    steps = [
        PhysicalMatrixStep("web_start", "Secure local web start", True, True),
        PhysicalMatrixStep("two_account_failover", "Two-account typed A->B failover", True, True),
        PhysicalMatrixStep("deepseek_live", "DeepSeek live response", True, True),
        PhysicalMatrixStep("three_modes", "Three runtime modes proven", True, True),
        PhysicalMatrixStep("alias_routing", "GPT/Deep alias routing", False, True),
        PhysicalMatrixStep("codex_deep_delegation", "Codex->Deep delegation", False, True),
        PhysicalMatrixStep("persistence_relaunch", "Persistent profile relaunch", False, True),
        PhysicalMatrixStep("recovery_drill", "Recovery drill", False, True),
        PhysicalMatrixStep("cleanup", "Exact cleanup, zero safety counters", False, True),
    ]
    # No live receipts at all: the synthetic proof NEVER fabricates live proof,
    # so every live step is unsatisfied -> WAIT_EXTERNAL_PREREQUISITE.
    no_receipts = build_release_e2e_receipt(
        candidate=candidate, steps=steps, live_receipts=None
    )
    # Partial receipts (one of four live steps) still must not be enough: the
    # remaining three live steps are unsatisfied -> still WAIT. This locks the
    # false-green containment: a single declared live step cannot greenlight the
    # whole release.
    partial_receipts = build_release_e2e_receipt(
        candidate=candidate, steps=steps,
        live_receipts=[
            LiveReceipt(
                step_id="web_start", provider="wbp", model="n/a",
                route_id="loopback", request_id="req-1",
                result="ok", evidence_level="PHYSICAL_PROVEN",
                observed_at_utc="2026-01-01T00:00:00Z", response_observed=True,
            ),
        ],
    )

    receipts = [no_receipts, partial_receipts]
    violations: list[str] = []
    for r in receipts:
        violations.extend(command_packets.inspect_command_packet_semantics(r))
    contract_holds = (
        not violations
        and no_receipts["machine_error_code"] == "WAIT_EXTERNAL_PREREQUISITE"
        and partial_receipts["machine_error_code"] != "WEB_RELEASE_V0_1_0_ACCEPTED"
    )
    # The synthetic proof demonstrates that the deterministic contract holds; it
    # must NEVER claim physical acceptance. ok=True only certifies that the
    # synthetic contract is internally consistent, while machine_error_code is
    # SYNTHETIC_PROVEN (not OK / not ACCEPTED) to keep physical proof honest.
    return _build_packet(
        ok=contract_holds,
        human_message=(
            "Release E2E synthetic proof complete (synthetic contract proven; "
            "no physical acceptance claimed)."
            if contract_holds
            else "Release E2E synthetic proof violations."
        ),
        machine_error_code="SYNTHETIC_PROVEN" if contract_holds else "RELEASE_E2E_PROOF_VIOLATIONS",
        operator_action="none" if contract_holds else "stop",
        liveness="healthy" if contract_holds else "degraded",
        severity="recoverable",
        changed_files=[],
        effect=E2E_EFFECT_READ,
        extra={
            "evidence_level": "SYNTHETIC_PROVEN",
            "receipt_count": len(receipts),
            "live_proof_deferred_without_credentials": no_receipts["machine_error_code"] == "WAIT_EXTERNAL_PREREQUISITE",
            "partial_receipts_not_enough": partial_receipts["machine_error_code"] != "WEB_RELEASE_V0_1_0_ACCEPTED",
            "step_count": len(steps),
            "packet_violations": violations,
        },
    )


__all__ = [
    "ReleaseCandidateIdentity",
    "PhysicalMatrixStep",
    "LiveReceipt",
    "build_release_e2e_receipt",
    "run_release_e2e_synthetic_proof",
    "WEB_RELEASE_VERSION",
]
