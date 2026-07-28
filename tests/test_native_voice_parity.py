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
    _SYNTHETIC_OBS = [{"step": "icon_check", "result": "observed", "evidence": "synthetic"}]

    def test_unproven_without_observations(self):
        r = vp.build_voice_parity_receipt()
        _assert(self, r)
        self.assertEqual(r["machine_error_code"], "VOICE_STATUS_UNPROVEN")
        self.assertFalse(r["observations_provided"])

    def test_all_acceptance_met(self):
        r = vp.build_voice_parity_receipt(
            acceptance=vp.V01_ACCEPTANCE, observations=self._SYNTHETIC_OBS,
        )
        _assert(self, r)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["machine_error_code"], "OK")
        self.assertTrue(r["no_browser_bridge"])
        self.assertTrue(r["no_auto_submit"])
        self.assertTrue(r["observations_provided"])

    def test_forbidden_action_detected(self):
        r = vp.build_voice_parity_receipt(
            acceptance=vp.V01_ACCEPTANCE,
            forbidden={"clipboard_paste_bridge": True},
            observations=self._SYNTHETIC_OBS,
        )
        _assert(self, r)
        self.assertEqual(r["status"], "error")

    def test_acceptance_not_met(self):
        bad_acc = dict(vp.V01_ACCEPTANCE)
        bad_acc["native_voice_shortcut_available"] = False
        r = vp.build_voice_parity_receipt(
            acceptance=bad_acc, observations=self._SYNTHETIC_OBS,
        )
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
