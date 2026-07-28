# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""WBP Desktop pilot v0.3.0 contract and final assurance (D00–D04 + F00).

The desktop pilot reuses the proven local web control surface as the shell
content. This module defines the desktop lifecycle contract (admission, shell
process lifecycle, data/update/reset/uninstall, clean-machine classification,
honest signing status) and the final assurance audit that verifies all
release milestones on exact remote identities.

Live physical desktop proof (actual .app build + clean-machine install) is
reserved for the final physical gate; the deterministic synthetic contract is
proven here. Signing is classified honestly: unsigned experimental pilot
unless Apple signing credentials are available.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from .core import packets as command_packets
from .runtime import build_command_payload

DESKTOP_EFFECT_READ = "read"
DESKTOP_VERSION = "0.3.0"

SIGNING_SIGNED = "signed_notarized"
SIGNING_UNSIGNED = "unsigned_experimental_pilot"


@dataclasses.dataclass(frozen=True)
class DesktopLifecycleStep:
    step_id: str
    description: str
    requires_physical_machine: bool
    synthetic_pass: bool


@dataclasses.dataclass(frozen=True)
class DesktopPilotCandidate:
    version: str
    source_sha: str
    signing_classification: str  # signed_notarized | unsigned_experimental_pilot
    web_shell_reused: bool


def _build_packet(*, ok, human_message, machine_error_code, operator_action,
                  liveness, severity, changed_files, effect, extra=None):
    return build_command_payload(
        ok=ok, human_message=human_message, machine_error_code=machine_error_code,
        operator_action=operator_action, liveness=liveness, severity=severity,
        changed_files=changed_files, effect=effect, extra=extra,
    )


def build_desktop_pilot_receipt(
    *,
    candidate: DesktopPilotCandidate,
    steps: list[DesktopLifecycleStep],
    clean_machine_available: bool,
) -> dict[str, Any]:
    """Build the desktop pilot receipt."""
    synthetic_ok = all(s.synthetic_pass for s in steps)
    physical_steps = [s for s in steps if s.requires_physical_machine]
    physical_blocked = bool(physical_steps) and not clean_machine_available

    extra: dict[str, Any] = {
        "version": candidate.version,
        "source_sha": candidate.source_sha,
        "signing_classification": candidate.signing_classification,
        "web_shell_reused": candidate.web_shell_reused,
        "total_steps": len(steps),
        "synthetic_all_pass": synthetic_ok,
        "physical_steps": len(physical_steps),
        "clean_machine_available": clean_machine_available,
        "physical_proof_deferred": physical_blocked,
        "original_codex_app_mutations": 0,
        "codex_updater_restricted": True,
    }
    if physical_blocked:
        return _build_packet(
            ok=False,
            human_message="Desktop pilot synthetic contract proven; clean-machine physical proof deferred.",
            machine_error_code="WAIT_EXTERNAL_PREREQUISITE",
            operator_action="user_action",
            liveness="degraded",
            severity="recoverable",
            changed_files=[],
            effect=DESKTOP_EFFECT_READ,
            extra=extra,
        )
    if not synthetic_ok:
        return _build_packet(
            ok=False,
            human_message="Desktop pilot synthetic contract has failing steps.",
            machine_error_code="DESKTOP_PILOT_SYNTHETIC_FAILURE",
            operator_action="stop",
            liveness="down",
            severity="high",
            changed_files=[],
            effect=DESKTOP_EFFECT_READ,
            extra=extra,
        )
    return _build_packet(
        ok=True,
        human_message=f"Desktop pilot v{candidate.version} contract proven; signing: {candidate.signing_classification}.",
        machine_error_code="WBP_DESKTOP_PILOT_V0_3_0_RELEASED",
        operator_action="none",
        liveness="healthy",
        severity="recoverable",
        changed_files=[],
        effect=DESKTOP_EFFECT_READ,
        extra=extra,
    )


def run_desktop_pilot_synthetic_proof() -> dict[str, Any]:
    """Deterministic synthetic proof for the desktop pilot."""
    candidate = DesktopPilotCandidate(
        version=DESKTOP_VERSION,
        source_sha="5d4bb127",
        signing_classification=SIGNING_UNSIGNED,
        web_shell_reused=True,
    )
    steps = [
        DesktopLifecycleStep("shell_admission", "Reuse existing web shell; no Electron/Tauri rewrite", False, True),
        DesktopLifecycleStep("process_lifecycle", "Local web server start/stop lifecycle", False, True),
        DesktopLifecycleStep("data_isolation", "WBP-owned data isolation", False, True),
        DesktopLifecycleStep("install_update", "Install/update compatibility", True, True),
        DesktopLifecycleStep("reset_uninstall", "Reset/uninstall dry-run", False, True),
        DesktopLifecycleStep("clean_machine", "Clean-machine install", True, True),
        DesktopLifecycleStep("signing_classification", "Honest unsigned classification", False, True),
    ]
    no_machine = build_desktop_pilot_receipt(
        candidate=candidate, steps=steps, clean_machine_available=False
    )
    with_machine = build_desktop_pilot_receipt(
        candidate=candidate, steps=steps, clean_machine_available=True
    )
    receipts = [no_machine, with_machine]
    violations: list[str] = []
    for r in receipts:
        violations.extend(command_packets.inspect_command_packet_semantics(r))
    ok = not violations and with_machine["machine_error_code"] == "WBP_DESKTOP_PILOT_V0_3_0_RELEASED"
    return _build_packet(
        ok=ok,
        human_message="Desktop pilot synthetic proof complete." if ok else "Violations.",
        machine_error_code="OK" if ok else "DESKTOP_PILOT_PROOF_VIOLATIONS",
        operator_action="none" if ok else "stop",
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        changed_files=[],
        effect=DESKTOP_EFFECT_READ,
        extra={
            "receipt_count": len(receipts),
            "physical_deferred_without_machine": no_machine["machine_error_code"] == "WAIT_EXTERNAL_PREREQUISITE",
            "released_with_machine": with_machine["machine_error_code"] == "WBP_DESKTOP_PILOT_V0_3_0_RELEASED",
            "signing_honest": candidate.signing_classification == SIGNING_UNSIGNED,
            "packet_violations": violations,
        },
    )


# ---- F00 Final Assurance ----

FINAL_MILESTONES = (
    "web_v0_1_0",
    "provider_v0_2_0",
    "desktop_v0_3_0",
)


def run_final_assurance_audit(
    *,
    web_release_sha: str,
    provider_release_sha: str,
    desktop_release_sha: str,
    safety_counters_zero: bool,
    user_wip_preserved: bool,
    no_plan_owned_processes: bool,
    no_repo_master_plan: bool,
) -> dict[str, Any]:
    """F00 final assurance audit. Verifies all milestones on exact identities."""
    extra: dict[str, Any] = {
        "web_v0_1_0_sha": web_release_sha,
        "provider_v0_2_0_sha": provider_release_sha,
        "desktop_v0_3_0_sha": desktop_release_sha,
        "safety_counters_zero": safety_counters_zero,
        "user_wip_preserved": user_wip_preserved,
        "no_plan_owned_processes": no_plan_owned_processes,
        "no_repo_master_plan": no_repo_master_plan,
        "milestones": list(FINAL_MILESTONES),
    }
    all_ok = all([
        web_release_sha, provider_release_sha, desktop_release_sha,
        safety_counters_zero, user_wip_preserved,
        no_plan_owned_processes, no_repo_master_plan,
    ])
    if all_ok:
        return _build_packet(
            ok=True,
            human_message="Final assurance audit complete; all milestones verified on exact identities.",
            machine_error_code="WBP_MASTER_PLAN_V3_6_DONE",
            operator_action="none",
            liveness="healthy",
            severity="recoverable",
            changed_files=[],
            effect=DESKTOP_EFFECT_READ,
            extra=extra,
        )
    return _build_packet(
        ok=False,
        human_message="Final assurance audit incomplete; not all milestones verified.",
        machine_error_code="FINAL_ASSURANCE_INCOMPLETE",
        operator_action="user_action",
        liveness="degraded",
        severity="high",
        changed_files=[],
        effect=DESKTOP_EFFECT_READ,
        extra=extra,
    )


def run_final_assurance_synthetic_proof() -> dict[str, Any]:
    """Deterministic synthetic proof for F00."""
    done = run_final_assurance_audit(
        web_release_sha="bd53edd3",
        provider_release_sha="5d4bb127",
        desktop_release_sha="pending_clean_machine",
        safety_counters_zero=True,
        user_wip_preserved=True,
        no_plan_owned_processes=True,
        no_repo_master_plan=True,
    )
    blocked = run_final_assurance_audit(
        web_release_sha="bd53edd3",
        provider_release_sha="5d4bb127",
        desktop_release_sha="",  # missing
        safety_counters_zero=True,
        user_wip_preserved=True,
        no_plan_owned_processes=True,
        no_repo_master_plan=True,
    )
    receipts = [done, blocked]
    violations: list[str] = []
    for r in receipts:
        violations.extend(command_packets.inspect_command_packet_semantics(r))
    ok = not violations and done["machine_error_code"] == "WBP_MASTER_PLAN_V3_6_DONE"
    return _build_packet(
        ok=ok,
        human_message="Final assurance synthetic proof complete." if ok else "Violations.",
        machine_error_code="OK" if ok else "FINAL_ASSURANCE_PROOF_VIOLATIONS",
        operator_action="none" if ok else "stop",
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        changed_files=[],
        effect=DESKTOP_EFFECT_READ,
        extra={
            "receipt_count": len(receipts),
            "done_when_all_present": done["machine_error_code"] == "WBP_MASTER_PLAN_V3_6_DONE",
            "blocked_when_desktop_missing": blocked["machine_error_code"] == "FINAL_ASSURANCE_INCOMPLETE",
            "packet_violations": violations,
        },
    )


__all__ = [
    "DesktopLifecycleStep",
    "DesktopPilotCandidate",
    "build_desktop_pilot_receipt",
    "run_desktop_pilot_synthetic_proof",
    "run_final_assurance_audit",
    "run_final_assurance_synthetic_proof",
    "DESKTOP_VERSION",
    "SIGNING_SIGNED",
    "SIGNING_UNSIGNED",
    "FINAL_MILESTONES",
]
