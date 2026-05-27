# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class NativeFinalE2eClassificationR1ProbeTests(unittest.TestCase):
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
        (repo_root / "audit_results").mkdir()
        (repo_root / "audit_results" / ".gitkeep").write_text("", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True)
        subprocess.run(["git", "add", "audit_results/.gitkeep"], cwd=repo_root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "fixture"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )

    def _write_source_owner_ux(self, root: Path) -> Path:
        source_dir = root / "audit_results" / "source_owner_ux"
        source_dir.mkdir(parents=True)
        packets = {
            "owner_ux_route_summary_packet.json": {
                "status": "ok",
                "owner_ux_confirmed": True,
                "route_trace_confirmed": True,
            },
            "two_lane_result_matrix.json": {
                "status": "ok",
                "route_trace_bound": True,
                "ux_status": "confirmed",
            },
            "native_custom_launch_packet.json": {
                "status": "ok",
                "custom_process_observed": True,
                "launcher_pid": 123,
                "model": "gpt-5.4-mini",
                "downstream_wbp_endpoint": "http://127.0.0.1:8318/v1",
            },
            "live_trace_setup_packet.json": {
                "status": "ok",
                "native_app_launch_attempted": True,
                "model": "gpt-5.4-mini",
                "downstream_wbp_endpoint": "http://127.0.0.1:8318/v1",
            },
            "native_route_trace_binding_packet.json": {
                "status": "ok",
                "route_trace_bound": True,
                "trace_request_body_sha256": "req",
                "trace_response_body_sha256": "resp",
            },
            "wbp_trace_observation_packet.json": {
                "status": "ok",
                "route_status": "confirmed",
                "forwarded_to_wbp": True,
                "request_observed": True,
                "response_observed": True,
                "trace_path": "/v1/responses",
                "request_body_sha256": "req",
                "response_body_sha256": "resp",
            },
            "owner_action_boundary_packet.json": {
                "status": "ok",
                "owner_typed_specified_prompt": True,
                "runtime_authority_edited": False,
                "provider_or_model_authority_edited": False,
            },
            "owner_manual_ux_check_packet.json": {
                "status": "ok",
                "owner_typed_prompt": True,
                "owner_saw_window": True,
                "owner_saw_response": True,
            },
            "owner_visible_response_confirmation_packet.json": {
                "status": "ok",
                "owner_reported_agent_answered": True,
            },
            "cleanup_reversibility_packet.json": {
                "status": "ok",
                "custom_processes_gone": True,
            },
            "native_owner_ux_false_green_audit.json": {
                "status": "ok",
            },
            "independent_owner_ux_route_audit.json": {
                "status": "ok",
            },
        }
        for name, packet in packets.items():
            (source_dir / name).write_text(json.dumps(packet), encoding="utf-8")
        return source_dir

    def _write_references(self, root: Path) -> None:
        refs = {
            "audit_results/wbp_provider_auth_strategy_contract_r1_2026-05-27/provider_auth_strategy_packet.json": {
                "status": "ok",
                "target_status": "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
                "selected_strategy": "auth.command",
            },
            "audit_results/wbp_responses_live_compatibility_non_native_r1_2026-05-27/responses_live_non_native_summary_packet.json": {
                "status": "ok",
                "request_reaches_wbp": True,
                "route_selected": True,
                "upstream_accepts": True,
            },
            "audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27/model_availability_direct_only_summary_packet.json": {
                "status": "ok",
                "final_status": "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
                "direct_wbp_non_stream_passed_models": ["gpt-5.4-mini"],
            },
            "audit_results/wbp_native_custom_safety_refresh_pre_live_r1_2026-05-27/native_custom_safety_refresh_summary_packet.json": {
                "status": "ok",
                "final_status": "NATIVE_CUSTOM_SAFETY_REFRESH_CLASSIFIED",
            },
            "audit_results/wbp_native_custom_safety_refresh_pre_live_r1_2026-05-27/native_custom_safety_admission_packet.json": {
                "status": "ok",
                "admission_ready": True,
            },
            "audit_results/wbp_native_custom_owner_ux_acceptance_import_r1_2026-05-27/native_owner_usability_summary_packet.json": {
                "status": "ok",
                "final_status": "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABLE_WITH_OWNER_CONFIRMATION",
            },
            "audit_results/wbp_original_codex_via_wbp_reversibility_import_r1_2026-05-27/original_wbp_reversibility_summary_packet.json": {
                "status": "ok",
                "final_status": "ORIGINAL_CODEX_VIA_WBP_PROVEN_REVERSIBLE",
            },
            "audit_results/wbp_original_codex_via_wbp_reversibility_import_r1_2026-05-27/original_wbp_reversibility_classification_packet.json": {
                "status": "ok",
                "reversibility_proven_on_declared_observed_surfaces_only": True,
                "general_original_works_claimed": False,
            },
            "audit_results/wbp_detached_native_custom_egress_owner_execution_import_r4_2026-05-27/detached_native_custom_egress_import_summary_packet.json": {
                "status": "ok",
                "final_status": "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_OBSERVED",
            },
            "audit_results/wbp_detached_native_custom_egress_owner_execution_import_r4_2026-05-27/network_claim_classification_packet.json": {
                "status": "ok",
                "network_claim_classified": True,
                "final_e2e_claimed": False,
                "direct_non_wbp_model_egress_observed": True,
            },
        }
        for rel, packet in refs.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(packet), encoding="utf-8")

    def test_probe_emits_final_e2e_pass_when_binding_is_complete(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "native_final_e2e_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            source_dir = self._write_source_owner_ux(temp_repo)
            self._write_references(temp_repo)
            evidence_dir = temp_repo / "audit_results" / "final_e2e"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--source-owner-ux-dir",
                    str(source_dir),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((evidence_dir / "final_e2e_summary_packet.json").read_text())
            binding = json.loads(
                (evidence_dir / "final_e2e_cross_contour_binding_packet.json").read_text()
            )
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["final_status"], "WBP_NATIVE_CODEX_APP_LAUNCH_COMPLETE")
            self.assertTrue(binding["bridge_satisfied_by_imported_source_event"])

    def test_probe_classifies_with_limits_when_route_binding_is_missing(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "native_final_e2e_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            source_dir = self._write_source_owner_ux(temp_repo)
            self._write_references(temp_repo)
            bad_route = source_dir / "native_route_trace_binding_packet.json"
            bad_route.write_text(
                json.dumps(
                    {
                        "status": "blocked",
                        "route_trace_bound": False,
                        "trace_request_body_sha256": "req",
                        "trace_response_body_sha256": "resp",
                    }
                ),
                encoding="utf-8",
            )
            evidence_dir = temp_repo / "audit_results" / "final_e2e"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--source-owner-ux-dir",
                    str(source_dir),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            summary = json.loads((evidence_dir / "final_e2e_summary_packet.json").read_text())
            binding = json.loads(
                (evidence_dir / "final_e2e_cross_contour_binding_packet.json").read_text()
            )
            self.assertEqual(summary["status"], "blocked")
            self.assertEqual(
                summary["final_status"],
                "WBP_NATIVE_CODEX_APP_LAUNCH_CLASSIFIED_WITH_LIMITS",
            )
            self.assertFalse(binding["bridge_satisfied_by_imported_source_event"])


if __name__ == "__main__":
    unittest.main()
