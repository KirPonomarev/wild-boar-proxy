# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class KeychainPromptBehaviorImportR1ProbeTests(unittest.TestCase):
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
            "readiness": root / "audit_results" / "readiness",
            "observed_prompt": root / "audit_results" / "observed",
            "repaired_lane": root / "audit_results" / "repaired",
            "auth_strategy": root / "audit_results" / "auth",
            "custom_safety": root / "audit_results" / "safety",
        }
        for path in dirs.values():
            path.mkdir(parents=True)

        readiness_packets = {
            "declared_write_surfaces_packet.json": {
                "status": "ok",
            },
            "keychain_prompt_readiness_summary_packet.json": {
                "status": "ok",
                "final_status": "CODEX_CUSTOM_KEYCHAIN_PROMPT_BEHAVIOR_READINESS_R1_CLASSIFIED",
            },
            "keychain_observation_readiness_packet.json": {
                "status": "ok",
                "machine_prompt_observed": False,
            },
            "keychain_allowed_owner_action_boundary_packet.json": {
                "status": "ok",
                "allowed_future_owner_actions": ["Cancel", "Allow", "Ignore", "Not Observed"],
                "owner_cancel_counted_as_machine_proof": False,
                "owner_allow_counted_as_auth_success": False,
            },
            "keychain_prompt_surface_inventory_packet.json": {"status": "ok"},
            "keychain_prompt_non_substitution_packet.json": {"status": "ok"},
            "auth_strategy_prompt_interaction_readiness_packet.json": {"status": "ok"},
            "auth_strategy_reference_digest_packet.json": {"status": "ok"},
            "keychain_no_hidden_mutation_packet.json": {
                "status": "ok",
                "keychain_mutation_performed": False,
                "keychain_reset_performed": False,
                "keychain_default_changed": False,
                "original_codex_keychain_mutated": False,
            },
            "original_codex_auth_keychain_non_dependency_packet.json": {"status": "ok"},
            "system_prompt_suppression_prohibition_packet.json": {
                "status": "ok",
                "suppression_attempted": False,
                "hidden_runtime_mutation_allowed": False,
            },
            "prompt_minimization_not_suppression_packet.json": {
                "status": "ok",
                "hidden_suppression_performed": False,
            },
            "future_live_owner_stop_gate_packet.json": {
                "status": "ok",
            },
            "future_live_keychain_observation_contract_packet.json": {
                "status": "ok",
            },
            "keychain_prompt_false_green_audit.json": {"status": "ok"},
            "independent_keychain_prompt_readiness_audit.json": {"status": "ok"},
        }
        for name, packet in readiness_packets.items():
            self._write_json(root, f"audit_results/readiness/{name}", packet)

        observed_packets = {
            "keychain_prompt_observation_packet.json": {
                "status": "blocked",
                "keychain_reset_prompt_observed": True,
            },
            "keychain_prompt_refined_observation_packet.json": {
                "status": "blocked",
                "strong_keychain_prompt_observed": True,
                "destructive_dialog_interacted_with": False,
                "after": {
                    "security_windows": {"stdout": "SecurityAgent:Связка ключей не найдена"}
                },
            },
            "final_safety_repair_summary.json": {
                "status": "blocked",
                "machine_error_code": "CUSTOM_PROTECTED_SURFACE_OR_KEYCHAIN_SAFETY_NOT_PROVEN",
            },
            "custom_profile_isolation_repair_packet.json": {
                "status": "blocked",
                "keychain_reset_prompt_observed": True,
            },
            "independent_profile_safety_audit.json": {"status": "blocked"},
        }
        for name, packet in observed_packets.items():
            self._write_json(root, f"audit_results/observed/{name}", packet)

        repaired_packets = {
            "keychain_risk_localization_packet.json": {
                "repeated_machine_visible_keychain_prompt_observed": False,
            },
            "custom_isolation_repair_packet.json": {
                "status": "ok",
                "route_or_prompt_claimed": False,
                "real_home_wrapper_launch_forbidden": True,
                "process_observed": True,
                "window_observed": False,
            },
            "independent_repair_audit.json": {"status": "ok"},
        }
        for name, packet in repaired_packets.items():
            self._write_json(root, f"audit_results/repaired/{name}", packet)

        auth_packets = {
            "provider_auth_strategy_summary_packet.json": {
                "status": "ok",
                "selected_strategy": "auth.command",
                "bounded_bearer_selected": False,
                "file_auth_selected": False,
                "silent_fallback_detected": False,
            },
            "auth_strategy_false_green_audit.json": {"status": "ok"},
        }
        for name, packet in auth_packets.items():
            self._write_json(root, f"audit_results/auth/{name}", packet)

        safety_packets = {
            "native_custom_auth_boundary_refresh_packet.json": {
                "status": "ok",
                "selected_strategy": "auth.command",
                "auth_boundary_dependency_check_only": True,
            },
            "native_custom_safety_false_green_audit.json": {"status": "ok"},
            "independent_native_custom_safety_audit.json": {"status": "ok"},
        }
        for name, packet in safety_packets.items():
            self._write_json(root, f"audit_results/safety/{name}", packet)
        return dirs

    def test_probe_classifies_with_limits_from_historical_chain(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "keychain_prompt_behavior_import_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            evidence_dir = temp_repo / "audit_results" / "keychain_behavior_import"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--readiness-dir",
                    str(dirs["readiness"]),
                    "--observed-prompt-dir",
                    str(dirs["observed_prompt"]),
                    "--repaired-lane-dir",
                    str(dirs["repaired_lane"]),
                    "--auth-strategy-dir",
                    str(dirs["auth_strategy"]),
                    "--custom-safety-dir",
                    str(dirs["custom_safety"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((evidence_dir / "keychain_prompt_summary_packet.json").read_text())
            classification = json.loads(
                (evidence_dir / "keychain_prompt_behavior_classification_packet.json").read_text()
            )
            scanner = json.loads(
                (evidence_dir / "scanner_agent_fact_report_packet.json").read_text()
            )
            independent = json.loads(
                (evidence_dir / "independent_keychain_prompt_behavior_audit.json").read_text()
            )
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(
                summary["final_status"],
                "CODEX_CUSTOM_KEYCHAIN_PROMPT_BEHAVIOR_CLASSIFIED_WITH_LIMITS",
            )
            self.assertTrue(classification["historical_pre_repair_prompt_observed"])
            self.assertFalse(classification["current_live_prompt_behavior_proven"])
            self.assertEqual(scanner["status"], "ok")
            self.assertTrue(scanner["facts"]["historical_pre_repair_prompt_observed"])
            self.assertEqual(
                scanner["facts"]["prompt_class"],
                "keychain_security_agent_prompt_historically_observed",
            )
            self.assertTrue(scanner["facts"]["auth_strategy_reference_only"])
            self.assertEqual(independent["status"], "ok")
            self.assertTrue(independent["historical_prompt_chain_imported"])
            self.assertFalse(independent["current_live_prompt_observation_collected"])

    def test_probe_blocks_when_auth_strategy_reference_is_wrong(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "keychain_prompt_behavior_import_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            bad_auth = dirs["auth_strategy"] / "provider_auth_strategy_summary_packet.json"
            bad_auth.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "selected_strategy": "bounded_bearer",
                        "bounded_bearer_selected": True,
                        "file_auth_selected": False,
                        "silent_fallback_detected": False,
                    }
                ),
                encoding="utf-8",
            )
            evidence_dir = temp_repo / "audit_results" / "keychain_behavior_import"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--readiness-dir",
                    str(dirs["readiness"]),
                    "--observed-prompt-dir",
                    str(dirs["observed_prompt"]),
                    "--repaired-lane-dir",
                    str(dirs["repaired_lane"]),
                    "--auth-strategy-dir",
                    str(dirs["auth_strategy"]),
                    "--custom-safety-dir",
                    str(dirs["custom_safety"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            summary = json.loads((evidence_dir / "keychain_prompt_summary_packet.json").read_text())
            self.assertEqual(summary["status"], "blocked")

    def test_probe_blocks_when_hidden_suppression_is_claimed(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "keychain_prompt_behavior_import_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            bad_suppression = dirs["readiness"] / "prompt_minimization_not_suppression_packet.json"
            bad_suppression.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "hidden_suppression_performed": True,
                    }
                ),
                encoding="utf-8",
            )
            evidence_dir = temp_repo / "audit_results" / "keychain_behavior_import"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--readiness-dir",
                    str(dirs["readiness"]),
                    "--observed-prompt-dir",
                    str(dirs["observed_prompt"]),
                    "--repaired-lane-dir",
                    str(dirs["repaired_lane"]),
                    "--auth-strategy-dir",
                    str(dirs["auth_strategy"]),
                    "--custom-safety-dir",
                    str(dirs["custom_safety"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            false_green = json.loads(
                (evidence_dir / "keychain_prompt_false_green_audit.json").read_text()
            )
            verification = json.loads(
                (evidence_dir / "verification_results_packet.json").read_text()
            )
            independent = json.loads(
                (evidence_dir / "independent_keychain_prompt_behavior_audit.json").read_text()
            )
            self.assertEqual(false_green["status"], "blocked")
            self.assertEqual(verification["status"], "blocked")
            self.assertEqual(independent["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
