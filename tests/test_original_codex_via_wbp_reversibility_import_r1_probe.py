# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class OriginalCodexViaWbpReversibilityImportR1ProbeTests(unittest.TestCase):
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
            "declared_write_surfaces_packet.json": {
                "status": "ok",
                "declared_write_surfaces": [
                    "fresh evidence directory only",
                    "/Users/kirillponomarev/.codex/config.toml",
                ],
                "owner_authorization_required": True,
                "owner_authorization_status": "ok",
                "original_codex_profile_write_allowed": True,
            },
            "original_profile_before_packet.json": {
                "status": "ok",
                "config_before_hash_or_absent_state_recorded": True,
                "native_original_launch_attempted": False,
                "original_profile_write_performed": False,
                "config_toml": {
                    "path": "/Users/kirillponomarev/.codex/config.toml",
                    "hash_recorded": True,
                    "sha256": "before",
                },
                "auth_json_hash_recorded": True,
                "current_auth_json_execution_dependency": False,
            },
            "rollback_point_packet.json": {
                "status": "ok",
                "rollback_point_created": True,
                "rollback_point_verified": True,
            },
            "temporary_route_apply_execution_packet.json": {
                "status": "ok",
                "apply_attempted": True,
                "apply_succeeded": True,
                "original_profile_write_performed": True,
                "exact_target_path": "/Users/kirillponomarev/.codex/config.toml",
                "written_surfaces": ["/Users/kirillponomarev/.codex/config.toml"],
            },
            "original_auth_boundary_packet.json": {
                "status": "ok",
            },
            "native_original_launch_execution_packet.json": {
                "status": "ok",
                "launch_attempted": True,
            },
            "wbp_trace_observation_packet.json": {
                "status": "ok",
                "route_status": "confirmed",
                "forwarded_to_wbp": True,
                "request_observed": True,
                "response_observed": True,
                "upstream_status_ok": True,
                "upstream_status": 200,
            },
            "restore_verification_packet.json": {
                "status": "ok",
                "rollback_execution_attempted": True,
                "restore_verified": True,
                "restore_matches_before": True,
                "before_state": {"sha256": "before"},
                "after_state": {"sha256": "before"},
            },
            "original_via_wbp_false_green_audit.json": {
                "status": "ok",
            },
            "independent_original_via_wbp_audit.json": {
                "status": "ok",
            },
            "original_via_wbp_summary_packet.json": {
                "status": "ok",
                "final_status": "ORIGINAL_CODEX_VIA_WBP_TEMP_ROUTE_AND_RESTORE_PROVEN_WITH_LIMITS",
                "original_route_proven": True,
                "rollback_executed": True,
                "restore_verified": True,
            },
        }
        for name, packet in packets.items():
            (source_dir / name).write_text(json.dumps(packet), encoding="utf-8")

    def test_import_probe_emits_reversible_original_classification(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "original_codex_via_wbp_reversibility_import_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            source_dir = temp_repo / "audit_results" / "source_original_reversibility"
            self._write_source_packets(source_dir)
            evidence_dir = temp_repo / "audit_results" / "original_reversibility_import"

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

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (evidence_dir / "original_wbp_reversibility_summary_packet.json").read_text()
            )
            classification = json.loads(
                (
                    evidence_dir / "original_wbp_reversibility_classification_packet.json"
                ).read_text()
            )
            route_reference = json.loads(
                (
                    evidence_dir / "original_wbp_route_observation_reference_packet.json"
                ).read_text()
            )
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(
                summary["final_status"],
                "ORIGINAL_CODEX_VIA_WBP_PROVEN_REVERSIBLE",
            )
            self.assertTrue(
                summary["reversibility_proven_on_declared_observed_surfaces_only"]
            )
            self.assertTrue(classification["source_live_pass_imported"])
            self.assertEqual(route_reference["status"], "ok")

    def test_import_probe_blocks_when_restore_is_not_verified(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "original_codex_via_wbp_reversibility_import_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            source_dir = temp_repo / "audit_results" / "source_original_reversibility"
            self._write_source_packets(source_dir)
            restore = source_dir / "restore_verification_packet.json"
            restore.write_text(
                json.dumps(
                    {
                        "status": "blocked",
                        "rollback_execution_attempted": True,
                        "restore_verified": False,
                        "restore_matches_before": False,
                        "before_state": {"sha256": "before"},
                        "after_state": {"sha256": "after"},
                    }
                ),
                encoding="utf-8",
            )
            evidence_dir = temp_repo / "audit_results" / "original_reversibility_import"

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
                (evidence_dir / "original_wbp_reversibility_summary_packet.json").read_text()
            )
            classification = json.loads(
                (
                    evidence_dir / "original_wbp_reversibility_classification_packet.json"
                ).read_text()
            )
            self.assertEqual(summary["status"], "blocked")
            self.assertEqual(
                summary["final_status"],
                "ORIGINAL_CODEX_VIA_WBP_REVERSIBILITY_CLASSIFIED_WITH_LIMITS",
            )
            self.assertFalse(
                classification["reversibility_proven_on_declared_observed_surfaces_only"]
            )


if __name__ == "__main__":
    unittest.main()
