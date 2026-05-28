# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy.external_models.credentials import provider_specs_inventory


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "generic_provider_auth_and_secret_admission_r1_probe.py"


class GenericProviderAuthAndSecretAdmissionR1ProbeTests(unittest.TestCase):
    def test_provider_specs_inventory_is_generic_schema_only(self) -> None:
        inventory = provider_specs_inventory()
        providers = {entry["provider"] for entry in inventory}

        self.assertTrue({"openrouter", "deepseek", "mistral", "gemini", "groq", "cerebras"} <= providers)
        self.assertTrue(all(entry["schema_admitted"] is True for entry in inventory))
        self.assertTrue(all(entry["classification_scope"] == "credential_admission_only" for entry in inventory))
        self.assertTrue(all(entry["provider_runtime_compatibility_claimed"] is False for entry in inventory))
        self.assertTrue(all(entry["model_runtime_compatibility_claimed"] is False for entry in inventory))
        self.assertTrue(all(entry["generic_route_transform_support_claimed"] is False for entry in inventory))
        self.assertTrue(all(entry["generic_response_compatibility_claimed"] is False for entry in inventory))

    def test_probe_writes_bounded_packets_and_keeps_seed_only_gap(self) -> None:
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

            inventory = json.loads(
                (evidence_dir / "generic_provider_auth_inventory_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(inventory["provider_runtime_compatibility_claimed_here"])
            self.assertFalse(inventory["model_runtime_compatibility_claimed_here"])
            self.assertIn("zai", inventory["seed_only_providers"])

            schema = json.loads(
                (evidence_dir / "provider_auth_schema_packet.json").read_text(encoding="utf-8")
            )
            self.assertEqual(schema["supported_sources"], ["owner-env"])
            self.assertFalse(schema["browser_secret_intake"])
            self.assertFalse(schema["generic_provider_support_claimed"])

            boundary = json.loads(
                (evidence_dir / "provider_auth_boundary_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(boundary["server_owned_secret_source_only"])
            self.assertFalse(boundary["browser_can_supply_provider_config"])

            non_claims = json.loads(
                (evidence_dir / "provider_auth_non_claims_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(non_claims["provider_auth_implies_route_runtime"])
            self.assertFalse(non_claims["provider_auth_implies_model_runtime"])

            gap_matrix = json.loads(
                (evidence_dir / "provider_auth_gap_matrix.json").read_text(encoding="utf-8")
            )
            gap_ids = {gap["id"] for gap in gap_matrix["gaps"]}
            self.assertIn("primary_route_heuristic_provider_coupling", gap_ids)
            self.assertIn("route_schema_accepts_broader_provider_space_than_validator_proves", gap_ids)

