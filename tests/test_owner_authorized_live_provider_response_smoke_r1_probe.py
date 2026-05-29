# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.owner_authorized_live_provider_response_smoke_r1_probe import (
    STATUS_BUDGET_POLICY_REQUIRED,
    STATUS_OWNER_AUTH_REQUIRED,
    STATUS_PROVEN_WITH_LIMITS,
    build_packets,
    validate_packets,
)


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "owner_authorized_live_provider_response_smoke_r1_probe.py"


class OwnerAuthorizedLiveProviderResponseSmokeR1ProbeTests(unittest.TestCase):
    def test_missing_owner_authorization_blocks_without_live_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            packets = build_packets(repo_root=ROOT, evidence_dir=Path(tmpdir) / "evidence")

        summary = packets["live_provider_response_smoke_summary_packet.json"]
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["final_status"], STATUS_OWNER_AUTH_REQUIRED)
        self.assertFalse(summary["live_request_attempted"])
        self.assertFalse(summary["upstream_response_observed"])
        self.assertFalse(summary["fallback_attempted"])
        self.assertFalse(summary["parallel_fanout_attempted"])
        self.assertFalse(summary["original_codex_touched"])

        owner = packets["owner_authorization_packet.json"]
        self.assertEqual(owner["status"], "blocked")
        self.assertIn("owner_authorization_missing", owner["failed_checks"])
        self.assertIn("provider_id_missing", owner["failed_checks"])
        self.assertIn("model_id_missing", owner["failed_checks"])
        self.assertIn("route_id_missing", owner["failed_checks"])
        self.assertFalse(owner["raw_secret_authorized"])
        self.assertFalse(owner["raw_secret_recorded"])

        evidence = packets["live_provider_response_evidence_packet.json"]
        self.assertEqual(evidence["status"], "blocked")
        self.assertFalse(evidence["request_attempted"])
        self.assertFalse(evidence["upstream_response_observed"])
        self.assertFalse(evidence["route_snapshot_counted_as_provider_response"])
        self.assertFalse(evidence["recording_runner_counted_as_live_upstream"])
        self.assertFalse(evidence["plain_text_response_counts_as_tools_proof"])
        self.assertFalse(evidence["plain_text_response_counts_as_streaming_proof"])
        self.assertFalse(evidence["provider_family_compatibility_claimed"])
        self.assertFalse(evidence["acceleration_claimed"])

        validation = packets["validation_packet.json"]
        self.assertEqual(validation["status"], "ok")
        self.assertEqual(validation["violation_count"], 0)

    def test_owner_authorized_but_missing_budget_blocks_before_live_request(self) -> None:
        request = {
            "owner_authorized": True,
            "provider_id": "openrouter",
            "model_id": "openrouter-test-model",
            "server_model_id": "wbp-web-primary-openrouter",
            "route_id": "wbp-web-primary-openrouter",
            "request_limit": 1,
            "retry_limit": 0,
            "cost_ceiling": "0.01 USD",
            "credential_ref_allowed": True,
            "budget_policy_present": False,
            "fallback_forbidden": True,
            "parallel_fanout_forbidden": True,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            packets = build_packets(
                repo_root=ROOT,
                evidence_dir=Path(tmpdir) / "evidence",
                request=request,
            )

        self.assertEqual(
            packets["live_provider_response_smoke_summary_packet.json"]["final_status"],
            STATUS_BUDGET_POLICY_REQUIRED,
        )
        self.assertEqual(packets["owner_authorization_packet.json"]["status"], "ok")
        budget = packets["budget_policy_packet.json"]
        self.assertEqual(budget["status"], "blocked")
        self.assertIn("budget_policy_missing", budget["failed_checks"])
        self.assertTrue(budget["paid_call_without_budget_forbidden"])
        self.assertEqual(budget["request_limit"], 1)
        self.assertEqual(budget["retry_limit"], 0)
        self.assertEqual(budget["fallback_policy"], "forbidden")
        self.assertEqual(budget["parallel_fanout_policy"], "forbidden")
        self.assertFalse(
            packets["live_provider_response_evidence_packet.json"]["request_attempted"]
        )

    def test_raw_browser_backend_fields_block_manual_choice(self) -> None:
        request = {
            "owner_authorized": True,
            "provider_id": "openrouter",
            "model_id": "openrouter-test-model",
            "server_model_id": "wbp-web-primary-openrouter",
            "route_id": "wbp-web-primary-openrouter",
            "request_limit": 1,
            "retry_limit": 0,
            "cost_ceiling": "0.01 USD",
            "credential_ref_allowed": True,
            "budget_policy_present": True,
            "fallback_forbidden": True,
            "parallel_fanout_forbidden": True,
            "browser_payload": {
                "model_id": "wbp-web-primary-openrouter",
                "base_url": "https://example.invalid",
                "secret_ref": "OPENROUTER_API_KEY",
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            packets = build_packets(
                repo_root=ROOT,
                evidence_dir=Path(tmpdir) / "evidence",
                request=request,
            )

        choice = packets["manual_model_choice_packet.json"]
        self.assertEqual(choice["status"], "blocked")
        self.assertEqual(choice["forbidden_browser_backend_fields"], ["base_url", "secret_ref"])
        self.assertTrue(choice["browser_raw_backend_authority_widened"])
        self.assertFalse(choice["selection_intent_counts_as_execution"])

    def test_validation_blocks_false_green_proven_without_provider_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            packets = build_packets(repo_root=ROOT, evidence_dir=Path(tmpdir) / "evidence")
        packets["live_provider_response_smoke_summary_packet.json"]["final_status"] = (
            STATUS_PROVEN_WITH_LIMITS
        )
        packets["live_provider_response_smoke_summary_packet.json"]["status"] = "ok"
        packets["owner_authorization_packet.json"]["status"] = "ok"
        packets["budget_policy_packet.json"]["status"] = "ok"
        packets["live_provider_response_evidence_packet.json"]["request_attempted"] = False
        packets["live_provider_response_evidence_packet.json"][
            "upstream_response_observed"
        ] = False
        packets["live_provider_response_evidence_packet.json"]["fallback_attempted"] = True
        packets["false_green_boundary_packet.json"][
            "route_snapshot_treated_as_provider_response"
        ] = True

        result = validate_packets(packets)
        violations = {item["violation"] for item in result["violations"]}
        self.assertEqual(result["status"], "blocked")
        self.assertIn("proven_status_without_upstream_response", violations)
        self.assertIn("proven_status_without_request_attempt", violations)
        self.assertIn("fallback_attempted", violations)
        self.assertIn("false_green_guard_enabled", violations)

    def test_probe_writes_owner_auth_required_packets(self) -> None:
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
            self.assertEqual(summary["packet_count"], 8)
            self.assertEqual(summary["final_status"], STATUS_OWNER_AUTH_REQUIRED)

            written_summary = json.loads(
                (
                    evidence_dir / "live_provider_response_smoke_summary_packet.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(written_summary["final_status"], STATUS_OWNER_AUTH_REQUIRED)
            self.assertFalse(written_summary["live_request_attempted"])


if __name__ == "__main__":
    unittest.main()
