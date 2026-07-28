# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Deterministic contract tests for keychain credential broker (P04)."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from wild_boar_proxy import keychain_credential_broker as kcb
from wild_boar_proxy.core import packets


def _assert_semantics(testcase, packet):
    missing = packets.missing_required_fields(packet, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    testcase.assertEqual(missing, [], f"missing: {missing}")
    violations = packets.inspect_command_packet_semantics(packet)
    testcase.assertEqual(violations, [], f"violations: {violations}")


class ForbiddenProviderTests(unittest.TestCase):
    def test_codex_blocked(self) -> None:
        r = kcb.lookup_keychain_credential(provider="codex")
        self.assertFalse(r.found)

    def test_openai_blocked(self) -> None:
        r = kcb.lookup_keychain_credential(provider="openai")
        self.assertFalse(r.found)

    def test_chatgpt_blocked(self) -> None:
        r = kcb.lookup_keychain_credential(provider="chatgpt")
        self.assertFalse(r.found)


class SafePacketFieldsTests(unittest.TestCase):
    def test_no_secret_value_in_safe_fields(self) -> None:
        r = kcb.KeychainLookupResult(
            provider="kimi", found=True, service="Moonshot", account="key",
            secret_value="sk-secret-value-here", secret_digest="a" * 64,
        )
        safe = r.safe_packet_fields
        body = json.dumps(safe)
        self.assertNotIn("sk-secret", body)
        self.assertNotIn("secret_value", body)
        self.assertTrue(safe["credential_present"])
        self.assertEqual(safe["credential_ref_digest"], "a" * 64)

    def test_missing_result_has_no_digest(self) -> None:
        r = kcb.KeychainLookupResult(
            provider="kimi", found=False, service=None, account=None,
            secret_value=None, secret_digest=None,
        )
        self.assertFalse(r.safe_packet_fields["credential_present"])
        self.assertIsNone(r.safe_packet_fields["credential_ref_digest"])


class KeychainLookupTests(unittest.TestCase):
    def test_custom_service_account_used(self) -> None:
        with mock.patch.object(kcb, "_security_find_generic_password", return_value="key123") as m:
            r = kcb.lookup_keychain_credential(
                provider="kimi", custom_service="MyService", custom_account="MyAccount"
            )
        self.assertTrue(r.found)
        self.assertEqual(r.service, "MyService")
        m.assert_called_once_with(service="MyService", account="MyAccount")

    def test_not_found_returns_empty(self) -> None:
        with mock.patch.object(kcb, "_security_find_generic_password", return_value=None):
            r = kcb.lookup_keychain_credential(provider="kimi")
        self.assertFalse(r.found)
        self.assertIsNone(r.secret_value)

    def test_kimi_candidates_iterated(self) -> None:
        call_count = {"n": 0}
        def fake_lookup(*, service, account):
            call_count["n"] += 1
            if service == "Kimi" and account == "api_key":
                return "found-it"
            return None
        with mock.patch.object(kcb, "_security_find_generic_password", side_effect=fake_lookup):
            r = kcb.lookup_keychain_credential(provider="kimi")
        self.assertTrue(r.found)
        self.assertEqual(r.service, "Kimi")
        self.assertEqual(r.secret_value, "found-it")


class StatusPacketTests(unittest.TestCase):
    def test_found_packet_ok(self) -> None:
        with mock.patch.object(kcb, "_security_find_generic_password", return_value="key"):
            packet = kcb.build_keychain_credential_status_packet(provider="kimi")
        _assert_semantics(self, packet)
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["credential_present"])

    def test_missing_packet_ok_with_code(self) -> None:
        with mock.patch.object(kcb, "_security_find_generic_password", return_value=None):
            packet = kcb.build_keychain_credential_status_packet(provider="glm")
        _assert_semantics(self, packet)
        self.assertFalse(packet["credential_present"])
        self.assertEqual(packet["machine_error_code"], "KEYCHAIN_CREDENTIAL_MISSING")

    def test_no_secret_in_packet(self) -> None:
        with mock.patch.object(kcb, "_security_find_generic_password", return_value="sk-secret"):
            packet = kcb.build_keychain_credential_status_packet(provider="kimi")
        body = json.dumps(packet)
        self.assertNotIn("sk-secret", body)

    def test_keychain_dump_false(self) -> None:
        packet = kcb.build_keychain_credential_status_packet(provider="kimi")
        self.assertFalse(packet["keychain_dump_performed"])
        self.assertFalse(packet["keychain_mutation_performed"])
        self.assertFalse(packet["original_codex_keychain_read"])


class SyntheticProofTests(unittest.TestCase):
    def test_summary_ok(self) -> None:
        s = kcb.run_keychain_broker_synthetic_proof()
        _assert_semantics(self, s)
        self.assertEqual(s["status"], "ok")
        self.assertTrue(s["forbidden_provider_blocked"])
        self.assertTrue(s["no_secret_leak"])
        self.assertTrue(s["no_keychain_dump"])
        self.assertTrue(s["no_keychain_mutation"])
        self.assertTrue(s["no_codex_keychain_read"])


if __name__ == "__main__":
    unittest.main()
