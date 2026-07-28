# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Deterministic contract tests for provider capability schema v2 (P00–P04)."""

from __future__ import annotations

import unittest

from wild_boar_proxy import provider_capability_schema_v2 as pcs
from wild_boar_proxy.core import packets


def _assert_semantics(testcase, packet):
    missing = packets.missing_required_fields(packet, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    testcase.assertEqual(missing, [], f"missing: {missing}")
    violations = packets.inspect_command_packet_semantics(packet)
    testcase.assertEqual(violations, [], f"violations: {violations}")


class CapabilityMatrixTests(unittest.TestCase):
    def test_three_release_providers(self) -> None:
        self.assertEqual(len(pcs.RELEASE_PROVIDERS), 3)
        self.assertIn(pcs.PROVIDER_DEEPSEEK, pcs.RELEASE_PROVIDERS)
        self.assertIn(pcs.PROVIDER_GLM, pcs.RELEASE_PROVIDERS)
        self.assertIn(pcs.PROVIDER_KIMI, pcs.RELEASE_PROVIDERS)

    def test_qwen_excluded(self) -> None:
        self.assertIn(pcs.PROVIDER_QWEN, pcs.EXCLUDED_PROVIDERS)
        self.assertTrue(pcs.PROVIDER_PROFILES[pcs.PROVIDER_QWEN].excluded)

    def test_glm_has_vision_and_web_search(self) -> None:
        glm = pcs.PROVIDER_PROFILES[pcs.PROVIDER_GLM]
        self.assertTrue(glm.capability_vision)
        self.assertTrue(glm.capability_web_search)

    def test_kimi_has_vision_and_web_search(self) -> None:
        kimi = pcs.PROVIDER_PROFILES[pcs.PROVIDER_KIMI]
        self.assertTrue(kimi.capability_vision)
        self.assertTrue(kimi.capability_web_search)

    def test_deepseek_no_vision(self) -> None:
        ds = pcs.PROVIDER_PROFILES[pcs.PROVIDER_DEEPSEEK]
        self.assertFalse(ds.capability_vision)


class ReceiptTests(unittest.TestCase):
    def test_matrix_receipt_ok(self) -> None:
        r = pcs.build_provider_capability_matrix_receipt()
        _assert_semantics(self, r)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["schema_version"], 2)
        self.assertTrue(r["qwen_excluded"])

    def test_synthetic_proof_ok(self) -> None:
        s = pcs.run_provider_v02_synthetic_proof()
        _assert_semantics(self, s)
        self.assertEqual(s["status"], "ok")
        self.assertTrue(s["qwen_excluded"])


if __name__ == "__main__":
    unittest.main()
