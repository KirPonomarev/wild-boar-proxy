# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.owner_handoff_blocker_gate_r1_probe import (
    FINAL_STATUS,
    OWNER_BLOCKER_IDS,
    build_packets,
    validate_blocker_gate_payload,
)


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "owner_handoff_blocker_gate_r1_probe.py"


class OwnerHandoffBlockerGateR1ProbeTests(unittest.TestCase):
    def test_build_packets_keeps_owner_blockers_open_without_live_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            packets = build_packets(repo_root=ROOT, evidence_dir=Path(tmpdir) / "evidence")

        gate = packets["owner_handoff_blocker_gate_packet.json"]
        self.assertEqual(gate["status"], "ok")
        self.assertEqual(gate["final_status"], FINAL_STATUS)
        self.assertTrue(gate["final_status_with_limits"])
        self.assertFalse(gate["global_product_acceptance_claimed"])
        self.assertFalse(gate["readiness_counts_as_proof"])
        self.assertFalse(gate["owner_required_blockers_counted_as_closed"])
        self.assertFalse(gate["gate_is_repo_resident_roadmap"])
        self.assertFalse(gate["live_actions_attempted_here"])
        self.assertFalse(gate["paid_calls_attempted_here"])
        self.assertFalse(gate["original_codex_touched_here"])
        self.assertEqual(gate["owner_required_blocker_count"], len(OWNER_BLOCKER_IDS))
        self.assertEqual(gate["validation"]["status"], "ok")
        self.assertEqual(gate["validation"]["violation_count"], 0)

        rows = {row["id"]: row for row in gate["owner_required_blockers"]}
        self.assertEqual(set(rows), set(OWNER_BLOCKER_IDS))
        for blocker_id, row in rows.items():
            self.assertTrue(row["owner_required"], blocker_id)
            self.assertFalse(row["proof_present"], blocker_id)
            self.assertFalse(row["readiness_counts_as_proof"], blocker_id)
            self.assertFalse(row["counts_as_closed_without_owner"], blocker_id)
            self.assertIn(
                row["status"],
                {"blocked_owner_required", "classified_with_limits"},
                blocker_id,
            )
            self.assertTrue(row["supporting_packets"], blocker_id)
            self.assertFalse(any(row["guards"].values()), blocker_id)

        history = rows["live_native_relaunch_history_restore"]["guards"]
        self.assertFalse(history["synthetic_storage_counted_as_live_history_restore"])
        self.assertFalse(history["thread_history_files_counted_as_native_visible_restore"])
        self.assertFalse(history["role_slot_persistence_counted_as_thread_history"])
        self.assertFalse(history["operator_visible_context_counted_as_storage_proof"])

        provider = rows["live_provider_response_smoke"]["guards"]
        self.assertFalse(provider["selection_intent_counted_as_execution"])
        self.assertFalse(provider["selection_intent_counted_as_provider_response"])
        self.assertFalse(provider["route_snapshot_counted_as_provider_response"])
        self.assertFalse(provider["recording_runner_counted_as_live_upstream"])
        self.assertFalse(provider["provider_matrix_claimed_live_acceptance"])

        concurrency = rows["live_concurrent_dual_lane_execution"]["guards"]
        self.assertFalse(concurrency["sequential_chain_counted_as_concurrency"])
        self.assertFalse(concurrency["same_session_counted_as_parallel_execution"])
        self.assertFalse(concurrency["concurrency_classification_counted_as_throughput_gain"])
        self.assertFalse(concurrency["paid_parallel_fanout_counted_as_proven"])

        budget = rows["owner_authorized_paid_budget_policy"]["guards"]
        self.assertFalse(budget["paid_route_executed_without_owner_policy"])
        self.assertFalse(budget["declared_policy_counted_as_hard_spend_gate"])
        self.assertFalse(budget["hard_spend_gate_claimed_without_proof"])
        self.assertFalse(budget["fallback_policy_settled_without_owner"])

        binding = packets["owner_handoff_final_matrix_binding_packet.json"]
        self.assertEqual(binding["status"], "ok")
        self.assertTrue(binding["final_matrix_with_limits_preserved"])
        self.assertFalse(binding["final_matrix_global_product_acceptance_claimed"])
        self.assertFalse(binding["final_matrix_owner_leftovers_counted_as_closed"])
        self.assertFalse(binding["gate_counts_as_live_api_history_or_concurrency_proof"])

        false_green = packets["false_green_boundary_packet.json"]
        self.assertEqual(false_green["status"], "ok")
        self.assertFalse(false_green["readiness_treated_as_proof"])
        self.assertFalse(false_green["selection_intent_treated_as_execution"])
        self.assertFalse(false_green["selection_intent_treated_as_provider_response"])
        self.assertFalse(false_green["route_snapshot_treated_as_provider_response"])
        self.assertFalse(false_green["synthetic_storage_treated_as_live_history_restore"])
        self.assertFalse(false_green["recording_runner_treated_as_live_upstream"])
        self.assertFalse(false_green["operator_observed_context_treated_as_durable_storage"])
        self.assertFalse(false_green["with_limits_treated_as_full_green"])
        self.assertFalse(false_green["owner_blockers_closed_without_owner"])
        self.assertFalse(false_green["gate_treated_as_roadmap"])

        audit = packets["independent_audit_packet.json"]
        self.assertEqual(audit["status"], "ok")
        finding_ids = {finding["id"] for finding in audit["findings"]}
        self.assertIn("owner_blockers_remain_blocked_or_limited_until_owner_action", finding_ids)
        self.assertIn("final_dual_lane_status_remains_with_limits", finding_ids)
        self.assertIn(
            "live_provider_response_history_restore_and_concurrency_unproven_here",
            finding_ids,
        )
        self.assertIn("paid_budget_policy_requires_owner_authorization", finding_ids)

    def test_validation_blocks_false_green_owner_gate_payloads(self) -> None:
        valid = {
            "final_status": FINAL_STATUS,
            "final_status_with_limits": True,
            "global_product_acceptance_claimed": False,
            "gate_is_repo_resident_roadmap": False,
            "owner_required_blockers_counted_as_closed": False,
            "owner_required_blockers": [
                {
                    "id": blocker_id,
                    "status": "blocked_owner_required",
                    "owner_required": True,
                    "proof_present": False,
                    "readiness_counts_as_proof": False,
                    "counts_as_closed_without_owner": False,
                    "guards": {},
                }
                for blocker_id in OWNER_BLOCKER_IDS
            ],
        }
        self.assertEqual(validate_blocker_gate_payload(valid)["status"], "ok")

        bad = json.loads(json.dumps(valid))
        bad["final_status"] = "OWNER_HANDOFF_BLOCKER_GATE_PROVEN"
        bad["global_product_acceptance_claimed"] = True
        bad["gate_is_repo_resident_roadmap"] = True
        bad["owner_required_blockers_counted_as_closed"] = True
        bad["owner_required_blockers"][0]["proof_present"] = True
        bad["owner_required_blockers"][0]["counts_as_closed_without_owner"] = True
        bad["owner_required_blockers"][1]["readiness_counts_as_proof"] = True
        bad["owner_required_blockers"][2]["guards"] = {
            "route_snapshot_treated_as_provider_response": True
        }
        result = validate_blocker_gate_payload(bad)
        violations = {item["violation"] for item in result["violations"]}
        self.assertEqual(result["status"], "blocked")
        self.assertIn("wrong_final_status", violations)
        self.assertIn("final_status_without_with_limits", violations)
        self.assertIn("global_product_acceptance_claimed", violations)
        self.assertIn("gate_treated_as_repo_resident_roadmap", violations)
        self.assertIn("owner_required_blockers_counted_as_closed", violations)
        self.assertIn("proof_present_without_owner", violations)
        self.assertIn("owner_blocker_closed_without_owner", violations)
        self.assertIn("readiness_counted_as_proof", violations)
        self.assertIn("false_green_guard_enabled", violations)

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
            self.assertEqual(summary["packet_count"], 4)

            gate = json.loads(
                (evidence_dir / "owner_handoff_blocker_gate_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(gate["status"], "ok")
            self.assertEqual(gate["final_status"], FINAL_STATUS)
            self.assertFalse(gate["owner_required_blockers_counted_as_closed"])


if __name__ == "__main__":
    unittest.main()
