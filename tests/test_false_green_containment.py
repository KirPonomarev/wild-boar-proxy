# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""False-green containment tests.

These tests verify that deterministic synthetic proofs can never be mistaken
for physical acceptance, and that placeholder/fake git identities can never be
accepted as physical proof. They lock the contract repair (T01/T02):

- Synthetic E2E / voice proofs report ``SYNTHETIC_PROVEN`` (never ``OK``).
- Final assurance rejects fake SHAs with ``FINAL_ASSURANCE_INVALID_IDENTITY``
  and still accepts valid 40-hex SHAs with ``WBP_MASTER_PLAN_V3_6_DONE``.
- Kimi / GLM route builders pass the production ``validate_route_schema()``.
"""

from __future__ import annotations

import unittest

import final_assurance_git_fixture as fa_fixture
from wild_boar_proxy import (
    desktop_pilot_contract as dpc,
    kimi_glm_provider_slices as kg,
    native_voice_parity as vp,
    release_e2e_contract as re2e,
)
from wild_boar_proxy.core import packets
from wild_boar_proxy.external_models.routes import validate_route_schema


def _assert_semantics(testcase, packet):
    missing = packets.missing_required_fields(
        packet, list(packets.COMMAND_PACKET_REQUIRED_FIELDS)
    )
    testcase.assertEqual(missing, [], f"missing: {missing}")
    violations = packets.inspect_command_packet_semantics(packet)
    testcase.assertEqual(violations, [], f"violations: {violations}")


class ReleaseE2ESyntheticProofContainmentTests(unittest.TestCase):
    def test_synthetic_proof_reports_synthetic_proven_not_ok(self) -> None:
        s = re2e.run_release_e2e_synthetic_proof()
        _assert_semantics(self, s)
        self.assertNotEqual(s["machine_error_code"], "OK")
        self.assertEqual(s["machine_error_code"], "SYNTHETIC_PROVEN")

    def test_synthetic_proof_human_message_says_synthetic(self) -> None:
        s = re2e.run_release_e2e_synthetic_proof()
        self.assertIn("synthetic", s["human_message"].lower())

    def test_synthetic_proof_marks_evidence_level(self) -> None:
        s = re2e.run_release_e2e_synthetic_proof()
        self.assertEqual(s["evidence_level"], "SYNTHETIC_PROVEN")


class VoiceSyntheticProofContainmentTests(unittest.TestCase):
    def test_synthetic_proof_reports_synthetic_proven_not_ok(self) -> None:
        s = vp.run_voice_synthetic_proof()
        _assert_semantics(self, s)
        self.assertNotEqual(s["machine_error_code"], "OK")
        self.assertEqual(s["machine_error_code"], "SYNTHETIC_PROVEN")

    def test_synthetic_proof_human_message_says_synthetic(self) -> None:
        s = vp.run_voice_synthetic_proof()
        self.assertIn("synthetic", s["human_message"].lower())

    def test_synthetic_proof_marks_evidence_level(self) -> None:
        s = vp.run_voice_synthetic_proof()
        self.assertEqual(s["evidence_level"], "SYNTHETIC_PROVEN")


class FinalAssuranceIdentityContainmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Valid identities come from a hermetic fixture git repository (three
        # tagged commits, ``dpc._REPO_ROOT`` patched to it): a clean CI
        # checkout may not carry the v0.x release tags, and resolving the real
        # tags would collapse every identity to HEAD (SHA_COLLISION verdict).
        cls._SHAS = fa_fixture.install_final_assurance_git_fixture(cls)

    def test_fake_shas_rejected_as_invalid_identity(self) -> None:
        r = dpc.run_final_assurance_audit(
            web_release_sha="fake",
            provider_release_sha="x",
            desktop_release_sha="totally_fake",
            safety_counters_zero=True,
            user_wip_preserved=True,
            no_plan_owned_processes=True,
            no_repo_master_plan=True,
        )
        _assert_semantics(self, r)
        self.assertNotEqual(r["machine_error_code"], "WBP_MASTER_PLAN_V3_6_DONE")
        self.assertEqual(
            r["machine_error_code"], dpc.FINAL_ASSURANCE_INVALID_IDENTITY
        )

    def test_valid_40hex_shas_still_accepted_as_done(self) -> None:
        # Fixture repo commit SHAs for the three milestones: only identities
        # that resolve to existing commits are accepted.
        shas = self._SHAS
        r = dpc.run_final_assurance_audit(
            web_release_sha=shas["web_v0_1_0"],
            provider_release_sha=shas["provider_v0_2_0"],
            desktop_release_sha=shas["desktop_v0_3_0"],
            safety_counters_zero=True,
            user_wip_preserved=True,
            no_plan_owned_processes=True,
            no_repo_master_plan=True,
        )
        _assert_semantics(self, r)
        self.assertEqual(r["machine_error_code"], "WBP_MASTER_PLAN_V3_6_DONE")

    def test_validate_git_sha_existence(self) -> None:
        # Shape check helper still classifies well-formed 40-hex strings.
        self.assertTrue(dpc._git_sha_is_hex("a" * 40))
        self.assertTrue(dpc._git_sha_is_hex("0123456789abcdef" * 2 + "0123456789ABCDEF"[:8]))
        self.assertFalse(dpc._git_sha_is_hex("fake"))
        self.assertFalse(dpc._git_sha_is_hex("a" * 39))
        self.assertFalse(dpc._git_sha_is_hex("a" * 41))
        self.assertFalse(dpc._git_sha_is_hex("g" * 40))  # non-hex
        self.assertFalse(dpc._git_sha_is_hex(""))
        # The strict validator must reject a well-shaped-but-nonexistent SHA
        # (it does not exist as a commit in the repo) and accept a real one.
        self.assertFalse(dpc._validate_git_sha("a" * 40))
        self.assertFalse(dpc._validate_git_sha("0123456789abcdef" * 2 + "0123456789ABCDEF"[:8]))
        self.assertTrue(dpc._validate_git_sha(self._SHAS["web_v0_1_0"]))


class KimiGlmRouteDefinitionContainmentTests(unittest.TestCase):
    def test_kimi_route_passes_production_validator(self) -> None:
        route = kg.build_kimi_route_definition()
        validated = validate_route_schema(route)
        self.assertEqual(validated["route_id"], "wbp-kimi-primary")
        self.assertEqual(validated["provider"], kg.KIMI_PROVIDER_ID)

    def test_glm_route_passes_production_validator(self) -> None:
        route = kg.build_glm_route_definition()
        validated = validate_route_schema(route)
        self.assertEqual(validated["route_id"], "wbp-glm-primary")
        self.assertEqual(validated["provider"], kg.GLM_PROVIDER_ID)


if __name__ == "__main__":
    unittest.main()
