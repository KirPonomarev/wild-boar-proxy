# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.persistent_custom_profile_history_r2b_probe import (
    _redact_owner_nonce_in_packet,
    build_parser,
    build_r3_cutoff_baseline_target_manifest,
    build_r3_false_green_audit,
    build_r3_owner_visible_thread_continuity_packet,
    build_r3_profile_state_with_thread_target_retention_packet,
    build_r3_storage_level_history_correlation_packet,
    build_r3_summary_packet,
    build_r3_thread_history_preservation_packet,
    build_r3_thread_target_selection_packet,
)


class PersistentCustomProfileHistoryR3ProbeTests(unittest.TestCase):
    def test_owner_nonce_redaction_covers_nested_packet_strings(self) -> None:
        packet = _redact_owner_nonce_in_packet(
            {
                "relative_path": "home/Documents/Codex/ok-nonce-123",
                "nested": ["OK nonce-123", {"path": "sessions/nonce-123.jsonl"}],
            },
            owner_nonce="nonce-123",
        )

        dumped = str(packet)
        self.assertNotIn("nonce-123", dumped)
        self.assertIn("<owner_nonce>", dumped)

    def test_r3_thread_target_selection_uses_session_surfaces_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "session_index.jsonl").write_text("private body\n", encoding="utf-8")
            (root / "sessions/2026/05/28").mkdir(parents=True)
            (root / "sessions/2026/05/28/rollout.jsonl").write_text(
                "private body\n", encoding="utf-8"
            )
            (root / ".tmp/plugins/example").mkdir(parents=True)
            (root / ".tmp/plugins/example/conversation-to-wiki.json").write_text(
                "private body\n", encoding="utf-8"
            )
            (root / "node_modules/pkg").mkdir(parents=True)
            (root / "node_modules/pkg/thread_annotations.h").write_text(
                "private body\n", encoding="utf-8"
            )

            packet = build_r3_thread_target_selection_packet(profile_root=root)

        selected = {row["relative_path"] for row in packet["selected_hypotheses"]}
        self.assertEqual(packet["status"], "ok")
        self.assertIn("session_index.jsonl", selected)
        self.assertIn("sessions/2026/05/28/rollout.jsonl", selected)
        self.assertNotIn(".tmp/plugins/example/conversation-to-wiki.json", selected)
        self.assertNotIn("node_modules/pkg/thread_annotations.h", selected)

    def test_r3_thread_target_selection_prefers_nonce_bearing_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "session_index.jsonl").write_text("index\n", encoding="utf-8")
            (root / "sessions/2026/05/28").mkdir(parents=True)
            older = root / "sessions/2026/05/28/older.jsonl"
            older.write_text("old private body\n", encoding="utf-8")
            nonce_file = root / "sessions/2026/05/28/nonce.jsonl"
            nonce_file.write_text("private OK nonce-123 body\n", encoding="utf-8")

            packet = build_r3_thread_target_selection_packet(
                profile_root=root,
                owner_nonce="nonce-123",
            )

        selected = packet["selected_hypotheses"]
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["same_nonce_candidate_selected"])
        self.assertEqual(selected[1]["relative_path"], "sessions/2026/05/28/nonce.jsonl")
        self.assertTrue(selected[1]["same_nonce_candidate"])
        self.assertTrue(selected[1]["nonce_sha256"])
        self.assertFalse(selected[1]["raw_content_recorded"])

    def test_r3_cutoff_baseline_marks_selected_changed_paths_without_raw_content(self) -> None:
        packet = build_r3_cutoff_baseline_target_manifest(
            selection_packet={
                "selected_hypotheses": [
                    {
                        "relative_path": "session_index.jsonl",
                        "mtime_ns": 200,
                        "size": 10,
                    },
                    {
                        "relative_path": "sessions/2026/05/28/nonce.jsonl",
                        "mtime_ns": 250,
                        "size": 20,
                    },
                ]
            },
            profile_root=Path("/tmp/profile"),
            cutoff_ns=100,
            phase="r3_before",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["baseline_inferred_from_cutoff"])
        for target in packet["targets"]:
            self.assertFalse(target["raw_content_recorded"])
            self.assertTrue(target["baseline_inferred_from_cutoff"])
            self.assertTrue(target["selected_path_changed_after_cutoff"])

    def test_r3_profile_state_can_be_preserved_by_retained_thread_targets(self) -> None:
        packet = build_r3_profile_state_with_thread_target_retention_packet(
            profile_state_packet={
                "status": "blocked",
                "reason_class": "PERSISTENT_PROFILE_STATE_PRESERVATION_UNPROVEN",
                "profile_state_preserved": False,
                "same_persistent_profile_identity": True,
                "after_action_storage_changed": True,
                "after_relaunch_state_kept": False,
            },
            target_delta_packet={
                "changed_target_count": 2,
                "retained_target_count": 2,
            },
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["profile_state_preserved"])
        self.assertTrue(packet["after_relaunch_state_kept"])
        self.assertTrue(packet["profile_state_preserved_by_selected_thread_target_retention"])
        self.assertTrue(packet["service_runtime_churn_not_counted_as_thread_history_loss"])
        self.assertFalse(packet["counts_as_thread_history_proof"])

    def test_r3_profile_state_retention_helper_does_not_override_identity_failure(self) -> None:
        packet = build_r3_profile_state_with_thread_target_retention_packet(
            profile_state_packet={
                "status": "blocked",
                "profile_state_preserved": False,
                "same_persistent_profile_identity": False,
                "after_action_storage_changed": True,
            },
            target_delta_packet={
                "changed_target_count": 2,
                "retained_target_count": 2,
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["profile_state_preserved"])

    def test_r3_owner_visible_thread_continuity_stays_context_only(self) -> None:
        packet = build_r3_owner_visible_thread_continuity_packet(
            visibility_result_packet={
                "same_persistent_profile_identity": True,
                "owner_visible_thread_continuity_classified": True,
            },
            owner_visibility_packet={"same_nonce_thread_visible": True},
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["same_nonce_thread_visible"])
        self.assertFalse(packet["owner_visible_thread_counts_as_storage_proof"])
        self.assertFalse(packet["storage_level_thread_history_proven"])

    def test_r3_storage_correlation_packet_records_selected_target_delta_only(self) -> None:
        packet = build_r3_storage_level_history_correlation_packet(
            selection_packet={
                "selected_hypotheses": [
                    {"relative_path": "session_index.jsonl"},
                    {
                        "relative_path": "sessions/2026/05/28/rollout.jsonl",
                        "same_nonce_candidate": True,
                    },
                ]
            },
            target_delta_packet={
                "changed_target_count": 1,
                "retained_target_count": 2,
                "target_delta_rows": [
                    {
                        "relative_path": "session_index.jsonl",
                        "changed_after_owner_action": True,
                        "retained_after_relaunch": True,
                    },
                    {
                        "relative_path": "sessions/2026/05/28/rollout.jsonl",
                        "changed_after_owner_action": True,
                        "retained_after_relaunch": True,
                    },
                ],
            },
            storage_correlation_packet={"storage_correlation_classified": True},
            correlation_classification_packet={
                "final_status": (
                    "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_LOCAL_RESTORATION_CORRELATION_CLASSIFIED"
                )
            },
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["selected_target_count"], 2)
        self.assertTrue(packet["storage_correlation_classified"])
        self.assertTrue(packet["selected_target_set_sufficient"])
        self.assertTrue(packet["selected_target_delta_sufficient"])
        self.assertTrue(packet["same_nonce_target_binding_proven"])
        self.assertTrue(packet["storage_level_thread_history_proven"])
        self.assertFalse(packet["durable_restoration_proven"])

    def test_r3_storage_correlation_requires_session_index_and_retained_delta(self) -> None:
        packet = build_r3_storage_level_history_correlation_packet(
            selection_packet={
                "selected_hypotheses": [
                    {"relative_path": "sessions/2026/05/28/rollout.jsonl"},
                ]
            },
            target_delta_packet={
                "changed_target_count": 1,
                "retained_target_count": 0,
                "target_delta_rows": [
                    {
                        "relative_path": "sessions/2026/05/28/rollout.jsonl",
                        "changed_after_owner_action": True,
                        "retained_after_relaunch": False,
                    }
                ],
            },
            storage_correlation_packet={"storage_correlation_classified": True},
            correlation_classification_packet={
                "final_status": (
                    "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_LOCAL_RESTORATION_CORRELATION_CLASSIFIED"
                )
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["storage_correlation_classified"])
        self.assertEqual(packet["reason_class"], "SELECTED_THREAD_TARGET_SET_INSUFFICIENT")

    def test_r3_thread_history_preservation_stays_blocked_without_storage_level_proof(self) -> None:
        with_limits_packet = build_r3_thread_history_preservation_packet(
            profile_state_packet={"profile_state_preserved": True},
            owner_visible_thread_continuity_packet={
                "same_nonce_thread_visible": True,
                "owner_visible_thread_continuity_classified": True,
            },
            storage_level_history_correlation_packet={
                "storage_correlation_classified": True,
                "storage_level_thread_history_proven": False,
                "bounded_selected_session_target_correlation_proven": True,
                "same_nonce_target_binding_proven": False,
            },
            keychain_packet={"status": "ok"},
        )
        full_packet = build_r3_thread_history_preservation_packet(
            profile_state_packet={"profile_state_preserved": True},
            owner_visible_thread_continuity_packet={
                "same_nonce_thread_visible": True,
                "owner_visible_thread_continuity_classified": True,
            },
            storage_level_history_correlation_packet={
                "storage_correlation_classified": True,
                "storage_level_thread_history_proven": False,
                "bounded_selected_session_target_correlation_proven": True,
                "same_nonce_target_binding_proven": True,
            },
            keychain_packet={"status": "ok"},
        )
        blocked_packet = build_r3_thread_history_preservation_packet(
            profile_state_packet={"profile_state_preserved": True},
            owner_visible_thread_continuity_packet={
                "same_nonce_thread_visible": False,
                "owner_visible_thread_continuity_classified": False,
            },
            storage_level_history_correlation_packet={
                "storage_correlation_classified": False,
                "storage_level_thread_history_proven": False,
                "bounded_selected_session_target_correlation_proven": False,
                "same_nonce_target_binding_proven": False,
            },
            keychain_packet={"status": "ok"},
        )

        self.assertEqual(with_limits_packet["status"], "ok")
        self.assertTrue(with_limits_packet["thread_history_preservation_candidate"])
        self.assertFalse(with_limits_packet["thread_history_preserved"])
        self.assertTrue(with_limits_packet["thread_history_preserved_with_limits"])
        self.assertEqual(with_limits_packet["reason_class"], "")
        self.assertFalse(with_limits_packet["storage_level_thread_history_proven"])
        self.assertEqual(
            with_limits_packet["thread_history_limit_class"],
            "SAME_NONCE_STORAGE_BINDING_UNPROVEN",
        )
        self.assertFalse(with_limits_packet["durable_restoration_proven"])
        self.assertEqual(full_packet["status"], "ok")
        self.assertTrue(full_packet["thread_history_preserved"])
        self.assertFalse(full_packet["thread_history_preserved_with_limits"])
        self.assertTrue(full_packet["storage_level_thread_history_proven"])
        self.assertEqual(blocked_packet["status"], "blocked")
        self.assertFalse(blocked_packet["thread_history_preserved"])
        self.assertEqual(
            blocked_packet["reason_class"],
            "SAME_NONCE_THREAD_NOT_VISIBLE",
        )

    def test_r3_false_green_audit_blocks_widened_claims(self) -> None:
        audit = build_r3_false_green_audit(
            owner_visible_thread_continuity_packet={
                "owner_visible_thread_counts_as_storage_proof": True,
            },
            storage_level_history_correlation_packet={
                "storage_level_thread_history_proven": False,
                "durable_restoration_proven": False,
                "target_delta_counts_as_thread_identity_proof": False,
            },
            thread_history_preservation_packet={
                "thread_history_preserved": True,
                "thread_history_preserved_with_limits": True,
                "storage_level_thread_history_proven": True,
                "storage_level_proof_scope": "selected_session_surface_metadata_plus_same_nonce_visibility",
                "durable_restoration_proven": False,
                "thread_history_limit_class": "",
            },
            legacy_r2_thread_history_packet={"thread_history_preserved": False},
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])

    def test_r3_summary_uses_with_limits_status_when_storage_proof_absent(self) -> None:
        summary = build_r3_summary_packet(
            profile_id="wbp-custom-main",
            profile_root=Path("/tmp/wbp-custom-main"),
            relaunch_packet={"custom_process_observed": True},
            profile_state_packet={"profile_state_preserved": True},
            owner_continuity_packet={"owner_visible_thread_continuity_classified": True},
            storage_correlation_packet={"storage_correlation_classified": True},
            thread_history_packet={
                "thread_history_preservation_candidate": True,
                "thread_history_preserved": False,
                "thread_history_preserved_with_limits": True,
                "storage_level_thread_history_proven": False,
                "durable_restoration_proven": False,
            },
            keychain_packet={"status": "ok"},
            false_green_packet={"status": "ok"},
            legacy_false_green_packet={"status": "ok"},
        )

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(
            summary["final_status"],
            "CUSTOM_CODEX_PERSISTENT_THREAD_HISTORY_CLASSIFIED_WITH_LIMITS",
        )
        self.assertFalse(summary["thread_history_preserved"])
        self.assertTrue(summary["thread_history_preserved_with_limits"])
        self.assertFalse(summary["storage_level_thread_history_proven"])

    def test_r3_summary_reaches_full_success_only_with_storage_level_proof(self) -> None:
        summary = build_r3_summary_packet(
            profile_id="wbp-custom-main",
            profile_root=Path("/tmp/wbp-custom-main"),
            relaunch_packet={"custom_process_observed": True},
            profile_state_packet={"profile_state_preserved": True},
            owner_continuity_packet={"owner_visible_thread_continuity_classified": True},
            storage_correlation_packet={"storage_correlation_classified": True},
            thread_history_packet={
                "thread_history_preservation_candidate": True,
                "thread_history_preserved": True,
                "thread_history_preserved_with_limits": False,
                "storage_level_thread_history_proven": True,
                "durable_restoration_proven": False,
            },
            keychain_packet={"status": "ok"},
            false_green_packet={"status": "ok"},
            legacy_false_green_packet={"status": "ok"},
        )

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(
            summary["final_status"],
            "CUSTOM_CODEX_THREAD_HISTORY_PRESERVED_ACROSS_RELAUNCH",
        )
        self.assertTrue(summary["thread_history_preserved"])
        self.assertTrue(summary["storage_level_thread_history_proven"])
        self.assertFalse(summary["durable_restoration_proven"])

    def test_parser_exposes_same_nonce_visibility_separately_from_legacy_prior_thread_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--execution-mode",
                "relaunch-classify",
                "--owner-visible-prior-thread",
                "true",
                "--same-nonce-thread-visible",
                "false",
            ]
        )

        self.assertEqual(args.owner_visible_prior_thread, "true")
        self.assertEqual(args.same_nonce_thread_visible, "false")
