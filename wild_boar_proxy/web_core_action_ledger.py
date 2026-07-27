# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Web core action ledger and disabled-reason matrix (W10).

Inventories every visible web control, classifies it as functional, deferred
(disabled with machine-readable reason), or absent, and records a bounded
action ledger of recent web actions. Ensures no release control is decorative.
"""

from __future__ import annotations

import dataclasses
import hashlib
import time
from collections import deque
from typing import Any, Deque, Mapping

from .core import packets as command_packets
from .runtime import build_command_payload

LEDGER_EFFECT_READ = "read"
LEDGER_EFFECT_MUTATE = "mutate"

CONTROL_FUNCTIONAL = "functional"
CONTROL_DEFERRED = "deferred"
CONTROL_ABSENT = "absent"

MAX_LEDGER_ENTRIES = 32


@dataclasses.dataclass(frozen=True)
class ControlInventoryEntry:
    control_id: str
    screen: str
    classification: str  # functional / deferred / absent
    disabled_reason: str | None
    owner_command: str | None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class ActionLedgerEntry:
    action_id: str
    control_id: str
    observed_at_utc: str
    outcome: str  # "ok" / "error"
    machine_error_code: str
    changed_files: list[str]

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class ActionLedger:
    """Bounded in-memory action ledger (max MAX_LEDGER_ENTRIES)."""

    def __init__(self, max_entries: int = MAX_LEDGER_ENTRIES) -> None:
        self._entries: Deque[ActionLedgerEntry] = deque(maxlen=max_entries)

    def record(self, entry: ActionLedgerEntry) -> None:
        self._entries.append(entry)

    def entries(self) -> list[ActionLedgerEntry]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_packet(
    *, ok, human_message, machine_error_code, operator_action,
    liveness, severity, changed_files, effect, extra=None,
) -> dict[str, Any]:
    return build_command_payload(
        ok=ok, human_message=human_message, machine_error_code=machine_error_code,
        operator_action=operator_action, liveness=liveness, severity=severity,
        changed_files=changed_files, effect=effect, extra=extra,
    )


def build_control_inventory_receipt(
    *,
    entries: list[ControlInventoryEntry],
    ledger: ActionLedger | None = None,
) -> dict[str, Any]:
    """Build the control inventory + disabled-reason matrix receipt."""
    functional = [e for e in entries if e.classification == CONTROL_FUNCTIONAL]
    deferred = [e for e in entries if e.classification == CONTROL_DEFERRED]
    absent = [e for e in entries if e.classification == CONTROL_ABSENT]
    decorative = [
        e for e in entries
        if e.classification == CONTROL_FUNCTIONAL and not e.owner_command
    ]
    ledger_entries = [e.to_dict() for e in ledger.entries()] if ledger else []

    extra: dict[str, Any] = {
        "total_controls": len(entries),
        "functional_count": len(functional),
        "deferred_count": len(deferred),
        "absent_count": len(absent),
        "decorative_count": len(decorative),
        "deferred_with_reason": all(e.disabled_reason for e in deferred),
        "controls": [e.to_dict() for e in entries],
        "action_ledger": ledger_entries,
        "action_ledger_count": len(ledger_entries),
    }
    ok = len(decorative) == 0 and all(e.disabled_reason for e in deferred)
    return _build_packet(
        ok=ok,
        human_message=(
            "All release-visible controls are functional or deferred with reason."
            if ok
            else f"{len(decorative)} decorative control(s) or deferred-without-reason detected."
        ),
        machine_error_code="OK" if ok else "DECORATIVE_OR_UNREASONED_CONTROLS",
        operator_action="none" if ok else "user_action",
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        changed_files=[],
        effect=LEDGER_EFFECT_READ,
        extra=extra,
    )


def run_web_core_actions_synthetic_proof() -> dict[str, Any]:
    """Deterministic synthetic proof covering functional, deferred, absent
    controls, action ledger recording, and decorative detection."""
    # Standard control set: all functional or deferred-with-reason.
    good_entries = [
        ControlInventoryEntry("quick_start_runtime_status", "quick-start", CONTROL_FUNCTIONAL, None, "status"),
        ControlInventoryEntry("accounts_onboard", "accounts", CONTROL_FUNCTIONAL, None, "accounts onboard"),
        ControlInventoryEntry("api_connections_validate", "api-connections", CONTROL_FUNCTIONAL, None, "external-models validate"),
        ControlInventoryEntry("recovery_rollback", "recovery", CONTROL_DEFERRED, "rollback_requires_verified_snapshot", "rollback"),
        ControlInventoryEntry("diagnostics_export", "diagnostics", CONTROL_FUNCTIONAL, None, "diagnostics export"),
        ControlInventoryEntry("settings_setup_init", "settings", CONTROL_FUNCTIONAL, None, "installer init"),
    ]
    ledger = ActionLedger()
    for i, e in enumerate(good_entries[:3]):
        if e.classification == CONTROL_FUNCTIONAL:
            ledger.record(ActionLedgerEntry(
                action_id=f"act-{i}", control_id=e.control_id,
                observed_at_utc=_utc_now(), outcome="ok",
                machine_error_code="OK", changed_files=[],
            ))

    good_receipt = build_control_inventory_receipt(entries=good_entries, ledger=ledger)

    # Negative: decorative control (functional but no owner_command).
    bad_entries = good_entries + [
        ControlInventoryEntry("broken_button", "overview", CONTROL_FUNCTIONAL, None, None),
    ]
    bad_receipt = build_control_inventory_receipt(entries=bad_entries, ledger=ledger)

    # Negative: deferred without reason.
    no_reason_entries = [
        ControlInventoryEntry("deferred_no_reason", "settings", CONTROL_DEFERRED, None, None),
    ]
    no_reason_receipt = build_control_inventory_receipt(entries=no_reason_entries)

    receipts = [good_receipt, bad_receipt, no_reason_receipt]
    violations: list[str] = []
    for r in receipts:
        violations.extend(command_packets.inspect_command_packet_semantics(r))

    ok = not violations and good_receipt["status"] == "ok"
    return _build_packet(
        ok=ok,
        human_message="Web core actions synthetic proof complete." if ok else "Violations detected.",
        machine_error_code="OK" if ok else "WEB_CORE_ACTIONS_PROOF_VIOLATIONS",
        operator_action="none" if ok else "stop",
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        changed_files=[],
        effect=LEDGER_EFFECT_READ,
        extra={
            "receipt_count": len(receipts),
            "good_inventory_ok": good_receipt["status"] == "ok",
            "decorative_detected": bad_receipt["status"] == "error",
            "deferred_no_reason_detected": no_reason_receipt["status"] == "error",
            "packet_violations": violations,
        },
    )


__all__ = [
    "ControlInventoryEntry",
    "ActionLedgerEntry",
    "ActionLedger",
    "build_control_inventory_receipt",
    "run_web_core_actions_synthetic_proof",
    "CONTROL_FUNCTIONAL",
    "CONTROL_DEFERRED",
    "CONTROL_ABSENT",
]
