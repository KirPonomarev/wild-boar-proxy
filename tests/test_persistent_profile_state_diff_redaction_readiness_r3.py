# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.persistent_profile_state_diff_redaction_readiness_r3_probe import (
    PARENT_STATUS,
    TARGET_STATUS,
    build_false_green_audit,
    build_independent_audit_packet,
    build_readiness_packets,
    build_summary_packet,
)
from wild_boar_proxy.persistent_profile_state_diff import (
    build_profile_snapshot,
    classify_persistent_profile_state_path,
    diff_profile_snapshots,
    marker_scan_text,
    redacted_snapshot_entry,
    synthetic_profile_snapshots,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class PersistentProfileStateDiffRedactionReadinessR3Tests(unittest.TestCase):
    def test_classifier_maps_required_state_classes_without_runtime_truth(self) -> None:
        examples = {
            "conversations/thread-redacted.json": "thread_history",
            "Local Storage/state.vscdb": "session_state",
            "settings/config.toml": "user_settings",
            "model-menu/catalog.json": "model_menu_state",
            "wbp/provider-linkage.json": "provider_wbp_linkage_state",
            "integrations/connector-state.json": "integration_state",
            "Cache/blob_storage/index": "cache_or_incidental_state",
            "unknown/file.bin": "unclassified_profile_state",
        }

        classified = {
            path: classify_persistent_profile_state_path(path)
            for path in examples
        }

        self.assertEqual(classified, examples)

    def test_snapshot_schema_records_hashes_not_content_or_raw_prompt(self) -> None:
        entry = redacted_snapshot_entry(
            relative_path="conversations/thread-redacted.json",
            size=123,
            content_hash="abc123",
        )
        snapshot = build_profile_snapshot(snapshot_label="unit", entries=[entry])

        self.assertEqual(snapshot["entry_count"], 1)
        self.assertEqual(snapshot["entries"][0]["state_class"], "thread_history")
        self.assertFalse(snapshot["entries"][0]["content_recorded"])
        self.assertFalse(snapshot["entries"][0]["raw_prompt_recorded"])
        self.assertFalse(snapshot["entries"][0]["raw_secret_recorded"])
        self.assertFalse(snapshot["snapshot_is_live_profile_proof"])
        self.assertFalse(snapshot["snapshot_is_thread_history_proof"])

    def test_diff_classifies_before_after_without_saved_thread_or_ux_claim(self) -> None:
        snapshots = synthetic_profile_snapshots()
        diff = diff_profile_snapshots(
            snapshots["before"],
            snapshots["after"],
            diff_label="unit_before_after",
        )

        created_classes = {item["state_class"] for item in diff["created"]}
        changed_classes = {item["state_class"] for item in diff["changed"]}

        self.assertTrue(diff["diff_detected"])
        self.assertIn("thread_history", created_classes)
        self.assertIn("cache_or_incidental_state", changed_classes)
        self.assertFalse(diff["diff_detected_is_saved_thread_proof"])
        self.assertFalse(diff["hash_changed_is_user_visible_state"])
        self.assertFalse(diff["synthetic_diff_is_real_profile_pass"])
        self.assertFalse(diff["thread_history_preservation_claimed"])
        self.assertFalse(diff["profile_storage_persistence_claimed"])

    def test_relaunch_diff_shape_does_not_claim_actual_relaunch(self) -> None:
        snapshots = synthetic_profile_snapshots()
        diff = diff_profile_snapshots(
            snapshots["after"],
            snapshots["relaunch"],
            diff_label="unit_relaunch",
        )

        self.assertTrue(diff["synthetic_fixture"])
        self.assertGreaterEqual(diff["changed_count"], 1)
        self.assertFalse(diff["synthetic_diff_is_real_profile_pass"])
        self.assertFalse(diff["diff_detected_is_saved_thread_proof"])

    def test_marker_scan_detects_prompt_and_secret_but_does_not_claim_exhaustive_dlp(self) -> None:
        clean = marker_scan_text("paths sizes hashes only")
        dirty = marker_scan_text("OPENAI_API_KEY=example nonce_used=true")

        self.assertFalse(clean["raw_prompt_found"])
        self.assertFalse(clean["raw_secret_found"])
        self.assertTrue(dirty["raw_prompt_found"])
        self.assertTrue(dirty["raw_secret_found"])
        self.assertFalse(clean["exhaustive_dlp_claimed"])
        self.assertFalse(dirty["exhaustive_dlp_claimed"])

    def test_packets_close_r3_only_and_keep_parent_open(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        summary = packets["persistent_state_diff_summary_packet.json"]

        if summary["status"] == "blocked":
            self.assertIn("sync_gate_packet.json", summary["blocked_packets"])
            self.assertFalse(summary["parent_target_closed"])
            self.assertFalse(summary["this_target_closed"])
            self.assertFalse(summary["native_launch_attempted"])
            return
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_status"], TARGET_STATUS)
        self.assertEqual(summary["parent_target"], PARENT_STATUS)
        self.assertFalse(summary["parent_target_closed"])
        self.assertTrue(summary["this_target_closed"])
        self.assertFalse(summary["native_launch_attempted"])
        self.assertFalse(summary["custom_app_launch_attempted"])
        self.assertFalse(summary["owner_prompt_required"])
        self.assertFalse(summary["owner_input_required"])
        self.assertFalse(summary["live_provider_request_attempted"])
        self.assertFalse(summary["persistent_profile_state_written"])
        self.assertFalse(summary["real_thread_created"])
        self.assertFalse(summary["real_relaunch_performed"])
        self.assertFalse(summary["thread_history_preservation_claimed"])
        self.assertFalse(summary["profile_storage_persistence_claimed"])
        self.assertFalse(summary["native_ux_claimed"])
        self.assertFalse(summary["keychain_behavior_classified"])
        self.assertFalse(summary["original_reversibility_proven"])
        self.assertFalse(summary["final_e2e_claimed"])

    def test_deliverable_packets_preserve_layer_boundaries(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        classifier = packets["persistent_state_classifier_non_runtime_truth_packet.json"]
        thread = packets["thread_history_non_claim_packet.json"]
        cache = packets["cache_drift_non_claim_packet.json"]
        before_after = packets["synthetic_before_after_diff_packet.json"]
        relaunch = packets["synthetic_relaunch_diff_packet.json"]

        self.assertFalse(classifier["classifier_label_treated_as_runtime_truth"])
        self.assertFalse(classifier["state_class_label_is_runtime_truth"])
        self.assertFalse(classifier["state_class_label_is_thread_preservation_proof"])
        self.assertFalse(thread["thread_history_preservation_claimed"])
        self.assertFalse(thread["saved_thread_proven"])
        self.assertFalse(cache["cache_drift_is_thread_history"])
        self.assertFalse(cache["hash_changed_is_user_visible_state"])
        self.assertFalse(before_after["real_profile_pass_claimed"])
        self.assertFalse(before_after["real_thread_created"])
        self.assertFalse(relaunch["real_relaunch_performed"])
        self.assertFalse(relaunch["synthetic_relaunch_is_actual_relaunch_proof"])

    def test_false_green_audit_blocks_synthetic_classifier_hash_and_cache_overclaims(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        mutated = dict(packets)
        mutated["persistent_state_classifier_non_runtime_truth_packet.json"] = {
            **mutated["persistent_state_classifier_non_runtime_truth_packet.json"],
            "classifier_label_treated_as_runtime_truth": True,
        }
        mutated["synthetic_relaunch_diff_packet.json"] = {
            **mutated["synthetic_relaunch_diff_packet.json"],
            "synthetic_relaunch_is_actual_relaunch_proof": True,
        }
        mutated["cache_drift_non_claim_packet.json"] = {
            **mutated["cache_drift_non_claim_packet.json"],
            "cache_drift_is_thread_history": True,
        }
        mutated["synthetic_before_after_diff_packet.json"] = {
            **mutated["synthetic_before_after_diff_packet.json"],
            "changed": [
                {
                    "relative_path": "Cache/blob_storage/index",
                    "state_class": "cache_or_incidental_state",
                    "hash_changed_is_user_visible_state": True,
                }
            ],
        }

        audit = build_false_green_audit(mutated)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "persistent_state_classifier_non_runtime_truth_packet.json.classifier_label_treated_as_runtime_truth",
            audit["findings"],
        )
        self.assertIn(
            "synthetic_relaunch_diff_packet.json.synthetic_relaunch_is_actual_relaunch_proof",
            audit["findings"],
        )
        self.assertIn(
            "cache_drift_non_claim_packet.json.cache_drift_is_thread_history",
            audit["findings"],
        )
        self.assertIn(
            "synthetic_before_after_diff_packet.json.changed[0].hash_changed_is_user_visible_state",
            audit["findings"],
        )

    def test_independent_audit_and_summary_block_forbidden_or_missing_packets(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        mutated = dict(packets)
        mutated["thread_history_non_claim_packet.json"] = {
            **mutated["thread_history_non_claim_packet.json"],
            "thread_history_preservation_claimed": True,
        }
        audit = build_independent_audit_packet(mutated)

        blocked_packets = dict(packets)
        blocked_packets["persistent_state_diff_false_green_audit.json"] = {
            **blocked_packets["persistent_state_diff_false_green_audit.json"],
            "status": "blocked",
        }
        blocked_summary = build_summary_packet(blocked_packets)

        missing_packets = dict(packets)
        del missing_packets["synthetic_before_after_diff_packet.json"]
        missing_summary = build_summary_packet(missing_packets)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "thread_history_non_claim_packet.json.thread_history_preservation_claimed",
            audit["forbidden_true_fields"],
        )
        self.assertEqual(blocked_summary["status"], "blocked")
        self.assertIn(
            "persistent_state_diff_false_green_audit.json",
            blocked_summary["blocked_packets"],
        )
        self.assertEqual(missing_summary["status"], "blocked")
        self.assertIn(
            "synthetic_before_after_diff_packet.json",
            missing_summary["missing_required_packets"],
        )

    def test_secret_audit_records_no_raw_prompt_or_secret(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        secret = packets["secret_redaction_audit.json"]

        self.assertEqual(secret["status"], "ok")
        self.assertFalse(secret["raw_secret_found"])
        self.assertFalse(secret["raw_prompt_found"])
        self.assertFalse(secret["raw_secret_recorded"])
        self.assertFalse(secret["raw_prompt_recorded"])
        self.assertFalse(secret["exhaustive_dlp_claimed"])
        self.assertEqual(secret["marker_findings"], [])
        self.assertEqual(secret["secret_pattern_findings"], [])


if __name__ == "__main__":
    unittest.main()
