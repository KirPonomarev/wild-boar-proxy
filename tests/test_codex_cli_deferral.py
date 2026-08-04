# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B16_OPTIONAL: Codex CLI deferral tests."""

from __future__ import annotations

import json
import unittest

from wild_boar_proxy import codex_cli_deferral as ccd


class CodexCliDeferralTests(unittest.TestCase):
    def test_default_outcome_is_deferred(self) -> None:
        packet = ccd.evaluate_codex_cli_deferral()
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["outcome"], "CODEX_CLI_EXTENSION=DEFERRED"
        )
        self.assertTrue(packet["deferred"])
        self.assertEqual(packet["machine_error_code"], "OK")

    def test_safety_override_blocks_even_with_prerequisites(self) -> None:
        # Even if every execution prerequisite were claimed, the safety
        # override forbids the main Codex surface: deferral wins.
        packet = ccd.evaluate_codex_cli_deferral(
            owner_marker_present=True,
            dedicated_account_present=True,
            separate_home_present=True,
            file_credential_store_present=True,
            no_main_keyring_reuse_proven=True,
            codex_cli_experiment_authorized=True,
            safety_override_in_force=True,
        )
        self.assertTrue(packet["deferred"])
        self.assertEqual(packet["outcome"], ccd.CODEX_CLI_DEFERRED_OUTCOME)

    def test_facts_recorded_verbatim(self) -> None:
        packet = ccd.evaluate_codex_cli_deferral()
        facts = packet["facts"]
        self.assertFalse(facts["owner_exact_marker_present"])
        self.assertFalse(facts["dedicated_account_present"])
        self.assertFalse(facts["separate_home_present"])
        self.assertFalse(facts["file_credential_store_present"])
        self.assertFalse(facts["no_main_account_keyring_reuse_proven"])
        self.assertTrue(facts["safety_override_in_force"])
        self.assertFalse(facts["codex_cli_experiment_authorized"])

    def test_module_never_touches_codex_surface(self) -> None:
        packet = ccd.evaluate_codex_cli_deferral()
        self.assertFalse(packet["codex_surface_touched"])
        self.assertTrue(packet["probe_free_module"])

    def test_packet_contains_no_secrets_or_paths(self) -> None:
        packet = ccd.evaluate_codex_cli_deferral()
        body = json.dumps(packet)
        self.assertNotIn(".codex", body)
        self.assertNotIn("auth.json", body)
        self.assertNotIn("sk-", body)


if __name__ == "__main__":
    unittest.main()
