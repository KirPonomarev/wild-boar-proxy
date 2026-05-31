# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.role_slot_provider_model_identity_persistence_across_relaunch_r1_probe import (
    build_packets,
)


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "role_slot_provider_model_identity_persistence_across_relaunch_r1_probe.py"


class RoleSlotProviderModelIdentityPersistenceAcrossRelaunchR1ProbeTests(unittest.TestCase):
    def test_build_packets_proves_saved_identity_revalidate_runtime_and_no_hidden_fallback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            packets = build_packets(repo_root=ROOT, evidence_dir=evidence_dir)

        saved = packets["role_slot_saved_binding_packet.json"]
        self.assertEqual(saved["status"], "ok")
        self.assertTrue(saved["session_root_under_persistent_profile"])
        self.assertEqual(saved["saved_slot_binding_count"], 2)
        self.assertEqual(saved["saved_primary_slot_model_id"], "gpt-5.3-codex")
        self.assertEqual(saved["saved_coding_slot_model_id"], "wbp-web-primary-openrouter")
        self.assertTrue(saved["slot_catalog_revalidated_before_reload"])

        relaunch = packets["role_slot_relaunch_identity_packet.json"]
        self.assertEqual(relaunch["status"], "ok")
        self.assertTrue(relaunch["same_persistent_profile_identity"])
        self.assertTrue(relaunch["same_session_id_after_reload"])
        self.assertFalse(relaunch["slot_catalog_revalidated_after_reload"])

        persistence = packets["role_slot_provider_model_persistence_packet.json"]
        self.assertEqual(persistence["status"], "ok")
        self.assertTrue(persistence["slot_catalog_revalidated"])
        self.assertTrue(persistence["provider_model_identity_persistence_proven"])
        self.assertTrue(
            persistence["no_hidden_fallback_from_saved_slot_to_different_provider_model_proven"]
        )
        self.assertTrue(persistence["same_provider_account_selection_proven"])
        self.assertEqual(len(persistence["role_slot_rows"]), 2)

        runtime = packets["role_slot_post_relaunch_runtime_packet.json"]
        self.assertEqual(runtime["status"], "ok")
        self.assertTrue(runtime["primary_runtime_identity_proven"])
        self.assertTrue(runtime["coding_runtime_identity_proven"])
        self.assertEqual(runtime["primary_runtime_selected_model"], "gpt-5.3-codex")
        self.assertEqual(runtime["coding_runtime_selected_model"], "wbp-web-primary-openrouter")

        provenance = packets["role_slot_post_relaunch_provenance_packet.json"]
        self.assertEqual(provenance["status"], "ok")
        self.assertEqual(provenance["primary_selected_source_provenance"], "backend_proven")
        self.assertEqual(provenance["coding_selected_source_provenance"], "route_proven")
        self.assertFalse(provenance["provenance_ambiguous"])

        fallback = packets["role_slot_hidden_fallback_boundary_packet.json"]
        self.assertEqual(fallback["status"], "ok")
        self.assertFalse(fallback["primary_fallback_attempted"])
        self.assertFalse(fallback["coding_fallback_attempted"])
        self.assertFalse(fallback["silent_provider_model_remap_observed"])

        audit = packets["independent_audit_packet.json"]
        self.assertEqual(audit["status"], "ok")
        self.assertFalse(audit["provider_family_compatibility_claimed"])
        self.assertFalse(audit["concurrent_execution_claimed"])
        self.assertFalse(audit["thread_history_source_claimed"])

    def test_probe_writes_required_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--repo-root",
                    str(ROOT),
                    "--evidence-dir",
                    str(evidence_dir),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["packet_count"], 7)

            expected = {
                "role_slot_saved_binding_packet.json",
                "role_slot_relaunch_identity_packet.json",
                "role_slot_provider_model_persistence_packet.json",
                "role_slot_post_relaunch_runtime_packet.json",
                "role_slot_post_relaunch_provenance_packet.json",
                "role_slot_hidden_fallback_boundary_packet.json",
                "independent_audit_packet.json",
            }
            self.assertEqual(set(summary["written_packets"]), expected)
