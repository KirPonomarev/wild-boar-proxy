# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Deterministic contract tests for web core action ledger (W10)."""

from __future__ import annotations

import unittest

from wild_boar_proxy import web_core_action_ledger as wca
from wild_boar_proxy.core import packets


def _assert_semantics(testcase, packet):
    missing = packets.missing_required_fields(packet, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    testcase.assertEqual(missing, [], f"missing: {missing}")
    violations = packets.inspect_command_packet_semantics(packet)
    testcase.assertEqual(violations, [], f"violations: {violations}")


class ControlInventoryTests(unittest.TestCase):
    def test_all_functional_ok(self) -> None:
        entries = [
            wca.ControlInventoryEntry("a", "s", wca.CONTROL_FUNCTIONAL, None, "cmd"),
            wca.ControlInventoryEntry("b", "s", wca.CONTROL_FUNCTIONAL, None, "cmd2"),
        ]
        r = wca.build_control_inventory_receipt(entries=entries)
        _assert_semantics(self, r)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["functional_count"], 2)

    def test_deferred_with_reason_ok(self) -> None:
        entries = [
            wca.ControlInventoryEntry("a", "s", wca.CONTROL_FUNCTIONAL, None, "cmd"),
            wca.ControlInventoryEntry("b", "s", wca.CONTROL_DEFERRED, "needs_config", "cmd2"),
        ]
        r = wca.build_control_inventory_receipt(entries=entries)
        _assert_semantics(self, r)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["deferred_count"], 1)

    def test_decorative_detected(self) -> None:
        entries = [
            wca.ControlInventoryEntry("a", "s", wca.CONTROL_FUNCTIONAL, None, None),  # no owner_command
        ]
        r = wca.build_control_inventory_receipt(entries=entries)
        _assert_semantics(self, r)
        self.assertEqual(r["status"], "error")
        self.assertEqual(r["machine_error_code"], "DECORATIVE_OR_UNREASONED_CONTROLS")
        self.assertEqual(r["decorative_count"], 1)

    def test_deferred_without_reason_detected(self) -> None:
        entries = [
            wca.ControlInventoryEntry("a", "s", wca.CONTROL_DEFERRED, None, "cmd"),
        ]
        r = wca.build_control_inventory_receipt(entries=entries)
        _assert_semantics(self, r)
        self.assertEqual(r["status"], "error")

    def test_absent_counted(self) -> None:
        entries = [
            wca.ControlInventoryEntry("a", "s", wca.CONTROL_ABSENT, None, None),
        ]
        r = wca.build_control_inventory_receipt(entries=entries)
        _assert_semantics(self, r)
        self.assertEqual(r["absent_count"], 1)


class ActionLedgerTests(unittest.TestCase):
    def test_ledger_records_and_retrieves(self) -> None:
        ledger = wca.ActionLedger()
        entry = wca.ActionLedgerEntry(
            action_id="a1", control_id="c1", observed_at_utc="2026-07-28T00:00:00Z",
            outcome="ok", machine_error_code="OK", changed_files=[],
        )
        ledger.record(entry)
        self.assertEqual(len(ledger.entries()), 1)

    def test_ledger_bounded(self) -> None:
        ledger = wca.ActionLedger(max_entries=3)
        for i in range(5):
            ledger.record(wca.ActionLedgerEntry(
                action_id=f"a{i}", control_id="c", observed_at_utc="2026-07-28T00:00:00Z",
                outcome="ok", machine_error_code="OK", changed_files=[],
            ))
        self.assertEqual(len(ledger.entries()), 3)

    def test_ledger_in_receipt(self) -> None:
        ledger = wca.ActionLedger()
        ledger.record(wca.ActionLedgerEntry(
            action_id="a1", control_id="c1", observed_at_utc="2026-07-28T00:00:00Z",
            outcome="ok", machine_error_code="OK", changed_files=[],
        ))
        entries = [wca.ControlInventoryEntry("c1", "s", wca.CONTROL_FUNCTIONAL, None, "cmd")]
        r = wca.build_control_inventory_receipt(entries=entries, ledger=ledger)
        self.assertEqual(r["action_ledger_count"], 1)


class SyntheticProofTests(unittest.TestCase):
    def test_summary_ok(self) -> None:
        s = wca.run_web_core_actions_synthetic_proof()
        _assert_semantics(self, s)
        self.assertEqual(s["status"], "ok")
        self.assertTrue(s["good_inventory_ok"])
        self.assertTrue(s["decorative_detected"])
        self.assertTrue(s["deferred_no_reason_detected"])


if __name__ == "__main__":
    unittest.main()
