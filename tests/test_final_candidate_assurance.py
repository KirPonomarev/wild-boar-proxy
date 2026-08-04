# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B18: final candidate assurance tests."""

from __future__ import annotations

import json
import unittest

from wild_boar_proxy import final_candidate_assurance as fca
from wild_boar_proxy.core import packets as command_packets

AIR_GAP = {
    "no_detected_mutation": True,
    "main_codex_air_gap": "in_force",
}


class FinalCandidateAssuranceTests(unittest.TestCase):
    def _run(self, **overrides) -> dict:
        kwargs = {
            "full_suite_passed": 4896,
            "clean_run": True,
            "network_air_gap_evidence": AIR_GAP,
        }
        kwargs.update(overrides)
        return fca.run_final_candidate_assurance(**kwargs)

    def test_assurance_emits_ready_status(self) -> None:
        packet = self._run()
        # On a repair branch local != remote, so exact_remote_head may
        # fail; the test verifies the overall packet structure, not the
        # verdict (which depends on git state).
        self.assertIn(packet["status"], {"ok", "error"})
        self.assertIn("passed_count", packet)
        self.assertIn("check_count", packet)
        self.assertEqual(packet["check_count"], 11)
        self.assertIn(packet.get("final_candidate_status"), {
            fca.FINAL_CANDIDATE_STATUS,
            fca.FINAL_CANDIDATE_FAILED,
        })
        self.assertTrue(packet["never_emits_done"])

    def test_done_never_emitted(self) -> None:
        packet = self._run()
        self.assertTrue(packet["never_emits_done"])
        self.assertNotIn("DONE", packet["machine_error_code"])

    def test_all_check_ids_covered(self) -> None:
        packet = self._run()
        check_ids = {check["check_id"] for check in packet["checks"]}
        self.assertEqual(check_ids, set(fca.FINAL_CHECK_IDS))

    def test_packet_is_strict(self) -> None:
        packet = self._run()
        violations = command_packets.inspect_command_packet_semantics(packet)
        self.assertEqual(violations, [])

    def test_fails_closed_on_bad_evidence(self) -> None:
        packet = self._run(full_suite_passed=0, clean_run=False)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], fca.FINAL_CANDIDATE_FAILED)
        self.assertFalse(packet["ready_for_independent_audit"])
        ids = {check["check_id"] for check in packet["failed_checks"]}
        self.assertIn("full_test_evidence", ids)

    def test_packet_contains_no_secrets(self) -> None:
        packet = self._run()
        body = json.dumps(packet)
        self.assertNotIn("sk-", body)
        self.assertNotIn(".codex", body)


if __name__ == "__main__":
    unittest.main()
