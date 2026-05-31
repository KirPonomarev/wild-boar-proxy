# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ProviderBenchmarkingAdmissionClassificationR1ProbeTests(unittest.TestCase):
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
        (repo_root / "wild_boar_proxy").mkdir(parents=True, exist_ok=True)
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

    def _write_sources(self, root: Path) -> tuple[dict[str, Path], Path]:
        dirs = {
            "provider_matrix": root / "audit_results" / "provider_matrix",
            "model_availability": root / "audit_results" / "model_availability",
        }
        for path in dirs.values():
            path.mkdir(parents=True)

        self._write_json(
            root,
            "audit_results/provider_matrix/provider_adapter_summary_packet.json",
            {
                "status": "ok",
                "final_status": "WBP_PROVIDER_ADAPTER_MATRIX_CLASSIFIED_WITH_LIMITS",
                "active_provider_family_count": 2,
                "provider_family_compatibility_proven": False,
                "family_wide_model_compatibility_proven": False,
            },
        )
        self._write_json(
            root,
            "audit_results/provider_matrix/provider_adapter_family_matrix_packet.json",
            {
                "status": "ok",
                "rows": [
                    {
                        "provider_family": "deepseek",
                        "adapter_present": True,
                        "auth_strategy_classified": True,
                        "generic_request_shape_classified": True,
                        "generic_response_shape_classified": True,
                        "generic_failure_semantics_classified": True,
                        "representative_model_scope_explicit": True,
                        "provider_specific_credential_present": True,
                        "provider_specific_route_observed": True,
                        "provider_specific_validate_passed": True,
                        "matrix_proof_level": "classified",
                        "family_wide_model_proof": False,
                        "provider_family_compatibility_proven": False,
                        "representative_models": ["deepseek-chat"],
                        "limits": ["REPRESENTATIVE_MODEL_ONLY"],
                    },
                    {
                        "provider_family": "openrouter",
                        "adapter_present": True,
                        "auth_strategy_classified": True,
                        "generic_request_shape_classified": True,
                        "generic_response_shape_classified": True,
                        "generic_failure_semantics_classified": True,
                        "representative_model_scope_explicit": True,
                        "provider_specific_credential_present": False,
                        "provider_specific_route_observed": True,
                        "provider_specific_provider_check_ran": False,
                        "matrix_proof_level": "declared",
                        "family_wide_model_proof": False,
                        "provider_family_compatibility_proven": False,
                        "representative_models": ["deepseek/deepseek-chat"],
                        "limits": ["OWNER_CREDENTIAL_MISSING"],
                    },
                ],
            },
        )
        self._write_json(
            root,
            "audit_results/provider_matrix/provider_adapter_false_green_audit.json",
            {"status": "ok"},
        )
        self._write_json(
            root,
            "audit_results/provider_matrix/scanner_agent_fact_report_packet.json",
            {"status": "ok"},
        )

        self._write_json(
            root,
            "audit_results/model_availability/model_availability_direct_only_summary_packet.json",
            {
                "status": "ok",
                "final_status": "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
                "proof_transport": "direct_wbp_http_non_stream",
                "codex_acceptance_proven": False,
            },
        )
        self._write_json(
            root,
            "audit_results/model_availability/model_availability_matrix.json",
            {
                "status": "ok",
                "direct_only_contour": True,
                "codex_acceptance_proven": False,
            },
        )
        self._write_json(
            root,
            "audit_results/model_availability/model_availability_false_green_audit.json",
            {"status": "ok"},
        )
        self._write_json(
            root,
            "audit_results/model_availability/independent_model_availability_audit.json",
            {"status": "ok"},
        )

        validate_file = root / "wild_boar_proxy" / "external_models" / "validate.py"
        validate_file.parent.mkdir(parents=True, exist_ok=True)
        validate_file.write_text(
            '''
def fake():
    result = {
        "latency_ms": response.latency_ms,
        "verification_scope": "route_provider_only",
        "available_models_count": model_count,
    }
''',
            encoding="utf-8",
        )
        return dirs, validate_file

    def test_probe_classifies_benchmarking_as_not_yet_admitted(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "provider_benchmarking_admission_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs, validate_file = self._write_sources(temp_repo)
            evidence_dir = temp_repo / "audit_results" / "benchmarking_admission"

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
                    "--model-availability-dir",
                    str(dirs["model_availability"]),
                    "--external-validate-file",
                    str(validate_file),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (evidence_dir / "provider_benchmark_admission_summary_packet.json").read_text()
            )
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(
                summary["final_status"], "WBP_PROVIDER_BENCHMARKING_NOT_YET_ADMITTED"
            )
            self.assertEqual(summary["comparable_row_count"], 1)

    def test_probe_can_classify_admitted_when_two_rows_meet_floor(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "provider_benchmarking_admission_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs, validate_file = self._write_sources(temp_repo)
            matrix_path = dirs["provider_matrix"] / "provider_adapter_family_matrix_packet.json"
            packet = json.loads(matrix_path.read_text())
            packet["rows"][1]["provider_specific_credential_present"] = True
            packet["rows"][1]["provider_specific_provider_check_ran"] = True
            matrix_path.write_text(json.dumps(packet), encoding="utf-8")
            evidence_dir = temp_repo / "audit_results" / "benchmarking_admission"

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
                    "--model-availability-dir",
                    str(dirs["model_availability"]),
                    "--external-validate-file",
                    str(validate_file),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (evidence_dir / "provider_benchmark_admission_summary_packet.json").read_text()
            )
            self.assertEqual(
                summary["final_status"], "WBP_PROVIDER_BENCHMARKING_ADMISSION_CLASSIFIED"
            )
            self.assertEqual(summary["comparable_row_count"], 2)

    def test_probe_blocks_when_provider_matrix_is_overclaimed(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "provider_benchmarking_admission_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs, validate_file = self._write_sources(temp_repo)
            bad = dirs["provider_matrix"] / "provider_adapter_summary_packet.json"
            packet = json.loads(bad.read_text())
            packet["provider_family_compatibility_proven"] = True
            bad.write_text(json.dumps(packet), encoding="utf-8")
            evidence_dir = temp_repo / "audit_results" / "benchmarking_admission"

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
                    "--model-availability-dir",
                    str(dirs["model_availability"]),
                    "--external-validate-file",
                    str(validate_file),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            validation = json.loads(
                (evidence_dir / "source_provider_benchmark_validation_packet.json").read_text()
            )
            failed = {item["name"] for item in validation["checks"] if not item["passed"]}
            self.assertIn("provider_matrix_reference_ok", failed)


if __name__ == "__main__":
    unittest.main()
