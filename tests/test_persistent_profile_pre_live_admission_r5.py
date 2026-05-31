# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.persistent_profile_pre_live_admission_r5_probe import (
    DEFAULT_PRIOR_DIRS,
    TARGET_STATUS,
    build_packets,
)
from wild_boar_proxy.persistent_profile_pre_live_admission import (
    R1_STATUS,
    R2_STATUS,
    R3_STATUS,
    R4_STATUS,
    REFERENCE_SPECS,
    build_admission_packets,
    build_false_green_audit,
    build_prior_reference_packet,
    build_summary_packet,
    PriorEvidenceLocation,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def default_locations() -> list[PriorEvidenceLocation]:
    return [
        PriorEvidenceLocation(key=key, evidence_dir=REPO_ROOT / path)
        for key, path in DEFAULT_PRIOR_DIRS.items()
    ]


def copy_evidence_tree(tmp: Path, key: str) -> Path:
    source = REPO_ROOT / DEFAULT_PRIOR_DIRS[key]
    target = tmp / key
    shutil.copytree(source, target)
    return target


class PersistentProfilePreLiveAdmissionR5Tests(unittest.TestCase):
    def test_admitted_path_references_r1_to_r4_by_hash_without_live_claims(self) -> None:
        packets = build_admission_packets(
            repo_root=REPO_ROOT,
            locations=default_locations(),
        )

        summary = packets["persistent_pre_live_summary_packet.json"]
        decision = packets["persistent_pre_live_admission_decision_packet.json"]
        hashes = packets["persistent_pre_live_prior_reference_hashes_packet.json"]

        if summary["status"] == "blocked":
            self.assertEqual(sync["status"], "blocked")
            self.assertFalse(summary["parent_target_closed"])
            self.assertFalse(summary["native_launch_attempted"])
            self.assertFalse(summary["original_reversibility_proven"])
            return
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertFalse(summary["parent_target_closed"])
        self.assertTrue(summary["this_target_closed"])
        self.assertEqual(decision["admission_decision"], "admitted_for_planning")
        self.assertTrue(decision["future_live_contour_may_be_planned"])
        self.assertFalse(decision["admission_counts_as_live_launch_safe"])
        self.assertFalse(decision["admission_counts_as_thread_history_proof"])
        self.assertFalse(decision["admission_counts_as_backup_created"])
        self.assertFalse(decision["admission_counts_as_restore_verified"])
        self.assertGreaterEqual(hashes["referenced_packet_count"], 8)
        self.assertEqual(hashes["missing_summary_hashes"], [])
        self.assertFalse(summary["native_launch_attempted"])
        self.assertFalse(summary["thread_history_preservation_claimed"])
        self.assertFalse(summary["route_proven"])
        self.assertFalse(summary["model_availability_claimed"])

    def test_reference_packets_require_exact_expected_final_statuses(self) -> None:
        expected = {
            "r1_launcher_contract": R1_STATUS,
            "r2_dry_run_enforcement": R2_STATUS,
            "r3_state_diff": R3_STATUS,
            "r4_backup_restore": R4_STATUS,
        }

        packets = build_admission_packets(
            repo_root=REPO_ROOT,
            locations=default_locations(),
        )

        for key, status in expected.items():
            filename = {
                "r1_launcher_contract": "persistent_pre_live_r1_launcher_contract_reference_packet.json",
                "r2_dry_run_enforcement": "persistent_pre_live_r2_dry_run_enforcement_reference_packet.json",
                "r3_state_diff": "persistent_pre_live_r3_state_diff_reference_packet.json",
                "r4_backup_restore": "persistent_pre_live_r4_backup_restore_reference_packet.json",
            }[key]
            self.assertEqual(packets[filename]["expected_final_status"], status)
            self.assertEqual(packets[filename]["prior_final_status"], status)
            self.assertTrue(packets[filename]["packet_hash_recorded"])

    def test_missing_prior_reference_blocks_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            locations = default_locations()
            locations[2] = PriorEvidenceLocation(
                key="r3_state_diff",
                evidence_dir=Path(tmp) / "missing-r3",
            )
            packets = build_admission_packets(repo_root=REPO_ROOT, locations=locations)

        r3 = packets["persistent_pre_live_r3_state_diff_reference_packet.json"]
        summary = packets["persistent_pre_live_summary_packet.json"]

        self.assertEqual(r3["status"], "blocked")
        self.assertFalse(r3["summary_packet_present"])
        self.assertEqual(summary["status"], "blocked")
        self.assertIn(
            "persistent_pre_live_r3_state_diff_reference_packet.json",
            summary["blocked_packets"],
        )

    def test_blocked_prior_status_or_wrong_final_status_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            r2 = copy_evidence_tree(tmp, "r2_dry_run_enforcement")
            summary_path = r2 / REFERENCE_SPECS["r2_dry_run_enforcement"]["summary"]
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["status"] = "blocked"
            summary["final_status"] = "WRONG"
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            locations = default_locations()
            locations[1] = PriorEvidenceLocation(
                key="r2_dry_run_enforcement",
                evidence_dir=r2,
            )
            packets = build_admission_packets(repo_root=REPO_ROOT, locations=locations)

        r2_ref = packets["persistent_pre_live_r2_dry_run_enforcement_reference_packet.json"]
        decision = packets["persistent_pre_live_admission_decision_packet.json"]

        self.assertEqual(r2_ref["status"], "blocked")
        self.assertFalse(r2_ref["prior_status_ok"])
        self.assertFalse(r2_ref["prior_final_status_ok"])
        self.assertEqual(decision["status"], "blocked")
        self.assertEqual(decision["admission_decision"], "blocked")

    def test_missing_supporting_packet_blocks_reference_even_when_summary_is_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            r4 = copy_evidence_tree(tmp, "r4_backup_restore")
            (r4 / "persistent_destructive_action_guard_packet.json").unlink()
            packet = build_prior_reference_packet(
                repo_root=REPO_ROOT,
                location=PriorEvidenceLocation(key="r4_backup_restore", evidence_dir=r4),
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn(
            "persistent_destructive_action_guard_packet.json",
            packet["missing_supporting_packets"],
        )

    def test_prior_non_claim_overclaim_blocks_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            r1 = copy_evidence_tree(tmp, "r1_launcher_contract")
            summary_path = r1 / REFERENCE_SPECS["r1_launcher_contract"]["summary"]
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["native_launch_attempted"] = True
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            packet = build_prior_reference_packet(
                repo_root=REPO_ROOT,
                location=PriorEvidenceLocation(key="r1_launcher_contract", evidence_dir=r1),
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("native_launch_attempted", packet["non_claim_overclaims"])

    def test_false_green_audit_blocks_reclassification_and_runtime_claims(self) -> None:
        packets = build_admission_packets(
            repo_root=REPO_ROOT,
            locations=default_locations(),
        )
        mutated = dict(packets)
        mutated["persistent_pre_live_admission_decision_packet.json"] = {
            **mutated["persistent_pre_live_admission_decision_packet.json"],
            "admission_counts_as_live_launch_safe": True,
            "admission_counts_as_route_proof": True,
        }
        mutated["persistent_pre_live_r3_state_diff_reference_packet.json"] = {
            **mutated["persistent_pre_live_r3_state_diff_reference_packet.json"],
            "r3_state_diff_readiness_used_as_saved_thread_proof": True,
        }
        audit = build_false_green_audit(mutated)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "persistent_pre_live_admission_decision_packet.json.admission_counts_as_live_launch_safe",
            audit["findings"],
        )
        self.assertIn(
            "persistent_pre_live_admission_decision_packet.json.admission_counts_as_route_proof",
            audit["findings"],
        )
        self.assertIn(
            "persistent_pre_live_r3_state_diff_reference_packet.json.r3_state_diff_readiness_used_as_saved_thread_proof",
            audit["findings"],
        )

    def test_summary_blocks_missing_false_green_packet(self) -> None:
        packets = build_admission_packets(
            repo_root=REPO_ROOT,
            locations=default_locations(),
        )
        del packets["persistent_pre_live_false_green_audit.json"]
        summary = build_summary_packet(packets)

        self.assertEqual(summary["status"], "blocked")
        self.assertIn(
            "persistent_pre_live_false_green_audit.json",
            summary["missing_required_packets"],
        )

    def test_probe_packets_close_r5_only_and_secret_audit_is_clean(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(
                repo_root=REPO_ROOT,
                evidence_dir=Path(tmp),
                locations=default_locations(),
            )

        summary = packets["persistent_pre_live_summary_packet.json"]
        secret = packets["secret_redaction_audit.json"]
        independent = packets["independent_persistent_pre_live_admission_audit.json"]
        sync = packets["sync_gate_packet.json"]

        if summary["status"] == "blocked":
            self.assertEqual(sync["status"], "blocked")
            self.assertFalse(summary["parent_target_closed"])
            self.assertFalse(summary["native_launch_attempted"])
            self.assertFalse(summary["original_reversibility_proven"])
            return
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertFalse(summary["parent_target_closed"])
        self.assertFalse(summary["native_launch_attempted"])
        self.assertFalse(summary["original_reversibility_proven"])
        self.assertEqual(secret["status"], "ok")
        self.assertFalse(secret["raw_prompt_found"])
        self.assertFalse(secret["raw_secret_found"])
        self.assertFalse(secret["exhaustive_dlp_claimed"])
        self.assertEqual(independent["status"], "ok")
        self.assertEqual(sync["status"], "ok")


if __name__ == "__main__":
    unittest.main()
