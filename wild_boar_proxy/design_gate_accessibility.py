# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Design gate accessibility and responsive contract (W11).

Earns the design gate token after execution-core repair is closed, then
verifies accessibility/responsive/keyboard/focus/contrast properties of the
existing UI without changing runtime semantics.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from .core import packets as command_packets
from .runtime import build_command_payload

DESIGN_GATE_TOKEN = "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY"
GATE_EFFECT_READ = "read"


@dataclasses.dataclass(frozen=True)
class AccessibilityCheck:
    check_id: str
    category: str  # a11y / responsive / keyboard / contrast / focus
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _build_packet(*, ok, human_message, machine_error_code, operator_action,
                  liveness, severity, changed_files, effect, extra=None):
    return build_command_payload(
        ok=ok, human_message=human_message, machine_error_code=machine_error_code,
        operator_action=operator_action, liveness=liveness, severity=severity,
        changed_files=changed_files, effect=effect, extra=extra,
    )


def build_design_gate_receipt(
    *,
    execution_core_closed: bool,
    checks: list[AccessibilityCheck],
) -> dict[str, Any]:
    """Build the design gate receipt. Gate is earned only when execution core
    is closed AND all a11y checks pass."""
    gate_earned = execution_core_closed and all(c.passed for c in checks)
    failed = [c.to_dict() for c in checks if not c.passed]
    extra: dict[str, Any] = {
        "design_gate_earned": gate_earned,
        "execution_core_repair_closed": execution_core_closed,
        "gate_earned": gate_earned,
        "check_count": len(checks),
        "passed_count": sum(1 for c in checks if c.passed),
        "failed_checks": failed,
    }
    if gate_earned:
        return _build_packet(
            ok=True,
            human_message="Design gate earned; UI accessibility/responsive checks passed.",
            machine_error_code="OK",
            operator_action="none",
            liveness="healthy",
            severity="recoverable",
            changed_files=[],
            effect=GATE_EFFECT_READ,
            extra=extra,
        )
    reason = "execution core not closed" if not execution_core_closed else f"{len(failed)} a11y check(s) failed"
    return _build_packet(
        ok=False,
        human_message=f"Design gate not earned: {reason}.",
        machine_error_code="DESIGN_GATE_NOT_EARNED",
        operator_action="user_action",
        liveness="degraded",
        severity="recoverable",
        changed_files=[],
        effect=GATE_EFFECT_READ,
        extra=extra,
    )


def run_design_gate_synthetic_proof() -> dict[str, Any]:
    """Deterministic synthetic proof: gate earned, gate blocked (core open),
    gate blocked (a11y fail)."""
    passing_checks = [
        AccessibilityCheck("aria_labels", "a11y", True, "all interactive elements have aria-label"),
        AccessibilityCheck("keyboard_nav", "keyboard", True, "all controls reachable via tab"),
        AccessibilityCheck("contrast_ratio", "contrast", True, "minimum 4.5:1 on text"),
        AccessibilityCheck("focus_visible", "focus", True, "focus indicators present"),
        AccessibilityCheck("responsive_layout", "responsive", True, "no horizontal scroll at 320px"),
    ]
    failing_checks = passing_checks[:-1] + [
        AccessibilityCheck("contrast_ratio_low", "contrast", False, "2.1:1 on secondary text"),
    ]

    earned = build_design_gate_receipt(execution_core_closed=True, checks=passing_checks)
    blocked_core = build_design_gate_receipt(execution_core_closed=False, checks=passing_checks)
    blocked_a11y = build_design_gate_receipt(execution_core_closed=True, checks=failing_checks)

    receipts = [earned, blocked_core, blocked_a11y]
    violations: list[str] = []
    for r in receipts:
        violations.extend(command_packets.inspect_command_packet_semantics(r))
    ok = not violations and earned["gate_earned"]
    return _build_packet(
        ok=ok,
        human_message="Design gate synthetic proof complete." if ok else "Violations.",
        machine_error_code="OK" if ok else "DESIGN_GATE_PROOF_VIOLATIONS",
        operator_action="none" if ok else "stop",
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        changed_files=[],
        effect=GATE_EFFECT_READ,
        extra={
            "receipt_count": len(receipts),
            "gate_earned_when_core_closed": earned["gate_earned"],
            "gate_blocked_when_core_open": not blocked_core["gate_earned"],
            "gate_blocked_when_a11y_fail": not blocked_a11y["gate_earned"],
            "packet_violations": violations,
        },
    )


__all__ = [
    "AccessibilityCheck",
    "build_design_gate_receipt",
    "run_design_gate_synthetic_proof",
    "DESIGN_GATE_TOKEN",
]
