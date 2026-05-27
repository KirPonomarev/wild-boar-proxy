# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class NativeCustomOwnerUxAcceptanceImportR1ProbeTests(unittest.TestCase):
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

    def _write_source_packets(self, source_dir: Path) -> None:
        source_dir.mkdir(parents=True)
        packets = {
            "owner_action_boundary_packet.json": {
                "status": "ok",
                "owner_typed_specified_prompt": True,
                "runtime_authority_edited": False,
                "provider_or_model_authority_edited": False,
                "hidden_cleanup_performed": False,
            },
            "owner_manual_ux_check_packet.json": {
                "status": "ok",
                "owner_saw_window": True,
                "owner_typed_prompt": True,
                "owner_saw_response": True,
                "ux_status": "confirmed",
            },
            "owner_visible_response_confirmation_packet.json": {
                "status": "ok",
                "owner_saw_response": True,
                "owner_reported_agent_answered": True,
                "owner_reported_config_model_route_untouched": True,
                "owner_reported_hidden_cleanup_not_performed": True,
            },
            "wbp_trace_observation_packet.json": {
                "status": "ok",
                "route_status": "confirmed",
                "forwarded_to_wbp": True,
                "upstream_status": 200,
                "raw_prompt_recorded": False,
                "auth_header_recorded": False,
                "raw_auth_recorded": False,
            },
            "native_route_trace_binding_packet.json": {
                "status": "ok",
                "route_trace_bound": True,
            },
            "two_lane_result_matrix.json": {
                "status": "ok",
                "final_status": "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABLE_WITH_OWNER_CONFIRMATION",
                "owner_ux_confirmed": True,
                "route_trace_confirmed": True,
            },
            "native_owner_ux_false_green_audit.json": {
                "status": "ok",
            },
            "independent_owner_ux_route_audit.json": {
                "status": "ok",
            },
            "owner_ux_route_summary_packet.json": {
                "status": "ok",
                "final_status": "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABLE_WITH_OWNER_CONFIRMATION",
            },
        }
        for name, packet in packets.items():
            (source_dir / name).write_text(json.dumps(packet), encoding="utf-8")

    def test_import_probe_emits_owner_confirmed_usability(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "native_custom_owner_ux_acceptance_import_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            source_dir = temp_repo / "audit_results" / "source_owner_ux"
            self._write_source_packets(source_dir)
            route_reference = temp_repo / "audit_results" / "route_reference_summary.json"
            route_reference.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "final_status": "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_OBSERVED",
                    }
                ),
                encoding="utf-8",
            )
            evidence_dir = temp_repo / "audit_results" / "owner_ux_import"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--source-evidence-dir",
                    str(source_dir),
                    "--route-reference-summary",
                    str(route_reference),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (evidence_dir / "native_owner_usability_summary_packet.json").read_text()
            )
            classification = json.loads(
                (
                    evidence_dir / "native_owner_usability_classification_packet.json"
                ).read_text()
            )
            route_reference_packet = json.loads(
                (evidence_dir / "route_reference_truth_packet.json").read_text()
            )
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(
                summary["final_status"],
                "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABLE_WITH_OWNER_CONFIRMATION",
            )
            self.assertTrue(summary["owner_confirmation_imported"])
            self.assertFalse(summary["current_owner_action_collected"])
            self.assertEqual(classification["usability_classification"], "usable")
            self.assertEqual(route_reference_packet["status"], "ok")

    def test_import_probe_blocks_when_source_summary_is_not_pass(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "native_custom_owner_ux_acceptance_import_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            source_dir = temp_repo / "audit_results" / "source_owner_ux"
            self._write_source_packets(source_dir)
            bad_summary = source_dir / "owner_ux_route_summary_packet.json"
            bad_summary.write_text(
                json.dumps(
                    {
                        "status": "blocked",
                        "final_status": "OWNER_UX_AND_ROUTE_BLOCKED",
                    }
                ),
                encoding="utf-8",
            )
            evidence_dir = temp_repo / "audit_results" / "owner_ux_import"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--source-evidence-dir",
                    str(source_dir),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            summary = json.loads(
                (evidence_dir / "native_owner_usability_summary_packet.json").read_text()
            )
            validation = json.loads(
                (
                    evidence_dir / "source_owner_ux_summary_validation_packet.json"
                ).read_text()
            )
            self.assertEqual(summary["status"], "blocked")
            self.assertEqual(
                summary["final_status"],
                "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABILITY_CLASSIFIED_WITH_LIMITS",
            )
            self.assertEqual(validation["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
