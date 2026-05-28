# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from tools.budget_quota_fallback_and_concurrency_policy_r1_probe import build_packets
from wild_boar_proxy.codex_custom_sessions import CodexCustomSessionManager


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "budget_quota_fallback_and_concurrency_policy_r1_probe.py"


class BudgetQuotaFallbackAndConcurrencyPolicyR1ProbeTests(unittest.TestCase):
    def test_session_manager_blocks_concurrent_prompt_execution_per_session(self) -> None:
        from tools.budget_quota_fallback_and_concurrency_policy_r1_probe import (
            API_MODEL_ID,
            PRIMARY_MODEL_ID,
            api_snapshot,
            commands,
            operator_status,
        )

        started = threading.Event()
        release = threading.Event()
        calls: list[dict[str, object]] = []

        def runner(payload: dict[str, object]) -> dict[str, object]:
            calls.append(dict(payload))
            started.set()
            release.wait(timeout=2)
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "final_message": "PRIMARY_POLICY_OK",
                "secret_value_recorded": False,
                "configured_provider": "cliproxy",
                "configured_wire_api": "responses",
                "wbp_endpoint_configured": True,
                "config_endpoint_matches": True,
                "config_provider_matches": True,
                "config_wire_api_matches": True,
                "command_uses_stdin_dash": True,
                "command_json_mode": True,
                "env_codex_home_is_temp": True,
                "env_home_is_temp": True,
                "workdir_is_temp": True,
                "command_workdir_is_temp": True,
                "command_output_file_is_temp": True,
                "current_codex_home_used": False,
                "independent_wbp_trace_observed": True,
                "trace_observer_packet": {
                    "path": "/v1/responses",
                    "upstream_status": 200,
                    "forwarded_to_wbp": True,
                },
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CodexCustomSessionManager(Path(tmpdir) / "probe_session_root")
            created = manager.create_packet(
                {
                    "primary_model_id": PRIMARY_MODEL_ID,
                    "coding_agent_model_id": API_MODEL_ID,
                },
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )
            session_id = created["session"]["session_id"]
            thread_result: dict[str, object] = {}

            def invoke_first() -> None:
                thread_result["packet"] = manager.prompt_packet(
                    session_id,
                    {"prompt": "Reply with exactly FIRST."},
                    runner,
                    owner_authorized=True,
                )

            worker = threading.Thread(target=invoke_first)
            worker.start()
            self.assertTrue(started.wait(timeout=2))
            blocked = manager.prompt_packet(
                session_id,
                {"prompt": "Reply with exactly SECOND."},
                runner,
                owner_authorized=True,
            )
            release.set()
            worker.join(timeout=2)

        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(
            blocked["machine_error_code"], "CONCURRENT_PROMPT_EXECUTION_NOT_ALLOWED"
        )
        self.assertFalse(blocked["prompt_runner_called"])
        self.assertFalse(blocked["fallback_attempted"])
        self.assertEqual(blocked["next_action"], "wait_for_current_prompt_completion")
        self.assertEqual(len(calls), 1)
        self.assertEqual(thread_result["packet"]["status"], "ok")

    def test_build_packets_keep_policy_claims_narrow_and_packet_backed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            packets = build_packets(repo_root=ROOT, evidence_dir=evidence_dir)

        budget = packets["budget_boundary_packet.json"]
        self.assertEqual(budget["status"], "ok")
        self.assertTrue(budget["external_paid_route_policy_present"])
        self.assertFalse(budget["external_paid_routes_enabled_default"])
        self.assertEqual(budget["external_paid_route_default"], "blocked")
        self.assertFalse(budget["custom_session_budget_packet_present"])
        self.assertFalse(budget["hard_overspend_prevention_proven"])
        self.assertFalse(budget["pre_execution_spend_gate_proven"])
        self.assertEqual(budget["policy_enforcement_state"], "declared_or_partial_only")

        quota = packets["quota_handling_packet.json"]
        self.assertEqual(quota["quota_exhausted_count"], 1)
        self.assertEqual(quota["auth_invalid_count"], 1)
        self.assertEqual(quota["cooldown_only_count"], 1)
        self.assertFalse(quota["401_403_429_5xx_separate_runtime_policy_proven"])
        self.assertFalse(quota["retry_policy_explicit"])
        self.assertFalse(quota["quota_failure_implies_provider_family_incompatibility"])

        fallback = packets["fallback_boundary_packet.json"]
        self.assertTrue(fallback["fallback_eligible_schema_field_present"])
        self.assertFalse(fallback["automatic_fallback_policy_present"])
        self.assertTrue(fallback["invalid_slot_rejected_without_primary_fallback"])
        self.assertFalse(fallback["prompt_path_fallback_attempted"])
        self.assertTrue(fallback["blocked_provider_rows_present"])
        self.assertFalse(fallback["blocked_rows_auto_fallback_observed"])
        self.assertFalse(fallback["fallback_eligibility_implies_auto_fallback"])

        concurrency = packets["concurrency_boundary_packet.json"]
        self.assertTrue(concurrency["prompt_run_single_slot_only"])
        self.assertTrue(concurrency["browser_multi_slot_batch_request_forbidden"])
        self.assertTrue(concurrency["runner_payload_one_model_id_per_call"])
        self.assertTrue(concurrency["concurrent_execution_blocked_observed"])
        self.assertFalse(concurrency["concurrent_execution_observed"])
        self.assertFalse(concurrency["paid_parallel_fanout_proven"])
        self.assertEqual(concurrency["classification"], "forbidden_with_runtime_guard")
        self.assertFalse(concurrency["concurrency_classification_implies_throughput_gain"])

        slot_limits = packets["slot_execution_limit_packet.json"]
        self.assertIn("slot_ids", slot_limits["forbidden_prompt_run_fields"])
        self.assertEqual(slot_limits["runner_payload_keys"], ["model_id", "prompt"])
        self.assertTrue(slot_limits["one_model_dispatch_per_run"])
        self.assertFalse(slot_limits["slot_binding_runtime_dispatch_claimed"])

        gaps = packets["policy_gap_matrix.json"]
        gap_ids = {gap["id"] for gap in gaps["gaps"]}
        self.assertIn("hard_budget_enforcement_not_proven_in_custom_session_runtime", gap_ids)
        self.assertIn("operator_surface_pre_execution_spend_gate_not_proven_here", gap_ids)
        self.assertIn("automatic_fallback_policy_remains_absent_or_manual_only", gap_ids)
        self.assertIn("web_launch_default_model_substitution_not_closed_here", gap_ids)
        self.assertIn("concurrent_paid_fanout_remains_forbidden_or_unproven", gap_ids)

        false_green = packets["false_green_boundary_packet.json"]
        self.assertFalse(false_green["compatibility_row_becomes_automatic_fallback_target"])
        self.assertFalse(false_green["budget_presence_treated_as_hard_spend_protection"])
        self.assertFalse(false_green["concurrency_limit_treated_as_performance_improvement"])

    def test_probe_writes_required_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--repo-root",
                    str(ROOT),
                    "--evidence-dir",
                    str(evidence_dir),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["packet_count"], 9)

            policy_non_claims = json.loads(
                (evidence_dir / "policy_non_claims_packet.json").read_text(encoding="utf-8")
            )
            self.assertFalse(policy_non_claims["automatic_cross_provider_fallback_safe"])
            self.assertFalse(policy_non_claims["retry_behavior_production_grade"])
            self.assertFalse(policy_non_claims["budget_packet_presence_alone_implies_hard_spend_enforcement"])

            audit = json.loads(
                (evidence_dir / "independent_audit_packet.json").read_text(encoding="utf-8")
            )
            self.assertEqual(audit["status"], "ok")
            finding_ids = {finding["id"] for finding in audit["findings"]}
            self.assertIn(
                "silent_browser_driven_fallback_not_observed_in_current_prompt_path",
                finding_ids,
            )
            self.assertIn(
                "external_paid_route_policy_exists_only_as_declared_contract_here",
                finding_ids,
            )
            self.assertIn(
                "operator_surface_executes_before_full_spend_gate_proof",
                finding_ids,
            )
            self.assertIn(
                "launch_surfaces_still_allow_default_model_substitution_outside_this_fix",
                finding_ids,
            )


if __name__ == "__main__":
    unittest.main()
