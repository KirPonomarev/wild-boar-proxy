# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Deterministic contract tests for desktop pilot and final assurance (D00–F00)."""

from __future__ import annotations

import unittest

import final_assurance_git_fixture as fa_fixture
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

    def test_empty_step_set_rejected(self) -> None:
        # B00 F1: an empty required-step collection must never be accepted as a
        # released pilot (`all([])` is True for an empty list).
        r = dpc.build_desktop_pilot_receipt(
            candidate=self._candidate(), steps=[], clean_machine_available=True
        )
        _assert_semantics(self, r)
        self.assertNotEqual(r["machine_error_code"], "WBP_DESKTOP_PILOT_V0_3_0_RELEASED")
        self.assertEqual(r["machine_error_code"], "DESKTOP_PILOT_EMPTY_STEP_SET")
        self.assertEqual(r["status"], "error")


class FinalAssuranceTests(unittest.TestCase):
    # Milestone identities come from a hermetic fixture git repository (three
    # tagged commits, ``dpc._REPO_ROOT`` patched to it): a clean CI checkout
    # may not carry the v0.1.0/v0.2.0/v0.3.0 tags, and resolving the real
    # tags would collapse every identity to HEAD (FINAL_ASSURANCE_SHA_COLLISION).
    @classmethod
    def setUpClass(cls) -> None:
        shas = fa_fixture.install_final_assurance_git_fixture(cls)
        cls._SHA_WEB = shas["web_v0_1_0"]
        cls._SHA_PROVIDER = shas["provider_v0_2_0"]
        cls._SHA_DESKTOP = shas["desktop_v0_3_0"]

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

    def test_well_shaped_but_nonexistent_sha_rejected(self) -> None:
        # "a"*40 is a valid SHA shape but does not exist as a commit: the audit
        # must reject it rather than accept it on shape alone.
        r = dpc.run_final_assurance_audit(
            web_release_sha="a" * 40,
            provider_release_sha=self._SHA_PROVIDER,
            desktop_release_sha=self._SHA_DESKTOP,
            safety_counters_zero=True, user_wip_preserved=True,
            no_plan_owned_processes=True, no_repo_master_plan=True,
        )
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], dpc.FINAL_ASSURANCE_INVALID_IDENTITY)
        self.assertEqual(r["invalid_identities"], ["web_release_sha"])

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

    def test_same_sha_for_all_milestones_rejected(self) -> None:
        # B00 F2: one SHA must not stand for multiple independent release
        # milestones (web_v0_1_0 / provider_v0_2_0 / desktop_v0_3_0).
        r = dpc.run_final_assurance_audit(
            web_release_sha=self._SHA_WEB,
            provider_release_sha=self._SHA_WEB,
            desktop_release_sha=self._SHA_WEB,
            safety_counters_zero=True, user_wip_preserved=True,
            no_plan_owned_processes=True, no_repo_master_plan=True,
        )
        _assert_semantics(self, r)
        self.assertNotEqual(r["machine_error_code"], "WBP_MASTER_PLAN_V3_6_DONE")
        self.assertEqual(r["machine_error_code"], dpc.FINAL_ASSURANCE_SHA_COLLISION)
        self.assertEqual(r["status"], "error")


class SyntheticProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # run_final_assurance_synthetic_proof resolves milestone SHAs from git
        # tags via _REPO_ROOT; point it at the hermetic fixture repo so the
        # proof does not depend on the host checkout's tags or history depth.
        fa_fixture.install_final_assurance_git_fixture(cls)

    def test_desktop_proof_ok(self) -> None:
        s = dpc.run_desktop_pilot_synthetic_proof()
        _assert_semantics(self, s)
        self.assertEqual(s["status"], "ok")

    def test_final_assurance_proof_ok(self) -> None:
        s = dpc.run_final_assurance_synthetic_proof()
        _assert_semantics(self, s)
        self.assertEqual(s["status"], "ok")
        self.assertTrue(s["done_when_all_present"])
        self.assertTrue(s["blocked_when_safety_nonzero"])


if __name__ == "__main__":
    unittest.main()
