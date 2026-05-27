# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.keychain_system_prompt_behavior_readiness_r1_probe import (
    PARENT_STATUS,
    TARGET_STATUS,
    build_independent_audit_packet,
    build_keychain_prompt_false_green_audit,
    build_readiness_packets,
    build_summary_packet,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class KeychainSystemPromptBehaviorReadinessR1ProbeTests(unittest.TestCase):
    def test_summary_closes_readiness_only_and_keeps_parent_open(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        summary = packets["keychain_prompt_readiness_summary_packet.json"]

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertEqual(summary["parent_target"], PARENT_STATUS)
        self.assertFalse(summary["parent_target_closed"])
        self.assertTrue(summary["this_target_closed"])
        self.assertFalse(summary["native_launch_attempted"])
        self.assertFalse(summary["custom_app_launch_attempted"])
        self.assertFalse(summary["owner_prompt_required"])
        self.assertFalse(summary["live_provider_request_attempted"])
        self.assertFalse(summary["keychain_mutation_performed"])
        self.assertFalse(summary["keychain_reset_performed"])
        self.assertFalse(summary["keychain_independence_claimed"])
        self.assertFalse(summary["prompt_behavior_classified"])
        self.assertFalse(summary["prompt_suppressed_claimed"])
        self.assertFalse(summary["auth_success_claimed"])
        self.assertFalse(summary["native_ux_claimed"])
        self.assertFalse(summary["original_codex_auth_keychain_dependency"])
        self.assertFalse(summary["final_e2e_claimed"])

    def test_owner_action_boundary_does_not_become_machine_or_auth_proof(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        owner = packets["keychain_allowed_owner_action_boundary_packet.json"]

        self.assertEqual(
            owner["allowed_future_owner_actions"],
            ["Cancel", "Allow", "Ignore", "Not Observed"],
        )
        self.assertFalse(owner["owner_action_performed"])
        self.assertFalse(owner["owner_cancel_counted_as_machine_proof"])
        self.assertFalse(owner["owner_allow_counted_as_auth_success"])
        self.assertFalse(owner["owner_ignore_counted_as_prompt_resolution"])
        self.assertFalse(owner["automatic_owner_ready_treated_as_live_authorization"])
        self.assertTrue(owner["prompt_action_boundary_ack_required_for_future_live"])

    def test_keychain_absence_is_not_independence_and_no_hidden_mutation(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        observation = packets["keychain_observation_readiness_packet.json"]
        mutation = packets["keychain_no_hidden_mutation_packet.json"]

        self.assertEqual(observation["status"], "ok")
        self.assertFalse(observation["machine_prompt_observed"])
        self.assertFalse(observation["prompt_behavior_classified"])
        self.assertFalse(observation["keychain_independence_claimed"])
        self.assertFalse(observation["auth_success_claimed"])
        self.assertFalse(mutation["keychain_mutation_performed"])
        self.assertFalse(mutation["keychain_reset_performed"])
        self.assertFalse(mutation["keychain_default_changed"])
        self.assertFalse(mutation["original_codex_keychain_mutated"])
        self.assertFalse(mutation["keychain_write_allowed"])

    def test_original_codex_auth_keychain_is_not_custom_dependency(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        dependency = packets["original_codex_auth_keychain_non_dependency_packet.json"]

        self.assertEqual(dependency["status"], "ok")
        self.assertFalse(dependency["original_codex_auth_keychain_dependency"])
        self.assertFalse(dependency["original_codex_auth_json_execution_dependency"])
        self.assertFalse(dependency["original_codex_keychain_runtime_dependency"])
        self.assertFalse(dependency["original_codex_keychain_mutated"])
        self.assertFalse(dependency["current_auth_json_copied"])
        self.assertFalse(dependency["current_auth_json_symlinked"])
        self.assertFalse(dependency["file_auth_used_in_this_contour"])
        self.assertFalse(dependency["readiness_counts_as_runtime_non_dependency_proof"])

    def test_auth_strategy_interaction_is_reference_only_not_auth_success(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        auth = packets["auth_strategy_prompt_interaction_readiness_packet.json"]

        self.assertEqual(auth["status"], "ok")
        self.assertTrue(auth["auth_strategy_reference"]["reference_only"])
        self.assertEqual(auth["selected_strategy"], "auth.command")
        self.assertFalse(auth["auth_strategy_reproved_in_this_contour"])
        self.assertFalse(auth["auth_invoked_in_this_contour"])
        self.assertFalse(auth["auth_success_claimed"])
        self.assertTrue(auth["auth_success_requires_future_live_trace"])
        self.assertFalse(auth["keychain_prompt_behavior_classified"])
        self.assertFalse(auth["current_codex_auth_json_used"])
        self.assertFalse(auth["original_codex_auth_keychain_dependency"])

    def test_minimization_is_not_hidden_suppression(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        prohibition = packets["system_prompt_suppression_prohibition_packet.json"]
        minimization = packets["prompt_minimization_not_suppression_packet.json"]

        self.assertFalse(prohibition["asar_patching_allowed"])
        self.assertFalse(prohibition["codesign_hacks_allowed"])
        self.assertFalse(prohibition["dyld_injection_allowed"])
        self.assertFalse(prohibition["hidden_runtime_mutation_allowed"])
        self.assertFalse(prohibition["suppression_attempted"])
        self.assertFalse(prohibition["prompt_suppressed_claimed"])
        self.assertTrue(minimization["minimization_prepared"])
        self.assertFalse(minimization["minimization_executed"])
        self.assertFalse(minimization["prompt_suppressed_claimed"])
        self.assertFalse(minimization["hidden_suppression_performed"])
        self.assertFalse(minimization["absence_of_prompt_counts_as_minimization_success"])
        self.assertFalse(minimization["minimization_counts_as_keychain_independence"])

    def test_future_live_stop_gate_blocks_automatic_owner_ready(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        gate = packets["future_live_owner_stop_gate_packet.json"]

        self.assertTrue(gate["future_live_must_stop_before_launch"])
        self.assertFalse(gate["live_execution_allowed_in_this_contour"])
        self.assertFalse(gate["automatic_owner_ready_treated_as_live_authorization"])
        self.assertFalse(gate["previous_owner_approval_reusable"])
        self.assertFalse(gate["generic_owner_ready_enough"])
        self.assertIn("prompt_action_boundary_ack=true", gate["allowed_future_owner_signals"])
        self.assertIn("generic owner_ready_now=true", gate["not_enough_by_itself"])
        self.assertFalse(gate["owner_input_required"])
        self.assertFalse(gate["owner_prompt_required"])

    def test_false_green_audit_blocks_core_overclaims(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        owner = dict(packets["keychain_allowed_owner_action_boundary_packet.json"])
        owner["owner_allow_counted_as_auth_success"] = True
        no_mutation = dict(packets["keychain_no_hidden_mutation_packet.json"])
        no_mutation["keychain_reset_performed"] = True
        original = dict(packets["original_codex_auth_keychain_non_dependency_packet.json"])
        original["original_codex_auth_keychain_dependency"] = True
        auth = dict(packets["auth_strategy_prompt_interaction_readiness_packet.json"])
        auth["auth_success_claimed"] = True
        suppression = dict(packets["system_prompt_suppression_prohibition_packet.json"])
        suppression["suppression_attempted"] = True
        minimization = dict(packets["prompt_minimization_not_suppression_packet.json"])
        minimization["prompt_suppressed_claimed"] = True
        live_stop = dict(packets["future_live_owner_stop_gate_packet.json"])
        live_stop["automatic_owner_ready_treated_as_live_authorization"] = True

        audit = build_keychain_prompt_false_green_audit(
            owner_action=owner,
            no_mutation=no_mutation,
            original_dependency=original,
            auth_interaction=auth,
            suppression=suppression,
            minimization=minimization,
            live_stop=live_stop,
            non_substitution=packets["keychain_prompt_non_substitution_packet.json"],
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertIn("owner_allow_counted_as_auth_success", audit["findings"])
        self.assertIn("keychain_reset_performed", audit["findings"])
        self.assertIn("original_codex_auth_keychain_dependency", audit["findings"])
        self.assertIn("auth_success_claimed", audit["findings"])
        self.assertIn("system_prompt_suppression_attempted", audit["findings"])
        self.assertIn("prompt_minimization_treated_as_suppression", audit["findings"])
        self.assertIn(
            "automatic_owner_ready_treated_as_live_authorization",
            audit["findings"],
        )

    def test_independent_audit_blocks_forbidden_true_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        mutated = dict(packets)
        mutated["future_live_owner_stop_gate_packet.json"] = {
            **mutated["future_live_owner_stop_gate_packet.json"],
            "live_execution_allowed_in_this_contour": True,
        }
        audit = build_independent_audit_packet(mutated)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "future_live_owner_stop_gate_packet.json.live_execution_allowed_in_this_contour",
            audit["forbidden_true_fields"],
        )

    def test_summary_blocks_missing_or_blocked_gating_packets(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        blocked_packets = dict(packets)
        blocked_packets["keychain_prompt_false_green_audit.json"] = {
            **blocked_packets["keychain_prompt_false_green_audit.json"],
            "status": "blocked",
        }
        blocked_summary = build_summary_packet(blocked_packets)

        missing_packets = dict(packets)
        del missing_packets["future_live_owner_stop_gate_packet.json"]
        missing_summary = build_summary_packet(missing_packets)

        self.assertEqual(blocked_summary["status"], "blocked")
        self.assertIn(
            "keychain_prompt_false_green_audit.json",
            blocked_summary["blocked_packets"],
        )
        self.assertEqual(missing_summary["status"], "blocked")
        self.assertIn(
            "future_live_owner_stop_gate_packet.json",
            missing_summary["missing_required_packets"],
        )

    def test_secret_audit_records_no_raw_prompt_or_secret(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        secret = packets["secret_redaction_audit.json"]

        self.assertEqual(secret["status"], "ok")
        self.assertFalse(secret["raw_secret_found"])
        self.assertFalse(secret["raw_prompt_found"])
        self.assertFalse(secret["raw_secret_recorded"])
        self.assertFalse(secret["raw_prompt_recorded"])
        self.assertFalse(secret["exhaustive_dlp_claimed"])
        self.assertEqual(secret["secret_marker_findings"], [])
        self.assertEqual(secret["prompt_marker_findings"], [])


if __name__ == "__main__":
    unittest.main()
