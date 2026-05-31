# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.custom_codex_via_wbp_owner_accepted_with_limits_r2_probe import (
    DEFAULT_SOURCE_FILES,
    FINAL_STATUS_BLOCKED,
    FINAL_STATUS_OK,
    build_closeout,
    build_packets,
    overall_status,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class CustomCodexViaWbpOwnerAcceptedWithLimitsR2ProbeTests(unittest.TestCase):
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
            "owner_summary": {
                "status": "ok",
                "final_status": "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABLE_WITH_OWNER_CONFIRMATION",
                "owner_confirmation_imported": True,
            },
            "owner_classification": {
                "status": "ok",
                "usability_classification": "usable",
                "machine_ui_proof_claimed": False,
                "general_day_to_day_usability_claimed": False,
            },
            "route_reference_truth": {
                "status": "ok",
                "route_reference_supports_interpretation_only": True,
                "route_reference_reopens_route_proof": False,
            },
            "owner_source_validation": {
                "status": "ok",
                "route_trace_confirmed_in_source": True,
            },
            "owner_action_boundary": {
                "status": "ok",
                "owner_typed_specified_prompt": True,
                "runtime_authority_edited": False,
                "provider_or_model_authority_edited": False,
                "hidden_cleanup_performed": False,
            },
            "owner_visible_interaction": {
                "status": "ok",
                "window_visibly_present": True,
                "prompt_entry_visibly_possible": True,
                "submit_action_visibly_possible": True,
                "response_visibly_appeared": True,
            },
            "owner_response_visibility": {
                "status": "ok",
                "owner_reported_agent_answered": True,
            },
            "owner_false_green": {"status": "ok"},
            "owner_independent_audit": {"status": "ok"},
            "owner_live_trace": {
                "status": "ok",
                "forwarded_to_wbp": True,
                "request_observed": True,
                "response_observed": True,
                "route_status": "confirmed",
                "trace_path": "/v1/responses",
                "upstream_status": 200,
            },
            "owner_live_summary": {"status": "ok"},
            "owner_live_matrix": {
                "status": "ok",
                "route_trace_confirmed": True,
            },
            "persistent_launcher_contract": {
                "status": "ok",
                "profile_mode": "persistent_custom",
                "selected_profile_id": "wbp-custom-main",
                "selected_profile_root": "/profiles/wbp-custom-main",
                "launcher_path": "/profiles/wbp-custom-main/codex-custom-launch.sh",
                "persistent_launcher_contract_recorded": True,
                "silent_fallback_to_ephemeral_allowed": False,
                "launcher_contract_counts_as_launch_execution": False,
            },
            "persistent_profile_identity": {
                "status": "ok",
                "persistent_profile_id": "wbp-custom-main",
                "persistent_profile_root": "/profiles/wbp-custom-main",
                "same_profile_id_as_expected": True,
                "same_profile_root_as_expected": True,
                "silent_profile_switching_detected": False,
            },
            "persistent_concurrent_policy": {
                "status": "ok",
                "policy": "single_writer_only",
                "launcher_enforces_policy": True,
                "same_profile_multi_writer_allowed": False,
                "state_consistency_risk_classified": True,
                "lock_path": "/profiles/wbp-custom-main/.wbp-profile.lock",
            },
            "persistent_cleanup_policy": {
                "status": "ok",
                "cleanup_attempted": False,
                "cleanup_executed": False,
                "cleanup_deletes_persistent_profile_by_default": False,
                "persistent_history_delete_allowed_by_default": False,
                "explicit_owner_delete_authorization_required": True,
                "ordinary_cleanup_must_preserve_history": True,
            },
            "persistent_original_non_dependency": {
                "status": "ok",
                "original_codex_profile_dependency": False,
                "original_codex_profile_mutated": False,
            },
            "persistent_readiness_summary": {
                "status": "ok",
                "command_executed": False,
                "persistent_profile_state_written": False,
                "keychain_behavior_classified": False,
                "thread_history_preservation_claimed": False,
                "profile_storage_persistence_claimed": False,
            },
            "original_summary": {
                "status": "ok",
                "final_status": "ORIGINAL_CODEX_VIA_WBP_PROVEN_REVERSIBLE",
                "source_live_pass_imported": True,
            },
            "original_classification": {
                "status": "ok",
                "reversibility_proven_on_declared_observed_surfaces_only": True,
                "general_original_works_claimed": False,
                "broad_original_filesystem_innocence_claimed": False,
                "final_e2e_claimed": False,
            },
            "original_false_green": {"status": "ok"},
            "original_independent_audit": {"status": "ok"},
        }

    def test_build_packets_emits_owner_acceptance_with_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "owner_acceptance"
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
        self.assertEqual(packets["custom_launcher_contract_packet.json"]["status"], "ok")
        self.assertEqual(packets["custom_profile_mode_packet.json"]["status"], "ok")
        self.assertEqual(packets["custom_route_trace_packet.json"]["status"], "ok")
        self.assertEqual(packets["original_codex_drift_packet.json"]["status"], "ok")
        self.assertEqual(packets["false_green_audit.json"]["status"], "ok")
        self.assertIn("imported packet truth", closeout)
        self.assertIn("final verdict: CUSTOM_CODEX_VIA_WBP_OWNER_ACCEPTED_WITH_LIMITS", closeout)
        self.assertIn("resume from here: CLOSED", closeout)

    def test_build_packets_blocks_persistence_or_original_equivalence_overclaims(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "owner_acceptance"
            sources = copy.deepcopy(self._source_packets())
            sources["persistent_readiness_summary"]["profile_storage_persistence_claimed"] = True
            sources["original_classification"]["general_original_works_claimed"] = True
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        status, verdict = overall_status(packets)
        audit = packets["false_green_audit.json"]

        self.assertEqual(status, "blocked")
        self.assertEqual(verdict, FINAL_STATUS_BLOCKED)
        self.assertEqual(packets["custom_profile_mode_packet.json"]["status"], "blocked")
        self.assertEqual(packets["original_codex_drift_packet.json"]["status"], "blocked")
        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "custom_profile_mode_packet.json.profile_storage_persistence_claimed",
            audit["findings"],
        )
        self.assertIn(
            "original_codex_drift_packet.json.general_original_works_claimed",
            audit["findings"],
        )

    def test_probe_reports_input_error_when_required_source_packet_missing(self) -> None:
        tool = (
            REPO_ROOT
            / "tools"
            / "custom_codex_via_wbp_owner_accepted_with_limits_r2_probe.py"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = (
                repo_root
                / "audit_results"
                / "custom_codex_via_wbp_owner_accepted_with_limits_r2_2026-05-27"
            )
            for key, packet in self._source_packets().items():
                if key == "owner_summary":
                    continue
                path = repo_root / DEFAULT_SOURCE_FILES[key]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(packet), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(repo_root),
                    "--evidence-dir",
                    str(evidence_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            error_packet = json.loads((evidence_dir / "false_green_audit.json").read_text())
            self.assertEqual(error_packet["status"], "blocked")
            self.assertEqual(error_packet["final_status"], FINAL_STATUS_BLOCKED)
            self.assertIn("required packet missing", error_packet["message"])


if __name__ == "__main__":
    unittest.main()
