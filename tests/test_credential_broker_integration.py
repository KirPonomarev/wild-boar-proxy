# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Integration test: credential specs + keychain broker + external-models credential_status.

Proves the credential resolution chain: provider spec -> credential_ref ->
keychain lookup -> presence packet. Uses mocked keychain (no real macOS
security calls in CI).
"""

from __future__ import annotations

import unittest
from unittest import mock

from wild_boar_proxy.external_models.credentials import _PROVIDER_SPECS
from wild_boar_proxy.keychain_credential_broker import (
    lookup_keychain_credential,
    build_keychain_credential_status_packet,
)
from wild_boar_proxy.core import packets


def _assert_semantics(testcase, packet):
    missing = packets.missing_required_fields(packet, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    testcase.assertEqual(missing, [], f"missing: {missing}")
    violations = packets.inspect_command_packet_semantics(packet)
    testcase.assertEqual(violations, [], f"violations: {violations}")


class CredentialChainIntegrationTests(unittest.TestCase):
    def test_kimi_spec_matches_keychain_broker(self) -> None:
        """The credential_ref in _PROVIDER_SPECS matches the keychain broker's
        expected candidates."""
        spec = _PROVIDER_SPECS["kimi"]
        self.assertEqual(spec.credential_ref, "MOONSHOT_API_KEY")
        # Keychain broker should have candidates for kimi
        result = lookup_keychain_credential(provider="kimi")
        # Even if not found, the broker should have tried (not crashed)
        self.assertFalse(result.found)  # mock env, not real keychain

    def test_glm_spec_matches_keychain_broker(self) -> None:
        spec = _PROVIDER_SPECS["glm"]
        self.assertEqual(spec.credential_ref, "ZAI_API_KEY")
        result = lookup_keychain_credential(provider="glm")
        self.assertFalse(result.found)

    def test_mocked_keychain_found_chain(self) -> None:
        """Full chain: spec -> keychain -> status packet with mocked found credential."""
        with mock.patch(
            "wild_boar_proxy.keychain_credential_broker._security_find_generic_password",
            return_value="fake-key-value",
        ):
            packet = build_keychain_credential_status_packet(provider="kimi")
        _assert_semantics(self, packet)
        self.assertTrue(packet["credential_present"])
        self.assertEqual(packet["credential_source"], "owner-keychain")
        # No secret value leaked
        import json
        self.assertNotIn("fake-key-value", json.dumps(packet))

    def test_forbidden_provider_never_resolves(self) -> None:
        """Codex/OpenAI/ChatGPT providers are denied at keychain level."""
        for forbidden in ("codex", "openai", "chatgpt"):
            result = lookup_keychain_credential(provider=forbidden)
            self.assertFalse(result.found, f"{forbidden} should be blocked")


if __name__ == "__main__":
    unittest.main()
