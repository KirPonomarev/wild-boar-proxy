# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.custom_codex_agent_runtime_compatibility_r1_probe import (
    TARGET_STATUS,
    build_agent_capable_workflow_classification_packet,
    build_bundled_plugin_availability_packet,
    build_false_green_audit,
    build_original_profile_contamination_guard_packet,
    build_packets,
    build_profile_isolation_during_runtime_packet,
    build_runtime_cache_path_classification_packet,
    build_summary_packet,
    build_sync_gate_packet,
    run_text,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def write_plugin_surface(root: Path, vendor: str, plugin: str, version: str, skill: str) -> None:
    plugin_root = root / "plugins" / "cache" / vendor / plugin / version
    manifest = plugin_root / ".codex-plugin" / "plugin.json"
    skill_file = plugin_root / "skills" / skill / "SKILL.md"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "name": plugin,
                "version": version,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    skill_file.write_text(f"# {skill}\n", encoding="utf-8")


def write_profile_fixture(base_dir: Path, profile_id: str = "wbp-custom-main") -> Path:
    root = base_dir / profile_id
    write_plugin_surface(root, "openai-bundled", "browser", "1.0.0", "browser")
    write_plugin_surface(root, "openai-primary-runtime", "documents", "1.0.0", "documents")
    write_plugin_surface(root, "openai-primary-runtime", "spreadsheets", "1.0.0", "spreadsheets")
    write_plugin_surface(root, "openai-primary-runtime", "presentations", "1.0.0", "presentations")
    (root / "home" / ".cache" / "codex-runtimes").mkdir(parents=True, exist_ok=True)
    (root / ".tmp").mkdir(parents=True, exist_ok=True)
    return root


class CustomCodexAgentRuntimeCompatibilityR1Tests(unittest.TestCase):
    def test_bundled_plugin_availability_requires_all_surfaces_inside_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp) / "profiles"
            write_profile_fixture(base_dir)

            packet = build_bundled_plugin_availability_packet(
                profile_id="wbp-custom-main",
                base_dir=base_dir,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["all_required_surfaces_available"])
        self.assertTrue(packet["all_required_surfaces_inside_custom_profile"])
        self.assertFalse(packet["plugin_invocation_performed"])
        self.assertFalse(packet["all_plugins_claimed"])

    def test_bundled_plugin_availability_blocks_missing_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp) / "profiles"
            root = write_profile_fixture(base_dir)
            for path in (root / "plugins" / "cache" / "openai-primary-runtime" / "documents").rglob("*"):
                if path.is_file():
                    path.unlink()

            packet = build_bundled_plugin_availability_packet(
                profile_id="wbp-custom-main",
                base_dir=base_dir,
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["all_required_surfaces_available"])

    def test_agent_capable_workflow_can_be_unavailable_without_failing(self) -> None:
        packet = build_agent_capable_workflow_classification_packet(
            observed=False,
            source="not attempted in unit test",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["workflow_observed"])
        self.assertTrue(packet["unavailable_is_not_failure"])
        self.assertFalse(packet["performance_claimed"])

    def test_profile_isolation_blocks_plugin_surface_outside_profile(self) -> None:
        packet = build_profile_isolation_during_runtime_packet(
            profile_id="wbp-custom-main",
            base_dir=Path("/tmp/profiles"),
            plugin_availability_packet={
                "surfaces": [
                    {
                        "manifest_path_under_custom_profile": False,
                        "skill_path_under_custom_profile": True,
                    }
                ]
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["plugin_surfaces_outside_custom_profile"])

    def test_runtime_cache_paths_stay_inside_custom_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp) / "profiles"
            write_profile_fixture(base_dir)

            packet = build_runtime_cache_path_classification_packet(
                profile_id="wbp-custom-main",
                base_dir=base_dir,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(
            all(entry["under_custom_profile"] for entry in packet["cache_paths"].values())
        )
        self.assertFalse(packet["performance_claimed"])
        self.assertFalse(packet["cache_persistence_proven"])

    def test_original_profile_guard_records_metadata_only_without_hashes(self) -> None:
        packet = build_original_profile_contamination_guard_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["bounded_metadata_only"])
        self.assertFalse(packet["original_profile_content_recorded"])
        self.assertFalse(packet["original_profile_mutated"])
        for surface in packet["protected_surfaces"].values():
            self.assertFalse(surface["content_recorded"])
            self.assertNotIn("sha256", surface)

    def test_false_green_audit_blocks_performance_and_model_grid_overclaims(self) -> None:
        audit = build_false_green_audit(
            {
                "sync_gate_packet.json": {"status": "ok"},
                "agent_runtime_inventory_packet.json": {"status": "ok"},
                "bundled_plugin_availability_packet.json": {"status": "ok"},
                "agent_capable_workflow_classification_packet.json": {
                    "status": "ok",
                    "performance_claimed": True,
                },
                "profile_isolation_during_runtime_packet.json": {"status": "ok"},
                "runtime_cache_path_classification_packet.json": {
                    "status": "ok",
                    "model_grid_claimed": True,
                },
                "original_profile_contamination_guard_packet.json": {"status": "ok"},
                "agent_runtime_claim_limits_packet.json": {"status": "ok"},
            }
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "agent_capable_workflow_classification_packet.json.performance_claimed",
            audit["findings"],
        )
        self.assertIn(
            "runtime_cache_path_classification_packet.json.model_grid_claimed",
            audit["findings"],
        )

    def test_false_green_audit_blocks_failed_sync_gate(self) -> None:
        audit = build_false_green_audit(
            {
                "sync_gate_packet.json": {"status": "blocked"},
                "agent_runtime_inventory_packet.json": {"status": "ok"},
                "bundled_plugin_availability_packet.json": {"status": "ok"},
                "agent_capable_workflow_classification_packet.json": {"status": "ok"},
                "profile_isolation_during_runtime_packet.json": {"status": "ok"},
                "runtime_cache_path_classification_packet.json": {"status": "ok"},
                "original_profile_contamination_guard_packet.json": {"status": "ok"},
                "agent_runtime_claim_limits_packet.json": {"status": "ok"},
            }
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertIn("sync_gate_packet.json.status=blocked", audit["findings"])

    def test_build_packets_closes_classification_without_acceleration_claims(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            base_dir = Path(tmp) / "profiles"
            write_profile_fixture(base_dir)

            packets = build_packets(
                repo_root=REPO_ROOT,
                evidence_dir=Path(tmp) / "evidence",
                profile_id="wbp-custom-main",
                base_dir=base_dir,
                agent_workflow_observed=True,
                agent_workflow_source="unit-test-scanner",
                skip_git=True,
            )

        summary = packets["agent_runtime_compatibility_summary_packet.json"]
        independent = packets["independent_agent_runtime_audit.json"]

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertFalse(summary["performance_claimed"])
        self.assertFalse(summary["parity_claimed"])
        self.assertFalse(summary["model_grid_claimed"])
        self.assertTrue(
            packets["agent_capable_workflow_classification_packet.json"]["workflow_observed"]
        )
        self.assertEqual(independent["status"], "ok")

    def test_run_text_preserves_git_status_leading_spaces(self) -> None:
        output = run_text(REPO_ROOT, ["python3", "-c", "print(' M path')"])

        self.assertEqual(output, " M path")

    def test_sync_gate_declares_quarantine_policy(self) -> None:
        packet = build_sync_gate_packet(
            REPO_ROOT,
            REPO_ROOT / "audit_results" / "unit-test-evidence",
            skip_git=True,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["git_status_short"], [])
        self.assertEqual(packet["unexpected_dirty_entries"], [])
        self.assertFalse(packet["historical_dirty_quarantined"])
        self.assertTrue(packet["sync_gate_blocks_only_unquarantined_current_contour_dirty"])

    def test_summary_blocks_missing_required_packet(self) -> None:
        summary = build_summary_packet(
            {
                "sync_gate_packet.json": {"status": "ok"},
                "agent_runtime_inventory_packet.json": {"status": "ok"},
                "bundled_plugin_availability_packet.json": {"status": "ok"},
                "agent_capable_workflow_classification_packet.json": {"status": "ok"},
                "profile_isolation_during_runtime_packet.json": {"status": "ok"},
                "runtime_cache_path_classification_packet.json": {"status": "ok"},
                "original_profile_contamination_guard_packet.json": {"status": "ok"},
                "agent_runtime_claim_limits_packet.json": {"status": "ok"},
                "false_green_audit.json": {"status": "ok"},
            }
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("independent_agent_runtime_audit.json", summary["missing_required_packets"])

    def test_summary_blocks_required_packet_status(self) -> None:
        summary = build_summary_packet(
            {
                "sync_gate_packet.json": {"status": "blocked"},
                "agent_runtime_inventory_packet.json": {"status": "ok"},
                "bundled_plugin_availability_packet.json": {"status": "ok"},
                "agent_capable_workflow_classification_packet.json": {"status": "ok"},
                "profile_isolation_during_runtime_packet.json": {"status": "ok"},
                "runtime_cache_path_classification_packet.json": {"status": "ok"},
                "original_profile_contamination_guard_packet.json": {"status": "ok"},
                "agent_runtime_claim_limits_packet.json": {"status": "ok"},
                "false_green_audit.json": {"status": "ok"},
                "independent_agent_runtime_audit.json": {"status": "ok"},
            }
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("sync_gate_packet.json", summary["blocked_packets"])


if __name__ == "__main__":
    unittest.main()
