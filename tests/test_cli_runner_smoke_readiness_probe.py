# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.cli_runner_smoke_readiness_probe import (
    PARENT_STATUS,
    TARGET_STATUS,
    build_false_green_audit,
    build_independent_audit_packet,
    build_readiness_packets,
    build_summary_packet,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class CliRunnerSmokeReadinessProbeTests(unittest.TestCase):
    def test_summary_closes_readiness_only_not_cli_runner_works(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        summary = packets["cli_runner_readiness_summary_packet.json"]
        live_gate = packets["cli_runner_live_promotion_gate_packet.json"]
        false_green = packets["cli_runner_false_green_audit.json"]

        if summary["status"] == "blocked":
            self.assertIn("sync_gate_packet.json", summary["blocked_packets"])
            self.assertFalse(summary["parent_target_closed"])
            self.assertFalse(summary["cli_runner_smoke_pass_proven"])
            self.assertFalse(summary["codex_runner_smoke_executed"])
            return
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertEqual(summary["parent_target"], PARENT_STATUS)
        self.assertFalse(summary["parent_target_closed"])
        self.assertFalse(summary["cli_runner_smoke_pass_proven"])
        self.assertFalse(summary["codex_runner_smoke_executed"])
        self.assertFalse(summary["native_app_proven"])
        self.assertFalse(summary["model_availability_proven"])
        self.assertFalse(live_gate["codex_runner_smoke_allowed_in_this_contour"])
        self.assertFalse(false_green["cli_runner_smoke_pass_claimed"])

    def test_command_shape_and_prompt_are_prepared_but_not_executed(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        command = packets["cli_runner_command_shape_packet.json"]
        prompt = packets["cli_runner_prompt_redaction_packet.json"]

        self.assertTrue(command["command_shape_prepared"])
        self.assertFalse(command["command_executed"])
        self.assertFalse(command["codex_runner_smoke_executed"])
        self.assertFalse(command["live_provider_request_attempted"])
        self.assertFalse(command["native_launch_attempted"])
        self.assertFalse(command["command_shape_counts_as_cli_smoke_pass"])
        self.assertFalse(command["command_shape_counts_as_model_availability"])
        self.assertFalse(command["raw_prompt_recorded"])
        self.assertTrue(prompt["prompt_hash_only"])
        self.assertFalse(prompt["prompt_text_used_for_execution"])
        self.assertFalse(prompt["prompt_redaction_counts_as_response_proof"])

    def test_auth_and_model_selection_do_not_become_proof(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        auth = packets["cli_runner_auth_boundary_packet.json"]
        model = packets["cli_runner_model_selection_boundary_packet.json"]

        self.assertEqual(auth["status"], "ok")
        self.assertTrue(auth["auth_command_required"])
        self.assertFalse(auth["auth_reproved_in_this_contour"])
        self.assertFalse(auth["auth_invoked_in_this_contour"])
        self.assertFalse(auth["current_codex_auth_json_used"])
        self.assertFalse(auth["auth_boundary_counts_as_cli_smoke_pass"])
        self.assertEqual(model["status"], "ok")
        self.assertTrue(model["model_readiness_reference"]["reference_only"])
        self.assertEqual(
            model["candidate_selection_source"],
            "model_availability_readiness_reference",
        )
        self.assertTrue(model["candidate_selected_for_future_smoke"])
        self.assertFalse(model["model_availability_reproved_in_this_contour"])
        self.assertFalse(model["model_availability_claimed"])
        self.assertFalse(model["gpt_5_5_availability_claimed"])
        self.assertFalse(model["browser_can_supply_model_authority"])
        self.assertFalse(model["selection_counts_as_cli_smoke_pass"])
        self.assertFalse(model["selection_counts_as_model_availability"])

    def test_non_substitution_keeps_cli_readiness_below_native_and_e2e(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        non_substitution = packets["cli_runner_non_substitution_packet.json"]

        self.assertFalse(non_substitution["cli_runner_readiness_is_cli_smoke_pass"])
        self.assertFalse(non_substitution["cli_runner_smoke_pass_is_native_codex_app_proof"])
        self.assertFalse(non_substitution["cli_runner_smoke_pass_is_model_availability_matrix"])
        self.assertFalse(non_substitution["cli_runner_smoke_pass_is_final_e2e"])
        self.assertFalse(non_substitution["cli_runner_response_is_native_codex_app_response"])
        self.assertFalse(non_substitution["native_app_claimed"])
        self.assertFalse(non_substitution["direct_egress_absence_claimed"])
        self.assertFalse(non_substitution["streaming_claimed"])
        self.assertFalse(non_substitution["tool_loop_claimed"])
        self.assertFalse(non_substitution["final_e2e_claimed"])

    def test_false_green_audit_blocks_execution_or_overclaim_regression(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        command = dict(packets["cli_runner_command_shape_packet.json"])
        command["command_executed"] = True
        model = dict(packets["cli_runner_model_selection_boundary_packet.json"])
        model["model_availability_claimed"] = True
        live_gate = dict(packets["cli_runner_live_promotion_gate_packet.json"])
        live_gate["live_execution_allowed_in_this_contour"] = True

        audit = build_false_green_audit(
            command_shape=command,
            auth=packets["cli_runner_auth_boundary_packet.json"],
            model_selection=model,
            non_substitution=packets["cli_runner_non_substitution_packet.json"],
            live_gate=live_gate,
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertIn("command_executed", audit["findings"])
        self.assertIn("model_availability_claimed", audit["findings"])
        self.assertIn("live_execution_allowed", audit["findings"])

    def test_false_green_audit_blocks_non_reference_model_source(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        model = dict(packets["cli_runner_model_selection_boundary_packet.json"])
        model["model_readiness_reference"] = {
            **model["model_readiness_reference"],
            "reference_only": False,
        }

        audit = build_false_green_audit(
            command_shape=packets["cli_runner_command_shape_packet.json"],
            auth=packets["cli_runner_auth_boundary_packet.json"],
            model_selection=model,
            non_substitution=packets["cli_runner_non_substitution_packet.json"],
            live_gate=packets["cli_runner_live_promotion_gate_packet.json"],
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertIn("model_readiness_reference_not_reference_only", audit["findings"])

    def test_independent_audit_blocks_forbidden_true_fields_anywhere(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        mutated = dict(packets)
        mutated["cli_runner_command_shape_packet.json"] = {
            **mutated["cli_runner_command_shape_packet.json"],
            "command_executed": True,
        }
        audit = build_independent_audit_packet(mutated)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "cli_runner_command_shape_packet.json.command_executed",
            audit["forbidden_true_fields"],
        )

    def test_summary_blocks_missing_or_blocked_gating_packets(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        blocked_packets = dict(packets)
        blocked_packets["cli_runner_false_green_audit.json"] = {
            **blocked_packets["cli_runner_false_green_audit.json"],
            "status": "blocked",
            "findings": ["forced_test_finding"],
        }
        blocked_summary = build_summary_packet(blocked_packets)

        missing_packets = dict(packets)
        del missing_packets["cli_runner_command_shape_packet.json"]
        missing_summary = build_summary_packet(missing_packets)

        self.assertEqual(blocked_summary["status"], "blocked")
        self.assertIn("cli_runner_false_green_audit.json", blocked_summary["blocked_packets"])
        self.assertEqual(missing_summary["status"], "blocked")
        self.assertIn("cli_runner_command_shape_packet.json", missing_summary["missing_required_packets"])

    def test_secret_redaction_audit_does_not_record_raw_prompt_or_secret(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        secret = packets["secret_redaction_audit.json"]

        self.assertEqual(secret["status"], "ok")
        self.assertFalse(secret["raw_secret_found"])
        self.assertFalse(secret["raw_prompt_found"])
        self.assertFalse(secret["raw_prompt_recorded"])
        self.assertFalse(secret["exhaustive_dlp_claimed"])
        self.assertEqual(secret["secret_marker_findings"], [])


if __name__ == "__main__":
    unittest.main()
