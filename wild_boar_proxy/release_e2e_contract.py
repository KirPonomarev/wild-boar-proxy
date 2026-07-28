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
    dedicated_credentials_admitted: bool,
) -> dict[str, Any]:
    """Build the W13 release candidate E2E receipt.

    If dedicated credentials are not admitted, the receipt honestly reports
    WAIT_EXTERNAL_PREREQUISITE for the live-credential steps while the
    synthetic contract remains proven.
    """
    synthetic_all_pass = all(s.synthetic_pass for s in steps)
    live_steps = [s for s in steps if s.requires_live_credentials]
    live_blocked = live_steps and not dedicated_credentials_admitted

    extra: dict[str, Any] = {
        "version": candidate.version,
        "source_sha": candidate.source_sha,
        "artifact_hashes": candidate.artifact_hashes,
        "total_steps": len(steps),
        "synthetic_all_pass": synthetic_all_pass,
        "live_credential_steps": len(live_steps),
        "dedicated_credentials_admitted": dedicated_credentials_admitted,
        "live_proof_deferred": bool(live_blocked),
    }

    if live_blocked:
        return _build_packet(
            ok=False,
            human_message=(
                "Release candidate synthetic contract proven, but live physical "
                "steps require dedicated credentials that are not admitted."
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
    # Without credentials: WAIT_EXTERNAL_PREREQUISITE
    no_cred = build_release_e2e_receipt(
        candidate=candidate, steps=steps, dedicated_credentials_admitted=False
    )
    # With credentials: ACCEPTED
    with_cred = build_release_e2e_receipt(
        candidate=candidate, steps=steps, dedicated_credentials_admitted=True
    )

    receipts = [no_cred, with_cred]
    violations: list[str] = []
    for r in receipts:
        violations.extend(command_packets.inspect_command_packet_semantics(r))
    ok = not violations and with_cred["machine_error_code"] == "WEB_RELEASE_V0_1_0_ACCEPTED"
    return _build_packet(
        ok=ok,
        human_message="Release E2E synthetic proof complete." if ok else "Violations.",
        machine_error_code="OK" if ok else "RELEASE_E2E_PROOF_VIOLATIONS",
        operator_action="none" if ok else "stop",
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        changed_files=[],
        effect=E2E_EFFECT_READ,
        extra={
            "receipt_count": len(receipts),
            "live_proof_deferred_without_credentials": no_cred["machine_error_code"] == "WAIT_EXTERNAL_PREREQUISITE",
            "accepted_with_credentials": with_cred["machine_error_code"] == "WEB_RELEASE_V0_1_0_ACCEPTED",
            "step_count": len(steps),
            "packet_violations": violations,
        },
    )


__all__ = [
    "ReleaseCandidateIdentity",
    "PhysicalMatrixStep",
    "build_release_e2e_receipt",
    "run_release_e2e_synthetic_proof",
    "WEB_RELEASE_VERSION",
]
