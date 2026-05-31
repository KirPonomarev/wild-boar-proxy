# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy.codex_model_registry import (
    build_generic_model_registry_packet,
    build_generic_provider_registry_packet,
)


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "generic_provider_and_model_registry_r1_probe.py"


def operator_status() -> dict[str, object]:
    return {
        "status": {
            "status": "ok",
            "machine_error_code": "OK",
            "configured_model": "gpt-5.3-codex",
        },
        "claim_gate": {"status": "passed"},
        "models": {
            "ok": True,
            "model_ids": ["gpt-5.3-codex", "gpt-5.4"],
            "server_issued": True,
        },
    }


def api_snapshot() -> dict[str, object]:
    return {
        "routes": [
            {
                "route_id": "wbp-web-primary-openrouter",
                "provider": "openrouter",
                "upstream_model": "openrouter/upstream",
                "enabled": True,
                "secret_ref": "OPENROUTER_API_KEY",
            }
        ]
    }


class GenericProviderAndModelRegistryR1Tests(unittest.TestCase):
    def test_generic_provider_registry_separates_auth_admitted_and_seed_only(self) -> None:
        packet = build_generic_provider_registry_packet()
        rows = {row["provider"]: row for row in packet["rows"]}

        self.assertEqual(packet["status"], "ok")
        self.assertIn("openrouter", rows)
        self.assertIn("deepseek", rows)
        self.assertIn("mistral", rows)
        self.assertIn("gemini", rows)
        self.assertIn("groq", rows)
        self.assertIn("cerebras", rows)
        self.assertIn("zai", rows)
        self.assertTrue(rows["openrouter"]["auth_schema_admitted"])
        self.assertTrue(rows["mistral"]["auth_schema_admitted"])
        self.assertFalse(rows["zai"]["auth_schema_admitted"])
        self.assertEqual(rows["zai"]["current_status"], "seed_only")
        self.assertFalse(packet["auth_admission_is_runtime_admission"])
        self.assertFalse(packet["provider_family_compatibility_claimed"])

    def test_generic_model_registry_separates_current_catalog_and_seed_only(self) -> None:
        packet = build_generic_model_registry_packet(
            operator_status(),
            api_snapshot=api_snapshot(),
        )
        current_rows = {row["model_id"]: row for row in packet["current_catalog_models"]}
        seed_rows = {row["model_id"]: row for row in packet["seed_only_models"]}

        self.assertEqual(packet["status"], "ok")
        self.assertIn("gpt-5.3-codex", current_rows)
        self.assertIn("gpt-5.4", current_rows)
        self.assertIn("wbp-web-primary-openrouter", current_rows)
        self.assertIn("direct-mistral-devstral-2512", seed_rows)
        self.assertIn("direct-gemini-2.5-flash", seed_rows)
        self.assertNotIn("gpt-5.3-codex", seed_rows)
        self.assertFalse(packet["current_catalog_is_runtime_proof"])
        self.assertFalse(packet["seed_only_is_current_runtime_catalog"])
        self.assertFalse(seed_rows["direct-mistral-devstral-2512"]["server_issued_for_runtime_selection"])
        self.assertFalse(seed_rows["direct-mistral-devstral-2512"]["selection_enabled"])
        self.assertEqual(seed_rows["direct-mistral-devstral-2512"]["current_status"], "seed_only")

    def test_probe_writes_bounded_registry_packets(self) -> None:
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

            model_registry = json.loads(
                (evidence_dir / "generic_model_registry_packet.json").read_text(encoding="utf-8")
            )
            self.assertFalse(model_registry["current_catalog_is_runtime_proof"])
            self.assertFalse(model_registry["seed_only_is_current_runtime_catalog"])

            matrix = json.loads(
                (evidence_dir / "current_vs_seed_model_matrix.json").read_text(encoding="utf-8")
            )
            self.assertFalse(matrix["seed_only_promoted_to_current_catalog"])
            self.assertFalse(matrix["seed_only_server_issued_for_runtime_selection"])

            truth_layers = json.loads(
                (evidence_dir / "registry_truth_layers_packet.json").read_text(encoding="utf-8")
            )
            self.assertFalse(truth_layers["display_metadata_is_runtime_truth"])
            self.assertFalse(truth_layers["runtime_truth_is_capability_proof"])

            non_claims = json.loads(
                (evidence_dir / "registry_non_claims_packet.json").read_text(encoding="utf-8")
            )
            self.assertFalse(non_claims["registry_presence_means_runtime_usable"])
            self.assertFalse(non_claims["seed_only_entries_are_current_runtime_candidates"])

            gaps = json.loads(
                (evidence_dir / "registry_gap_matrix.json").read_text(encoding="utf-8")
            )
            gap_ids = {gap["id"] for gap in gaps["gaps"]}
            self.assertIn("route_backed_model_can_inherit_account_selection_without_explicit_route", gap_ids)
            self.assertIn("raw_registry_fresh_truth_can_be_misread_as_runtime_readiness", gap_ids)
            self.assertIn("static_route_readiness_reused_as_session_provenance_truth", gap_ids)

            audit = json.loads(
                (evidence_dir / "independent_audit_packet.json").read_text(encoding="utf-8")
            )
            open_risk_ids = {
                finding["id"]
                for finding in audit["findings"]
                if finding.get("status") == "open_risk"
            }
            self.assertIn(
                "route_backed_model_without_explicit_route_selection_can_fall_back_to_account_truth",
                open_risk_ids,
            )
            self.assertIn(
                "raw_registry_support_booleans_still_read_broader_than_proven_runtime_compatibility",
                open_risk_ids,
            )


if __name__ == "__main__":
    unittest.main()
