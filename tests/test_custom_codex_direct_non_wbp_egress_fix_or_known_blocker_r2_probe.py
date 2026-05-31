# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.custom_codex_direct_non_wbp_egress_fix_or_known_blocker_r2_probe import (
    DEFAULT_SOURCE_FILES,
    FINAL_STATUS_BLOCKED,
    FINAL_STATUS_OK,
    SourcePacketError,
    build_closeout,
    build_packets,
    load_source_packets,
    overall_status,
)


class CustomCodexDirectNonWbpEgressFixOrKnownBlockerR2ProbeTests(unittest.TestCase):
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
        subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "fixture"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )

    def _source_paths(self, repo_root: Path) -> dict[str, str]:
        return {
            key: str((repo_root / relative_path).resolve())
            for key, relative_path in DEFAULT_SOURCE_FILES.items()
        }

    def _source_packets(self) -> dict[str, dict[str, object]]:
        return {
            "current_truth": {
                "status": "ok",
                "final_status": "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_OBSERVED",
                "reason_class": "DIRECT_NON_WBP_MODEL_EGRESS_OBSERVED",
                "direct_non_wbp_model_egress_observed": True,
                "direct_non_wbp_model_egress_absent_within_bounded_window": False,
                "direct_egress_absence_proven": False,
                "api_openai_com_absence_proven": False,
                "domain_attribution_available": False,
            },
            "pass4_route_trace": {
                "status": "ok",
                "forwarded_to_wbp": True,
                "upstream_status": 200,
                "direct_egress_claimed": False,
                "trace_path": "/v1/responses",
            },
            "r4_import_summary": {
                "status": "ok",
                "final_status": "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_OBSERVED",
                "reason_class": "DIRECT_NON_WBP_MODEL_EGRESS_OBSERVED",
                "command_hash_matches": True,
                "owner_readiness_status": "ok",
                "owner_attestation_context_only": True,
                "native_launch_attempted_from_current_thread": False,
                "external_evidence_dir": "/tmp/external-r3",
            },
            "r4_network_classification": {
                "status": "ok",
                "final_status": "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_OBSERVED",
                "reason_class": "DIRECT_NON_WBP_MODEL_EGRESS_OBSERVED",
                "direct_non_wbp_model_egress_observed": True,
                "direct_non_wbp_model_egress_absent_within_bounded_window": False,
                "final_e2e_claimed": False,
            },
            "r4_trace_validation": {
                "status": "ok",
                "wbp_trace_confirmed": True,
            },
            "r3_direct_claim": {
                "status": "blocked",
                "final_status": "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_BACKGROUND_CODEX_NOISE",
                "reason_class": "BACKGROUND_CODEX_NOISE",
                "custom_process_bound": True,
                "route_trace_confirmed": True,
                "direct_model_egress_observed": True,
            },
            "r3_network_observation": {
                "status": "ok",
                "classification": "direct_model_egress_observed",
                "non_local_peer_endpoints_present": True,
                "allowed_local_endpoint_observed": True,
            },
            "r2_direct_claim": {
                "status": "blocked",
                "final_status": "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_BACKGROUND_CODEX_NOISE",
                "reason_class": "BACKGROUND_CODEX_NOISE",
                "direct_non_wbp_model_egress_absent_proven": False,
            },
            "r2_network_observation": {
                "status": "ok",
                "classification": "insufficient_observation",
                "non_local_peer_endpoints_present": True,
                "allowed_local_endpoint_observed": False,
            },
            "r2_background_noise": {
                "status": "blocked",
                "background_codex_noise_detected": True,
            },
        }

    def test_build_packets_synthesizes_known_blocker_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass5"
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=self._source_packets(),
                source_paths=self._source_paths(repo_root),
            )
            status, verdict = overall_status(packets)
            closeout = build_closeout(repo_root, evidence_dir, packets)

        self.assertEqual(status, "ok")
        self.assertEqual(verdict, FINAL_STATUS_OK)
        self.assertEqual(
            packets["direct_non_wbp_egress_reproduction_packet.json"]["classification"],
            "imported_authenticated_direct_egress_observed",
        )
        self.assertTrue(
            packets["direct_non_wbp_egress_reproduction_packet.json"][
                "strongest_authenticated_direct_egress_observed"
            ]
        )
        self.assertFalse(
            packets["direct_non_wbp_egress_fix_attempt_packet.json"]["fix_attempted"]
        )
        self.assertIsNone(
            packets["direct_non_wbp_egress_localization_packet.json"][
                "exact_root_cause_requires_separate_fix_contour"
            ]
        )
        self.assertEqual(
            packets["direct_non_wbp_egress_localization_packet.json"][
                "remediation_contour_need_classification"
            ],
            "unknown",
        )
        self.assertTrue(
            packets["direct_non_wbp_vs_wbp_boundary_packet.json"][
                "wbp_routed_truth_preserved"
            ]
        )
        self.assertTrue(
            packets["direct_non_wbp_failure_semantics_packet.json"][
                "direct_non_wbp_model_egress_known_blocker"
            ]
        )
        self.assertEqual(packets["false_green_audit.json"]["status"], "ok")
        self.assertIn(
            "final verdict: `CUSTOM_CODEX_DIRECT_NON_WBP_EGRESS_KNOWN_BLOCKER`",
            closeout,
        )
        self.assertIn("resume from here: CLOSED", closeout)

    def test_weaker_later_non_healing_evidence_does_not_erase_stronger_prior_truth(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass5"
            sources = self._source_packets()
            sources["r2_direct_claim"]["reason_class"] = "BACKGROUND_CODEX_NOISE"
            sources["r2_network_observation"]["classification"] = "insufficient_observation"
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        status, verdict = overall_status(packets)
        self.assertEqual(status, "ok")
        self.assertEqual(verdict, FINAL_STATUS_OK)
        self.assertTrue(
            packets["direct_non_wbp_egress_reproduction_packet.json"][
                "stronger_prior_evidence_beats_weaker_later_non_healing_observation"
            ]
        )
        self.assertEqual(
            packets["direct_non_wbp_failure_semantics_packet.json"]["status"], "ok"
        )

    def test_build_packets_blocks_contradictory_core_fact_and_boundary_overclaim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass5"
            sources = copy.deepcopy(self._source_packets())
            sources["current_truth"]["final_status"] = (
                "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_ABSENT_WITH_LIMITS"
            )
            sources["current_truth"]["direct_non_wbp_model_egress_observed"] = False
            sources["pass4_route_trace"]["direct_egress_claimed"] = True
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        status, verdict = overall_status(packets)
        self.assertEqual(status, "blocked")
        self.assertEqual(verdict, FINAL_STATUS_BLOCKED)
        self.assertEqual(
            packets["direct_non_wbp_egress_reproduction_packet.json"]["status"],
            "blocked",
        )
        self.assertEqual(
            packets["direct_non_wbp_vs_wbp_boundary_packet.json"]["status"], "blocked"
        )
        self.assertEqual(packets["false_green_audit.json"]["status"], "blocked")

    def test_localization_blocks_when_r3_binding_or_route_confirmation_weakens(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass5"
            sources = copy.deepcopy(self._source_packets())
            sources["r3_direct_claim"]["custom_process_bound"] = False
            sources["r3_direct_claim"]["route_trace_confirmed"] = False
            sources["r3_network_observation"]["classification"] = "insufficient_observation"
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        self.assertEqual(
            packets["direct_non_wbp_egress_localization_packet.json"]["status"],
            "blocked",
        )
        self.assertEqual(packets["false_green_audit.json"]["status"], "blocked")

    def test_boundary_blocks_when_imported_route_evidence_weakens(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            evidence_dir = repo_root / "audit_results" / "pass5"
            sources = copy.deepcopy(self._source_packets())
            sources["pass4_route_trace"]["forwarded_to_wbp"] = False
            sources["r4_trace_validation"]["wbp_trace_confirmed"] = False
            packets = build_packets(
                repo_root,
                evidence_dir,
                source_packets=sources,
                source_paths=self._source_paths(repo_root),
            )

        self.assertEqual(
            packets["direct_non_wbp_vs_wbp_boundary_packet.json"]["status"], "blocked"
        )
        self.assertEqual(packets["false_green_audit.json"]["status"], "blocked")

    def test_load_source_packets_blocks_missing_required_source_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._init_repo(repo_root)
            source_files = copy.deepcopy(DEFAULT_SOURCE_FILES)
            source_files["current_truth"] = Path("audit_results/missing/current_truth.json")

            with self.assertRaises(SourcePacketError):
                load_source_packets(repo_root, source_files=source_files)


if __name__ == "__main__":
    unittest.main()
