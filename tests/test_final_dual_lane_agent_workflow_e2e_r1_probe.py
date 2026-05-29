# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.final_dual_lane_agent_workflow_e2e_r1_probe import (
    _build_provenance_matrix,
    _dangerous_provenance_transitions,
    _provenance_row,
    build_packets,
)


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "final_dual_lane_agent_workflow_e2e_r1_probe.py"


class FinalDualLaneAgentWorkflowE2ER1ProbeTests(unittest.TestCase):
    def test_provenance_guard_blocks_dangerous_layer_transitions(self) -> None:
        rows = [
            _provenance_row(
                claim_id="bad_historical_runtime",
                source_packet="old.json",
                evidence_surface="historical",
                proof_level="historical_reference_only",
                freshness="historical",
                acceptance_role="bad",
                counted_in_bounded_final_flow=False,
                counts_as_live_runtime_proof=True,
                counts_as_capability_proof=False,
                with_limits=True,
                classification_reason="bad",
            ),
            _provenance_row(
                claim_id="bad_synthetic_runtime",
                source_packet="synthetic.json",
                evidence_surface="synthetic",
                proof_level="current_synthetic_storage_packet",
                freshness="current",
                acceptance_role="bad",
                counted_in_bounded_final_flow=False,
                counts_as_live_runtime_proof=True,
                counts_as_capability_proof=False,
                with_limits=True,
                classification_reason="bad",
            ),
            _provenance_row(
                claim_id="bad_imported_current",
                source_packet="imported.json",
                evidence_surface="imported",
                proof_level="imported_prior_packet",
                freshness="current",
                acceptance_role="bad",
                counted_in_bounded_final_flow=False,
                counts_as_live_runtime_proof=False,
                counts_as_capability_proof=False,
                with_limits=True,
                classification_reason="bad",
            ),
            _provenance_row(
                claim_id="bad_mocked_capability",
                source_packet="mock.json",
                evidence_surface="mocked",
                proof_level="current_mocked_runtime_packet",
                freshness="current",
                acceptance_role="bad",
                counted_in_bounded_final_flow=True,
                counts_as_live_runtime_proof=False,
                counts_as_capability_proof=True,
                with_limits=True,
                classification_reason="bad",
            ),
            _provenance_row(
                claim_id="bad_mocked_live_runtime",
                source_packet="mock.json",
                evidence_surface="mocked",
                proof_level="current_mocked_runtime_packet",
                freshness="current",
                acceptance_role="bad",
                counted_in_bounded_final_flow=True,
                counts_as_live_runtime_proof=True,
                counts_as_capability_proof=False,
                with_limits=True,
                classification_reason="bad",
            ),
        ]
        violations = {item["violation"] for item in _dangerous_provenance_transitions(rows)}
        self.assertIn("historical_reference_counted_as_live_runtime_proof", violations)
        self.assertIn("synthetic_storage_counted_as_live_runtime_proof", violations)
        self.assertIn("imported_prior_packet_marked_current", violations)
        self.assertIn("mocked_runtime_counted_as_capability_proof", violations)
        self.assertIn("mocked_runtime_counted_as_live_runtime_proof", violations)
        self.assertIn("capability_claim_without_separate_capability_packet", violations)

        no_limits_matrix = _build_provenance_matrix(
            final_status="CUSTOM_CODEX_DUAL_LANE_AGENT_WORKFLOW_PROVEN",
            global_product_acceptance_claimed=False,
        )
        self.assertEqual(no_limits_matrix["status"], "blocked")
        self.assertFalse(no_limits_matrix["final_status_with_limits"])

        global_acceptance_matrix = _build_provenance_matrix(
            final_status="CUSTOM_CODEX_DUAL_LANE_AGENT_WORKFLOW_PROVEN_WITH_LIMITS",
            global_product_acceptance_claimed=True,
        )
        self.assertEqual(global_acceptance_matrix["status"], "blocked")

    def test_build_packets_keep_final_flow_bounded_and_honest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packets = build_packets(repo_root=ROOT, evidence_dir=Path(temp_dir))

        selection = packets["final_dual_lane_selection_packet.json"]
        self.assertEqual(selection["status"], "ok")
        self.assertTrue(selection["server_issued_catalog_used"])
        self.assertTrue(selection["selection_intent_only_before_runtime"])
        self.assertFalse(selection["browser_authority_widened"])
        self.assertEqual(selection["allowed_browser_fields"], ["chatgpt_model_id", "api_model_id"])
        self.assertTrue(selection["selected_models_are_server_issued"])

        binding = packets["final_dual_lane_session_binding_packet.json"]
        self.assertEqual(binding["status"], "ok")
        self.assertEqual(binding["role_slot_binding_count"], 2)
        self.assertEqual(binding["primary_slot_model_id"], "gpt-5.3-codex")
        self.assertEqual(binding["coding_agent_slot_model_id"], "wbp-web-primary-openrouter")
        self.assertTrue(binding["role_slot_binding_proven"])
        self.assertTrue(binding["slot_catalog_revalidated"])
        self.assertFalse(binding["binding_is_chat_folklore"])

        runtime = packets["final_dual_lane_runtime_packet.json"]
        self.assertEqual(runtime["status"], "ok")
        self.assertTrue(runtime["same_custom_codex_environment"])
        self.assertEqual(
            runtime["primary_start_slot_id"],
            "primary_model_slot",
        )
        self.assertEqual(
            runtime["coding_slot_id"],
            "coding_agent_model_slot",
        )
        self.assertEqual(runtime["primary_return_slot_id"], "primary_model_slot")
        self.assertEqual(runtime["primary_start_provider"], "cliproxy")
        self.assertEqual(runtime["coding_provider"], "external_route")
        self.assertEqual(runtime["primary_return_provider"], "cliproxy")
        self.assertEqual(runtime["primary_start_source_provenance"], "backend_proven")
        self.assertEqual(runtime["coding_source_provenance"], "route_proven")
        self.assertEqual(runtime["primary_return_source_provenance"], "backend_proven")
        self.assertTrue(runtime["lane_specific_provenance_preserved"])
        self.assertFalse(runtime["silent_slot_substitution_observed"])
        self.assertFalse(runtime["silent_provider_substitution_observed"])
        self.assertEqual(runtime["runner_call_count"], 3)

        workflow = packets["final_dual_lane_workflow_packet.json"]
        self.assertEqual(workflow["status"], "ok")
        self.assertEqual(workflow["workflow_shape"], "primary_to_coding_to_primary")
        self.assertTrue(workflow["operator_mediated_sequential"])
        self.assertFalse(workflow["autonomous_orchestration_proven"])
        self.assertEqual(
            workflow["chain_step_messages"],
            ["PRIMARY_HANDOFF_READY", "CODING_ARTIFACT:API_PATCH", "PRIMARY_RETURN_CONFIRMED"],
        )
        self.assertTrue(workflow["coding_artifact_returned"])
        self.assertTrue(workflow["primary_return_consumed_coding_artifact"])
        self.assertFalse(workflow["successful_chain_implies_autonomy"])

        history = packets["final_dual_lane_history_packet.json"]
        self.assertEqual(history["status"], "ok")
        self.assertEqual(history["classification"], "synthetic_storage_only_with_limits")
        self.assertTrue(history["same_persistent_profile_identity"])
        self.assertTrue(history["profile_storage_changed"])
        self.assertTrue(history["thread_history_class_observed"])
        self.assertIn("thread_history", history["observed_state_classes"])
        self.assertIn("session_state", history["observed_state_classes"])
        self.assertTrue(history["owner_visible_thread_context_only"])
        self.assertFalse(history["owner_visible_thread_counted_as_storage_proof"])
        self.assertFalse(history["role_slot_persistence_counted_as_thread_history"])
        self.assertFalse(history["route_trace_counted_as_saved_thread_proof"])
        self.assertFalse(history["native_visible_thread_history_proven"])
        self.assertTrue(history["synthetic_history_state_preserved"])

        integrity = packets["final_dual_lane_integrity_packet.json"]
        self.assertEqual(integrity["status"], "ok")
        self.assertEqual(
            integrity["classification"],
            "inspection_only_boundary_plus_imported_safety_with_limits",
        )
        self.assertEqual(integrity["protected_surface_read_status"], "ok")
        self.assertFalse(integrity["current_contour_native_launch_attempted"])
        self.assertFalse(integrity["current_contour_temp_surface_action_performed"])
        self.assertFalse(integrity["current_contour_original_codex_write_performed"])
        self.assertTrue(integrity["protected_surface_scope_declared"])
        self.assertTrue(integrity["ambient_protected_surface_drift_can_block_stronger_claims"])
        self.assertEqual(integrity["imported_persistent_profile_safety_status"], "ok")
        self.assertFalse(integrity["imported_safety_final_e2e_claimed"])
        self.assertFalse(integrity["imported_safety_thread_history_claimed"])
        self.assertTrue(integrity["native_integrity_boundary_ok"])
        self.assertEqual(integrity["integration_baseline_status"], "ok")
        self.assertTrue(integrity["original_codex_untouched_within_admitted_evidence_scope"])

        acceptance = packets["final_dual_lane_acceptance_matrix.json"]
        self.assertEqual(acceptance["status"], "ok")
        self.assertEqual(
            acceptance["final_status"],
            "CUSTOM_CODEX_DUAL_LANE_AGENT_WORKFLOW_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(acceptance["bounded_final_flow_proven_here"])
        self.assertTrue(acceptance["acceptance_rows_all_satisfied"])
        self.assertEqual(
            acceptance["provenance_matrix_packet"],
            "final_dual_lane_provenance_matrix.json",
        )
        self.assertTrue(acceptance["provenance_matrix_required"])
        self.assertEqual(acceptance["provenance_matrix_status"], "ok")
        self.assertFalse(acceptance["historical_item_0_counted_as_closed"])
        self.assertTrue(acceptance["historical_item_0_inventory_closed"])
        self.assertFalse(acceptance["historical_item_0_runtime_acceptance_closed"])
        self.assertFalse(acceptance["historical_item_0_final_acceptance_counted"])
        self.assertEqual(
            acceptance["historical_item_0_classification_reason"],
            "reconciliation_only_not_runtime_acceptance",
        )
        self.assertEqual(acceptance["historical_item_0_runtime_proof_packet"], "")
        self.assertFalse(
            acceptance["historical_item_0_historical_evidence_used_as_runtime_proof"]
        )
        self.assertEqual(
            acceptance["historical_item_0_reconciliation_reference"],
            "historical_item_0_reconciliation_r1",
        )
        self.assertFalse(acceptance["global_product_acceptance_claimed"])
        row_index = {row["id"]: row for row in acceptance["rows"]}
        self.assertEqual(
            row_index["manual_provider_model_selection_works_for_both_lanes"]["acceptance_state"],
            "proven_here",
        )
        self.assertTrue(row_index["manual_provider_model_selection_works_for_both_lanes"]["satisfied"])
        self.assertEqual(
            row_index["persistent_history_is_separately_classified"]["acceptance_state"],
            "classified_with_limits_here",
        )
        self.assertTrue(row_index["persistent_history_is_separately_classified"]["with_limits"])
        self.assertEqual(
            row_index["original_codex_remains_untouched_within_admitted_scope"]["acceptance_state"],
            "classified_with_limits_here",
        )

        non_claims = packets["final_dual_lane_non_claims_packet.json"]
        self.assertFalse(non_claims["one_final_e2e_path_proves_broad_product_readiness"])
        self.assertFalse(non_claims["api_lane_equals_codex_high_or_extra_high"])
        self.assertFalse(non_claims["partial_acceleration_truth_becomes_broad_parity_here"])
        self.assertFalse(non_claims["historical_item_0_resolved_here"])
        self.assertFalse(
            non_claims["historical_item_0_inventory_closure_upgraded_to_runtime_acceptance"]
        )
        self.assertFalse(non_claims["bounded_workflow_success_implies_autonomy"])
        self.assertFalse(non_claims["one_admitted_api_row_proves_provider_family_compatibility"])
        self.assertFalse(non_claims["bounded_final_flow_acceptance_equals_global_product_acceptance"])
        self.assertFalse(non_claims["imported_prior_truth_reproven_without_reexercise"])
        self.assertFalse(non_claims["history_continuity_strengthens_integrity"])
        self.assertFalse(non_claims["integrity_strengthens_workflow_usefulness"])

        false_green = packets["false_green_boundary_packet.json"]
        self.assertFalse(false_green["selection_treated_as_execution_without_runtime"])
        self.assertFalse(false_green["imported_truth_treated_as_reproven_without_reexercise"])
        self.assertFalse(false_green["history_evidence_collapsed_into_integrity_claim"])
        self.assertFalse(false_green["integrity_evidence_collapsed_into_history_claim"])
        self.assertFalse(false_green["one_api_row_treated_as_provider_family_compatibility"])
        self.assertFalse(false_green["final_acceptance_matrix_treated_as_global_product_acceptance"])
        self.assertFalse(false_green["historical_item_0_treated_as_closed_here"])
        self.assertFalse(false_green["historical_item_0_inventory_treated_as_runtime_acceptance"])
        self.assertFalse(
            false_green["historical_item_0_final_acceptance_counted_without_runtime_proof"]
        )
        self.assertFalse(false_green["with_limits_truth_collapsed_into_unconditional_pass"])

        provenance = packets["final_dual_lane_provenance_matrix.json"]
        self.assertEqual(provenance["status"], "ok")
        self.assertEqual(
            provenance["final_status"],
            "CUSTOM_CODEX_DUAL_LANE_AGENT_WORKFLOW_PROVEN_WITH_LIMITS",
        )
        self.assertTrue(provenance["final_status_with_limits"])
        self.assertFalse(provenance["global_product_acceptance_claimed"])
        self.assertEqual(provenance["dangerous_transition_count"], 0)
        self.assertEqual(provenance["dangerous_transitions"], [])
        self.assertEqual(provenance["missing_claims"], [])
        self.assertEqual(provenance["duplicate_claim_ids"], [])
        self.assertFalse(provenance["historical_reference_only_rows_counted_as_live_runtime"])
        self.assertFalse(provenance["synthetic_storage_rows_counted_as_live_runtime"])
        self.assertFalse(provenance["mocked_runtime_rows_counted_as_capability_proof"])
        self.assertFalse(provenance["mocked_runtime_rows_counted_as_live_runtime"])
        self.assertFalse(provenance["imported_prior_rows_marked_current"])

        provenance_rows = {row["claim_id"]: row for row in provenance["rows"]}
        self.assertTrue(set(provenance["mandatory_claims"]).issubset(provenance_rows))
        self.assertEqual(len(provenance_rows), len(provenance["rows"]))
        self.assertEqual(
            provenance_rows["manual_provider_model_selection"]["proof_level"],
            "current_packet",
        )
        self.assertTrue(
            provenance_rows["manual_provider_model_selection"][
                "counted_in_bounded_final_flow"
            ]
        )
        self.assertFalse(
            provenance_rows["manual_provider_model_selection"][
                "counts_as_live_runtime_proof"
            ]
        )
        self.assertEqual(
            provenance_rows["dual_lane_runtime_dispatch"]["proof_level"],
            "current_mocked_runtime_packet",
        )
        self.assertTrue(
            provenance_rows["dual_lane_runtime_dispatch"][
                "counted_in_bounded_final_flow"
            ]
        )
        self.assertFalse(
            provenance_rows["dual_lane_runtime_dispatch"][
                "counts_as_live_runtime_proof"
            ]
        )
        self.assertFalse(
            provenance_rows["dual_lane_runtime_dispatch"][
                "counts_as_capability_proof"
            ]
        )
        self.assertEqual(
            provenance_rows["persistent_history_classification"]["proof_level"],
            "current_synthetic_storage_packet",
        )
        self.assertFalse(
            provenance_rows["persistent_history_classification"][
                "counted_in_bounded_final_flow"
            ]
        )
        self.assertFalse(
            provenance_rows["persistent_history_classification"][
                "counts_as_live_runtime_proof"
            ]
        )
        self.assertEqual(
            provenance_rows["role_slot_persistence_thread_history_boundary"]["proof_level"],
            "imported_prior_packet",
        )
        self.assertEqual(
            provenance_rows["role_slot_persistence_thread_history_boundary"]["freshness"],
            "imported_prior",
        )
        self.assertFalse(
            provenance_rows["role_slot_persistence_thread_history_boundary"][
                "counts_as_live_runtime_proof"
            ]
        )
        self.assertEqual(
            provenance_rows["generic_provider_auth_boundary"]["proof_level"],
            "imported_prior_packet",
        )
        self.assertEqual(
            provenance_rows["paid_api_policy_boundary"]["proof_level"],
            "imported_prior_packet",
        )
        self.assertFalse(
            provenance_rows["paid_api_policy_boundary"]["counts_as_live_runtime_proof"]
        )
        self.assertEqual(
            provenance_rows["historical_item_0_boundary"]["proof_level"],
            "historical_reference_only",
        )
        self.assertFalse(
            provenance_rows["historical_item_0_boundary"][
                "counted_in_bounded_final_flow"
            ]
        )
        self.assertFalse(
            provenance_rows["historical_item_0_boundary"][
                "counts_as_live_runtime_proof"
            ]
        )
        self.assertTrue(provenance_rows["final_status_boundary"]["with_limits"])
        self.assertFalse(
            any(row["counts_as_capability_proof"] for row in provenance["rows"])
        )

        audit = packets["independent_audit_packet.json"]
        self.assertEqual(audit["status"], "ok")
        finding_ids = {finding["id"] for finding in audit["findings"]}
        self.assertIn(
            "manual_dual_lane_selection_remains_server_issued_and_non_raw_authority",
            finding_ids,
        )
        self.assertIn(
            "same_session_dual_lane_runtime_proven_with_lane_specific_provenance",
            finding_ids,
        )
        self.assertIn(
            "persistent_history_remains_synthetic_storage_only_with_limits",
            finding_ids,
        )
        self.assertIn(
            "integrity_truth_remains_boundary_scoped_with_limits",
            finding_ids,
        )
        self.assertIn(
            "historical_item_0_remains_open_and_non_counted",
            finding_ids,
        )

    def test_probe_writes_required_packets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = subprocess.run(
                [
                    "python3",
                    str(TOOL),
                    "--repo-root",
                    str(ROOT),
                    "--evidence-dir",
                    temp_dir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            summary = json.loads(completed.stdout)
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["packet_count"], 11)

            acceptance = json.loads(
                (Path(temp_dir) / "final_dual_lane_acceptance_matrix.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                acceptance["final_status"],
                "CUSTOM_CODEX_DUAL_LANE_AGENT_WORKFLOW_PROVEN_WITH_LIMITS",
            )
            self.assertTrue(acceptance["historical_item_0_inventory_closed"])
            self.assertFalse(acceptance["historical_item_0_runtime_acceptance_closed"])
            self.assertFalse(acceptance["historical_item_0_final_acceptance_counted"])
            self.assertEqual(
                acceptance["historical_item_0_classification_reason"],
                "reconciliation_only_not_runtime_acceptance",
            )
            self.assertEqual(
                acceptance["provenance_matrix_packet"],
                "final_dual_lane_provenance_matrix.json",
            )
            provenance = json.loads(
                (Path(temp_dir) / "final_dual_lane_provenance_matrix.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(provenance["status"], "ok")
            self.assertEqual(provenance["dangerous_transition_count"], 0)
            self.assertTrue(provenance["final_status_with_limits"])
            self.assertFalse(provenance["global_product_acceptance_claimed"])


if __name__ == "__main__":
    unittest.main()
