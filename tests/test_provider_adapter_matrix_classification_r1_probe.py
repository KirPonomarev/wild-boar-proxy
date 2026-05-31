# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ProviderAdapterMatrixClassificationR1ProbeTests(unittest.TestCase):
    def _init_repo(self, repo_root: Path, *, provider_families: list[str]) -> None:
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
        credentials_py = repo_root / "wild_boar_proxy" / "external_models" / "credentials.py"
        credentials_py.parent.mkdir(parents=True, exist_ok=True)
        entries = ",\n".join(
            f'    "{family}": object()' for family in provider_families
        )
        credentials_py.write_text(
            "_PROVIDER_SPECS = {\n" + entries + "\n}\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True)
        subprocess.run(["git", "add", "audit_results/.gitkeep"], cwd=repo_root, check=True)
        subprocess.run(["git", "add", "wild_boar_proxy/external_models/credentials.py"], cwd=repo_root, check=True)
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
            "auth_strategy": root / "audit_results" / "auth",
            "runtime_compat": root / "audit_results" / "runtime",
            "live_non_native": root / "audit_results" / "live",
            "model_availability": root / "audit_results" / "availability",
            "deepseek": root / "audit_results" / "deepseek",
            "openrouter": root / "audit_results" / "openrouter",
        }
        for path in dirs.values():
            path.mkdir(parents=True)

        auth_packets = {
            "provider_auth_source_inventory_packet.json": {
                "status": "ok",
                "all_auth_sources_classified": True,
            },
            "provider_auth_precedence_contract_packet.json": {
                "status": "ok",
                "selected_strategy": "auth.command",
                "silent_fallback_allowed": False,
            },
            "provider_auth_fallback_matrix_packet.json": {
                "status": "ok",
                "silent_fallback_detected": False,
            },
            "provider_auth_strategy_summary_packet.json": {
                "status": "ok",
                "selected_strategy": "auth.command",
            },
            "auth_strategy_false_green_audit.json": {"status": "ok"},
        }
        for name, packet in auth_packets.items():
            self._write_json(root, f"audit_results/auth/{name}", packet)

        runtime_packets = {
            "adapter_boundary_packet.json": {
                "status": "ok",
                "generic_runtime_harness_proves_provider_family_compatibility": False,
            },
            "responses_runtime_compatibility_matrix.json": {"status": "ok"},
            "responses_runtime_false_green_audit.json": {"status": "ok"},
        }
        for name, packet in runtime_packets.items():
            self._write_json(root, f"audit_results/runtime/{name}", packet)

        live_packets = {
            "responses_live_non_native_summary_packet.json": {
                "status": "ok",
                "provider_family_compatibility_proven": False,
            },
            "failure_taxonomy_packet.json": {
                "status": "ok",
                "failure_taxonomy_counts_as_provider_family_compatibility": False,
            },
            "failure_semantics_packet.json": {"status": "ok"},
            "responses_live_non_native_false_green_audit.json": {"status": "ok"},
        }
        for name, packet in live_packets.items():
            self._write_json(root, f"audit_results/live/{name}", packet)

        availability_packets = {
            "external_route_admission_packet.json": {
                "status": "ok",
                "provider_family_compatibility_claimed": False,
                "external_route_smoke_claims_provider_family_compatibility": False,
            },
            "route_family_classification_packet.json": {"status": "ok"},
            "model_availability_admission_packet.json": {"status": "ok"},
            "model_availability_false_green_audit.json": {"status": "ok"},
        }
        for name, packet in availability_packets.items():
            self._write_json(root, f"audit_results/availability/{name}", packet)

        deepseek_packets = {
            "proof.json": {
                "status": "ok",
                "route_truth": {
                    "provider": "deepseek",
                    "upstream_model": "deepseek-chat",
                },
                "credential_truth": {
                    "credential_present": True,
                },
                "direct_provider_probe": {
                    "status": "ok",
                    "http_status": 200,
                    "model": "deepseek-v4-flash",
                },
                "command_proof": {
                    "check_status": "ok",
                },
            },
            "independent_audit.json": {"status": "pass"},
            "redaction_audit.json": {"status": "pass"},
        }
        for name, packet in deepseek_packets.items():
            self._write_json(root, f"audit_results/deepseek/{name}", packet)

        openrouter_packets = {
            "credential_admission_proof.json": {
                "status": "error",
                "credential_result": {
                    "provider": "openrouter",
                    "credential_present": False,
                },
            },
            "provider_check_proof.json": {
                "status": "not_run",
                "provider": "openrouter",
            },
            "route_restore_proof.json": {
                "status": "not_attempted",
                "canonical_route_target": {
                    "provider": "openrouter",
                    "upstream_model": "deepseek/deepseek-chat",
                },
            },
            "independent_audit.json": {"status": "pass"},
            "redaction_audit.json": {"status": "pass"},
        }
        for name, packet in openrouter_packets.items():
            self._write_json(root, f"audit_results/openrouter/{name}", packet)

        return dirs

    def test_probe_classifies_multi_provider_matrix_with_limits(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "provider_adapter_matrix_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo, provider_families=["deepseek", "openrouter"])
            dirs = self._write_sources(temp_repo)
            evidence_dir = temp_repo / "audit_results" / "provider_adapter_matrix"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--auth-strategy-dir",
                    str(dirs["auth_strategy"]),
                    "--runtime-compat-dir",
                    str(dirs["runtime_compat"]),
                    "--live-non-native-dir",
                    str(dirs["live_non_native"]),
                    "--model-availability-dir",
                    str(dirs["model_availability"]),
                    "--deepseek-dir",
                    str(dirs["deepseek"]),
                    "--openrouter-dir",
                    str(dirs["openrouter"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (evidence_dir / "provider_adapter_summary_packet.json").read_text()
            )
            matrix = json.loads(
                (evidence_dir / "provider_adapter_family_matrix_packet.json").read_text()
            )
            scanner = json.loads(
                (evidence_dir / "scanner_agent_fact_report_packet.json").read_text()
            )
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(
                summary["final_status"],
                "WBP_PROVIDER_ADAPTER_MATRIX_CLASSIFIED_WITH_LIMITS",
            )
            rows = {row["provider_family"]: row for row in matrix["rows"]}
            self.assertEqual(rows["deepseek"]["matrix_proof_level"], "classified")
            self.assertEqual(rows["openrouter"]["matrix_proof_level"], "declared")
            self.assertFalse(matrix["provider_family_compatibility_proven"])
            self.assertEqual(scanner["facts"]["provider_count"], 2)

    def test_probe_blocks_when_only_one_provider_family_is_admitted(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "provider_adapter_matrix_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo, provider_families=["openrouter"])
            dirs = self._write_sources(temp_repo)
            evidence_dir = temp_repo / "audit_results" / "provider_adapter_matrix"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--auth-strategy-dir",
                    str(dirs["auth_strategy"]),
                    "--runtime-compat-dir",
                    str(dirs["runtime_compat"]),
                    "--live-non-native-dir",
                    str(dirs["live_non_native"]),
                    "--model-availability-dir",
                    str(dirs["model_availability"]),
                    "--deepseek-dir",
                    str(dirs["deepseek"]),
                    "--openrouter-dir",
                    str(dirs["openrouter"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            summary = json.loads(
                (evidence_dir / "provider_adapter_summary_packet.json").read_text()
            )
            scope = json.loads(
                (evidence_dir / "provider_adapter_scope_packet.json").read_text()
            )
            self.assertEqual(summary["status"], "blocked")
            self.assertFalse(scope["multi_provider_scope_admitted"])

    def test_probe_blocks_when_generic_runtime_is_overclaimed(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "provider_adapter_matrix_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo, provider_families=["deepseek", "openrouter"])
            dirs = self._write_sources(temp_repo)
            bad_packet = dirs["runtime_compat"] / "adapter_boundary_packet.json"
            bad_packet.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "generic_runtime_harness_proves_provider_family_compatibility": True,
                    }
                ),
                encoding="utf-8",
            )
            evidence_dir = temp_repo / "audit_results" / "provider_adapter_matrix"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--auth-strategy-dir",
                    str(dirs["auth_strategy"]),
                    "--runtime-compat-dir",
                    str(dirs["runtime_compat"]),
                    "--live-non-native-dir",
                    str(dirs["live_non_native"]),
                    "--model-availability-dir",
                    str(dirs["model_availability"]),
                    "--deepseek-dir",
                    str(dirs["deepseek"]),
                    "--openrouter-dir",
                    str(dirs["openrouter"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            summary = json.loads(
                (evidence_dir / "provider_adapter_summary_packet.json").read_text()
            )
            validation = json.loads(
                (evidence_dir / "source_provider_adapter_validation_packet.json").read_text()
            )
            self.assertEqual(summary["status"], "blocked")
            failed = {
                item["name"]
                for item in validation["checks"]
                if not item["passed"]
            }
            self.assertIn("runtime_generic_limits_ok", failed)


if __name__ == "__main__":
    unittest.main()
