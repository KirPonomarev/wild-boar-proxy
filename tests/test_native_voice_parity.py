# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations
import unittest
from wild_boar_proxy import native_voice_parity as vp
from wild_boar_proxy.core import packets

def _assert(t, p):
    m = packets.missing_required_fields(p, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    t.assertEqual(m, [], f"missing: {m}")
    v = packets.inspect_command_packet_semantics(p)
    t.assertEqual(v, [], f"violations: {v}")

class VoiceParityTests(unittest.TestCase):
    def test_all_acceptance_met(self):
        r = vp.build_voice_parity_receipt()
        _assert(self, r)
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["no_browser_bridge"])
        self.assertTrue(r["no_auto_submit"])

    def test_forbidden_action_detected(self):
        r = vp.build_voice_parity_receipt(forbidden={"clipboard_paste_bridge": True})
        _assert(self, r)
        self.assertEqual(r["status"], "error")

    def test_acceptance_not_met(self):
        r = vp.build_voice_parity_receipt(acceptance={"native_voice_shortcut_available": False, "native_voice_icon_observed": True,
            "microphone_permission_proven": True, "custom_profile_bound": True,
            "original_codex_mutated": False, "transcript_visible_in_composer": True, "prompt_auto_submitted": False})
        _assert(self, r)
        self.assertEqual(r["status"], "error")

class RegressionMatrixTests(unittest.TestCase):
    def test_alias_preserved(self):
        r = vp.build_voice_regression_matrix_receipt()
        _assert(self, r)
        self.assertTrue(all(a["alias_preserved_in_transcript"] for a in r["alias_tests"]))

    def test_covers_kimi_glm_dip_codex(self):
        labels = {a[0].split(":")[0] for a in vp.V03_ALIAS_TESTS}
        self.assertIn("Kimi", labels)
        self.assertIn("GLM", labels)
        self.assertIn("DIP", labels)
        self.assertIn("Codex", labels)

class SyntheticProofTests(unittest.TestCase):
    def test_summary_ok(self):
        s = vp.run_voice_synthetic_proof()
        _assert(self, s)
        self.assertEqual(s["status"], "ok")
        self.assertTrue(s["experimental_does_not_block_release"])

if __name__ == "__main__":
    unittest.main()
