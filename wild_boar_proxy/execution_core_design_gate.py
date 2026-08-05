# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Execution-core design gate (B13G / R54 GateEvidenceBundleV2).

The gate SELF-VERIFIES execution-core repair closure through the strict
GateEvidenceBundleV2: every required stage receipt is bound to a real
merge commit, a `git show`-read closeout blob, the remote-main
transition, the sealed plan hash, and the execution-state canonical hash.

R54 hard rules:

- no `main_head` argument;
- no `completed_stages` argument;
- no caller-provided counts or booleans;
- no environment-overridden project/control roots (server-owned roots
  from `gate_evidence_bundle_v2.production_verifier()`).

The token is earned, never claimed. Stage labels alone earn nothing.
"""

from __future__ import annotations

from typing import Any

from . import design_gate_accessibility as dga
from . import gate_evidence_bundle_v2 as gebv
from .runtime import build_command_payload

DESIGN_GATE_TOKEN = dga.DESIGN_GATE_TOKEN
DESIGN_GATE_NOT_EARNED = "DESIGN_GATE_NOT_EARNED"
GATE_SCHEMA_VERSION = 2


def run_execution_core_design_gate() -> dict[str, Any]:
    """Run the design gate with SELF-VERIFIED GateEvidenceBundleV2.

    Takes no arguments: any caller-provided SHA, stage list, count, or
    boolean would be forged input. Accessibility checks are NOT hardcoded
    True; they are omitted from this gate (they belong to the
    repository-native dga module, called separately when UI work is
    admitted).
    """
    verifier = gebv.production_verifier()
    result = verifier.verify_bundle()
    earned = bool(result["earned"])
    failures = result["failures"]
    findings = result["findings"]
    findings["evidence_bundle_version"] = gebv.RECEIPT_SCHEMA_VERSION
    findings["required_stages"] = sorted(gebv.REQUIRED_STAGES)

    first_code = failures[0]["code"] if failures else DESIGN_GATE_NOT_EARNED
    extra: dict[str, Any] = {
        "schema_version": GATE_SCHEMA_VERSION,
        "design_gate_token": DESIGN_GATE_TOKEN if earned else None,
        "design_gate_marker": DESIGN_GATE_TOKEN if earned else None,
        "design_gate_earned": earned,
        "execution_core_repair_closed": earned,
        "evidence_failures": failures,
        "findings": findings,
    }
    if earned:
        return build_command_payload(
            ok=True,
            human_message=(
                f"Execution-core repair closed; design gate earned with token "
                f"{DESIGN_GATE_TOKEN}. Self-verified GateEvidenceBundleV2: "
                f"{findings.get('receipt_count', 0)} receipts bound to merge "
                f"commits, git-show closeout blobs, sealed plan, and state hash."
            ),
            machine_error_code="OK",
            liveness="healthy",
            severity="info",
            operator_action="none",
            changed_files=[],
            exit_code=0,
            extra=extra,
        )
    reason_summary = "; ".join(
        sorted({f"{f['code']}:{f['reason']}" for f in failures[:5]})
    )
    return build_command_payload(
        ok=False,
        human_message=(
            f"Design gate not earned ({first_code}): {reason_summary}."
        ),
        machine_error_code=first_code,
        liveness="degraded",
        severity="recoverable",
        operator_action="user_action",
        changed_files=[],
        exit_code=1,
        extra=extra,
    )


__all__ = [
    "DESIGN_GATE_TOKEN",
    "DESIGN_GATE_NOT_EARNED",
    "run_execution_core_design_gate",
]
