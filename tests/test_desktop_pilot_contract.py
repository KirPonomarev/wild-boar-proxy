# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Deterministic contract tests for desktop pilot and final assurance (D00–F00)."""

from __future__ import annotations

import unittest

from wild_boar_proxy import desktop_pilot_contract as dpc
from wild_boar_proxy.core import packets


def _assert_semantics(testcase, packet):
    missing = packets.missing_required_fields(packet, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    testcase.assertEqual(missing, [], f"missing: {missing}")
    violations = packets.inspect_command_packet_semantics(packet)
    testcase.assertEqual(violations, [], f"violations: {violations}")


class DesktopPilotReceiptTests(unittest.TestCase):
    def _candidate(self):
        return dpc.DesktopPilotCandidate(
            version="0.3.0", source_sha="abc", signing_classification=dpc.SIGNING_UNSIGNED, web_shell_reused=True
        )

    def _steps(self):
        return [dpc.DesktopLifecycleStep("s1", "step", False, True)]

    def test_released_with_clean_machine(self) -> None:
        r = dpc.build_desktop_pilot_receipt(candidate=self._candidate(), steps=self._steps(), clean_machine_available=True)
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], "WBP_DESKTOP_PILOT_V0_3_0_RELEASED")

    def test_wait_without_clean_machine(self) -> None:
        steps = self._steps() + [dpc.DesktopLifecycleStep("cm", "clean", True, True)]
        r = dpc.build_desktop_pilot_receipt(candidate=self._candidate(), steps=steps, clean_machine_available=False)
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], "WAIT_EXTERNAL_PREREQUISITE")

    def test_synthetic_failure_blocks(self) -> None:
        steps = [dpc.DesktopLifecycleStep("bad", "bad", False, False)]
        r = dpc.build_desktop_pilot_receipt(candidate=self._candidate(), steps=steps, clean_machine_available=True)
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], "DESKTOP_PILOT_SYNTHETIC_FAILURE")

    def test_original_app_mutations_zero(self) -> None:
        r = dpc.build_desktop_pilot_receipt(candidate=self._candidate(), steps=self._steps(), clean_machine_available=True)
        self.assertEqual(r["original_codex_app_mutations"], 0)


class FinalAssuranceTests(unittest.TestCase):
    _SHA_WEB = "a" * 40
    _SHA_PROVIDER = "b" * 40
    _SHA_DESKTOP = "c" * 40

    def test_done_when_all_present(self) -> None:
        r = dpc.run_final_assurance_audit(
            web_release_sha=self._SHA_WEB,
            provider_release_sha=self._SHA_PROVIDER,
            desktop_release_sha=self._SHA_DESKTOP,
            safety_counters_zero=True, user_wip_preserved=True,
            no_plan_owned_processes=True, no_repo_master_plan=True,
        )
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], "WBP_MASTER_PLAN_V3_6_DONE")

    def test_invalid_identity_rejected(self) -> None:
        r = dpc.run_final_assurance_audit(
            web_release_sha="fake", provider_release_sha="also_fake",
            desktop_release_sha="totally_fake",
            safety_counters_zero=True, user_wip_preserved=True,
            no_plan_owned_processes=True, no_repo_master_plan=True,
        )
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], dpc.FINAL_ASSURANCE_INVALID_IDENTITY)

    def test_blocked_when_safety_nonzero(self) -> None:
        r = dpc.run_final_assurance_audit(
            web_release_sha=self._SHA_WEB,
            provider_release_sha=self._SHA_PROVIDER,
            desktop_release_sha=self._SHA_DESKTOP,
            safety_counters_zero=False, user_wip_preserved=True,
            no_plan_owned_processes=True, no_repo_master_plan=True,
        )
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], "FINAL_ASSURANCE_INCOMPLETE")


class SyntheticProofTests(unittest.TestCase):
    def test_desktop_proof_ok(self) -> None:
        s = dpc.run_desktop_pilot_synthetic_proof()
        _assert_semantics(self, s)
        self.assertEqual(s["status"], "ok")

    def test_final_assurance_proof_ok(self) -> None:
        s = dpc.run_final_assurance_synthetic_proof()
        _assert_semantics(self, s)
        self.assertEqual(s["status"], "ok")
        self.assertTrue(s["done_when_all_present"])
        self.assertTrue(s["blocked_when_desktop_missing"])


if __name__ == "__main__":
    unittest.main()
