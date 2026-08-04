# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B17: security / reliability / advanced-capability matrix tests."""

from __future__ import annotations

import json
import unittest

from wild_boar_proxy import security_reliability_matrix as srm
from wild_boar_proxy.core import packets as command_packets

CODE_X_FACTS = {
    "safety_override_in_force": True,
    "main_codex_paths_accessed": False,
    "main_codex_auth_read": False,
    "codex_commands_executed": [],
    "public_release_authorized": False,
}


class SecurityReliabilityMatrixTests(unittest.TestCase):
    def _run(self, facts=None) -> dict:
        return srm.run_security_reliability_matrix(main_codex_facts=facts or CODE_X_FACTS)

    def test_matrix_passes_all_checks(self) -> None:
        packet = self._run()
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], srm.MATRIX_OK)
        self.assertEqual(packet["check_count"], len(srm.MATRIX_CHECK_IDS))
        self.assertEqual(packet["passed_count"], 12)
        self.assertEqual(packet["guarded_count"], 1)
        self.assertEqual(packet["failed_checks"], [])
        check_ids = {check["check_id"] for check in packet["checks"]}
        self.assertEqual(check_ids, set(srm.MATRIX_CHECK_IDS))

    def test_matrix_packet_is_strict(self) -> None:
        packet = self._run()
        violations = command_packets.inspect_command_packet_semantics(packet)
        self.assertEqual(violations, [])

    def test_codex_guard_is_guarded_not_failed(self) -> None:
        packet = self._run()
        guard = next(
            check
            for check in packet["checks"]
            if check["check_id"] == "codex_upgrade_invalidation_guard"
        )
        self.assertEqual(guard["status"], "guarded")
        self.assertFalse(guard["detail"]["codex_surface_read"])

    def test_matrix_fails_closed_when_guard_facts_violated(self) -> None:
        bad_facts = dict(CODE_X_FACTS, main_codex_paths_accessed=True)
        packet = srm.run_security_reliability_matrix(main_codex_facts=bad_facts)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], srm.MATRIX_VIOLATIONS)
        ids = {check["check_id"] for check in packet["failed_checks"]}
        self.assertIn("protected_surface_guards", ids)
        self.assertIn("codex_upgrade_invalidation_guard", ids)

    def test_advanced_capabilities_checks_are_real(self) -> None:
        packet = self._run()
        advanced = next(
            check
            for check in packet["checks"]
            if check["check_id"] == "admitted_advanced_capabilities"
        )
        self.assertEqual(advanced["status"], "passed")
        self.assertTrue(advanced["detail"]["qwen_thinking"])
        self.assertTrue(advanced["detail"]["kimi_snapshot"])
        self.assertTrue(advanced["detail"]["glm"])

    def test_matrix_packet_contains_no_secrets(self) -> None:
        packet = self._run()
        body = json.dumps(packet)
        self.assertNotIn("sk-", body)
        self.assertNotIn("api_key", body.lower())
        self.assertNotIn(".codex", body)


if __name__ == "__main__":
    unittest.main()
