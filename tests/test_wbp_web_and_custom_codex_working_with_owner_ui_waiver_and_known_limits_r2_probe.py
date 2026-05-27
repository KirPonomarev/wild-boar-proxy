# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.wbp_web_and_custom_codex_working_with_owner_ui_waiver_and_known_limits_r2_probe import (
    DEFAULT_SOURCE_FILES,
    FINAL_STATUS_BLOCKED,
    FINAL_STATUS_OK,
    SourcePacketError,
    build_closeout,
    build_packets,
    load_source_packets,
    overall_status,
)


class FinalAcceptanceSynthesisProbeTests(unittest.TestCase):
    def _init_repo(self, repo_root: Path) -> None:
        subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        (repo_root / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "fixture"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )

    def _source_paths(self, repo_root: Path) -> dict[str, str]:
        return {
            key: str((repo_root / relative_path).resolve())
            for key, relative_path in DEFAULT_SOURCE_FILES.items()
        }

    def _source_packets(self) -> dict[str, dict[str, object]]:
        return {
            "current_truth_owner_ui_waiver": {
                "status": "ok",
                "owner_waives_machine_ui": True,
                "manual_ui_confirmation_allowed": True,
                "manual_ui_confirmation_replaces_route_trace": False,
                "machine_ui_proof_claimed": False,
                "waiver_does_not_close": [
                    "route_trace_proof",
                    "network_egress_proof",
                    "model_availability_proof",
                    "machine_ui_input_field_proof",
                    "machine_observed_response_text_proof",
                ],
            },
            "pass1_acceptance_summary": {
                "acceptance_truth": "ok",
                "final_verdict": "WBP_WEB_CONTROL_SURFACE_ACTIONS_WIRED_AND_GUARDED",
            },
            "pass1_false_green_audit": {"status": "ok"},
            "pass2_provider_lane_selection": {
                "selected_provider_lane": {
                    "provider": "openrouter",
                    "route_id": "wbp-web-primary-openrouter",
                    "enabled": True,
                },
                "selection_policy": {"exactly_one_provider_admitted": True},
            },
            "pass2_route_validation": {
                "packet": {"status": "ok", "data": {"route_state": "model_visible"}}
            },
            "pass2_route_smoke_check": {
                "packet": {"status": "ok", "data": {"route_state": "verified"}}
            },
            "pass2_false_green_audit": {"status": "ok"},
            "pass3_availability_lattice": {
                "status": "ok",
                "all_listed_models_equally_usable": False,
                "current_live_proven_model_ids": [
                    "gpt-5.3-codex",
                    "gpt-5.4",
                    "gpt-5.4-mini",
                    "gpt-5.5",
                ],
                "historically_bounded_model_ids": ["wbp-web-primary-openrouter"],
                "listed_only_model_ids": ["codex-auto-review", "gpt-5.2", "gpt-image-2"],
            },
            "pass3_false_green_audit": {"status": "ok"},
            "pass4_launcher_contract": {
                "status": "ok",
                "final_status": "CUSTOM_CODEX_VIA_WBP_OWNER_ACCEPTED_WITH_LIMITS",
                "historical_contract_imported": True,
                "imported_truth_only": True,
                "profile_mode": "persistent_custom",
                "profile_storage_persistence_proven": False,
                "thread_history_preservation_proven": False,
            },
            "pass4_owner_acceptance": {
                "status": "ok",
                "owner_ui_waiver_closes_ux_only": True,
                "machine_ui_proof_claimed": False,
                "historical_owner_acceptance_imported": True,
            },
            "pass4_route_trace": {
                "status": "ok",
                "forwarded_to_wbp": True,
                "upstream_status": 200,
                "direct_egress_claimed": False,
            },
            "pass4_original_drift": {
                "status": "ok",
                "original_equivalence_claimed": False,
                "bounded_non_equivalence_explicit": True,
            },
            "pass4_false_green_audit": {"status": "ok"},
            "pass45_profile_identity": {
                "status": "ok",
                "contour_final_status": "WBP_CUSTOM_PROFILE_AND_KEYCHAIN_CLASSIFIED_WITH_LIMITS",
                "classification": "identity_path_only",
                "identity_path_only_proven": True,
                "storage_continuity_proven": False,
                "thread_history_storage_proven": False,
                "owner_visible_continuity_proven": False,
            },
            "pass45_keychain_behavior": {
                "status": "ok",
                "classification": "historical_prompt_observed_current_behavior_unknown_bounded",
                "current_keychain_behavior_unknown_bounded": True,
                "current_live_prompt_behavior_proven": False,
                "prompt_absence_claimed": False,
            },
            "pass45_false_green_audit": {"status": "ok"},
            "pass5_failure_semantics": {
                "status": "ok",
                "final_status": "CUSTOM_CODEX_DIRECT_NON_WBP_EGRESS_KNOWN_BLOCKER",
                "direct_non_wbp_model_egress_known_blocker": True,
                "direct_lane_fix_proven": False,
                "wbp_routed_truth_preserved": True,
                "global_egress_failure_claimed": False,
            },
            "pass5_false_green_audit": {"status": "ok"},
        }

    def test_build_packets_synthesizes_final_bounded_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass6"
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=self._source_packets(),
                source_paths=self._source_paths(repo_root),
            )
            status, verdict = overall_status(packets)
            closeout = build_closeout(repo_root, evidence_dir, packets)

        self.assertEqual(status, "ok")
        self.assertEqual(verdict, FINAL_STATUS_OK)
        self.assertEqual(
            packets["final_acceptance_summary_packet.json"]["final_status"],
            FINAL_STATUS_OK,
        )
        self.assertTrue(
            packets["provider_and_catalog_boundary_packet.json"]["one_provider_lane_only"]
        )
        self.assertTrue(
            packets["direct_egress_boundary_packet.json"][
                "direct_non_wbp_model_egress_known_blocker"
            ]
        )
        self.assertFalse(
            packets["final_limits_boundary_packet.json"]["all_models_equally_usable_claimed"]
        )
        self.assertIn(
            "final verdict: `WBP_WEB_AND_CUSTOM_CODEX_WORKING_WITH_OWNER_UI_WAIVER_AND_KNOWN_LIMITS`",
            closeout,
        )
        self.assertNotIn("pending during closeout authoring", closeout)
        self.assertIn("## Git", closeout)

    def test_accepts_legacy_pass2_false_green_packet_shape_when_it_stays_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass6"
            sources = copy.deepcopy(self._source_packets())
            sources["pass2_false_green_audit"] = {
                "claims": {
                    "credentials_present_counts_as_route_smoke_pass": False,
                    "route_visible_in_routes_list_counts_as_route_smoke_pass": False,
                    "routes_validate_model_visible_counts_as_route_smoke_pass": False,
                    "profile_packet_counts_as_route_smoke_pass": False,
                    "http_200_with_null_message_content_counts_as_route_smoke_pass": False,
                    "second_provider_admission_counts_as_success": False,
                    "single_selected_route_smoke_check_ok_counts_as_success": True,
                }
            }
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        status, verdict = overall_status(packets)
        self.assertEqual(status, "ok")
        self.assertEqual(verdict, FINAL_STATUS_OK)

    def test_blocks_when_direct_egress_boundary_is_collapsed_into_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass6"
            sources = copy.deepcopy(self._source_packets())
            sources["pass5_failure_semantics"]["direct_lane_fix_proven"] = True
            sources["pass5_failure_semantics"]["global_egress_failure_claimed"] = True
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        status, verdict = overall_status(packets)
        self.assertEqual(status, "blocked")
        self.assertEqual(verdict, FINAL_STATUS_BLOCKED)
        self.assertEqual(
            packets["direct_egress_boundary_packet.json"]["status"], "blocked"
        )
        self.assertEqual(packets["false_green_audit.json"]["status"], "blocked")

    def test_blocks_when_pass1_verdict_alias_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass6"
            sources = copy.deepcopy(self._source_packets())
            sources["pass1_acceptance_summary"]["final_verdict"] = "BOGUS_COMPLETE_ALIAS"
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        status, verdict = overall_status(packets)
        self.assertEqual(status, "blocked")
        self.assertEqual(verdict, FINAL_STATUS_BLOCKED)
        self.assertEqual(packets["pass_truth_matrix_packet.json"]["status"], "blocked")
        self.assertEqual(packets["final_acceptance_summary_packet.json"]["status"], "blocked")

    def test_blocks_when_pass4_route_trace_packet_is_not_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass6"
            sources = copy.deepcopy(self._source_packets())
            sources["pass4_route_trace"]["status"] = "blocked"
            sources["pass4_route_trace"]["upstream_status"] = 500
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        status, verdict = overall_status(packets)
        self.assertEqual(status, "blocked")
        self.assertEqual(verdict, FINAL_STATUS_BLOCKED)
        self.assertEqual(
            packets["direct_egress_boundary_packet.json"]["status"], "blocked"
        )
        self.assertEqual(packets["final_acceptance_summary_packet.json"]["status"], "blocked")

    def test_blocks_when_provider_or_catalog_overclaim_appears(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass6"
            sources = copy.deepcopy(self._source_packets())
            sources["pass2_provider_lane_selection"]["selection_policy"][
                "exactly_one_provider_admitted"
            ] = False
            sources["pass3_availability_lattice"]["all_listed_models_equally_usable"] = True
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        status, verdict = overall_status(packets)
        self.assertEqual(status, "blocked")
        self.assertEqual(verdict, FINAL_STATUS_BLOCKED)
        self.assertEqual(
            packets["provider_and_catalog_boundary_packet.json"]["status"], "blocked"
        )
        self.assertEqual(packets["false_green_audit.json"]["status"], "blocked")

    def test_blocks_when_owner_ui_waiver_is_treated_as_network_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass6"
            sources = copy.deepcopy(self._source_packets())
            sources["current_truth_owner_ui_waiver"]["manual_ui_confirmation_replaces_route_trace"] = True
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        status, verdict = overall_status(packets)
        self.assertEqual(status, "blocked")
        self.assertEqual(verdict, FINAL_STATUS_BLOCKED)
        self.assertEqual(
            packets["owner_ui_waiver_boundary_packet.json"]["status"], "blocked"
        )
        self.assertEqual(packets["false_green_audit.json"]["status"], "blocked")

    def test_blocks_when_owner_ui_waiver_list_drops_required_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass6"
            sources = copy.deepcopy(self._source_packets())
            sources["current_truth_owner_ui_waiver"]["waiver_does_not_close"] = [
                "route_trace_proof"
            ]
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        status, verdict = overall_status(packets)
        self.assertEqual(status, "blocked")
        self.assertEqual(verdict, FINAL_STATUS_BLOCKED)
        self.assertEqual(
            packets["owner_ui_waiver_boundary_packet.json"]["status"], "blocked"
        )

    def test_blocks_when_pass4_original_drift_regresses_to_equivalence_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass6"
            sources = copy.deepcopy(self._source_packets())
            sources["pass4_original_drift"]["original_equivalence_claimed"] = True
            sources["pass4_original_drift"]["bounded_non_equivalence_explicit"] = False
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        status, verdict = overall_status(packets)
        self.assertEqual(status, "blocked")
        self.assertEqual(verdict, FINAL_STATUS_BLOCKED)
        self.assertEqual(packets["pass_truth_matrix_packet.json"]["status"], "blocked")

    def test_blocks_when_upstream_false_green_audit_is_not_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass6"
            sources = copy.deepcopy(self._source_packets())
            sources["pass5_false_green_audit"]["status"] = "blocked"
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        status, verdict = overall_status(packets)
        self.assertEqual(status, "blocked")
        self.assertEqual(verdict, FINAL_STATUS_BLOCKED)
        self.assertEqual(packets["pass_truth_matrix_packet.json"]["status"], "blocked")
        self.assertEqual(packets["final_acceptance_summary_packet.json"]["status"], "blocked")

    def test_load_source_packets_blocks_missing_required_source_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            source_files = copy.deepcopy(DEFAULT_SOURCE_FILES)
            source_files["pass1_acceptance_summary"] = Path("audit_results/missing/pass1.json")
            with self.assertRaises(SourcePacketError):
                load_source_packets(repo_root, source_files=source_files)


if __name__ == "__main__":
    unittest.main()
