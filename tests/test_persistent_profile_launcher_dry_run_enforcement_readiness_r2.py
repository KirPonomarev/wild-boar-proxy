# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from tools.persistent_profile_launcher_dry_run_enforcement_readiness_r2_probe import (
    PARENT_STATUS,
    TARGET_STATUS,
    build_false_green_audit,
    build_independent_audit_packet,
    build_readiness_packets,
    build_summary_packet,
)
from wild_boar_proxy.persistent_launcher_dry_run import (
    default_persistent_launcher_dry_run_config,
    dry_run_rejection_matrix,
    render_persistent_launcher_dry_run_command,
    validate_persistent_launcher_dry_run_config,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class PersistentProfileLauncherDryRunEnforcementReadinessR2Tests(unittest.TestCase):
    def test_validator_accepts_default_persistent_config_without_live_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = default_persistent_launcher_dry_run_config(base_dir=Path(tmp))
            validation = validate_persistent_launcher_dry_run_config(config)

        self.assertEqual(validation["status"], "ok")
        self.assertEqual(validation["failed_checks"], [])
        self.assertEqual(validation["profile_mode"], "persistent_custom")
        self.assertEqual(validation["persistent_profile_id"], "wbp-custom-main")
        self.assertTrue(validation["runtime_tmp_dir_under_tmp_root"])
        self.assertLess(validation["runtime_tmp_socket_candidate_length"], 104)
        self.assertFalse(validation["config_validation_is_live_runtime_enforcement"])
        self.assertFalse(validation["dry_run_rejection_is_live_rejection_proof"])
        self.assertFalse(validation["profile_path_existence_checked"])
        self.assertFalse(validation["profile_path_existence_counts_as_storage_proof"])
        self.assertFalse(validation["lock_policy_rendered_counts_as_lock_acquired"])

    def test_dry_run_command_renders_without_execution_or_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = default_persistent_launcher_dry_run_config(base_dir=Path(tmp))
            command = render_persistent_launcher_dry_run_command(config)

        self.assertEqual(command["argv"][0], "open")
        self.assertEqual(command["argv"][2], "/Applications/ChatGPT.app")
        self.assertIn("--user-data-dir", command["argv"])
        self.assertEqual(command["env"]["WBP_PROFILE_MODE"], "persistent_custom")
        self.assertEqual(command["env"]["WBP_PERSISTENT_PROFILE_ID"], "wbp-custom-main")
        self.assertEqual(command["env"]["WBP_RUNTIME_TMPDIR"], command["env"]["TMPDIR"])
        self.assertIn("/tmp/wbp-cdx-wbp-custom-main", command["env"]["TMPDIR"])
        self.assertTrue(command["dry_run_only"])
        self.assertFalse(command["command_executed"])
        self.assertFalse(command["native_launch_attempted"])
        self.assertFalse(command["custom_app_launch_attempted"])

    def test_validator_rejects_profile_mode_id_and_path_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = default_persistent_launcher_dry_run_config(base_dir=Path(tmp))
            mode = validate_persistent_launcher_dry_run_config(
                replace(config, profile_mode="ephemeral_custom")
            )
            missing_id = validate_persistent_launcher_dry_run_config(
                replace(config, persistent_profile_id="")
            )
            invalid_id = validate_persistent_launcher_dry_run_config(
                replace(config, persistent_profile_id="../original")
            )
            browser = validate_persistent_launcher_dry_run_config(
                replace(config, browser_client_path_authority=True)
            )
            remote = validate_persistent_launcher_dry_run_config(
                replace(config, remote_client_path_authority=True)
            )
            provider = validate_persistent_launcher_dry_run_config(
                replace(config, client_model_provider_authority=True)
            )

        self.assertIn("profile_mode_must_be_persistent_custom", mode["failed_checks"])
        self.assertIn("persistent_profile_id_invalid", missing_id["failed_checks"])
        self.assertIn("persistent_profile_id_invalid", invalid_id["failed_checks"])
        self.assertIn("browser_client_path_authority_forbidden", browser["failed_checks"])
        self.assertIn("remote_client_path_authority_forbidden", remote["failed_checks"])
        self.assertIn("client_model_provider_authority_forbidden", provider["failed_checks"])

    def test_validator_rejects_fallback_original_write_live_and_lock_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = default_persistent_launcher_dry_run_config(base_dir=Path(tmp))
            fallback = validate_persistent_launcher_dry_run_config(
                replace(config, silent_fallback_to_ephemeral_allowed=True)
            )
            original = validate_persistent_launcher_dry_run_config(
                replace(config, original_codex_profile_dependency=True)
            )
            mutation = validate_persistent_launcher_dry_run_config(
                replace(config, original_codex_profile_mutation_allowed=True)
            )
            write = validate_persistent_launcher_dry_run_config(
                replace(config, persistent_profile_state_write_allowed=True)
            )
            live = validate_persistent_launcher_dry_run_config(
                replace(config, live_execution_allowed=True)
            )
            lock = validate_persistent_launcher_dry_run_config(
                replace(config, lock_policy="concurrent_same_profile_classified")
            )

        self.assertIn(
            "silent_persistent_to_ephemeral_fallback_forbidden", fallback["failed_checks"]
        )
        self.assertIn("original_codex_profile_dependency_forbidden", original["failed_checks"])
        self.assertIn("original_codex_profile_mutation_forbidden", mutation["failed_checks"])
        self.assertIn(
            "persistent_profile_state_write_forbidden_in_dry_run", write["failed_checks"]
        )
        self.assertIn("live_execution_forbidden_in_dry_run", live["failed_checks"])
        self.assertIn("lock_policy_must_be_single_writer_only", lock["failed_checks"])

    def test_validator_rejects_runtime_tmp_outside_tmp_root_or_with_long_socket_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = default_persistent_launcher_dry_run_config(base_dir=Path(tmp))
            outside = validate_persistent_launcher_dry_run_config(
                replace(config, runtime_tmp_dir=Path("/Users/example/not-tmp"))
            )
            too_long = validate_persistent_launcher_dry_run_config(
                replace(
                    config,
                    runtime_tmp_dir=Path("/tmp") / ("w" * 120),
                )
            )

        self.assertIn("runtime_tmp_dir_must_be_under_tmp_root", outside["failed_checks"])
        self.assertIn("runtime_tmp_dir_socket_path_too_long", too_long["failed_checks"])

    def test_rejection_matrix_is_dry_run_only_and_covers_expected_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = default_persistent_launcher_dry_run_config(base_dir=Path(tmp))
            matrix = dry_run_rejection_matrix(config)

        self.assertEqual(len(matrix), 8)
        for case in matrix:
            self.assertEqual(case["status"], "blocked")
            self.assertTrue(case["expected_failure_present"])
            self.assertTrue(case["dry_run_rejection_only"])
            self.assertFalse(case["live_rejection_proven"])

    def test_packets_close_r2_only_and_keep_parent_open(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        summary = packets["persistent_launcher_enforcement_summary_packet.json"]

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
        self.assertFalse(summary["command_executed"])
        self.assertFalse(summary["persistent_profile_state_written"])
        self.assertFalse(summary["cleanup_executed"])
        self.assertFalse(summary["backup_export_executed"])
        self.assertFalse(summary["lock_acquired"])
        self.assertFalse(summary["live_enforcement_proven"])
        self.assertFalse(summary["thread_history_preservation_claimed"])
        self.assertFalse(summary["profile_storage_persistence_claimed"])
        self.assertFalse(summary["native_ux_claimed"])
        self.assertFalse(summary["keychain_behavior_classified"])
        self.assertFalse(summary["final_e2e_claimed"])

    def test_packet_deliverables_validate_expected_dry_run_rejections(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        mode = packets["persistent_profile_mode_validation_packet.json"]
        profile_id = packets["persistent_profile_id_validation_packet.json"]
        authority = packets["persistent_path_authority_enforcement_packet.json"]
        fallback = packets["persistent_no_silent_fallback_packet.json"]
        original = packets["persistent_original_profile_guard_packet.json"]
        lock = packets["persistent_lock_policy_dry_run_packet.json"]
        cleanup_backup = packets["persistent_cleanup_backup_policy_guard_packet.json"]
        live = packets["persistent_launcher_live_enforcement_non_claim_packet.json"]

        self.assertEqual(mode["status"], "ok")
        self.assertTrue(mode["expected_failure_present"])
        self.assertEqual(profile_id["status"], "ok")
        self.assertTrue(profile_id["missing_id_rejected"])
        self.assertTrue(profile_id["traversal_id_rejected"])
        self.assertTrue(authority["browser_client_path_authority_rejected"])
        self.assertTrue(authority["remote_client_path_authority_rejected"])
        self.assertTrue(authority["client_model_provider_authority_rejected"])
        self.assertTrue(fallback["fallback_rejected"])
        self.assertTrue(original["dependency_rejected"])
        self.assertTrue(original["mutation_rejected"])
        self.assertTrue(lock["invalid_policy_rejected"])
        self.assertFalse(lock["lock_acquired"])
        self.assertFalse(lock["lock_enforcement_claimed"])
        self.assertTrue(cleanup_backup["cleanup_execution_rejected"])
        self.assertTrue(cleanup_backup["backup_export_execution_rejected"])
        self.assertTrue(live["live_execution_rejected"])
        self.assertFalse(live["live_enforcement_proven"])

    def test_false_green_audit_blocks_overclaims(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        mutated = dict(packets)
        mutated["persistent_launcher_live_enforcement_non_claim_packet.json"] = {
            **mutated["persistent_launcher_live_enforcement_non_claim_packet.json"],
            "live_enforcement_proven": True,
        }
        mutated["persistent_lock_policy_dry_run_packet.json"] = {
            **mutated["persistent_lock_policy_dry_run_packet.json"],
            "lock_acquired": True,
        }
        mutated["persistent_launcher_dry_run_command_packet.json"] = {
            **mutated["persistent_launcher_dry_run_command_packet.json"],
            "command_executed": True,
            "rendered_command": {
                **mutated["persistent_launcher_dry_run_command_packet.json"]["rendered_command"],
                "native_launch_attempted": True,
            },
        }

        audit = build_false_green_audit(mutated)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "persistent_launcher_live_enforcement_non_claim_packet.json.live_enforcement_proven",
            audit["findings"],
        )
        self.assertIn(
            "persistent_lock_policy_dry_run_packet.json.lock_acquired",
            audit["findings"],
        )
        self.assertIn(
            "persistent_launcher_dry_run_command_packet.json.command_executed",
            audit["findings"],
        )
        self.assertIn(
            "persistent_launcher_dry_run_command_packet.json.rendered_command.native_launch_attempted",
            audit["findings"],
        )

    def test_independent_audit_and_summary_block_forbidden_or_missing_packets(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_readiness_packets(REPO_ROOT, Path(tmp))

        mutated = dict(packets)
        mutated["persistent_launcher_dry_run_command_packet.json"] = {
            **mutated["persistent_launcher_dry_run_command_packet.json"],
            "rendered_command": {
                **mutated["persistent_launcher_dry_run_command_packet.json"]["rendered_command"],
                "command_executed": True,
            },
        }
        audit = build_independent_audit_packet(mutated)

        blocked_packets = dict(packets)
        blocked_packets["persistent_launcher_enforcement_false_green_audit.json"] = {
            **blocked_packets["persistent_launcher_enforcement_false_green_audit.json"],
            "status": "blocked",
        }
        blocked_summary = build_summary_packet(blocked_packets)

        missing_packets = dict(packets)
        del missing_packets["persistent_launcher_dry_run_command_packet.json"]
        missing_summary = build_summary_packet(missing_packets)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn(
            "persistent_launcher_dry_run_command_packet.json.rendered_command.command_executed",
            audit["forbidden_true_fields"],
        )
        self.assertEqual(blocked_summary["status"], "blocked")
        self.assertIn(
            "persistent_launcher_enforcement_false_green_audit.json",
            blocked_summary["blocked_packets"],
        )
        self.assertEqual(missing_summary["status"], "blocked")
        self.assertIn(
            "persistent_launcher_dry_run_command_packet.json",
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
        self.assertEqual(secret["secret_marker_findings"], [])
        self.assertEqual(secret["prompt_marker_findings"], [])


if __name__ == "__main__":
    unittest.main()
