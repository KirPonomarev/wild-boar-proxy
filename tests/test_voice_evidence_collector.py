# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations
import unittest
from wild_boar_proxy.voice_evidence_collector import (
    VoiceObservationReceipt, collect_voice_observations, REQUIRED_OBSERVATION_TYPES,
)
from wild_boar_proxy.core import packets

def _assert(t, p):
    m = packets.missing_required_fields(p, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    t.assertEqual(m, [], f"missing: {m}")
    v = packets.inspect_command_packet_semantics(p)
    t.assertEqual(v, [], f"violations: {v}")

def _obs(otype, result="observed"):
    return VoiceObservationReceipt(
        observation_id=f"obs-{otype}", codex_version="0.130.0", codex_build="100",
        profile_id="custom-profile-a", observation_type=otype,
        result=result, timestamp_utc="2026-07-28T00:00:00Z",
        observer="operator", detail=f"{otype} check",
    )


class VoiceEvidenceCollectorTests(unittest.TestCase):
    def test_empty_observations_unproven(self):
        r = collect_voice_observations([])
        _assert(self, r)
        self.assertEqual(r["machine_error_code"], "VOICE_STATUS_UNPROVEN")

    def test_partial_observations_unproven(self):
        r = collect_voice_observations([_obs("icon_check")])
        self.assertEqual(r["machine_error_code"], "VOICE_STATUS_UNPROVEN")
        self.assertIn("shortcut_check", r["missing_types"])

    def test_all_observed_accepted(self):
        obs = [_obs(t) for t in REQUIRED_OBSERVATION_TYPES]
        r = collect_voice_observations(obs)
        _assert(self, r)
        self.assertEqual(r["machine_error_code"], "VOICE_PARITY_ACCEPTED")
        self.assertEqual(r["evidence_level"], "PHYSICAL_PROVEN")

    def test_one_not_observed_not_met(self):
        obs = [_obs(t) for t in REQUIRED_OBSERVATION_TYPES]
        # Replace shortcut_check with a not_observed result
        obs = [_obs("shortcut_check", result="not_observed") if o.observation_type == "shortcut_check" else o for o in obs]
        r = collect_voice_observations(obs)
        self.assertEqual(r["machine_error_code"], "VOICE_PARITY_NOT_MET")

    def test_extra_observations_allowed(self):
        obs = [_obs(t) for t in REQUIRED_OBSERVATION_TYPES]
        obs.append(_obs("russian_speech"))
        r = collect_voice_observations(obs)
        self.assertEqual(r["machine_error_code"], "VOICE_PARITY_ACCEPTED")


if __name__ == "__main__":
    unittest.main()
