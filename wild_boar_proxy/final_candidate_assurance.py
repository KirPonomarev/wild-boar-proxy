# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Final candidate assurance (B18 / R66 FinalAssuranceV2).

Read-only assurance over the strict AssuranceEvidenceBundleV2. It does
NOT create provider homes, auth/session markers, or test injection; does
NOT grant admission; does NOT run provider CLIs or synthetic workflow
lambdas; and does NOT accept a caller test count, clean-run boolean, or
arbitrary network dict. All physical acceptance comes from verified
bundle receipts (`assurance_evidence_bundle_v2`).

Emits only `FINAL_CANDIDATE_READY_FOR_INDEPENDENT_AUDIT`,
`WAIT_EXTERNAL_PREREQUISITE`, or a typed failure — never `DONE`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import assurance_evidence_bundle_v2 as aebv
from . import one_shot_cli_runtime as osr
from . import qwen_one_shot_cli as qoc
from . import kimi_one_shot_cli as km
from .runtime import build_command_payload

FINAL_CANDIDATE_STATUS = "FINAL_CANDIDATE_READY_FOR_INDEPENDENT_AUDIT"
FINAL_CANDIDATE_FAILED = "FINAL_CANDIDATE_ASSURANCE_FAILED"
FINAL_CANDIDATE_SCHEMA_VERSION = 2

WAIT_EXTERNAL_PREREQUISITE = aebv.WAIT_EXTERNAL_PREREQUISITE

FINAL_CHECK_IDS = aebv.REQUIRED_ASSURANCE_CHECKS


@dataclass(frozen=True)
class FinalCheck:
    check_id: str
    category: str
    passed: bool
    evidence: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "category": self.category,
            "passed": self.passed,
            "evidence": self.evidence,
            "detail": self.detail,
        }


def _check_cli() -> FinalCheck:
    """Read-only probe: the production facade must expose the exact-admission
    boundary without claiming an operational tool or runtime grant. Used by CI receipt
    emitters and hermeticity tests; not part of the assurance run path."""
    receipt = osr.default_production_facade().receipt()
    passed = (
        receipt["status"] == "ok"
        and receipt.get("cli_disabled") is False
        and receipt.get("cli_operational") is False
        and receipt.get("production_admission_supported") is True
        and receipt.get("runtime_grant_available") is False
        and receipt.get("declared_not_live_verified") is True
    )
    return FinalCheck(
        check_id="cli",
        category="cli",
        passed=passed,
        evidence=(
            "production CLI facade exact-admission boundary "
            f"(cli_disabled={receipt.get('cli_disabled')}, "
            f"cli_operational={receipt.get('cli_operational')}, "
            f"runtime_grant_available={receipt.get('runtime_grant_available')})"
        ),
        detail={
            "cli_disabled": receipt.get("cli_disabled"),
            "cli_operational": receipt.get("cli_operational"),
        },
    )


def _check_account_isolation() -> FinalCheck:
    """Read-only typed fail-closed compatibility probe.

    Provider sessions on the production facade must fail closed at their
    current distinct authority boundaries, with no KeyError and zero filesystem creation. This
    probe performs no writes and creates no provider homes. Used by CI
    receipt emitters and hermeticity tests; not part of the assurance
    run path.
    """
    qwen = qoc.qwen_one_shot_session()
    kimi = km.kimi_one_shot_session()
    qwen_ok = (
        qwen.get("status") == "error"
        and qwen.get("machine_error_code") == osr.CLI_BINARY_ADMISSION_MISSING
        and qwen.get("changed_files") == []
        and "qwen_home" not in qwen
    )
    kimi_ok = (
        kimi.get("status") == "error"
        and kimi.get("machine_error_code") == osr.CLI_BINARY_ADMISSION_MISSING
        and kimi.get("changed_files") == []
        and "kimi_code_home" not in kimi
    )
    passed = qwen_ok and kimi_ok
    return FinalCheck(
        check_id="account_isolation",
        category="isolation",
        passed=passed,
        evidence=(
            f"provider sessions fail closed at typed authority boundaries, no fs creation "
            f"(qwen={qwen.get('machine_error_code')}, kimi={kimi.get('machine_error_code')})"
        ),
        detail={
            "qwen_code": qwen.get("machine_error_code"),
            "kimi_code": kimi.get("machine_error_code"),
            "cli_disabled": False,
        },
    )


def run_final_candidate_assurance() -> dict[str, Any]:
    """Verify the AssuranceEvidenceBundleV2. Takes NO arguments: caller
    test counts, clean-run booleans, and network dicts are forged input.

    Outcomes:
    - all receipts proven -> FINAL_CANDIDATE_READY_FOR_INDEPENDENT_AUDIT;
    - no failures but typed pending receipts (e.g. CLI disabled) ->
      WAIT_EXTERNAL_PREREQUISITE, ready_for_independent_audit=false;
    - any failure -> the first typed failure code.
    Never a KeyError; never DONE.
    """
    verifier = aebv.production_verifier()
    result = verifier.verify_bundle()
    failures = result["failures"]
    pendings = result["pendings"]
    findings = result["findings"]
    ready = bool(result["ready"])
    waiting = bool(result["waiting"])

    extra: dict[str, Any] = {
        "schema_version": FINAL_CANDIDATE_SCHEMA_VERSION,
        "final_candidate_status": (
            FINAL_CANDIDATE_STATUS
            if ready
            else WAIT_EXTERNAL_PREREQUISITE
            if waiting
            else FINAL_CANDIDATE_FAILED
        ),
        "ready_for_independent_audit": ready,
        "waiting_external_prerequisite": waiting,
        "required_checks": sorted(FINAL_CHECK_IDS),
        "evidence_failures": failures,
        "pending_receipts": pendings,
        "findings": findings,
        "never_emits_done": True,
    }
    if ready:
        return build_command_payload(
            ok=True,
            human_message=(
                "Final candidate ready for independent audit "
                "(AssuranceEvidenceBundleV2 fully proven)."
            ),
            machine_error_code=FINAL_CANDIDATE_STATUS,
            liveness="healthy",
            severity="info",
            operator_action="none",
            changed_files=[],
            exit_code=0,
            extra=extra,
        )
    if waiting:
        return build_command_payload(
            ok=False,
            human_message=(
                "Final candidate is waiting on typed external prerequisites "
                f"({len(pendings)} pending receipt(s), e.g. provider CLI live "
                f"evidence); ready_for_independent_audit=false."
            ),
            machine_error_code=WAIT_EXTERNAL_PREREQUISITE,
            liveness="degraded",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra=extra,
        )
    first_code = failures[0]["code"] if failures else FINAL_CANDIDATE_FAILED
    return build_command_payload(
        ok=False,
        human_message=(
            f"Final candidate assurance failed ({first_code}): "
            f"{len(failures)} evidence failure(s)."
        ),
        machine_error_code=first_code,
        liveness="degraded",
        severity="error",
        operator_action="stop",
        changed_files=[],
        exit_code=1,
        extra=extra,
    )


__all__ = [
    "FINAL_CANDIDATE_STATUS",
    "FINAL_CANDIDATE_FAILED",
    "FINAL_CHECK_IDS",
    "WAIT_EXTERNAL_PREREQUISITE",
    "run_final_candidate_assurance",
]
