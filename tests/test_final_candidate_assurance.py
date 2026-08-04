# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B18: final candidate assurance tests (strict).

Uses mocked git state to test both success and failure deterministically.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch, MagicMock

from wild_boar_proxy import final_candidate_assurance as fca
from wild_boar_proxy.core import packets as command_packets


class FinalCandidateAssuranceTests(unittest.TestCase):
    """Tests use mocked git to control exact_remote_head deterministically."""

    @patch("wild_boar_proxy.final_candidate_assurance._git_remote_head")
    def test_assurance_emits_ready_when_heads_match(self, mock_heads) -> None:
        mock_heads.return_value = ("abc123", "abc123")
        packet = fca.run_final_candidate_assurance(
            full_suite_passed=4900,
            clean_run=True,
            network_air_gap_evidence={"x": True},
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], fca.FINAL_CANDIDATE_STATUS)
        self.assertEqual(packet["final_candidate_status"], fca.FINAL_CANDIDATE_STATUS)
        self.assertTrue(packet["ready_for_independent_audit"])
        self.assertEqual(packet["passed_count"], 11)
        self.assertEqual(packet["check_count"], 11)
        self.assertEqual(packet["failed_checks"], [])

    @patch("wild_boar_proxy.final_candidate_assurance._git_remote_head")
    def test_assurance_fails_when_heads_mismatch(self, mock_heads) -> None:
        mock_heads.return_value = ("local123", "remote456")
        packet = fca.run_final_candidate_assurance(
            full_suite_passed=4900,
            clean_run=True,
            network_air_gap_evidence={"x": True},
        )
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], fca.FINAL_CANDIDATE_FAILED)
        self.assertFalse(packet["ready_for_independent_audit"])
        ids = {c["check_id"] for c in packet["failed_checks"]}
        self.assertIn("exact_remote_head", ids)

    def test_done_never_emitted(self) -> None:
        with patch("wild_boar_proxy.final_candidate_assurance._git_remote_head", return_value=("a","a")):
            packet = fca.run_final_candidate_assurance(
                full_suite_passed=1, clean_run=True,
                network_air_gap_evidence={"x": True},
            )
        self.assertTrue(packet["never_emits_done"])
        self.assertNotIn("DONE", packet["machine_error_code"])

    def test_all_check_ids_covered(self) -> None:
        with patch("wild_boar_proxy.final_candidate_assurance._git_remote_head", return_value=("a","a")):
            packet = fca.run_final_candidate_assurance(
                full_suite_passed=1, clean_run=True,
                network_air_gap_evidence={"x": True},
            )
        check_ids = {check["check_id"] for check in packet["checks"]}
        self.assertEqual(check_ids, set(fca.FINAL_CHECK_IDS))

    def test_packet_is_strict(self) -> None:
        with patch("wild_boar_proxy.final_candidate_assurance._git_remote_head", return_value=("a","a")):
            packet = fca.run_final_candidate_assurance(
                full_suite_passed=1, clean_run=True,
                network_air_gap_evidence={"x": True},
            )
        violations = command_packets.inspect_command_packet_semantics(packet)
        self.assertEqual(violations, [])

    def test_packet_contains_no_secrets(self) -> None:
        with patch("wild_boar_proxy.final_candidate_assurance._git_remote_head", return_value=("a","a")):
            packet = fca.run_final_candidate_assurance(
                full_suite_passed=1, clean_run=True,
                network_air_gap_evidence={"x": True},
            )
        body = json.dumps(packet)
        self.assertNotIn("sk-", body)
        self.assertNotIn(".codex", body)


if __name__ == "__main__":
    unittest.main()
