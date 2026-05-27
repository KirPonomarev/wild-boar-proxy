# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class OptionalAnnexAdmissionStopClassificationR1ProbeTests(unittest.TestCase):
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

    def _write_json(self, root: Path, rel: str, packet: dict) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(packet), encoding="utf-8")

    def _write_sources(self, root: Path) -> dict[str, Path]:
        dirs = {
            "provider_matrix": root / "audit_results" / "provider_matrix",
            "remote_gate": root / "audit_results" / "remote_gate",
            "app_server_bridge": root / "audit_results" / "app_server_bridge",
            "provider_benchmark": root / "audit_results" / "provider_benchmark",
            "design_gate": root / "audit_results" / "design_gate",
            "design_gate_proof": root / "audit_results" / "design_gate_proof",
        }
        for path in dirs.values():
            path.mkdir(parents=True)

        self._write_json(
            root,
            "audit_results/provider_matrix/provider_adapter_summary_packet.json",
            {
                "status": "ok",
                "final_status": "WBP_PROVIDER_ADAPTER_MATRIX_CLASSIFIED_WITH_LIMITS",
            },
        )
        self._write_json(
            root,
            "audit_results/remote_gate/remote_control_readiness_summary_packet.json",
            {
                "status": "ok",
                "final_status": "WBP_REMOTE_CONTROL_READINESS_GATE_CLASSIFIED_WITH_LIMITS",
            },
        )
        self._write_json(
            root,
            "audit_results/app_server_bridge/app_server_bridge_summary_packet.json",
            {
                "status": "ok",
                "final_status": "WBP_APP_SERVER_BRIDGE_RESEARCH_CLASSIFIED_WITH_LIMITS",
            },
        )
        self._write_json(
            root,
            "audit_results/provider_benchmark/provider_benchmark_admission_summary_packet.json",
            {
                "status": "ok",
                "final_status": "WBP_PROVIDER_BENCHMARKING_NOT_YET_ADMITTED",
                "with_limits_reasons": ["ONLY_ONE_ROW_MEETS_COMPATIBILITY_FLOOR"],
            },
        )
        self._write_json(
            root,
            "audit_results/design_gate/decision_packet.json",
            {
                "design_gate_admitted": True,
                "design_gate_token": "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY",
            },
        )
        self._write_json(
            root,
            "audit_results/design_gate_proof/design_gate_proof.json",
            {
                "current_branch_gate_status": "evidenced",
                "repo_owned_gate_drift_found": False,
            },
        )
        self._write_json(
            root,
            "audit_results/stage20_c6_verification_packet.json",
            {
                "final_verdict": "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY",
            },
        )
        dirs["stage20_verify"] = root / "audit_results" / "stage20_c6_verification_packet.json"
        return dirs

    def test_probe_classifies_queue_still_has_admitted_work_when_design_gate_is_evidenced(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "optional_annex_admission_stop_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            evidence_dir = temp_repo / "audit_results" / "admission_stop"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--provider-matrix-dir",
                    str(dirs["provider_matrix"]),
                    "--remote-gate-dir",
                    str(dirs["remote_gate"]),
                    "--app-server-bridge-dir",
                    str(dirs["app_server_bridge"]),
                    "--provider-benchmark-dir",
                    str(dirs["provider_benchmark"]),
                    "--design-gate-dir",
                    str(dirs["design_gate"]),
                    "--design-gate-proof-dir",
                    str(dirs["design_gate_proof"]),
                    "--stage20-verify-packet",
                    str(dirs["stage20_verify"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((evidence_dir / "optional_annex_stop_summary_packet.json").read_text())
            self.assertEqual(
                summary["final_status"], "WBP_OPTIONAL_ANNEX_QUEUE_STILL_HAS_ADMITTED_WORK"
            )
            self.assertEqual(summary["currently_admitted_annexes"], ["role_profile_ui_polish"])

    def test_probe_classifies_no_further_named_contour_when_design_gate_not_evidenced(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "optional_annex_admission_stop_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            gate_path = dirs["design_gate"] / "decision_packet.json"
            packet = json.loads(gate_path.read_text())
            packet["design_gate_admitted"] = False
            gate_path.write_text(json.dumps(packet), encoding="utf-8")
            proof_path = dirs["design_gate_proof"] / "design_gate_proof.json"
            proof = json.loads(proof_path.read_text())
            proof["current_branch_gate_status"] = "not_evidenced"
            proof_path.write_text(json.dumps(proof), encoding="utf-8")
            evidence_dir = temp_repo / "audit_results" / "admission_stop"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--provider-matrix-dir",
                    str(dirs["provider_matrix"]),
                    "--remote-gate-dir",
                    str(dirs["remote_gate"]),
                    "--app-server-bridge-dir",
                    str(dirs["app_server_bridge"]),
                    "--provider-benchmark-dir",
                    str(dirs["provider_benchmark"]),
                    "--design-gate-dir",
                    str(dirs["design_gate"]),
                    "--design-gate-proof-dir",
                    str(dirs["design_gate_proof"]),
                    "--stage20-verify-packet",
                    str(dirs["stage20_verify"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            validation = json.loads(
                (evidence_dir / "optional_annex_source_validation_packet.json").read_text()
            )
            failed = {item["name"] for item in validation["checks"] if not item["passed"]}
            self.assertIn("design_gate_reference_ok", failed)

    def test_probe_blocks_if_benchmark_status_is_not_not_yet_admitted(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "optional_annex_admission_stop_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            benchmark_path = dirs["provider_benchmark"] / "provider_benchmark_admission_summary_packet.json"
            packet = json.loads(benchmark_path.read_text())
            packet["final_status"] = "WBP_PROVIDER_BENCHMARKING_ADMISSION_CLASSIFIED"
            benchmark_path.write_text(json.dumps(packet), encoding="utf-8")
            evidence_dir = temp_repo / "audit_results" / "admission_stop"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--provider-matrix-dir",
                    str(dirs["provider_matrix"]),
                    "--remote-gate-dir",
                    str(dirs["remote_gate"]),
                    "--app-server-bridge-dir",
                    str(dirs["app_server_bridge"]),
                    "--provider-benchmark-dir",
                    str(dirs["provider_benchmark"]),
                    "--design-gate-dir",
                    str(dirs["design_gate"]),
                    "--design-gate-proof-dir",
                    str(dirs["design_gate_proof"]),
                    "--stage20-verify-packet",
                    str(dirs["stage20_verify"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            validation = json.loads(
                (evidence_dir / "optional_annex_source_validation_packet.json").read_text()
            )
            failed = {item["name"] for item in validation["checks"] if not item["passed"]}
            self.assertIn("benchmark_admission_reference_ok", failed)


if __name__ == "__main__":
    unittest.main()
