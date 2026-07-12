# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import tools.persistent_custom_profile_history_r2b_probe as persistent_r2b_probe
import wild_boar_proxy.native_filesystem_probe as native_fs_probe
from wild_boar_proxy.runtime import repo_managed_default_launcher_recognized
from wild_boar_proxy.native_filesystem_probe import (
    build_provider_config,
    build_allowed_claims_matrix,
    build_external_detached_command_admission_packet,
    build_external_detached_handoff_allowed_claims_matrix,
    build_external_detached_handoff_command_packet,
    build_external_detached_handoff_false_green_audit,
    build_external_detached_import_contract_packet,
    build_external_detached_operator_boundary_packet,
    build_external_evidence_presence_packet,
    build_external_execution_command_verification_packet,
    build_external_execution_false_green_audit,
    build_external_execution_result_packet,
    build_external_execution_scope_boundary_packet,
    build_external_execution_secret_scan_packet,
    build_external_execution_observation_packet,
    build_external_result_command_integrity_packet,
    build_external_result_execution_ownership_packet,
    build_external_result_import_packet,
    build_external_result_secret_scan_packet,
    build_import_allowed_claims_matrix,
    build_keychain_boundary_packet,
    build_layer_separation_packet,
    build_cleanup_reversibility_plan_packet,
    build_cleanup_authority_limit_packet,
    build_current_codex_protection_packet,
    build_custom_launch_environment_packet,
    build_custom_profile_ownership_packet,
    build_custom_profile_write_inventory_packet,
    build_custom_user_data_dir_ownership_packet,
    build_custom_native_launch_safety_packet,
    build_incidental_routing_observation_packet,
    build_native_safety_layer_boundary_packet,
    build_native_safety_false_green_audit,
    build_native_custom_safety_claims_packet,
    build_native_safety_refresh_false_green_audit,
    build_native_safety_execution_mode_decision_packet,
    build_native_safety_isolated_path_packet,
    build_native_cleanup_rollback_expectation_packet,
    build_native_safety_reference_packet,
    build_native_integrity_packet,
    build_native_custom_admission_packet,
    build_native_safety_admission_false_green_audit,
    build_no_ambient_authority_safety_packet,
    build_native_safety_import_false_green_audit,
    build_no_launch_from_current_thread_packet,
    build_current_thread_boundary_packet,
    build_external_execution_minimal_json_packet,
    build_no_safety_interpretation_packet,
    build_owner_command_reverification_packet,
    build_owner_cleanup_perception_packet,
    build_owner_execution_attestation_packet,
    build_owner_execution_false_green_audit,
    build_owner_execution_layer_separation_packet,
    build_owner_execution_observation_packet,
    build_owner_historical_observation_import_packet,
    build_owner_handoff_instruction_packet,
    build_machine_ui_waiver_packet,
    build_native_owner_ux_false_green_audit,
    build_native_direct_egress_capability_packet,
    build_native_direct_egress_claim_packet,
    build_native_direct_egress_false_green_audit,
    build_bounded_observation_window_packet,
    build_custom_process_binding_packet,
    build_detached_egress_command_admission_packet,
    build_detached_egress_command_hash_packet,
    build_detached_egress_execution_command_packet,
    build_detached_egress_external_evidence_import_packet,
    build_detached_egress_command_hash_verification_packet,
    build_detached_egress_future_result_import_contract_packet,
    build_detached_egress_future_result_required_packets_packet,
    build_detached_egress_handoff_false_green_audit,
    build_detached_egress_handoff_prerequisite_packet,
    build_detached_egress_import_false_green_audit,
    build_detached_egress_import_secret_scan_packet,
    build_detached_egress_network_claim_classification_packet,
    build_detached_egress_network_observation_validation_packet,
    build_detached_egress_owner_action_boundary_packet,
    build_detached_egress_process_binding_validation_packet,
    build_detached_egress_quiescent_requirement_packet,
    build_detached_egress_safety_admission_prerequisite_packet,
    build_detached_egress_wbp_trace_validation_packet,
    build_domain_attribution_limit_packet,
    build_owner_visible_response_context_packet,
    build_temp_custom_cleanup_packet,
    build_persistent_backup_rollback_packet,
    build_persistent_cleanup_policy_packet,
    build_persistent_concurrent_launch_policy_packet,
    build_persistent_custom_profile_contract_packet,
    build_persistent_custom_profile_identity_packet,
    build_persistent_launcher_selection_packet,
    build_persistent_profile_false_green_audit,
    build_persistent_profile_state_preservation_packet,
    build_persistent_profile_state_diff_packet,
    build_persistent_thread_history_preservation_r2_packet,
    build_thread_history_preservation_packet,
    build_owner_visible_thread_context_packet,
    build_integration_ownership_baseline_packet,
    build_original_codex_profile_drift_packet,
    build_original_codex_protected_surface_scope_packet,
    build_bounded_process_egress_false_green_audit,
    build_native_route_trace_binding_packet,
    build_owner_manual_ux_check_packet,
    build_owner_nonce_prompt_packet,
    build_owner_ux_readiness_false_green_audit,
    build_owner_ux_readiness_packet,
    build_owner_ux_action_boundary_packet,
    build_owner_ux_historical_false_green_audit,
    build_owner_ux_layer_boundary_packet,
    build_owner_action_boundary_packet,
    build_owner_visible_response_observation_packet,
    build_provider_marker_observation_limit_packet,
    build_cleanup_perception_limit_packet,
    build_historical_or_incidental_route_context_packet,
    build_owner_external_execution_result_packet,
    build_owner_execution_boundary_packet,
    build_protected_surface_import_summary,
    build_protected_surface_read_classification_packet,
    build_quiescent_retry_blocker_packet,
    build_quiescent_retry_launch_admission_packet,
    build_two_lane_result_matrix,
    build_screenshot_limit_packet,
    build_historical_routing_trace_reference_packet,
    build_current_background_codex_noise_packet,
    build_egress_prior_blocker_replay_packet,
    build_historical_route_context_packet,
    build_native_egress_observer_false_green_audit,
    build_native_egress_observer_readiness_packet,
    build_wbp_endpoint_observation_limit_packet,
    build_process_attribution_limit_packet,
    build_absence_claim_limit_packet,
    build_owner_egress_handoff_instruction_packet,
    build_historical_route_context_reference_packet,
    build_egress_readiness_false_green_audit,
    build_wbp_trace_observation_packet,
    build_network_claim_limits_packet,
    build_network_observer_feasibility_decision_packet,
    build_quiescent_network_precondition_packet,
    build_original_auth_boundary_packet,
    build_original_live_last_chance_dry_run_packet,
    build_original_live_admissibility_decision_packet,
    build_original_process_window_state_packet,
    build_original_profile_inventory_packet,
    build_original_readiness_false_green_audit,
    build_original_readiness_reference_packet,
    build_original_rollback_feasibility_packet,
    build_original_live_false_green_audit,
    build_original_live_owner_authorization_packet,
    build_original_live_rollback_point_packet,
    build_original_live_restore_verification_packet,
    build_original_live_restore_failure_lockdown_packet,
    build_original_live_summary_packet,
    build_original_live_temporary_route_apply_admission_packet,
    build_original_live_temporary_config_candidate_packet,
    build_original_live_trace_timeout_policy_packet,
    build_original_surface_read_classification_packet,
    build_original_temporary_route_strategy_packet,
    build_original_via_wbp_claim_limits_packet,
    build_provider_auth_strategy_reference_packet,
    build_selected_model_trace_claim_packet,
    clean_env,
    classify_native_safety_retry_import,
    classify_environment_blocked_result,
    classify_external_detached_context_outcome,
    classify_host_context,
    classify_protected_codex_host_negative,
    classify_fresh_context_acquisition,
    classify_fresh_context_entry,
    classify_keychain_observation,
    classify_quiescent_handoff_admission,
    classify_quiescent_current_codex_precondition,
    classify_current_codex_delta,
    classify_user_data_dir_respected,
    collect_ambient_env_context,
    diff_scans,
    launch_native_candidate,
    scan_tree,
    summarize_idle_baseline_windows,
    validate_external_evidence_packets,
    validate_native_safety_admission_contour_packets,
)
from wild_boar_proxy.runtime import DETERMINISTIC_RUNTIME_PATH
from tools.persistent_custom_profile_history_r2_probe import (
    classify_r2_persistent_profile_history_packet,
)
from tools.persistent_custom_profile_history_r2b_probe import (
    build_bounded_state_diff_packet,
    build_first_launch_packets as build_r2b_first_launch_packets,
    build_redacted_owner_nonce_prompt_packet,
    build_relaunch_classification_packets as build_r2b_relaunch_classification_packets,
    build_rollback_reference_packet as build_r2b_rollback_reference_packet,
    collect_bounded_profile_manifest,
)
from tools.persistent_custom_profile_r2c_owner_visible_thread_continuity_probe import (
    build_r2c_false_green_audit,
    build_r2c_owner_nonce_prompt_packet,
    build_r2c_owner_relaunch_visibility_packet,
    build_r2c_storage_context_packet,
    build_r2c_thread_continuity_classification_packet,
)
from tools.persistent_custom_profile_storage_truth_r3_probe import (
    build_persistent_relaunch_restoration_source_packet,
    build_persistent_storage_candidate_state_matrix,
    build_persistent_storage_false_green_audit,
    build_persistent_storage_proof_ladder_packet,
    build_persistent_storage_truth_classification_packet,
    classify_r3_storage_state_class,
    collect_persistent_storage_surface_inventory,
)
from tools.persistent_custom_profile_storage_schema_attribution_r4_probe import (
    build_r4_false_green_audit,
    build_restoration_hypothesis_packet,
    build_schema_attribution_matrix,
    classify_candidate_surface_type,
    inspect_json_shapes,
    inspect_sqlite_schema,
    select_candidate_surfaces,
)
from tools.persistent_custom_profile_restoration_correlation_r5_probe import (
    build_r5_correlation_classification_packet,
    build_r5_false_green_audit,
    build_r5_nonce_prompt_packet,
    build_r5_target_delta_packet,
    build_storage_correlation_result_packet,
    build_visibility_result_packet,
    select_r5_hypotheses,
)
from tools.persistent_custom_profile_backup_repair_r1_probe import (
    classify_backup_surface,
)


class NativeFilesystemProbeTests(unittest.TestCase):
    def test_process_inventory_distinguishes_official_chatgpt_custom_instance(self) -> None:
        custom_user_data_dir = (
            "/Users/k/Library/Application Support/WildBoarProxy/"
            "CodexProfiles/wbp-custom-main/electron-user-data"
        )
        default_user_data_dir = "/Users/k/Library/Application Support/Codex"
        completed = subprocess.CompletedProcess(
            args=["ps"],
            returncode=0,
            stdout=(
                " 101 /Applications/ChatGPT.app/Contents/MacOS/ChatGPT\n"
                f" 102 /Applications/ChatGPT.app/Contents/MacOS/ChatGPT --user-data-dir={custom_user_data_dir}\n"
                f" 103 /Applications/ChatGPT.app/Contents/Frameworks/Codex Framework.framework/Helpers/Codex (Renderer) --user-data-dir={custom_user_data_dir}\n"
                f" 104 /Applications/ChatGPT.app/Contents/Frameworks/Codex Framework.framework/Helpers/Codex (Renderer) --user-data-dir={default_user_data_dir}\n"
            ),
            stderr="",
        )
        with mock.patch(
            "wild_boar_proxy.native_filesystem_probe.subprocess.run",
            return_value=completed,
        ):
            inventory = native_fs_probe.collect_codex_process_inventory(
                custom_user_data_dir=custom_user_data_dir,
                default_user_data_dir=default_user_data_dir,
            )

        self.assertEqual(inventory["custom_process_count"], 2)
        self.assertEqual(inventory["default_process_count"], 1)
        self.assertEqual(inventory["root_app_pids"], [101, 102])
        self.assertIn("ChatGPT.app/Contents/MacOS/ChatGPT", inventory["custom_process_lines"][0])

    def test_codex_process_inventory_uses_ps_command_lines_with_spaced_user_data_dir(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["ps"],
            returncode=0,
            stdout=(
                " 101 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/Users/k/Library/Application Support/WildBoarProxy/CodexProfiles/wbp-custom-main/electron-user-data\n"
                " 102 /Applications/Codex.app/Contents/Resources/codex app-server --listen stdio://\n"
                " 104 /Users/k/Applications/Codex WBP Clean.app/Contents/MacOS/Codex --user-data-dir=/Users/k/Library/Application Support/WildBoarProxy/CodexProfiles/wbp-custom-main/electron-user-data\n"
                " 103 /bin/zsh -c unrelated\n"
            ),
            stderr="",
        )
        with mock.patch(
            "wild_boar_proxy.native_filesystem_probe.subprocess.run",
            return_value=completed,
        ) as run:
            lines = native_fs_probe._collect_codex_process_lines()

        self.assertEqual(run.call_args.args[0], ["ps", "axww", "-o", "pid=,command="])
        self.assertEqual(len(lines), 3)
        self.assertIn("wbp-custom-main/electron-user-data", lines[0])

    def test_codex_process_inventory_keeps_helper_user_data_lines(self) -> None:
        custom_user_data_dir = "/Users/k/Library/Application Support/Codex WBP Clean"
        completed = subprocess.CompletedProcess(
            args=["ps"],
            returncode=0,
            stdout=(
                " 101 /Users/k/Applications/Codex WBP Clean.app/Contents/MacOS/Codex\n"
                " 102 /Users/k/Applications/Codex WBP Clean.app/Contents/Resources/codex app-server --analytics-default-enabled\n"
                " 103 /Users/k/Applications/Codex WBP Clean.app/Contents/Frameworks/Codex Framework.framework/Versions/149.0.7827.115/Helpers/Codex (Renderer).app/Contents/MacOS/Codex (Renderer) --type=renderer --user-data-dir=/Users/k/Library/Application Support/Codex WBP Clean\n"
                " 104 /Applications/Codex.app/Contents/MacOS/Codex\n"
            ),
            stderr="",
        )
        with mock.patch(
            "wild_boar_proxy.native_filesystem_probe.subprocess.run",
            return_value=completed,
        ):
            inventory = native_fs_probe.collect_codex_process_inventory(
                custom_user_data_dir=custom_user_data_dir,
            )

        self.assertEqual(inventory["line_count"], 4)
        self.assertEqual(inventory["custom_process_count"], 2)
        self.assertEqual(inventory["default_process_count"], 0)
        self.assertTrue(
            any("--user-data-dir=" in line for line in inventory["custom_process_lines"])
        )
        self.assertTrue(
            any(
                "Codex WBP Clean.app/Contents/MacOS/Codex" in line
                for line in inventory["custom_process_lines"]
            )
        )

    def test_codex_process_inventory_accepts_installed_custom_app_user_data_alias(self) -> None:
        profile_user_data_dir = (
            "/Users/k/Library/Application Support/WildBoarProxy/"
            "CodexProfiles/wbp-custom-main/electron-user-data"
        )
        installed_user_data_dir = native_fs_probe.DEFAULT_CUSTOM_APP_COPY_USER_DATA_DIR
        completed = subprocess.CompletedProcess(
            args=["ps"],
            returncode=0,
            stdout=(
                f" 101 /Users/k/Applications/Codex WBP Clean.app/Contents/MacOS/Codex --user-data-dir={installed_user_data_dir}\n"
                " 102 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/Users/k/Library/Application Support/Codex\n"
            ),
            stderr="",
        )
        with mock.patch(
            "wild_boar_proxy.native_filesystem_probe.subprocess.run",
            return_value=completed,
        ):
            inventory = native_fs_probe.collect_codex_process_inventory(
                custom_user_data_dir=profile_user_data_dir,
                default_user_data_dir="/Users/k/Library/Application Support/Codex",
            )

        self.assertEqual(inventory["custom_process_count"], 1)
        self.assertEqual(inventory["default_process_count"], 1)
        self.assertIn("Codex WBP Clean", inventory["custom_process_lines"][0])

    def test_remove_tree_with_retry_unlinks_runtime_tmp_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            target = temp_root / "target"
            target.mkdir()
            link = temp_root / "runtime-bind"
            link.symlink_to(target, target_is_directory=True)

            error = native_fs_probe.remove_tree_with_retry(link)

            self.assertEqual(error, "")
            self.assertFalse(link.exists())
            self.assertTrue(target.exists())

    def test_provider_config_uses_auth_command_when_cli_proxy_key_is_absent(self) -> None:
        with mock.patch(
            "wild_boar_proxy.native_filesystem_probe._cli_proxy_api_key",
            return_value="",
        ):
            config = build_provider_config(
                endpoint="http://127.0.0.1:8318/v1",
                model="gpt-5.4-mini",
                auth_command_path=Path("/repo/wbp_codex_auth_command.py"),
            )

        self.assertIn("[model_providers.wbp.auth]", config)
        self.assertIn('command = "/repo/wbp_codex_auth_command.py"', config)
        self.assertIn('wire_api = "responses"', config)
        self.assertIn('sandbox_mode = "workspace-write"', config)
        self.assertIn("requires_openai_auth = false", config)
        self.assertNotIn("experimental_bearer_token", config)

    def test_provider_config_prefers_auth_command_when_cli_proxy_key_exists(self) -> None:
        with mock.patch(
            "wild_boar_proxy.native_filesystem_probe._cli_proxy_api_key",
            return_value="fixture-token",
        ):
            config = build_provider_config(
                endpoint="http://127.0.0.1:8318/v1",
                model="gpt-5.4-mini",
                auth_command_path=Path("/repo/wbp_codex_auth_command.py"),
            )

        self.assertIn("[model_providers.wbp.auth]", config)
        self.assertIn('command = "/repo/wbp_codex_auth_command.py"', config)
        self.assertNotIn("experimental_bearer_token", config)
        self.assertNotIn("fixture-token", config)
        self.assertIn('wire_api = "responses"', config)
        self.assertIn('sandbox_mode = "workspace-write"', config)

    def test_provider_config_never_embeds_explicit_local_token(self) -> None:
        with mock.patch(
            "wild_boar_proxy.native_filesystem_probe._cli_proxy_api_key",
            return_value="stale-cli-token",
        ):
            config = build_provider_config(
                endpoint="http://127.0.0.1:8318/v1",
                model="gpt-5.4-mini",
                auth_command_path=Path("/repo/wbp_codex_auth_command.py"),
                local_token="fresh-local-token",
            )

        self.assertIn("[model_providers.wbp.auth]", config)
        self.assertIn('command = "/repo/wbp_codex_auth_command.py"', config)
        self.assertNotIn("experimental_bearer_token", config)
        self.assertNotIn("fresh-local-token", config)
        self.assertNotIn("stale-cli-token", config)

    def test_provider_config_rejects_unadmitted_sandbox_mode(self) -> None:
        with self.assertRaises(ValueError):
            build_provider_config(
                endpoint="http://127.0.0.1:8318/v1",
                model="gpt-5.4-mini",
                auth_command_path=Path("/repo/wbp_codex_auth_command.py"),
                sandbox_mode="danger-full-access",
            )

    def test_recursive_scan_and_diff_report_created_deleted_and_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            before_root = root / "before"
            after_root = root / "after"
            (before_root / "dir").mkdir(parents=True)
            (after_root / "dir").mkdir(parents=True)
            (before_root / "same.txt").write_text("same\n", encoding="utf-8")
            (after_root / "same.txt").write_text("same\n", encoding="utf-8")
            (before_root / "dir" / "changed.txt").write_text("old\n", encoding="utf-8")
            (after_root / "dir" / "changed.txt").write_text("new\n", encoding="utf-8")
            (before_root / "deleted.txt").write_text("gone\n", encoding="utf-8")
            (after_root / "created.txt").write_text("fresh\n", encoding="utf-8")

            diff = diff_scans(scan_tree(before_root), scan_tree(after_root))

        self.assertIn("created.txt", diff["created"])
        self.assertIn("deleted.txt", diff["deleted"])
        changed_paths = {entry["relative_path"] for entry in diff["changed"]}
        self.assertIn("dir/changed.txt", changed_paths)

    def test_recursive_scan_tolerates_transient_missing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            victim = root / "vanishes.txt"
            victim.write_text("short lived\n", encoding="utf-8")
            real_stat = Path.stat

            def flaky_stat(path: Path, *args: object, **kwargs: object) -> os.stat_result:
                if path == victim:
                    victim.unlink(missing_ok=True)
                    raise FileNotFoundError(str(path))
                return real_stat(path, *args, **kwargs)

            with mock.patch.object(Path, "stat", flaky_stat):
                packet = scan_tree(root)

        entries = {
            entry["relative_path"]: entry for entry in packet.get("entries", [])
        }
        self.assertEqual(
            entries["vanishes.txt"]["kind"],
            "transient_missing_during_scan",
        )

    def test_user_data_dir_respected_requires_owned_writes_and_unchanged_defaults(self) -> None:
        blocked = classify_user_data_dir_respected(
            custom_process_observed=True,
            owned_writes_present=False,
            protected_surfaces_changed=False,
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["reason_class"], "WRITE_ATTRIBUTION_AMBIGUOUS")
        self.assertFalse(blocked["user_data_dir_respected"])

        ok = classify_user_data_dir_respected(
            custom_process_observed=True,
            owned_writes_present=True,
            protected_surfaces_changed=False,
        )
        self.assertEqual(ok["status"], "ok")
        self.assertTrue(ok["user_data_dir_respected"])

    def test_default_surface_change_blocks_even_with_owned_writes(self) -> None:
        blocked = classify_user_data_dir_respected(
            custom_process_observed=True,
            owned_writes_present=True,
            protected_surfaces_changed=True,
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["reason_class"], "DEFAULT_PROTECTED_SURFACES_CHANGED")
        self.assertFalse(blocked["user_data_dir_respected"])

    def test_protected_surface_read_is_inspection_only_not_runtime_dependency(self) -> None:
        packet = build_protected_surface_read_classification_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["inspection_only"])
        self.assertTrue(packet["filesystem_read_performed"])
        self.assertFalse(packet["filesystem_write_performed"])
        self.assertFalse(packet["runtime_auth_input_used"])
        self.assertFalse(packet["runtime_provider_authority_used"])
        self.assertFalse(packet["current_auth_json_execution_dependency"])
        self.assertGreaterEqual(len(packet["snapshot_targets"]), 4)

    def test_original_surface_read_is_inspection_only(self) -> None:
        packet = build_original_surface_read_classification_packet(
            codex_home=Path("/tmp/original-codex-home"),
            app_support_dir=Path("/tmp/original-app-support"),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["inspection_only"])
        self.assertTrue(packet["filesystem_read_performed"])
        self.assertFalse(packet["filesystem_write_performed"])
        self.assertFalse(packet["runtime_auth_input_used"])
        self.assertFalse(packet["runtime_provider_authority_used"])
        self.assertFalse(packet["current_auth_json_execution_dependency"])
        self.assertFalse(packet["auth_json_token_value_read"])
        self.assertFalse(packet["auth_json_parsed"])
        self.assertFalse(packet["auth_json_copied"])

    def test_original_readiness_does_not_use_current_auth_json_as_runtime_input(self) -> None:
        inventory = build_original_profile_inventory_packet(
            codex_home=Path("/tmp/original-codex-home"),
            app_support_dir=Path("/tmp/original-app-support"),
        )
        auth = build_original_auth_boundary_packet(profile_inventory_packet=inventory)

        self.assertEqual(auth["status"], "ok")
        self.assertFalse(auth["auth_json_token_value_read"])
        self.assertFalse(auth["auth_json_parsed"])
        self.assertFalse(auth["auth_json_copied"])
        self.assertFalse(auth["auth_json_used_as_runtime_input"])
        self.assertFalse(auth["file_auth_used"])
        self.assertFalse(auth["proxy_auth_equated_to_file_auth"])

    def test_original_temporary_route_strategy_requires_exact_target_and_hash_plan(self) -> None:
        inventory = {
            "config_toml": {
                "path": "/tmp/not-original-config.toml",
                "state": "present",
                "sha256": "a" * 64,
            }
        }
        blocked = build_original_temporary_route_strategy_packet(
            profile_inventory_packet=inventory,
        )
        ok = build_original_temporary_route_strategy_packet(
            profile_inventory_packet={
                "config_toml": {
                    "path": "/Users/test/.codex/config.toml",
                    "state": "present",
                    "sha256": "b" * 64,
                }
            },
        )

        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("exact_original_config_target_required", blocked["failed_checks"])
        self.assertEqual(ok["status"], "ok")
        self.assertTrue(ok["before_hash_or_absent_state_recorded"])
        self.assertTrue(ok["expected_diff_shape_declared"])
        self.assertFalse(ok["route_proven"])

    def test_original_temporary_route_strategy_requires_rollback_plan(self) -> None:
        strategy = build_original_temporary_route_strategy_packet(
            profile_inventory_packet={
                "config_toml": {
                    "path": "/Users/test/.codex/config.toml",
                    "state": "absent",
                }
            },
        )
        rollback = build_original_rollback_feasibility_packet(
            temporary_route_strategy_packet=strategy,
        )

        self.assertEqual(strategy["status"], "ok")
        self.assertTrue(strategy["restore_command_declared"])
        self.assertTrue(strategy["rollback_trigger_declared"])
        self.assertEqual(rollback["status"], "ok")
        self.assertFalse(rollback["rollback_executed"])
        self.assertFalse(rollback["normal_original_post_cleanup_proven"])

    def test_original_readiness_does_not_claim_original_route(self) -> None:
        inventory = build_original_profile_inventory_packet(
            codex_home=Path("/tmp/original-codex-home"),
            app_support_dir=Path("/tmp/original-app-support"),
            config_path=Path("/Users/test/.codex/config.toml"),
        )
        strategy = build_original_temporary_route_strategy_packet(
            profile_inventory_packet=inventory,
        )
        rollback = build_original_rollback_feasibility_packet(
            temporary_route_strategy_packet=strategy,
        )
        decision = build_original_live_admissibility_decision_packet(
            surface_read_packet=build_original_surface_read_classification_packet(),
            profile_inventory_packet=inventory,
            auth_boundary_packet=build_original_auth_boundary_packet(
                profile_inventory_packet=inventory
            ),
            process_window_state_packet=build_original_process_window_state_packet(
                process_inventory_packet={"line_count": 0}
            ),
            temporary_route_strategy_packet=strategy,
            rollback_feasibility_packet=rollback,
            claim_limits_packet=build_original_via_wbp_claim_limits_packet(),
        )

        self.assertEqual(decision["status"], "ok")
        self.assertTrue(decision["future_live_original_admissible_with_owner_authorization"])
        self.assertFalse(decision["native_original_launch_attempted"])
        self.assertFalse(decision["original_profile_write_performed"])
        self.assertFalse(decision["original_route_proven"])
        self.assertFalse(decision["final_e2e_proven"])

    def test_original_readiness_does_not_claim_rollback_execution(self) -> None:
        limits = build_original_via_wbp_claim_limits_packet()

        self.assertEqual(limits["status"], "ok")
        self.assertFalse(limits["rollback_executed"])
        self.assertFalse(limits["original_route_proven"])
        self.assertFalse(limits["final_e2e_proven"])

    def test_original_process_window_inventory_not_ux_proof(self) -> None:
        packet = build_original_process_window_state_packet(
            process_inventory_packet={
                "line_count": 2,
                "default_process_count": 1,
                "root_app_pids": [123],
            }
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["process_inventory_only"])
        self.assertFalse(packet["native_window_ux_proven"])
        self.assertFalse(packet["owner_visible_response_proven"])
        self.assertFalse(packet["native_original_launch_attempted"])
        self.assertFalse(packet["original_process_killed_or_mutated"])

    def test_custom_native_proof_cannot_satisfy_original_claim(self) -> None:
        audit = build_original_readiness_false_green_audit(
            live_admissibility_decision_packet={
                "native_original_launch_attempted": False,
                "original_route_proven": False,
                "rollback_executed": False,
                "original_ux_proven": False,
                "egress_blocked_counted_as_pass": False,
            },
            claim_limits_packet={
                "original_route_proven": False,
                "final_e2e_proven": False,
            },
            custom_native_proof_used_as_original_proof=True,
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])

    def test_auth_model_history_cannot_satisfy_original_claim(self) -> None:
        audit = build_original_readiness_false_green_audit(
            live_admissibility_decision_packet={
                "native_original_launch_attempted": False,
                "original_route_proven": False,
                "rollback_executed": False,
                "original_ux_proven": False,
                "egress_blocked_counted_as_pass": False,
            },
            claim_limits_packet={
                "original_route_proven": False,
                "final_e2e_proven": False,
            },
            auth_model_history_used_as_original_proof=True,
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])

    def test_egress_blocked_not_counted_as_original_readiness_pass(self) -> None:
        audit = build_original_readiness_false_green_audit(
            live_admissibility_decision_packet={
                "native_original_launch_attempted": False,
                "original_route_proven": False,
                "rollback_executed": False,
                "original_ux_proven": False,
                "egress_blocked_counted_as_pass": True,
            },
            claim_limits_packet={
                "original_route_proven": False,
                "final_e2e_proven": False,
            },
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])

    def test_original_live_requires_owner_authorization(self) -> None:
        packet = build_original_live_owner_authorization_packet(
            owner_authorized=False,
            exact_target_path="/Users/test/.codex/config.toml",
            allowed_write_operation="temporary_wbp_route_config_replace",
            rollback_mode="restore_prior_bytes",
            launch_permission=True,
            owner_prompt_permission=True,
            restore_permission=True,
            expected_target_path=Path("/Users/test/.codex/config.toml"),
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "NO_OWNER_AUTHORIZATION")
        self.assertIn("owner_authorization_missing", packet["failed_checks"])
        self.assertFalse(packet["original_profile_write_allowed"])
        self.assertFalse(packet["native_original_launch_allowed"])

    def test_original_live_rejects_broad_owner_authorization(self) -> None:
        packet = build_original_live_owner_authorization_packet(
            owner_authorized=True,
            exact_target_path="/Users/test/.codex",
            allowed_write_operation="do_whatever_is_needed",
            rollback_mode="best_effort",
            launch_permission=True,
            owner_prompt_permission=True,
            restore_permission=True,
            expected_target_path=Path("/Users/test/.codex/config.toml"),
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "OWNER_AUTHORIZATION_TOO_BROAD")
        self.assertIn("exact_target_path_required", packet["failed_checks"])
        self.assertIn("allowed_write_operation_too_broad", packet["failed_checks"])
        self.assertFalse(packet["broad_authorization_accepted"])

    def test_original_live_requires_before_hash_or_absent_state(self) -> None:
        auth = build_original_live_owner_authorization_packet(
            owner_authorized=True,
            exact_target_path="/Users/test/.codex/config.toml",
            allowed_write_operation="temporary_wbp_route_config_replace",
            rollback_mode="restore_prior_bytes",
            launch_permission=True,
            owner_prompt_permission=True,
            restore_permission=True,
            expected_target_path=Path("/Users/test/.codex/config.toml"),
        )
        rollback = build_original_live_rollback_point_packet(
            profile_before_packet={"config_toml": {"path": "/Users/test/.codex/config.toml"}},
            owner_authorization_packet=auth,
            rollback_point_created=True,
            rollback_point_verified=True,
        )

        self.assertEqual(rollback["status"], "blocked")
        self.assertIn("before_hash_or_absent_state_required", rollback["failed_checks"])

    def test_original_live_requires_rollback_point_before_apply(self) -> None:
        auth = build_original_live_owner_authorization_packet(
            owner_authorized=True,
            exact_target_path="/Users/test/.codex/config.toml",
            allowed_write_operation="temporary_wbp_route_config_replace",
            rollback_mode="restore_prior_bytes",
            launch_permission=True,
            owner_prompt_permission=True,
            restore_permission=True,
            expected_target_path=Path("/Users/test/.codex/config.toml"),
        )
        readiness = build_original_readiness_reference_packet(
            readiness_summary_packet={
                "status": "ok",
                "final_status": "ORIGINAL_CODEX_VIA_WBP_READINESS_CLASSIFIED_LIVE_ADMISSIBLE_WITH_OWNER_AUTHORIZATION",
            },
            source_path="readiness.json",
        )
        rollback = build_original_live_rollback_point_packet(
            profile_before_packet={
                "config_toml": {
                    "path": "/Users/test/.codex/config.toml",
                    "state": "present",
                    "sha256": "a" * 64,
                }
            },
            owner_authorization_packet=auth,
            rollback_point_created=False,
            rollback_point_verified=False,
        )
        admission = build_original_live_temporary_route_apply_admission_packet(
            owner_authorization_packet=auth,
            rollback_point_packet=rollback,
            readiness_reference_packet=readiness,
        )

        self.assertEqual(rollback["status"], "blocked")
        self.assertEqual(admission["status"], "blocked")
        self.assertIn("rollback_point_required_before_apply", admission["failed_checks"])
        self.assertFalse(admission["original_profile_write_performed"])

    def test_original_live_forbids_auth_json_runtime_dependency(self) -> None:
        inventory = build_original_profile_inventory_packet(
            codex_home=Path("/tmp/original-codex-home"),
            app_support_dir=Path("/tmp/original-app-support"),
        )
        auth_boundary = build_original_auth_boundary_packet(
            profile_inventory_packet={
                **inventory,
                "current_auth_json_execution_dependency": True,
            }
        )

        self.assertEqual(auth_boundary["status"], "blocked")
        self.assertIn(
            "current_auth_json_must_not_be_runtime_input",
            auth_boundary["failed_checks"],
        )

    def test_original_live_forbids_file_auth_fallback(self) -> None:
        auth_boundary = build_original_auth_boundary_packet(
            profile_inventory_packet={
                "auth_json": {"exists": True, "sha256": "a" * 64},
                "auth_json_token_value_read": False,
                "auth_json_parsed": False,
                "current_auth_json_execution_dependency": False,
            }
        )

        self.assertEqual(auth_boundary["status"], "ok")
        self.assertFalse(auth_boundary["file_auth_used"])
        self.assertFalse(auth_boundary["proxy_auth_equated_to_file_auth"])

    def test_original_live_route_strategy_not_route_proof(self) -> None:
        summary = build_original_live_summary_packet(
            owner_authorization_packet={
                "status": "ok",
                "failed_checks": [],
            },
            apply_admission_packet={"status": "ok"},
            route_trace_packet={"route_trace_confirmed": False},
            restore_verification_packet={"status": "ok"},
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(
            summary["final_status"],
            "ORIGINAL_CODEX_VIA_WBP_BLOCKED_ROUTE_TRACE_MISSING",
        )
        self.assertFalse(summary["original_route_proven"])

    def test_original_live_requires_wbp_trace_for_route_claim(self) -> None:
        restore = build_original_live_restore_verification_packet(
            rollback_execution_attempted=True,
            restore_verified=True,
            before_state={"sha256": "a" * 64},
            after_state={"sha256": "a" * 64},
        )
        summary = build_original_live_summary_packet(
            owner_authorization_packet={"status": "ok", "failed_checks": []},
            apply_admission_packet={"status": "ok"},
            route_trace_packet={"route_trace_confirmed": True},
            restore_verification_packet=restore,
        )

        self.assertEqual(summary["status"], "ok")
        self.assertTrue(summary["original_route_proven"])
        self.assertFalse(summary["direct_egress_absence_proven"])
        self.assertFalse(summary["final_e2e_proven"])

    def test_original_live_selected_model_claim_is_trace_scoped_only(self) -> None:
        packet = build_selected_model_trace_claim_packet(
            selected_model="gpt-5.4-mini",
            route_trace_confirmed=True,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["allowed_claim"],
            "selected_model_responded_in_this_original_route_trace",
        )
        self.assertFalse(packet["model_availability_claimed"])
        self.assertFalse(packet["model_family_availability_claimed"])

    def test_original_live_requires_restore_verification(self) -> None:
        restore = build_original_live_restore_verification_packet(
            rollback_execution_attempted=True,
            restore_verified=False,
            before_state={"sha256": "a" * 64},
            after_state={"sha256": "b" * 64},
        )

        self.assertEqual(restore["status"], "blocked")
        self.assertFalse(restore["restore_matches_before"])
        self.assertFalse(restore["second_launch_allowed"])

    def test_original_live_restore_failure_blocks_second_launch(self) -> None:
        restore = build_original_live_restore_verification_packet(
            rollback_execution_attempted=True,
            restore_verified=True,
            before_state={"state": "absent"},
            after_state={"state": "present"},
        )

        self.assertEqual(restore["status"], "blocked")
        self.assertFalse(restore["second_launch_allowed"])
        self.assertFalse(restore["normal_original_sanity_allowed"])
        self.assertFalse(restore["second_launch_attempted_after_failed_restore"])

    def test_original_live_retry_mutation_requires_new_authorization(self) -> None:
        auth = build_original_live_owner_authorization_packet(
            owner_authorized=True,
            exact_target_path="/Users/test/.codex/config.toml",
            allowed_write_operation="temporary_wbp_route_config_replace",
            rollback_mode="restore_prior_bytes",
            launch_permission=True,
            owner_prompt_permission=True,
            restore_permission=True,
            expected_target_path=Path("/Users/test/.codex/config.toml"),
        )

        self.assertEqual(auth["status"], "ok")
        self.assertFalse(auth["retry_mutation_authorized"])

    def test_original_live_provider_auth_reference_is_not_reproof(self) -> None:
        packet = build_provider_auth_strategy_reference_packet(
            provider_auth_strategy_packet={
                "status": "ok",
                "selected_strategy": "auth.command",
                "auth_command": {
                    "path": "/repo/wbp_codex_auth_command.py",
                    "server_owned_path": True,
                    "raw_upstream_secret": False,
                },
            },
            source_path="/repo/audit_results/auth/provider_auth_strategy_packet.json",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["auth_strategy_reproved"])
        self.assertFalse(packet["file_auth_fallback_used"])
        self.assertFalse(packet["current_auth_json_runtime_dependency"])

    def test_original_live_forbids_auth_command_edit(self) -> None:
        packet = build_provider_auth_strategy_reference_packet(
            provider_auth_strategy_packet={
                "status": "ok",
                "selected_strategy": "auth.command",
                "auth_command": {
                    "path": "/repo/wbp_codex_auth_command.py",
                    "server_owned_path": True,
                    "raw_upstream_secret": False,
                },
            },
            auth_command_edited=True,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn(
            "auth_command_must_not_be_edited_in_original_live_contour",
            packet["failed_checks"],
        )

    def test_original_live_requires_last_chance_dry_run(self) -> None:
        apply_admission = build_original_live_temporary_route_apply_admission_packet(
            owner_authorization_packet={"status": "ok", "exact_target_path": "/x"},
            rollback_point_packet={"status": "ok"},
            readiness_reference_packet={"status": "ok"},
            last_chance_dry_run_packet={"status": "blocked"},
        )

        self.assertEqual(apply_admission["status"], "blocked")
        self.assertIn(
            "last_chance_dry_run_required_before_apply",
            apply_admission["failed_checks"],
        )
        self.assertFalse(apply_admission["original_profile_write_allowed"])

    def test_original_live_dry_run_candidate_must_match_authorization(self) -> None:
        dry_run = build_original_live_last_chance_dry_run_packet(
            owner_authorization_packet={
                "status": "ok",
                "exact_target_path": "/Users/test/.codex/config.toml",
            },
            rollback_point_packet={"status": "ok"},
            temporary_config_candidate_packet={
                "status": "ok",
                "exact_target_path": "/Users/test/.codex/other.toml",
                "expected_diff_summary": ["set model_provider=wbp"],
                "raw_auth_token_in_candidate": False,
            },
            provider_auth_strategy_reference_packet={"status": "ok"},
        )

        self.assertEqual(dry_run["status"], "blocked")
        self.assertIn(
            "candidate_target_must_match_owner_authorization",
            dry_run["failed_checks"],
        )
        self.assertFalse(dry_run["temporary_route_apply_performed"])

    def test_original_live_temporary_config_candidate_records_hash_not_secret(self) -> None:
        candidate = build_original_live_temporary_config_candidate_packet(
            owner_authorization_packet={
                "status": "ok",
                "exact_target_path": "/Users/test/.codex/config.toml",
            },
            provider_auth_strategy_reference_packet={
                "status": "ok",
                "auth_command_path": "/repo/wbp_codex_auth_command.py",
            },
        )

        self.assertEqual(candidate["status"], "ok")
        self.assertEqual(len(candidate["candidate_sha256"]), 64)
        self.assertFalse(candidate["candidate_text_recorded"])
        self.assertFalse(candidate["raw_auth_token_in_candidate"])
        self.assertTrue(candidate["auth_command_reference_only"])

    def test_original_live_trace_timeout_restores_first(self) -> None:
        packet = build_original_live_trace_timeout_policy_packet(
            trace_observed=False,
            restore_attempted_after_timeout=False,
            restore_verified_after_timeout=False,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["retry_mutation_allowed"])
        self.assertFalse(packet["second_launch_allowed_before_restore"])
        self.assertIn(
            "restore_attempt_required_after_trace_timeout",
            packet["failed_checks"],
        )

    def test_original_live_restore_failure_lockdown_blocks_second_launch(self) -> None:
        packet = build_original_live_restore_failure_lockdown_packet(
            restore_verified=False,
            second_launch_attempted=True,
            retry_apply_attempted=True,
            hidden_cleanup_performed=True,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["stop_and_diagnose_required"])
        self.assertFalse(packet["second_launch_allowed"])
        self.assertIn(
            "second_launch_forbidden_after_failed_restore",
            packet["failed_checks"],
        )

    def test_original_live_normal_sanity_not_final_e2e(self) -> None:
        summary = build_original_live_summary_packet(
            owner_authorization_packet={"status": "ok", "failed_checks": []},
            apply_admission_packet={"status": "ok"},
            route_trace_packet={"route_trace_confirmed": True},
            restore_verification_packet={"status": "ok"},
        )

        self.assertFalse(summary["normal_original_post_cleanup_proven"])
        self.assertFalse(summary["final_e2e_proven"])

    def test_original_live_does_not_claim_wire_compatibility(self) -> None:
        audit = build_original_live_false_green_audit(
            summary_packet={
                "direct_egress_absence_proven": False,
                "model_availability_proven": False,
                "wire_compatibility_proven": True,
                "full_native_ux_proven": False,
                "final_e2e_proven": False,
                "blocked_by_host_environment_counted_as_pass": False,
                "original_route_proven": False,
            }
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])

    def test_original_live_blocked_environment_not_pass(self) -> None:
        summary = build_original_live_summary_packet(
            owner_authorization_packet={"status": "ok", "failed_checks": []},
            apply_admission_packet={"status": "ok"},
            route_trace_packet={"route_trace_confirmed": True},
            restore_verification_packet={"status": "ok"},
            blocked_by_host_environment=True,
        )
        audit = build_original_live_false_green_audit(summary_packet=summary)

        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(
            summary["final_status"],
            "ORIGINAL_CODEX_VIA_WBP_BLOCKED_HOST_ENVIRONMENT",
        )
        self.assertFalse(summary["blocked_by_host_environment_counted_as_pass"])
        self.assertEqual(audit["status"], "ok")

    def test_original_live_does_not_claim_direct_egress_absence(self) -> None:
        audit = build_original_live_false_green_audit(
            summary_packet={
                "direct_egress_absence_proven": True,
                "model_availability_proven": False,
                "full_native_ux_proven": False,
                "final_e2e_proven": False,
                "blocked_by_host_environment_counted_as_pass": False,
                "original_route_proven": False,
            }
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])

    def test_original_live_does_not_claim_model_availability(self) -> None:
        audit = build_original_live_false_green_audit(
            summary_packet={
                "direct_egress_absence_proven": False,
                "model_availability_proven": False,
                "full_native_ux_proven": False,
                "final_e2e_proven": False,
                "blocked_by_host_environment_counted_as_pass": False,
                "original_route_proven": False,
            },
            selected_model_trace_claim_packet={"model_availability_claimed": True},
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])

    def test_original_live_does_not_claim_final_e2e(self) -> None:
        audit = build_original_live_false_green_audit(
            summary_packet={
                "direct_egress_absence_proven": False,
                "model_availability_proven": False,
                "full_native_ux_proven": False,
                "final_e2e_proven": True,
                "blocked_by_host_environment_counted_as_pass": False,
                "original_route_proven": False,
            }
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])

    def test_native_safety_layer_boundary_does_not_claim_adjacent_layers(self) -> None:
        packet = build_native_safety_layer_boundary_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["proves_native_custom_safety_only"])
        self.assertFalse(packet["native_ux_acceptance_proven"])
        self.assertFalse(packet["direct_egress_absence_proven"])
        self.assertFalse(packet["original_codex_reversibility_proven"])
        self.assertFalse(packet["auth_strategy_reproved"])
        self.assertFalse(packet["model_availability_reproved"])

    def test_custom_profile_and_user_data_ownership_require_tmp_root_scope(self) -> None:
        tmp_root = Path("/tmp/wbp-native-safety-r3-fixture")
        profile_dir = tmp_root / "profile"
        user_data_dir = profile_dir / "electron-user-data"

        profile = build_custom_profile_ownership_packet(
            tmp_root=tmp_root,
            profile_dir=profile_dir,
            codex_home=profile_dir,
        )
        user_data = build_custom_user_data_dir_ownership_packet(
            tmp_root=tmp_root,
            profile_dir=profile_dir,
            user_data_dir=user_data_dir,
        )

        self.assertEqual(profile["status"], "ok")
        self.assertEqual(user_data["status"], "ok")
        self.assertFalse(profile["current_codex_auth_json_runtime_dependency"])
        self.assertFalse(user_data["default_app_support_dependency"])

    def test_custom_profile_ownership_blocks_protected_surface_overlap(self) -> None:
        profile = build_custom_profile_ownership_packet(
            tmp_root=Path("/tmp/wbp-native-safety-r3-fixture"),
            profile_dir=Path.home() / ".codex",
            codex_home=Path.home() / ".codex",
        )

        self.assertEqual(profile["status"], "blocked")
        self.assertTrue(profile["protected_surface_overlap"])

    def test_custom_profile_write_inventory_and_cleanup_are_custom_owned_only(self) -> None:
        tmp_root = Path("/tmp/wbp-native-safety-r3-fixture")
        profile_dir = tmp_root / "profile"
        user_data_dir = profile_dir / "electron-user-data"
        inventory = build_custom_profile_write_inventory_packet(
            tmp_root=tmp_root,
            profile_dir=profile_dir,
            user_data_dir=user_data_dir,
            codex_home=profile_dir,
        )
        cleanup = build_cleanup_reversibility_plan_packet(
            tmp_root=tmp_root,
            owned_paths=[profile_dir, user_data_dir],
        )

        self.assertEqual(inventory["status"], "ok")
        self.assertFalse(inventory["native_launch_attempted"])
        self.assertEqual(cleanup["status"], "ok")
        self.assertTrue(cleanup["cleanup_removes_only_custom_owned_surfaces"])
        self.assertFalse(cleanup["cleanup_executed"])
        self.assertFalse(cleanup["original_codex_reversibility_claimed"])

    def test_cleanup_reversibility_blocks_outside_tmp_targets(self) -> None:
        cleanup = build_cleanup_reversibility_plan_packet(
            tmp_root=Path("/tmp/wbp-native-safety-r3-fixture"),
            owned_paths=[Path.home() / ".codex"],
        )

        self.assertEqual(cleanup["status"], "blocked")
        self.assertTrue(cleanup["outside_tmp_root_targets"])

    def test_current_codex_protection_does_not_reuse_normal_codex_as_custom(self) -> None:
        before = {
            "captured_at_utc": "2026-05-26T00:00:00Z",
            "root_app_pids": [100],
            "default_process_count": 1,
        }
        after = {
            "captured_at_utc": "2026-05-26T00:00:01Z",
            "root_app_pids": [100],
            "default_process_count": 1,
        }
        packet = build_current_codex_protection_packet(
            before_process_inventory=before,
            after_process_inventory=after,
            current_codex_delta_packet={"current_codex_touched": False},
            native_launch_attempted=False,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["existing_normal_codex_process_present"])
        self.assertFalse(packet["existing_normal_codex_reused_as_custom_proof"])
        self.assertFalse(packet["normal_codex_process_counted_as_isolated_custom"])
        self.assertTrue(packet["process_inventory_only"])

    def test_no_ambient_authority_safety_blocks_dirty_env_only_if_launch_attempted(self) -> None:
        ambient = {
            "status": "blocked",
            "reason_class": "AMBIENT_ENV_AUTHORITY_UNEXPLAINED",
        }
        no_launch = build_no_ambient_authority_safety_packet(
            ambient_env_packet=ambient,
            native_launch_attempted=False,
        )
        launch = build_no_ambient_authority_safety_packet(
            ambient_env_packet=ambient,
            native_launch_attempted=True,
        )

        self.assertEqual(no_launch["status"], "ok")
        self.assertTrue(no_launch["ambient_authority_present_but_not_used"])
        self.assertEqual(launch["status"], "blocked")
        self.assertFalse(no_launch["current_codex_auth_json_runtime_input"])

    def test_custom_launch_environment_requires_isolated_paths(self) -> None:
        packet = build_custom_launch_environment_packet(
            tmp_root=Path("/tmp/wbp-native-safety-r3-fixture"),
            codex_home=Path("/tmp/wbp-native-safety-r3-fixture/profile/.codex"),
            user_data_dir=Path("/tmp/wbp-native-safety-r3-fixture/profile/electron-user-data"),
            ambient_env_packet={"status": "ok"},
            native_launch_attempted=False,
        )
        blocked = build_custom_launch_environment_packet(
            tmp_root=Path("/tmp/wbp-native-safety-r3-fixture"),
            codex_home=Path.home() / ".codex",
            user_data_dir=Path("/tmp/wbp-native-safety-r3-fixture/profile/electron-user-data"),
            ambient_env_packet={"status": "ok"},
            native_launch_attempted=False,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["codex_home_isolated"])
        self.assertTrue(packet["user_data_dir_isolated"])
        self.assertEqual(blocked["status"], "blocked")

    def test_cleanup_authority_limit_forbids_hidden_cleanup(self) -> None:
        declared = {"status": "ok"}
        cleanup = build_cleanup_reversibility_plan_packet(
            tmp_root=Path("/tmp/wbp-native-safety-r3-fixture"),
            owned_paths=[Path("/tmp/wbp-native-safety-r3-fixture/profile")],
        )
        ok = build_cleanup_authority_limit_packet(
            cleanup_reversibility_packet=cleanup,
            declared_write_surfaces_packet=declared,
        )
        hidden = dict(cleanup)
        hidden["hidden_cleanup_performed"] = True
        blocked = build_cleanup_authority_limit_packet(
            cleanup_reversibility_packet=hidden,
            declared_write_surfaces_packet=declared,
        )

        self.assertEqual(ok["status"], "ok")
        self.assertFalse(ok["cleanup_executed"])
        self.assertEqual(blocked["status"], "blocked")
        self.assertTrue(blocked["stop_and_diagnose_required_for_extra_paths"])

    def test_incidental_routing_observation_never_proves_route_or_ux(self) -> None:
        packet = build_incidental_routing_observation_packet(
            custom_native_launch_safety_packet={
                "native_launch_attempted": False,
                "incidental_wbp_request_promoted_to_route_proof": False,
            },
            wbp_request_observed=True,
        )
        blocked = build_incidental_routing_observation_packet(
            custom_native_launch_safety_packet={
                "native_launch_attempted": False,
                "incidental_wbp_request_promoted_to_route_proof": True,
            },
            wbp_request_observed=True,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["wbp_request_observed"])
        self.assertFalse(packet["native_routing_proven"])
        self.assertFalse(packet["response_accepted_by_codex_proven"])
        self.assertFalse(packet["ux_acceptance_proven"])
        self.assertEqual(blocked["status"], "blocked")

    def test_custom_native_launch_safety_blocks_hosted_context_without_route_claim(self) -> None:
        packet = build_custom_native_launch_safety_packet(
            host_context_packet={"status": "blocked"},
            quiescent_precondition_packet={"status": "blocked"},
            native_launch_attempted=False,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "NATIVE_LAUNCH_BLOCKED_BY_HOST_ENVIRONMENT")
        self.assertFalse(packet["native_launch_attempted"])
        self.assertFalse(packet["native_launch_admitted"])
        self.assertFalse(packet["native_routing_proven"])
        self.assertFalse(packet["native_ux_proven"])
        self.assertFalse(packet["incidental_wbp_request_promoted_to_route_proof"])

    def test_native_custom_safety_claims_do_not_count_host_block_as_pass(self) -> None:
        claims = build_native_custom_safety_claims_packet(
            native_safety_result_packet={
                "status": "blocked",
                "actual_status": "NATIVE_CUSTOM_SAFETY_GUARD_BLOCKED_BY_HOST_ENVIRONMENT_WITH_HANDOFF",
            },
            custom_native_launch_safety_packet={
                "status": "blocked",
                "native_launch_attempted": False,
            },
            protected_surface_diff_packet={"all_protected_surfaces_unchanged": True},
            cleanup_reversibility_packet={"status": "ok"},
            keychain_observation_packet={"status": "ok"},
        )

        self.assertEqual(claims["status"], "blocked")
        self.assertEqual(claims["allowed_final_claim"], "")
        self.assertTrue(claims["blocked_by_host_environment"])
        self.assertFalse(claims["blocked_by_host_environment_counted_as_pass"])
        self.assertFalse(claims["native_wbp_routing_success_proven"])
        self.assertFalse(claims["direct_egress_absence_proven"])
        self.assertFalse(claims["original_codex_reversibility_proven"])

    def test_native_safety_refresh_false_green_audit_requires_reference_only_layers(self) -> None:
        tmp_root = Path("/tmp/wbp-native-safety-r3-fixture")
        profile_dir = tmp_root / "profile"
        user_data_dir = profile_dir / "electron-user-data"
        audit = build_native_safety_refresh_false_green_audit(
            layer_boundary_packet=build_native_safety_layer_boundary_packet(),
            owner_action_boundary_packet=build_owner_action_boundary_packet(),
            protected_surface_read_packet=build_protected_surface_read_classification_packet(),
            profile_ownership_packet=build_custom_profile_ownership_packet(
                tmp_root=tmp_root,
                profile_dir=profile_dir,
                codex_home=profile_dir,
            ),
            user_data_ownership_packet=build_custom_user_data_dir_ownership_packet(
                tmp_root=tmp_root,
                profile_dir=profile_dir,
                user_data_dir=user_data_dir,
            ),
            write_inventory_packet=build_custom_profile_write_inventory_packet(
                tmp_root=tmp_root,
                profile_dir=profile_dir,
                user_data_dir=user_data_dir,
                codex_home=profile_dir,
            ),
            cleanup_reversibility_packet=build_cleanup_reversibility_plan_packet(
                tmp_root=tmp_root,
                owned_paths=[profile_dir, user_data_dir],
            ),
            keychain_observation_packet=classify_keychain_observation(
                machine_prompt_observed=False
            ),
            auth_strategy_reference_packet={"auth_strategy_reproved_in_this_contour": False},
            model_availability_reference_packet={
                "model_availability_reproved_in_this_contour": False
            },
        )

        self.assertEqual(audit["status"], "ok")
        self.assertFalse(audit["ux_claimed"])
        self.assertFalse(audit["egress_claimed"])

    def _native_safety_admission_fixture(self) -> dict[str, dict[str, object]]:
        tmp_root = Path("/tmp/wbp-native-safety-admission-r1-fixture")
        profile_dir = tmp_root / "profile"
        codex_home = profile_dir / ".codex"
        user_data_dir = profile_dir / "electron-user-data"
        execution_mode = build_native_safety_execution_mode_decision_packet(
            execution_mode="inspection_only",
            native_launch_attempted=False,
            temp_surface_action_performed=False,
        )
        protected_read = build_protected_surface_read_classification_packet()
        no_ambient = build_no_ambient_authority_safety_packet(
            ambient_env_packet={"status": "blocked", "reason_class": "ambient_present"},
            native_launch_attempted=False,
        )
        cleanup = build_native_cleanup_rollback_expectation_packet(
            tmp_root=tmp_root,
            owned_paths=[profile_dir, codex_home, user_data_dir],
            temp_surface_action_performed=False,
            native_launch_attempted=False,
        )
        integrity = build_native_integrity_packet(
            native_launch_attempted=False,
            temp_surface_action_performed=False,
            protected_surface_read_packet=protected_read,
        )
        isolated_codex_home = build_native_safety_isolated_path_packet(
            packet_kind="isolated_codex_home",
            tmp_root=tmp_root,
            path=codex_home,
            path_role="CODEX_HOME",
            execution_mode="inspection_only",
        )
        isolated_user_data = build_native_safety_isolated_path_packet(
            packet_kind="isolated_user_data_dir",
            tmp_root=tmp_root,
            path=user_data_dir,
            path_role="electron_user_data_dir",
            execution_mode="inspection_only",
        )
        admission = build_native_custom_admission_packet(
            execution_mode_packet=execution_mode,
            isolated_codex_home_packet=isolated_codex_home,
            isolated_user_data_dir_packet=isolated_user_data,
            no_ambient_authority_packet=no_ambient,
            protected_surface_read_packet=protected_read,
            cleanup_rollback_expectation_packet=cleanup,
            native_integrity_packet=integrity,
        )
        auth_ref = build_native_safety_reference_packet(
            packet_kind="provider_auth_strategy_reference",
            source_path="audit_results/auth/provider_auth_strategy_packet.json",
            expected_status="WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
        )
        model_ref = build_native_safety_reference_packet(
            packet_kind="model_availability_reference",
            source_path="audit_results/model/model_availability_matrix.json",
            expected_status="WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
        )
        cli_ref = build_native_safety_reference_packet(
            packet_kind="cli_runner_reference",
            source_path="audit_results/cli/cli_runner_closeout_packet.json",
            expected_status="CODEX_CLI_RUNNER_VIA_WBP_WORKS_NOT_NATIVE_APP",
        )
        false_green = build_native_safety_admission_false_green_audit(
            native_custom_admission_packet=admission,
            auth_strategy_reference_packet=auth_ref,
            model_availability_reference_packet=model_ref,
            cli_runner_reference_packet=cli_ref,
        )
        return {
            "execution_mode_decision_packet.json": execution_mode,
            "native_custom_admission_packet.json": admission,
            "isolated_codex_home_packet.json": isolated_codex_home,
            "isolated_user_data_dir_packet.json": isolated_user_data,
            "no_ambient_authority_packet.json": no_ambient,
            "protected_surface_read_classification_packet.json": protected_read,
            "cleanup_rollback_expectation_packet.json": cleanup,
            "native_integrity_packet.json": integrity,
            "provider_auth_strategy_reference_packet.json": auth_ref,
            "model_availability_reference_packet.json": model_ref,
            "cli_runner_reference_packet.json": cli_ref,
            "native_safety_false_green_audit.json": false_green,
        }

    def test_native_safety_execution_mode_required(self) -> None:
        packet = build_native_safety_execution_mode_decision_packet(
            execution_mode="surprise_live_mode",
            native_launch_attempted=False,
            temp_surface_action_performed=False,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "NATIVE_SAFETY_EXECUTION_MODE_CONTRADICTION")

    def test_native_safety_inspection_only_forbids_launch_packets(self) -> None:
        packets = self._native_safety_admission_fixture()
        packets["native_process_observation_packet.json"] = {
            "packet_kind": "native_process_observation"
        }
        validation = validate_native_safety_admission_contour_packets(packets)

        self.assertEqual(validation["status"], "blocked")
        self.assertIn(
            "native_process_observation_packet.json",
            validation["forbidden_launch_packets_present"],
        )

    def test_native_safety_temp_action_requires_after_diff_cleanup(self) -> None:
        packets = self._native_safety_admission_fixture()
        packets["execution_mode_decision_packet.json"] = (
            build_native_safety_execution_mode_decision_packet(
                execution_mode="temp_surface_probe",
                native_launch_attempted=False,
                temp_surface_action_performed=True,
            )
        )
        validation = validate_native_safety_admission_contour_packets(packets)

        self.assertEqual(validation["status"], "blocked")
        self.assertIn(
            "protected_surface_recursive_diff.json",
            validation["missing_conditional_packets"],
        )
        self.assertIn(
            "cleanup_reversibility_packet.json",
            validation["missing_conditional_packets"],
        )

    def test_native_safety_native_launch_attempt_requires_after_diff_cleanup(self) -> None:
        packets = self._native_safety_admission_fixture()
        packets["execution_mode_decision_packet.json"] = (
            build_native_safety_execution_mode_decision_packet(
                execution_mode="native_launch",
                native_launch_attempted=True,
                temp_surface_action_performed=False,
            )
        )
        validation = validate_native_safety_admission_contour_packets(packets)

        self.assertEqual(validation["status"], "blocked")
        self.assertIn(
            "protected_surface_recursive_after.json",
            validation["missing_conditional_packets"],
        )
        self.assertIn(
            "custom_profile_write_inventory_packet.json",
            validation["missing_conditional_packets"],
        )

    def test_native_safety_admission_ready_not_launch_executed(self) -> None:
        packets = self._native_safety_admission_fixture()
        admission = packets["native_custom_admission_packet.json"]
        validation = validate_native_safety_admission_contour_packets(packets)

        self.assertEqual(admission["status"], "ok")
        self.assertTrue(admission["admission_ready"])
        self.assertFalse(admission["launch_executed"])
        self.assertEqual(validation["status"], "ok")

    def test_native_safety_reference_packets_not_reproof(self) -> None:
        packets = self._native_safety_admission_fixture()

        self.assertTrue(packets["provider_auth_strategy_reference_packet.json"]["reference_only"])
        self.assertFalse(
            packets["provider_auth_strategy_reference_packet.json"][
                "auth_strategy_reproved_in_this_contour"
            ]
        )
        self.assertFalse(
            packets["model_availability_reference_packet.json"][
                "model_availability_reproved_in_this_contour"
            ]
        )

    def test_native_safety_cli_runner_reference_not_native_proof(self) -> None:
        packets = self._native_safety_admission_fixture()
        cli_ref = packets["cli_runner_reference_packet.json"]

        self.assertTrue(cli_ref["reference_only"])
        self.assertFalse(cli_ref["native_proof_claimed_from_reference"])
        self.assertFalse(
            packets["native_custom_admission_packet.json"][
                "cli_runner_counted_as_native_proof"
            ]
        )

    def test_native_safety_no_route_ux_egress_claims(self) -> None:
        packets = self._native_safety_admission_fixture()
        admission = packets["native_custom_admission_packet.json"]
        audit = packets["native_safety_false_green_audit.json"]

        self.assertFalse(admission["native_route_proof_claimed"])
        self.assertFalse(admission["ux_claimed"])
        self.assertFalse(admission["egress_claimed"])
        self.assertEqual(audit["status"], "ok")

    def test_native_safety_protected_read_is_inspection_only(self) -> None:
        packets = self._native_safety_admission_fixture()
        protected_read = packets["protected_surface_read_classification_packet.json"]

        self.assertTrue(protected_read["inspection_only"])
        self.assertFalse(protected_read["runtime_auth_input_used"])
        self.assertEqual(packets["native_integrity_packet.json"]["status"], "ok")

    def test_native_safety_keychain_prompt_does_not_equal_auth_success(self) -> None:
        packet = classify_keychain_observation(
            machine_prompt_observed=True,
            owner_pressed_cancel=True,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["owner_cancel_classification"], "manual_observation_only")
        self.assertFalse(packet["keychain_cancel_equals_auth_success"])
        self.assertFalse(packet["auth_success_claimed"])

    def test_native_safety_keychain_reset_blocks(self) -> None:
        packet = classify_keychain_observation(
            machine_prompt_observed=True,
            keychain_reset_performed=True,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "KEYCHAIN_MUTATION_REQUIRED")

    def test_native_direct_egress_capability_requires_lsof_observer(self) -> None:
        blocked = build_native_direct_egress_capability_packet(
            lsof_path="",
            process_tree_observer_available=True,
        )
        ok = build_native_direct_egress_capability_packet(
            lsof_path="/usr/sbin/lsof",
            process_tree_observer_available=True,
        )

        self.assertEqual(blocked["status"], "blocked")
        self.assertFalse(blocked["observer_usable_for_bounded_native_classification"])
        self.assertEqual(ok["status"], "ok")
        self.assertTrue(ok["observer_usable_for_bounded_native_classification"])
        self.assertFalse(ok["full_network_absence_proven"])

    def test_native_direct_egress_local_only_requires_trace_and_process_binding(self) -> None:
        packet = build_native_direct_egress_claim_packet(
            process_network_observation_packet={
                "classification": "wbp_forward_only_proven",
                "direct_non_wbp_model_egress_absent_proven": True,
                "allowed_local_endpoint_observed": True,
            },
            wbp_trace_observation_packet={"route_status": "confirmed"},
            custom_process_bound=True,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_ABSENT_WITH_LIMITS",
        )
        self.assertTrue(packet["direct_non_wbp_model_egress_absent_proven"])
        self.assertFalse(packet["full_network_absence_proven"])
        self.assertFalse(packet["native_ux_claimed"])

    def test_native_direct_egress_route_trace_alone_does_not_pass(self) -> None:
        packet = build_native_direct_egress_claim_packet(
            process_network_observation_packet={
                "classification": "insufficient_observation",
                "direct_non_wbp_model_egress_absent_proven": False,
                "allowed_local_endpoint_observed": False,
            },
            wbp_trace_observation_packet={"route_status": "confirmed"},
            custom_process_bound=True,
        )
        audit = build_native_direct_egress_false_green_audit(
            native_direct_egress_claim_packet=packet,
            process_network_observation_packet={
                "classification": "insufficient_observation",
                "direct_non_wbp_model_egress_absent_proven": False,
            },
            wbp_trace_observation_packet={"route_status": "confirmed"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["direct_non_wbp_model_egress_absent_proven"])
        self.assertEqual(audit["status"], "ok")

    def test_native_direct_egress_direct_model_peer_blocks(self) -> None:
        packet = build_native_direct_egress_claim_packet(
            process_network_observation_packet={
                "classification": "direct_model_egress_observed",
                "direct_non_wbp_model_egress_absent_proven": False,
                "allowed_local_endpoint_observed": True,
            },
            wbp_trace_observation_packet={"route_status": "confirmed"},
            custom_process_bound=True,
        )
        audit = build_native_direct_egress_false_green_audit(
            native_direct_egress_claim_packet=packet,
            process_network_observation_packet={
                "classification": "direct_model_egress_observed",
                "direct_non_wbp_model_egress_absent_proven": False,
            },
            wbp_trace_observation_packet={"route_status": "confirmed"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["final_status"],
            "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_DIRECT_EGRESS_OBSERVED",
        )
        self.assertFalse(packet["direct_non_wbp_model_egress_absent_proven"])
        self.assertEqual(audit["status"], "ok")

    def test_native_direct_egress_background_noise_blocks_without_direct_claim(self) -> None:
        packet = build_native_direct_egress_claim_packet(
            process_network_observation_packet={
                "classification": "direct_model_egress_observed",
                "direct_non_wbp_model_egress_absent_proven": False,
                "allowed_local_endpoint_observed": True,
            },
            wbp_trace_observation_packet={"route_status": "confirmed"},
            custom_process_bound=True,
            background_codex_noise_detected=True,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["final_status"],
            "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_BACKGROUND_CODEX_NOISE",
        )
        self.assertFalse(packet["direct_non_wbp_model_egress_absent_proven"])

    def test_bounded_process_egress_limits_keep_adjacent_layers_out(self) -> None:
        window = build_bounded_observation_window_packet(wait_seconds=30)
        binding = build_custom_process_binding_packet(
            launch_packet={"custom_process_observed": True},
            observer_root_pid_bound=True,
        )
        domain = build_domain_attribution_limit_packet(
            process_network_observation_packet={
                "peer_endpoints": [
                    {"endpoint": "127.0.0.1:8318", "host_class": "local"}
                ]
            },
            domain_attribution_available=False,
        )
        owner_context = build_owner_visible_response_context_packet(
            owner_visible_response_reported=True,
            owner_confirmation_collected=True,
        )
        cleanup = build_temp_custom_cleanup_packet(
            cleanup_reversibility_packet={
                "status": "ok",
                "tmp_root_removed": True,
                "custom_processes_gone": True,
            }
        )
        claim = build_native_direct_egress_claim_packet(
            process_network_observation_packet={
                "classification": "wbp_forward_only_proven",
                "direct_non_wbp_model_egress_absent_proven": True,
                "allowed_local_endpoint_observed": True,
            },
            wbp_trace_observation_packet={"route_status": "confirmed"},
            custom_process_bound=True,
        )
        audit = build_bounded_process_egress_false_green_audit(
            native_direct_egress_claim_packet=claim,
            domain_attribution_limit_packet=domain,
            owner_visible_response_context_packet=owner_context,
            temp_custom_cleanup_packet=cleanup,
        )

        self.assertEqual(window["status"], "ok")
        self.assertFalse(window["global_network_absence_claim_allowed"])
        self.assertEqual(binding["status"], "ok")
        self.assertFalse(binding["counts_as_usable_window"])
        self.assertFalse(domain["api_openai_com_absence_proven"])
        self.assertFalse(domain["no_observed_api_openai_equals_absence"])
        self.assertTrue(owner_context["context_only"])
        self.assertFalse(owner_context["counts_as_egress_proof"])
        self.assertEqual(cleanup["status"], "ok")
        self.assertFalse(cleanup["filesystem_safety_proven"])
        self.assertEqual(audit["status"], "ok")

    def test_bounded_process_egress_false_green_blocks_api_and_ux_overclaim(self) -> None:
        claim = build_native_direct_egress_claim_packet(
            process_network_observation_packet={
                "classification": "wbp_forward_only_proven",
                "direct_non_wbp_model_egress_absent_proven": True,
                "allowed_local_endpoint_observed": True,
            },
            wbp_trace_observation_packet={"route_status": "confirmed"},
            custom_process_bound=True,
        )
        domain = build_domain_attribution_limit_packet(
            process_network_observation_packet={"peer_endpoints": []},
            domain_attribution_available=False,
        )
        bad_domain = dict(domain)
        bad_domain["api_openai_com_absence_proven"] = True
        owner_context = build_owner_visible_response_context_packet()
        bad_owner = dict(owner_context)
        bad_owner["counts_as_egress_proof"] = True
        cleanup = build_temp_custom_cleanup_packet(
            cleanup_reversibility_packet={
                "status": "ok",
                "tmp_root_removed": True,
                "custom_processes_gone": True,
            }
        )
        blocked_domain = build_bounded_process_egress_false_green_audit(
            native_direct_egress_claim_packet=claim,
            domain_attribution_limit_packet=bad_domain,
            owner_visible_response_context_packet=owner_context,
            temp_custom_cleanup_packet=cleanup,
        )
        blocked_owner = build_bounded_process_egress_false_green_audit(
            native_direct_egress_claim_packet=claim,
            domain_attribution_limit_packet=domain,
            owner_visible_response_context_packet=bad_owner,
            temp_custom_cleanup_packet=cleanup,
        )

        self.assertEqual(blocked_domain["status"], "blocked")
        self.assertTrue(blocked_domain["forbidden_claims_present"])
        self.assertEqual(blocked_owner["status"], "blocked")
        self.assertTrue(blocked_owner["forbidden_claims_present"])

    def test_egress_prior_blocker_replay_required(self) -> None:
        replay = build_egress_prior_blocker_replay_packet(
            prior_claim_packet={
                "final_status": "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_BACKGROUND_CODEX_NOISE",
                "reason_class": "BACKGROUND_CODEX_NOISE",
                "observer_classification": "direct_model_egress_observed",
                "direct_model_egress_observed": True,
                "direct_non_wbp_model_egress_absent_proven": False,
                "full_network_absence_proven": False,
            },
            prior_process_network_observation_packet={
                "classification": "direct_model_egress_observed",
            },
            prior_background_noise_packet={
                "background_codex_noise_detected": True,
            },
            prior_wbp_trace_observation_packet={
                "route_status": "confirmed",
            },
        )
        mismatch = build_egress_prior_blocker_replay_packet(
            prior_claim_packet={
                "final_status": "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_ABSENT_WITH_LIMITS",
                "direct_non_wbp_model_egress_absent_proven": True,
            },
            prior_process_network_observation_packet={},
            prior_background_noise_packet={
                "background_codex_noise_detected": False,
            },
            prior_wbp_trace_observation_packet={"route_status": "confirmed"},
        )

        self.assertEqual(replay["status"], "ok")
        self.assertTrue(replay["prior_background_codex_noise_detected"])
        self.assertFalse(replay["prior_direct_egress_absence_proven"])
        self.assertFalse(replay["current_egress_absence_claimed"])
        self.assertEqual(mismatch["status"], "blocked")

    def test_egress_route_trace_alone_not_absence(self) -> None:
        route = build_historical_route_context_packet(
            wbp_trace_observation_packet={
                "route_status": "confirmed",
                "forwarded_to_wbp": True,
                "trace_path": "/v1/responses",
                "upstream_status": 200,
            },
            source_trace_path="audit_results/source/source_wbp_trace_packet.json",
        )
        limits = build_network_claim_limits_packet()
        decision = build_network_observer_feasibility_decision_packet(
            prior_blocker_replay_packet={"status": "ok"},
            observer_capability_packet={"status": "ok"},
            quiescent_network_precondition_packet={"status": "blocked"},
        )
        audit = build_native_egress_observer_false_green_audit(
            historical_route_context_packet=route,
            network_observer_feasibility_decision_packet=decision,
            network_claim_limits_packet=limits,
        )

        self.assertEqual(route["status"], "ok")
        self.assertFalse(route["historical_route_counted_as_egress_absence"])
        self.assertFalse(decision["direct_egress_absence_proven"])
        self.assertEqual(audit["status"], "ok")

    def test_egress_owner_ux_and_screenshot_not_network_proof(self) -> None:
        route = build_historical_route_context_packet(
            wbp_trace_observation_packet={"route_status": "confirmed"},
            source_trace_path="source.json",
        )
        decision = build_network_observer_feasibility_decision_packet(
            prior_blocker_replay_packet={"status": "ok"},
            observer_capability_packet={"status": "ok"},
            quiescent_network_precondition_packet={"status": "ok"},
        )
        limits = build_network_claim_limits_packet()
        owner_bad = build_native_egress_observer_false_green_audit(
            historical_route_context_packet=route,
            network_observer_feasibility_decision_packet=decision,
            network_claim_limits_packet=limits,
            owner_ux_used_as_network_proof=True,
        )
        screenshot_bad = build_native_egress_observer_false_green_audit(
            historical_route_context_packet=route,
            network_observer_feasibility_decision_packet=decision,
            network_claim_limits_packet=limits,
            screenshot_used_as_network_proof=True,
        )

        self.assertEqual(owner_bad["status"], "blocked")
        self.assertTrue(owner_bad["forbidden_claims_present"])
        self.assertEqual(screenshot_bad["status"], "blocked")
        self.assertTrue(screenshot_bad["forbidden_claims_present"])

    def test_egress_background_noise_blocks_feasibility(self) -> None:
        current_noise = build_current_background_codex_noise_packet(
            current_process_inventory_packet={
                "line_count": 3,
                "root_app_pids": [111],
                "default_process_count": 2,
                "custom_process_count": 0,
            },
            hosted_by_codex_context=True,
        )
        precondition = build_quiescent_network_precondition_packet(
            observer_capability_packet={
                "observer_usable_for_bounded_native_classification": True,
            },
            current_background_codex_noise_packet=current_noise,
        )
        decision = build_network_observer_feasibility_decision_packet(
            prior_blocker_replay_packet={"status": "ok"},
            observer_capability_packet={"status": "ok"},
            quiescent_network_precondition_packet=precondition,
        )

        self.assertEqual(current_noise["status"], "blocked")
        self.assertTrue(current_noise["background_codex_noise_detected"])
        self.assertEqual(precondition["status"], "blocked")
        self.assertTrue(precondition["owner_assisted_quiescent_window_required"])
        self.assertEqual(
            decision["final_status"],
            "NATIVE_WBP_ROUTE_NETWORK_OBSERVER_FEASIBILITY_BLOCKED_CURRENT_NOISE",
        )
        self.assertFalse(decision["direct_egress_absence_proven"])

    def test_egress_observer_feasibility_does_not_claim_absence_or_launch(self) -> None:
        clean_noise = build_current_background_codex_noise_packet(
            current_process_inventory_packet={
                "line_count": 0,
                "root_app_pids": [],
                "default_process_count": 0,
                "custom_process_count": 0,
            },
            hosted_by_codex_context=False,
        )
        precondition = build_quiescent_network_precondition_packet(
            observer_capability_packet={
                "observer_usable_for_bounded_native_classification": True,
            },
            current_background_codex_noise_packet=clean_noise,
        )
        decision = build_network_observer_feasibility_decision_packet(
            prior_blocker_replay_packet={"status": "ok"},
            observer_capability_packet={"status": "ok"},
            quiescent_network_precondition_packet=precondition,
        )

        self.assertEqual(decision["status"], "ok")
        self.assertTrue(decision["separate_live_bounded_egress_contour_admissible"])
        self.assertFalse(decision["fresh_native_launch_attempted"])
        self.assertFalse(decision["direct_egress_absence_proven"])
        self.assertFalse(decision["api_openai_com_absence_proven"])

    def test_egress_readiness_limits_do_not_claim_route_or_absence(self) -> None:
        capability = build_native_direct_egress_capability_packet(
            lsof_path="/usr/sbin/lsof",
            process_tree_observer_available=True,
        )
        noise = build_current_background_codex_noise_packet(
            current_process_inventory_packet={
                "line_count": 2,
                "root_app_pids": [123],
                "default_process_count": 1,
                "custom_process_count": 0,
            },
            hosted_by_codex_context=True,
        )
        quiescent = build_quiescent_network_precondition_packet(
            observer_capability_packet=capability,
            current_background_codex_noise_packet=noise,
        )
        readiness = build_native_egress_observer_readiness_packet(
            observer_capability_packet=capability,
            current_background_codex_noise_packet=noise,
            quiescent_network_precondition_packet=quiescent,
        )
        wbp_limit = build_wbp_endpoint_observation_limit_packet(
            wbp_endpoint_observed=True,
            endpoint="http://127.0.0.1:12345/v1/responses",
        )
        attribution_limit = build_process_attribution_limit_packet(
            observer_capability_packet=capability,
            current_background_codex_noise_packet=noise,
        )
        absence_limit = build_absence_claim_limit_packet(
            quiescent_network_precondition_packet=quiescent,
            process_attribution_limit_packet=attribution_limit,
            observation_window_seconds=0,
        )

        self.assertEqual(readiness["status"], "blocked")
        self.assertEqual(
            readiness["final_status"],
            "NATIVE_DIRECT_EGRESS_OBSERVER_BLOCKED_BY_HOST_ENVIRONMENT_WITH_HANDOFF",
        )
        self.assertFalse(readiness["fresh_native_launch_attempted"])
        self.assertFalse(readiness["live_network_capture_attempted"])
        self.assertFalse(readiness["api_openai_com_absence_proven"])
        self.assertTrue(wbp_limit["counts_as_network_peer_observation_only"])
        self.assertFalse(wbp_limit["counts_as_route_proof"])
        self.assertFalse(wbp_limit["counts_as_direct_egress_absence"])
        self.assertFalse(
            attribution_limit["process_attribution_counts_as_usable_window"]
        )
        self.assertFalse(
            attribution_limit["process_attribution_counts_as_direct_egress_absence"]
        )
        self.assertFalse(absence_limit["direct_egress_absence_claim_allowed_now"])
        self.assertFalse(absence_limit["no_observed_api_openai_equals_absence"])

    def test_egress_readiness_false_green_blocks_cross_layer_claims(self) -> None:
        capability = build_native_direct_egress_capability_packet(
            lsof_path="/usr/sbin/lsof",
            process_tree_observer_available=True,
        )
        clean_noise = build_current_background_codex_noise_packet(
            current_process_inventory_packet={
                "line_count": 0,
                "root_app_pids": [],
                "default_process_count": 0,
                "custom_process_count": 0,
            },
            hosted_by_codex_context=False,
        )
        quiescent = build_quiescent_network_precondition_packet(
            observer_capability_packet=capability,
            current_background_codex_noise_packet=clean_noise,
        )
        readiness = build_native_egress_observer_readiness_packet(
            observer_capability_packet=capability,
            current_background_codex_noise_packet=clean_noise,
            quiescent_network_precondition_packet=quiescent,
        )
        wbp_limit = build_wbp_endpoint_observation_limit_packet()
        attribution_limit = build_process_attribution_limit_packet(
            observer_capability_packet=capability,
            current_background_codex_noise_packet=clean_noise,
        )
        absence_limit = build_absence_claim_limit_packet(
            quiescent_network_precondition_packet=quiescent,
            process_attribution_limit_packet=attribution_limit,
            observation_window_seconds=30,
        )
        network_limits = build_network_claim_limits_packet()
        route_reference = build_historical_route_context_reference_packet(
            source_packets=["audit_results/example/native_route_trace_packet.json"]
        )
        clean = build_egress_readiness_false_green_audit(
            native_egress_observer_readiness_packet=readiness,
            wbp_endpoint_observation_limit_packet=wbp_limit,
            process_attribution_limit_packet=attribution_limit,
            absence_claim_limit_packet=absence_limit,
            network_claim_limits_packet=network_limits,
            historical_route_context_reference_packet=route_reference,
        )
        bad_readiness = dict(readiness)
        bad_readiness["final_e2e_proven"] = True
        blocked = build_egress_readiness_false_green_audit(
            native_egress_observer_readiness_packet=bad_readiness,
            wbp_endpoint_observation_limit_packet=wbp_limit,
            process_attribution_limit_packet=attribution_limit,
            absence_claim_limit_packet=absence_limit,
            network_claim_limits_packet=network_limits,
            historical_route_context_reference_packet=route_reference,
        )
        handoff = build_owner_egress_handoff_instruction_packet()

        self.assertEqual(clean["status"], "ok")
        self.assertEqual(blocked["status"], "blocked")
        self.assertTrue(blocked["forbidden_claims_present"])
        self.assertTrue(handoff["owner_or_detached_handoff_required_for_live_egress"])
        self.assertFalse(handoff["handoff_counts_as_live_egress_proof"])

    def test_egress_observer_feasibility_probe_is_no_launch(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "native_wbp_route_network_observer_feasibility_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=temp_repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            (temp_repo / "README.md").write_text("fixture\n", encoding="utf-8")
            prior_dir = temp_repo / "audit_results" / "prior"
            prior_dir.mkdir(parents=True)
            (prior_dir / "native_direct_egress_claim_packet.json").write_text(
                json.dumps(
                    {
                        "final_status": "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_BACKGROUND_CODEX_NOISE",
                        "reason_class": "BACKGROUND_CODEX_NOISE",
                        "observer_classification": "direct_model_egress_observed",
                        "direct_model_egress_observed": True,
                        "direct_non_wbp_model_egress_absent_proven": False,
                        "full_network_absence_proven": False,
                    }
                ),
                encoding="utf-8",
            )
            (prior_dir / "native_process_network_observation_packet.json").write_text(
                json.dumps({"classification": "direct_model_egress_observed"}),
                encoding="utf-8",
            )
            (prior_dir / "native_background_codex_noise_packet.json").write_text(
                json.dumps({"background_codex_noise_detected": True}),
                encoding="utf-8",
            )
            (prior_dir / "source_wbp_trace_packet.json").write_text(
                json.dumps(
                    {
                        "request_observed": True,
                        "response_observed": True,
                        "forwarded_to_wbp": True,
                        "path": "/v1/responses",
                        "upstream_status": 200,
                        "response_body_sha256": "response-hash",
                    }
                ),
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "README.md", "audit_results"], cwd=temp_repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            evidence_dir = temp_repo / "audit_results" / "observer_feasibility"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--prior-evidence-dir",
                    str(prior_dir),
                    "--hosted-by-codex-context",
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (evidence_dir / "network_observer_feasibility_summary_packet.json").read_text()
            )
            decision = json.loads(
                (
                    evidence_dir / "network_observer_feasibility_decision_packet.json"
                ).read_text()
            )
            false_green = json.loads(
                (evidence_dir / "native_egress_observer_false_green_audit.json").read_text()
            )
            self.assertEqual(
                summary["final_status"],
                "NATIVE_WBP_ROUTE_NETWORK_OBSERVER_FEASIBILITY_BLOCKED_CURRENT_NOISE",
            )
            self.assertFalse(summary["fresh_native_launch_attempted"])
            self.assertFalse(summary["direct_egress_absence_proven"])
            self.assertFalse(decision["separate_live_bounded_egress_contour_admissible"])
            self.assertEqual(false_green["status"], "ok")

    def test_bounded_process_egress_probe_stops_before_live_launch_when_hosted(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = (
            repo_root
            / "tools"
            / "native_custom_bounded_process_egress_classification_probe.py"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=temp_repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            (temp_repo / "README.md").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=temp_repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            evidence_dir = temp_repo / "audit_results" / "bounded_egress"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--hosted-by-codex-context",
                    "--wait-seconds",
                    "5",
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (evidence_dir / "bounded_process_egress_summary_packet.json").read_text()
            )
            admission = json.loads(
                (evidence_dir / "native_launch_admission_packet.json").read_text()
            )
            owner_context = json.loads(
                (evidence_dir / "owner_visible_response_context_packet.json").read_text()
            )
            domain_limit = json.loads(
                (evidence_dir / "domain_attribution_limit_packet.json").read_text()
            )

            self.assertEqual(
                summary["final_status"],
                "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_BACKGROUND_CODEX_NOISE",
            )
            self.assertFalse(summary["native_launch_attempted"])
            self.assertFalse(summary["live_network_capture_attempted"])
            self.assertFalse(summary["api_openai_com_absence_proven"])
            self.assertFalse(admission["native_launch_admitted"])
            self.assertFalse(owner_context["counts_as_egress_proof"])
            self.assertFalse(domain_limit["no_observed_api_openai_equals_absence"])

    def test_environment_blocked_result_not_counted_as_pass(self) -> None:
        packet = classify_environment_blocked_result(
            item="machine_ui_input_field",
            status="blocked_by_host_environment",
            root_cause="macos_accessibility_detail_unavailable",
            exercised="process/window inventory",
            remains_unproven="input-capable UI",
        )

        self.assertEqual(packet["status"], "blocked_by_host_environment")
        self.assertFalse(packet["counts_as_pass"])

    def test_native_safety_does_not_claim_route_ux_or_egress(self) -> None:
        matrix = build_allowed_claims_matrix(
            final_status="NATIVE_CUSTOM_APP_SAFE_TO_CONTINUE_WITH_LIMITS"
        )

        self.assertFalse(matrix["route_claim_allowed"])
        self.assertFalse(matrix["ux_claim_allowed"])
        self.assertFalse(matrix["egress_claim_allowed"])
        self.assertIn("native_route_proven", matrix["forbidden_claims"])
        self.assertIn("owner_ux_proven", matrix["forbidden_claims"])
        self.assertIn("direct_egress_absent", matrix["forbidden_claims"])

    def test_native_safety_false_green_audit_requires_safety_packets(self) -> None:
        matrix = build_allowed_claims_matrix(
            final_status="NATIVE_CUSTOM_APP_SAFE_TO_CONTINUE_WITH_LIMITS"
        )
        audit = build_native_safety_false_green_audit(
            probe_packet={
                "protected_surface_recursive_diff": {
                    "all_protected_surfaces_unchanged": True
                },
                "user_data_dir_respected_packet": {"user_data_dir_respected": True},
                "cleanup_reversibility_packet": {"tmp_root_removed": True},
                "current_codex_delta": {"current_codex_touched": False},
                "keychain_observation_packet": {
                    "keychain_cancel_equals_auth_success": False
                },
            },
            allowed_claims_matrix=matrix,
        )

        self.assertEqual(audit["status"], "ok")
        self.assertFalse(audit["forbidden_claims_present"])

    def test_quiescent_retry_host_context_required(self) -> None:
        packet = classify_host_context(
            [
                {"pid": 100, "ppid": 90, "command": "/usr/bin/python3"},
                {
                    "pid": 90,
                    "ppid": 80,
                    "command": "/Applications/Codex.app/Contents/Resources/codex app-server",
                },
            ]
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["executor_context"], "protected_codex_hosted")
        self.assertTrue(packet["machine_filesystem_proof_environment_constrained"])

    def test_quiescent_retry_owner_action_boundary_required(self) -> None:
        packet = build_owner_action_boundary_packet(prompt_submitted=True)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "OWNER_ACTION_BOUNDARY_VIOLATED")

    def test_quiescent_retry_does_not_launch_before_prelaunch_gates(self) -> None:
        admission = build_quiescent_retry_launch_admission_packet(
            host_context_packet={"status": "blocked", "executor_context": "protected_codex_hosted"},
            owner_action_boundary_packet={"status": "ok"},
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": False
            },
            idle_stability_packet=None,
            declared_write_surfaces_packet={"status": "ok"},
            protected_surface_read_packet={"inspection_only": True},
        )

        self.assertEqual(admission["status"], "blocked")
        self.assertFalse(admission["native_launch_admitted"])
        self.assertFalse(admission["native_launch_attempted"])
        self.assertIn("host_context_required", admission["failed_checks"])
        self.assertIn("quiescent_current_codex_required", admission["failed_checks"])
        self.assertIn("idle_stability_required", admission["failed_checks"])

    def test_quiescent_retry_blocks_when_idle_drift_repeats(self) -> None:
        admission = build_quiescent_retry_launch_admission_packet(
            host_context_packet={"status": "ok", "executor_context": "detached_external"},
            owner_action_boundary_packet={"status": "ok"},
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": True
            },
            idle_stability_packet={
                "status": "ok",
                "final_verdict": "ACTIVE_CURRENT_CODEX_BASELINE_UNSTABLE",
            },
            declared_write_surfaces_packet={"status": "ok"},
            protected_surface_read_packet={"inspection_only": True},
        )

        self.assertEqual(admission["status"], "blocked")
        self.assertIn("idle_stability_required", admission["failed_checks"])

    def test_quiescent_retry_blocked_result_is_closed_evidence(self) -> None:
        admission = build_quiescent_retry_launch_admission_packet(
            host_context_packet={"status": "blocked", "executor_context": "protected_codex_hosted"},
            owner_action_boundary_packet={"status": "ok"},
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": False
            },
        )
        blocker = build_quiescent_retry_blocker_packet(
            launch_admission_packet=admission,
            host_context_packet={"executor_context": "protected_codex_hosted"},
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": False
            },
        )

        self.assertEqual(blocker["status"], "blocked")
        self.assertEqual(
            blocker["actual_status"],
            "NATIVE_CUSTOM_SAFETY_BLOCKED_BY_HOSTED_EXECUTOR_CONTEXT",
        )
        self.assertFalse(blocker["native_launch_attempted"])
        self.assertFalse(blocker["route_claimed"])
        self.assertFalse(blocker["ux_claimed"])
        self.assertFalse(blocker["egress_claimed"])

    def test_external_detached_handoff_command_is_bounded(self) -> None:
        repo_root = Path("/repo").resolve()
        evidence_dir = repo_root / "audit_results" / "wbp_external_EXTERNAL_2026"
        command = build_external_detached_handoff_command_packet(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
        )
        admission = build_external_detached_command_admission_packet(
            command,
            repo_root=repo_root,
        )

        self.assertEqual(admission["status"], "ok")
        self.assertEqual(command["cwd"], str(repo_root))
        self.assertIn("native_custom_quiescent_safety_retry_probe.py", command["argv"][1])
        self.assertFalse(command["command_executed"])
        self.assertFalse(command["external_result_imported"])
        self.assertFalse(admission["protected_surfaces_write_allowed"])

    def test_external_detached_handoff_rejects_wildcard_or_non_audit_evidence_dir(
        self,
    ) -> None:
        repo_root = Path("/repo").resolve()
        command = build_external_detached_handoff_command_packet(
            repo_root=repo_root,
            evidence_dir=Path("/tmp/unsafe-*"),
        )
        admission = build_external_detached_command_admission_packet(
            command,
            repo_root=repo_root,
        )

        self.assertEqual(admission["status"], "blocked")
        self.assertIn("shell_wildcards_forbidden", admission["failed_checks"])
        self.assertIn("evidence_dir_must_be_under_audit_results", admission["failed_checks"])

    def test_external_detached_handoff_operator_boundary_required(self) -> None:
        packet = build_external_detached_operator_boundary_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["owner_edits_command_allowed"])
        self.assertFalse(packet["owner_runtime_authority_edits_allowed"])
        self.assertFalse(packet["owner_prompt_allowed"])

    def test_external_detached_handoff_import_contract_required(self) -> None:
        packet = build_external_detached_import_contract_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertIn("host_context_packet.json", packet["required_packets"])
        self.assertTrue(packet["future_import_must_verify_json"])
        self.assertFalse(packet["external_result_imported_in_this_contour"])
        self.assertFalse(packet["route_claim_allowed"])

    def test_external_detached_handoff_forbids_current_thread_launch(self) -> None:
        packet = build_no_launch_from_current_thread_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["native_launch_attempted"])
        self.assertFalse(packet["filesystem_retry_attempted"])
        self.assertFalse(packet["external_command_executed"])
        self.assertFalse(packet["external_result_imported"])

    def test_external_detached_handoff_no_route_ux_egress_claim(self) -> None:
        matrix = build_external_detached_handoff_allowed_claims_matrix()

        self.assertFalse(matrix["route_claim_allowed"])
        self.assertFalse(matrix["ux_claim_allowed"])
        self.assertFalse(matrix["egress_claim_allowed"])
        self.assertFalse(matrix["native_safety_pass_claim_allowed"])
        self.assertIn("native_route_proven", matrix["forbidden_claims"])

    def test_external_detached_handoff_does_not_import_result_in_handoff_only_mode(
        self,
    ) -> None:
        repo_root = Path("/repo").resolve()
        command = build_external_detached_handoff_command_packet(
            repo_root=repo_root,
            evidence_dir=repo_root / "audit_results" / "wbp_external_EXTERNAL_2026",
        )
        admission = build_external_detached_command_admission_packet(
            command,
            repo_root=repo_root,
        )
        import_contract = build_external_detached_import_contract_packet()
        no_launch = build_no_launch_from_current_thread_packet()
        matrix = build_external_detached_handoff_allowed_claims_matrix()
        audit = build_external_detached_handoff_false_green_audit(
            command_admission_packet=admission,
            import_contract_packet=import_contract,
            no_launch_packet=no_launch,
            allowed_claims_matrix=matrix,
        )

        self.assertEqual(audit["status"], "ok")
        self.assertFalse(audit["forbidden_claims_present"])

    def test_external_detached_handoff_audit_detects_forbidden_claims(self) -> None:
        repo_root = Path("/repo").resolve()
        command = build_external_detached_handoff_command_packet(
            repo_root=repo_root,
            evidence_dir=repo_root / "audit_results" / "wbp_external_EXTERNAL_2026",
        )
        admission = build_external_detached_command_admission_packet(
            command,
            repo_root=repo_root,
        )
        import_contract = build_external_detached_import_contract_packet()
        no_launch = build_no_launch_from_current_thread_packet()
        matrix = build_external_detached_handoff_allowed_claims_matrix()
        matrix["allowed_claims"].append("native_safety_passed")
        audit = build_external_detached_handoff_false_green_audit(
            command_admission_packet=admission,
            import_contract_packet=import_contract,
            no_launch_packet=no_launch,
            allowed_claims_matrix=matrix,
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])
        self.assertIn(
            {"name": "forbidden_claims_absent", "passed": False},
            audit["checks"],
        )

    def test_external_result_import_requires_handoff_packet(self) -> None:
        repo_root = Path("/repo").resolve()
        command = build_external_detached_handoff_command_packet(
            repo_root=repo_root,
            evidence_dir=repo_root / "audit_results" / "retry_EXTERNAL_2026",
        )
        integrity = build_external_result_command_integrity_packet(
            handoff_command_packet=command,
            external_evidence_dir=repo_root / "audit_results" / "retry_EXTERNAL_2026",
            repo_root=repo_root,
        )

        self.assertEqual(integrity["status"], "ok")
        self.assertTrue(integrity["external_evidence_path_matches_handoff"])
        self.assertFalse(integrity["current_thread_executed_command"])

    def test_external_result_import_rejects_command_mismatch(self) -> None:
        repo_root = Path("/repo").resolve()
        command = build_external_detached_handoff_command_packet(
            repo_root=repo_root,
            evidence_dir=repo_root / "audit_results" / "retry_EXTERNAL_2026",
        )
        integrity = build_external_result_command_integrity_packet(
            handoff_command_packet=command,
            external_evidence_dir=repo_root / "audit_results" / "other_EXTERNAL_2026",
            repo_root=repo_root,
        )

        self.assertEqual(integrity["status"], "blocked")
        self.assertIn("external_evidence_path_mismatch", integrity["failed_checks"])

    def test_external_result_import_rejects_missing_required_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            validation = validate_external_evidence_packets(
                external_evidence_dir=root / "missing_EXTERNAL",
                required_packets=["sync_gate_packet.json", "launch_admission_packet.json"],
            )

        self.assertEqual(validation["status"], "blocked")
        self.assertEqual(validation["reason_class"], "EXTERNAL_EVIDENCE_DIR_MISSING")
        self.assertFalse(validation["json_validated"])

    def test_external_result_import_rejects_unvalidated_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            evidence = root / "evidence_EXTERNAL"
            evidence.mkdir()
            (evidence / "sync_gate_packet.json").write_text("{", encoding="utf-8")
            validation = validate_external_evidence_packets(
                external_evidence_dir=evidence,
                required_packets=["sync_gate_packet.json"],
            )

        self.assertEqual(validation["status"], "blocked")
        self.assertEqual(validation["reason_class"], "INVALID_EXTERNAL_PACKET_JSON")
        self.assertIn("sync_gate_packet.json", validation["invalid_json_packets"])

    def test_external_result_import_requires_secret_scan(self) -> None:
        packet = build_external_result_secret_scan_packet(
            external_evidence_dir=Path("/repo/audit_results/evidence_EXTERNAL"),
            matches=["secret-like-token"],
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["raw_secrets_found"])

    def test_external_result_import_does_not_claim_route_ux_egress(self) -> None:
        matrix = build_import_allowed_claims_matrix()
        layer = build_layer_separation_packet()

        self.assertFalse(matrix["route_claim_allowed"])
        self.assertFalse(matrix["ux_claim_allowed"])
        self.assertFalse(matrix["egress_claim_allowed"])
        self.assertFalse(layer["route_claim_allowed"])
        self.assertIn("NATIVE_ROUTING_PROVEN", matrix["forbidden_claims"])

    def test_external_result_import_does_not_treat_keychain_as_auth_proof(self) -> None:
        packet = build_keychain_boundary_packet(
            keychain_packet={
                "machine_prompt_observed": True,
                "owner_pressed_cancel": True,
            }
        )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["keychain_observation_treated_as_auth_proof"])

    def test_external_result_import_classifies_blocked_not_pass(self) -> None:
        classification = classify_native_safety_retry_import(
            command_integrity_packet={"status": "ok"},
            validation_packet={"status": "blocked", "parsed_packets": {}},
            secret_scan_packet={"status": "ok"},
            protected_surface_summary_packet={"status": "blocked"},
            keychain_boundary_packet={"status": "ok"},
        )

        self.assertEqual(classification["status"], "blocked")
        self.assertEqual(
            classification["final_status"],
            "NATIVE_CUSTOM_FILESYSTEM_SAFETY_IMPORT_BLOCKED",
        )
        self.assertFalse(classification["route_claimed"])

    def test_external_result_import_audit_detects_forbidden_classification_claims(
        self,
    ) -> None:
        classification = classify_native_safety_retry_import(
            command_integrity_packet={"status": "ok"},
            validation_packet={"status": "ok", "parsed_packets": {}},
            secret_scan_packet={"status": "ok"},
            protected_surface_summary_packet={"status": "ok"},
            keychain_boundary_packet={"status": "ok"},
        )
        classification["route_claimed"] = True
        audit = build_native_safety_import_false_green_audit(
            execution_ownership_packet=build_external_result_execution_ownership_packet(),
            command_integrity_packet={"status": "ok"},
            validation_packet={"status": "ok"},
            secret_scan_packet={"status": "ok"},
            classification_packet=classification,
            allowed_claims_matrix=build_import_allowed_claims_matrix(),
            layer_separation_packet=build_layer_separation_packet(),
            keychain_boundary_packet=build_keychain_boundary_packet(
                keychain_packet={}
            ),
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])
        self.assertIn(
            {"name": "forbidden_claims_absent", "passed": False},
            audit["checks"],
        )

    def test_external_result_import_pass_requires_protected_surface_diff(self) -> None:
        validation = {
            "status": "ok",
            "parsed_packets": {
                "launch_admission_packet.json": {"native_launch_admitted": True},
                "native_safety_false_green_audit.json": {"status": "ok"},
            },
        }
        protected = build_protected_surface_import_summary(
            validation_packet=validation,
        )
        classification = classify_native_safety_retry_import(
            command_integrity_packet={"status": "ok"},
            validation_packet=validation,
            secret_scan_packet={"status": "ok"},
            protected_surface_summary_packet=protected,
            keychain_boundary_packet={"status": "ok"},
        )

        self.assertEqual(protected["status"], "blocked")
        self.assertIn(
            "protected_surface_import_summary_required",
            classification["failed_checks"],
        )

    def test_external_result_import_pass_requires_cleanup_packet(self) -> None:
        classification = classify_native_safety_retry_import(
            command_integrity_packet={"status": "ok"},
            validation_packet={
                "status": "ok",
                "parsed_packets": {
                    "launch_admission_packet.json": {"native_launch_admitted": True},
                    "cleanup_reversibility_packet.json": {"tmp_root_removed": False},
                    "native_safety_false_green_audit.json": {"status": "ok"},
                },
            },
            secret_scan_packet={"status": "ok"},
            protected_surface_summary_packet={"status": "ok"},
            keychain_boundary_packet={"status": "ok"},
        )

        self.assertEqual(classification["status"], "blocked")
        self.assertIn("cleanup_reversibility_required", classification["failed_checks"])

    def test_native_safety_import_false_green_blocks_overclaim_layers(self) -> None:
        audit = build_native_safety_import_false_green_audit(
            execution_ownership_packet=build_external_result_execution_ownership_packet(),
            command_integrity_packet={"status": "ok"},
            validation_packet={"status": "blocked"},
            secret_scan_packet={"status": "ok"},
            classification_packet={
                "status": "blocked",
                "final_status": "NATIVE_CUSTOM_FILESYSTEM_SAFETY_IMPORT_BLOCKED",
            },
            allowed_claims_matrix=build_import_allowed_claims_matrix(),
            layer_separation_packet=build_layer_separation_packet(),
            keychain_boundary_packet=build_keychain_boundary_packet(),
        )

        self.assertEqual(audit["status"], "ok")
        self.assertFalse(audit["forbidden_claims_present"])

    def test_external_result_import_packet_reflects_blocked_validation(self) -> None:
        packet = build_external_result_import_packet(
            validation_packet={
                "status": "blocked",
                "external_evidence_dir": "/repo/audit_results/missing_EXTERNAL",
            },
            classification_packet={
                "status": "blocked",
                "final_status": "NATIVE_CUSTOM_FILESYSTEM_SAFETY_IMPORT_BLOCKED",
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["external_result_imported"])

    def test_external_result_import_packet_blocks_when_classification_blocks(self) -> None:
        packet = build_external_result_import_packet(
            validation_packet={
                "status": "ok",
                "external_evidence_dir": "/repo/audit_results/present_EXTERNAL",
            },
            classification_packet={
                "status": "blocked",
                "final_status": "NATIVE_CUSTOM_FILESYSTEM_SAFETY_IMPORT_BLOCKED",
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["external_evidence_json_loaded"])
        self.assertFalse(packet["external_result_imported"])

    def test_external_result_import_probe_entrypoint_emits_blocked_packets(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "native_custom_external_result_import_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=temp_repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            (temp_repo / "README.md").write_text("fixture\n", encoding="utf-8")
            (temp_repo / "audit_results").mkdir()
            (temp_repo / "audit_results" / ".gitkeep").write_text("", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=temp_repo, check=True)
            subprocess.run(["git", "add", "audit_results/.gitkeep"], cwd=temp_repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            handoff_dir = temp_repo / "handoff"
            handoff_dir.mkdir()
            external_evidence = (
                temp_repo / "audit_results" / "retry_EXTERNAL_missing"
            )
            evidence_dir = temp_repo / "audit_results" / "import_result"
            command = build_external_detached_handoff_command_packet(
                repo_root=temp_repo,
                evidence_dir=external_evidence,
            )
            (handoff_dir / "external_detached_command_packet.json").write_text(
                json.dumps(command),
                encoding="utf-8",
            )
            (handoff_dir / "evidence_import_contract_packet.json").write_text(
                json.dumps(
                    build_external_detached_import_contract_packet(
                        required_packets=[
                            "sync_gate_packet.json",
                            "launch_admission_packet.json",
                        ]
                    )
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--handoff-dir",
                    str(handoff_dir),
                    "--external-evidence-dir",
                    str(external_evidence),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            summary = json.loads((evidence_dir / "import_summary_packet.json").read_text())
            validation = json.loads(
                (evidence_dir / "external_evidence_validation_packet.json").read_text()
            )
            false_green = json.loads(
                (evidence_dir / "native_safety_import_false_green_audit.json").read_text()
            )
            self.assertEqual(
                summary["final_status"],
                "NATIVE_CUSTOM_FILESYSTEM_SAFETY_IMPORT_BLOCKED",
            )
            self.assertFalse(summary["current_thread_external_command_executed"])
            self.assertFalse(summary["current_thread_native_launch_attempted"])
            self.assertFalse(summary["external_result_imported"])
            self.assertEqual(validation["reason_class"], "EXTERNAL_EVIDENCE_DIR_MISSING")
            self.assertEqual(false_green["status"], "ok")

    def test_external_execution_scope_forbids_safety_import(self) -> None:
        packet = build_external_execution_scope_boundary_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["safety_result_imported"])
        self.assertFalse(packet["filesystem_safety_classified"])
        self.assertFalse(packet["native_safety_pass_claimed"])

    def test_external_execution_command_verification_requires_handoff_packet(self) -> None:
        repo_root = Path("/repo").resolve()
        evidence_dir = repo_root / "audit_results" / "retry_EXTERNAL_2026"
        command = build_external_detached_handoff_command_packet(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
        )
        packet = build_external_execution_command_verification_packet(
            handoff_command_packet=command,
            external_evidence_dir=evidence_dir,
            repo_root=repo_root,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["command_executed_in_current_thread"])
        self.assertTrue(packet["external_evidence_path_matches_handoff"])

    def test_external_execution_command_verification_rejects_mismatch(self) -> None:
        repo_root = Path("/repo").resolve()
        command = build_external_detached_handoff_command_packet(
            repo_root=repo_root,
            evidence_dir=repo_root / "audit_results" / "retry_EXTERNAL_2026",
        )
        packet = build_external_execution_command_verification_packet(
            handoff_command_packet=command,
            external_evidence_dir=repo_root / "audit_results" / "other_EXTERNAL_2026",
            repo_root=repo_root,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("external_evidence_path_mismatch", packet["failed_checks"])

    def test_external_execution_presence_classifies_missing_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            packet = build_external_evidence_presence_packet(
                external_evidence_dir=Path(tmpdir) / "missing_EXTERNAL",
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["classification"], "evidence_dir_missing")
        self.assertFalse(packet["filesystem_safety_classified"])

    def test_external_execution_presence_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence = Path(tmpdir) / "evidence_EXTERNAL"
            evidence.mkdir()
            for name in [
                "sync_gate_packet.json",
                "historical_dirt_quarantine_packet.json",
                "version_pinning_packet.json",
                "host_context_packet.json",
                "owner_action_boundary_packet.json",
                "current_codex_running_state_initial.json",
                "quiescent_current_codex_precondition_packet.json",
                "pre_custom_idle_stability_packet.json",
                "launch_admission_packet.json",
                "allowed_claims_matrix.json",
                "native_safety_false_green_audit.json",
                "native_safety_blocker_packet.json",
            ]:
                (evidence / name).write_text("{}", encoding="utf-8")
            (evidence / "sync_gate_packet.json").write_text("{", encoding="utf-8")
            packet = build_external_evidence_presence_packet(
                external_evidence_dir=evidence,
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["classification"], "evidence_present_but_invalid_json")
        self.assertIn("sync_gate_packet.json", packet["invalid_json_packets"])

    def test_external_execution_result_does_not_classify_safety(self) -> None:
        presence = {
            "status": "blocked",
            "classification": "evidence_dir_missing",
            "external_evidence_dir": "/repo/audit_results/missing_EXTERNAL",
            "external_evidence_dir_exists": False,
        }
        result = build_external_execution_result_packet(
            command_verification_packet={"status": "ok"},
            evidence_presence_packet=presence,
            secret_scan_packet={"status": "ok"},
        )

        self.assertEqual(
            result["final_status"],
            "EXTERNAL_NATIVE_SAFETY_EXECUTION_NO_EVIDENCE_PRODUCED",
        )
        self.assertFalse(result["filesystem_safety_classified"])
        self.assertFalse(result["native_safety_pass_claimed"])

    def test_external_execution_false_green_blocks_safety_claim(self) -> None:
        scope = build_external_execution_scope_boundary_packet()
        observation = build_external_execution_observation_packet(shell_command="echo test")
        result = build_external_execution_result_packet(
            command_verification_packet={"status": "ok"},
            evidence_presence_packet={
                "status": "blocked",
                "classification": "evidence_dir_missing",
                "external_evidence_dir_exists": False,
            },
            secret_scan_packet={"status": "ok", "secret_scan_performed": True},
        )
        audit = build_external_execution_false_green_audit(
            scope_boundary_packet=scope,
            command_verification_packet={"status": "ok"},
            owner_boundary_packet=build_owner_execution_boundary_packet(),
            observation_packet=observation,
            evidence_presence_packet={"classification": "evidence_dir_missing"},
            secret_scan_packet={"secret_scan_performed": True},
            result_packet=result,
            layer_separation_packet={"status": "ok"},
        )

        self.assertEqual(audit["status"], "ok")
        self.assertFalse(audit["forbidden_claims_present"])

    def test_external_execution_false_green_blocks_route_ux_egress_claim(self) -> None:
        result = build_external_execution_result_packet(
            command_verification_packet={"status": "ok"},
            evidence_presence_packet={
                "status": "blocked",
                "classification": "evidence_dir_missing",
                "external_evidence_dir_exists": False,
            },
            secret_scan_packet={"status": "ok"},
        )
        result["routing_claimed"] = True
        audit = build_external_execution_false_green_audit(
            scope_boundary_packet=build_external_execution_scope_boundary_packet(),
            command_verification_packet={"status": "ok"},
            owner_boundary_packet=build_owner_execution_boundary_packet(),
            observation_packet=build_external_execution_observation_packet(
                shell_command="echo test"
            ),
            evidence_presence_packet={"classification": "evidence_dir_missing"},
            secret_scan_packet={"secret_scan_performed": True},
            result_packet=result,
            layer_separation_packet={"status": "ok"},
        )

        self.assertEqual(audit["status"], "blocked")

    def test_external_execution_probe_entrypoint_no_owner_run_blocks_or_no_evidence(
        self,
    ) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "native_custom_external_execution_evidence_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=temp_repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            (temp_repo / "README.md").write_text("fixture\n", encoding="utf-8")
            (temp_repo / "audit_results").mkdir()
            (temp_repo / "audit_results" / ".gitkeep").write_text("", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=temp_repo, check=True)
            subprocess.run(["git", "add", "audit_results/.gitkeep"], cwd=temp_repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            external_evidence = temp_repo / "audit_results" / "retry_EXTERNAL_missing"
            handoff_packet = temp_repo / "external_detached_command_packet.json"
            evidence_dir = temp_repo / "audit_results" / "execution_result"
            command = build_external_detached_handoff_command_packet(
                repo_root=temp_repo,
                evidence_dir=external_evidence,
            )
            handoff_packet.write_text(json.dumps(command), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--handoff-command-packet",
                    str(handoff_packet),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            summary = json.loads(
                (evidence_dir / "external_execution_summary_packet.json").read_text()
            )
            scope = json.loads(
                (evidence_dir / "execution_scope_boundary_packet.json").read_text()
            )
            presence = json.loads(
                (evidence_dir / "external_evidence_presence_packet.json").read_text()
            )
            false_green = json.loads(
                (evidence_dir / "external_execution_false_green_audit.json").read_text()
            )
            self.assertEqual(
                summary["final_status"],
                "EXTERNAL_NATIVE_SAFETY_EXECUTION_NO_EVIDENCE_PRODUCED",
            )
            self.assertFalse(summary["current_thread_executed_command"])
            self.assertFalse(summary["native_launch_from_current_thread"])
            self.assertFalse(summary["safety_result_imported"])
            self.assertFalse(scope["filesystem_safety_classified"])
            self.assertEqual(presence["classification"], "evidence_dir_missing")
            self.assertEqual(false_green["status"], "ok")

    def test_owner_execution_command_reverification_requires_handoff_packet(self) -> None:
        repo_root = Path("/repo").resolve()
        evidence_dir = repo_root / "audit_results" / "retry_EXTERNAL_2026"
        command = build_external_detached_handoff_command_packet(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
        )
        packet = build_owner_command_reverification_packet(
            handoff_command_packet=command,
            expected_shell_command=command["shell_command"],
            external_evidence_dir=evidence_dir,
            repo_root=repo_root,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["shell_command_matches_expected"])
        self.assertFalse(packet["command_executed_in_current_thread"])

    def test_owner_execution_command_reverification_rejects_mismatch(self) -> None:
        repo_root = Path("/repo").resolve()
        evidence_dir = repo_root / "audit_results" / "retry_EXTERNAL_2026"
        command = build_external_detached_handoff_command_packet(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
        )
        packet = build_owner_command_reverification_packet(
            handoff_command_packet=command,
            expected_shell_command="echo edited",
            external_evidence_dir=evidence_dir,
            repo_root=repo_root,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("shell_command_mismatch", packet["failed_checks"])

    def test_owner_execution_observation_does_not_use_exit_code_as_proof(self) -> None:
        packet = build_owner_execution_observation_packet(
            owner_reported_execution=True,
            owner_reported_exit_code=0,
            owner_reported_output_summary="done",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["owner_report_is_not_packet_truth"])
        self.assertFalse(packet["exit_code_used_as_proof"])

    def test_owner_execution_presence_classifies_missing_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            packet = build_external_evidence_presence_packet(
                external_evidence_dir=Path(tmpdir) / "missing_EXTERNAL",
            )

        self.assertEqual(packet["classification"], "evidence_dir_missing")

    def test_owner_execution_presence_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence = Path(tmpdir) / "evidence_EXTERNAL"
            evidence.mkdir()
            for name in [
                "sync_gate_packet.json",
                "historical_dirt_quarantine_packet.json",
                "version_pinning_packet.json",
                "host_context_packet.json",
                "owner_action_boundary_packet.json",
                "current_codex_running_state_initial.json",
                "quiescent_current_codex_precondition_packet.json",
                "pre_custom_idle_stability_packet.json",
                "launch_admission_packet.json",
                "allowed_claims_matrix.json",
                "native_safety_false_green_audit.json",
                "native_safety_blocker_packet.json",
            ]:
                (evidence / name).write_text("{}", encoding="utf-8")
            (evidence / "launch_admission_packet.json").write_text("{", encoding="utf-8")

            packet = build_external_evidence_presence_packet(external_evidence_dir=evidence)

        self.assertEqual(packet["classification"], "evidence_present_but_invalid_json")
        self.assertIn("launch_admission_packet.json", packet["invalid_json_packets"])

    def test_owner_execution_minimal_json_rejects_missing_required_packets(self) -> None:
        packet = build_external_execution_minimal_json_packet(
            evidence_presence_packet={
                "status": "blocked",
                "classification": "evidence_present_but_required_packets_missing",
                "external_evidence_dir_exists": True,
                "missing_packets": ["launch_admission_packet.json"],
                "invalid_json_packets": [],
                "json_parse_check_completed": True,
            }
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["required_packets_present"])
        self.assertIn("launch_admission_packet.json", packet["missing_packets"])

    def test_owner_execution_no_safety_interpretation_required(self) -> None:
        packet = build_no_safety_interpretation_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["safety_interpreted"])
        self.assertFalse(packet["protected_surface_interpreted"])
        self.assertFalse(packet["launch_admission_interpreted"])
        self.assertFalse(packet["exit_code_used_as_proof"])

    def test_owner_execution_result_does_not_classify_safety(self) -> None:
        result = build_owner_external_execution_result_packet(
            command_reverification_packet={"status": "ok"},
            owner_attestation_packet={"owner_reported_execution": False},
            evidence_presence_packet={
                "classification": "evidence_dir_missing",
                "external_evidence_dir_exists": False,
            },
            minimal_json_packet={"status": "blocked"},
            secret_scan_packet={"status": "ok"},
            no_safety_interpretation_packet=build_no_safety_interpretation_packet(),
        )

        self.assertEqual(
            result["final_status"],
            "OWNER_EXTERNAL_EXECUTION_NO_EVIDENCE_PRODUCED",
        )
        self.assertFalse(result["owner_external_execution_evidence_produced"])
        self.assertFalse(result["safety_interpreted"])
        self.assertFalse(result["native_safety_pass_claimed"])

    def test_owner_execution_evidence_produced_requires_owner_attestation(self) -> None:
        result = build_owner_external_execution_result_packet(
            command_reverification_packet={"status": "ok"},
            owner_attestation_packet={"owner_reported_execution": False},
            evidence_presence_packet={
                "status": "ok",
                "classification": "evidence_dir_present",
                "external_evidence_dir_exists": True,
            },
            minimal_json_packet={"status": "ok"},
            secret_scan_packet={"status": "ok"},
            no_safety_interpretation_packet=build_no_safety_interpretation_packet(),
        )

        self.assertEqual(
            result["final_status"],
            "OWNER_EXTERNAL_EXECUTION_BLOCKED_WITH_PACKET_TRUTH",
        )
        self.assertFalse(result["owner_external_execution_evidence_produced"])
        self.assertTrue(result["owner_attestation_required_for_evidence_produced"])

    def test_owner_execution_result_records_valid_evidence_produced(self) -> None:
        result = build_owner_external_execution_result_packet(
            command_reverification_packet={"status": "ok"},
            owner_attestation_packet={"owner_reported_execution": True},
            evidence_presence_packet={
                "status": "ok",
                "classification": "evidence_dir_present",
                "external_evidence_dir_exists": True,
            },
            minimal_json_packet={"status": "ok"},
            secret_scan_packet={"status": "ok"},
            no_safety_interpretation_packet=build_no_safety_interpretation_packet(),
        )

        self.assertEqual(
            result["final_status"],
            "OWNER_EXTERNAL_EXECUTION_EVIDENCE_PRODUCED",
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["owner_external_execution_evidence_produced"])
        self.assertFalse(result["native_safety_pass_claimed"])

    def test_owner_execution_result_blocks_secret_scan_failure(self) -> None:
        result = build_owner_external_execution_result_packet(
            command_reverification_packet={"status": "ok"},
            owner_attestation_packet={"owner_reported_execution": True},
            evidence_presence_packet={
                "status": "ok",
                "classification": "evidence_dir_present",
                "external_evidence_dir_exists": True,
            },
            minimal_json_packet={"status": "ok"},
            secret_scan_packet={"status": "blocked"},
            no_safety_interpretation_packet=build_no_safety_interpretation_packet(),
        )

        self.assertEqual(
            result["final_status"],
            "OWNER_EXTERNAL_EXECUTION_BLOCKED_WITH_PACKET_TRUTH",
        )
        self.assertFalse(result["owner_external_execution_evidence_produced"])

    def test_owner_execution_false_green_blocks_produced_without_owner_report(self) -> None:
        result = build_owner_external_execution_result_packet(
            command_reverification_packet={"status": "ok"},
            owner_attestation_packet={"owner_reported_execution": True},
            evidence_presence_packet={
                "status": "ok",
                "classification": "evidence_dir_present",
                "external_evidence_dir_exists": True,
            },
            minimal_json_packet={"status": "ok"},
            secret_scan_packet={"status": "ok"},
            no_safety_interpretation_packet=build_no_safety_interpretation_packet(),
        )
        audit = build_owner_execution_false_green_audit(
            current_thread_boundary_packet=build_current_thread_boundary_packet(),
            command_reverification_packet={"status": "ok"},
            owner_attestation_packet=build_owner_execution_attestation_packet(
                owner_reported_execution=False
            ),
            owner_observation_packet=build_owner_execution_observation_packet(
                owner_reported_execution=False
            ),
            evidence_presence_packet={"classification": "evidence_dir_present"},
            minimal_json_packet={"json_parse_check_completed": True},
            secret_scan_packet={"secret_scan_performed": True},
            no_safety_interpretation_packet=build_no_safety_interpretation_packet(),
            result_packet=result,
            layer_separation_packet=build_owner_execution_layer_separation_packet(),
        )

        self.assertEqual(audit["status"], "blocked")

    def test_owner_execution_false_green_blocks_safety_claim(self) -> None:
        result = build_owner_external_execution_result_packet(
            command_reverification_packet={"status": "ok"},
            owner_attestation_packet={"owner_reported_execution": True},
            evidence_presence_packet={
                "classification": "evidence_dir_missing",
                "external_evidence_dir_exists": False,
            },
            minimal_json_packet={"status": "blocked"},
            secret_scan_packet={"status": "ok"},
            no_safety_interpretation_packet=build_no_safety_interpretation_packet(),
        )
        audit = build_owner_execution_false_green_audit(
            current_thread_boundary_packet=build_current_thread_boundary_packet(),
            command_reverification_packet={"status": "ok"},
            owner_attestation_packet=build_owner_execution_attestation_packet(
                owner_reported_execution=True
            ),
            owner_observation_packet=build_owner_execution_observation_packet(
                owner_reported_execution=True,
                owner_reported_exit_code=0,
            ),
            evidence_presence_packet={"classification": "evidence_dir_missing"},
            minimal_json_packet={"json_parse_check_completed": False},
            secret_scan_packet={"secret_scan_performed": True},
            no_safety_interpretation_packet=build_no_safety_interpretation_packet(),
            result_packet=result,
            layer_separation_packet=build_owner_execution_layer_separation_packet(),
        )

        self.assertEqual(audit["status"], "ok")
        self.assertFalse(audit["forbidden_claims_present"])

    def test_owner_execution_false_green_blocks_route_ux_egress_claim(self) -> None:
        result = build_owner_external_execution_result_packet(
            command_reverification_packet={"status": "ok"},
            owner_attestation_packet={"owner_reported_execution": True},
            evidence_presence_packet={
                "classification": "evidence_dir_missing",
                "external_evidence_dir_exists": False,
            },
            minimal_json_packet={"status": "blocked"},
            secret_scan_packet={"status": "ok"},
            no_safety_interpretation_packet=build_no_safety_interpretation_packet(),
        )
        result["ux_claimed"] = True
        audit = build_owner_execution_false_green_audit(
            current_thread_boundary_packet=build_current_thread_boundary_packet(),
            command_reverification_packet={"status": "ok"},
            owner_attestation_packet=build_owner_execution_attestation_packet(
                owner_reported_execution=True
            ),
            owner_observation_packet=build_owner_execution_observation_packet(
                owner_reported_execution=True
            ),
            evidence_presence_packet={"classification": "evidence_dir_missing"},
            minimal_json_packet={"json_parse_check_completed": False},
            secret_scan_packet={"secret_scan_performed": True},
            no_safety_interpretation_packet=build_no_safety_interpretation_packet(),
            result_packet=result,
            layer_separation_packet=build_owner_execution_layer_separation_packet(),
        )

        self.assertEqual(audit["status"], "blocked")

    def test_owner_execution_probe_entrypoint_no_evidence_blocks(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "native_custom_owner_external_terminal_execution_probe.py"
        with tempfile.TemporaryDirectory(
            dir=repo_root / "audit_results",
            prefix="owner_execution_test_",
        ) as tmpdir:
            evidence_dir = Path(tmpdir) / "owner_execution_result"
            handoff_packet = Path(tmpdir) / "external_detached_command_packet.json"
            command = {
                "argv": [
                    "python3",
                    "/Volumes/Work/wild-boar-proxy/tools/native_custom_quiescent_safety_retry_probe.py",
                    "--repo-root",
                    "/Volumes/Work/wild-boar-proxy",
                    "--evidence-dir",
                    "/Volumes/Work/wild-boar-proxy/audit_results/wbp_native_custom_quiescent_safety_retry_EXTERNAL_2026-05-26T000000Z",
                ],
                "command_executed": False,
                "cwd": "/Volumes/Work/wild-boar-proxy",
                "evidence_dir": (
                    "/Volumes/Work/wild-boar-proxy/audit_results/"
                    "wbp_native_custom_quiescent_safety_retry_EXTERNAL_2026-05-26T000000Z"
                ),
                "external_result_imported": False,
                "native_launch_attempted_from_current_thread": False,
                "packet_kind": "external_detached_command",
                "shell_command": (
                "cd /Volumes/Work/wild-boar-proxy && python3 "
                "/Volumes/Work/wild-boar-proxy/tools/native_custom_quiescent_safety_retry_probe.py "
                "--repo-root /Volumes/Work/wild-boar-proxy "
                "--evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/"
                "wbp_native_custom_quiescent_safety_retry_EXTERNAL_2026-05-26T000000Z"
                ),
                "status": "ok",
                "target_tool": (
                    "/Volumes/Work/wild-boar-proxy/tools/"
                    "native_custom_quiescent_safety_retry_probe.py"
                ),
            }
            handoff_packet.write_text(json.dumps(command), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(repo_root),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--handoff-command-packet",
                    str(handoff_packet),
                    "--owner-reported-execution",
                    "--owner-reported-exit-code",
                    "0",
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (evidence_dir / "owner_execution_summary_packet.json").read_text()
            )
            no_safety = json.loads(
                (evidence_dir / "no_safety_interpretation_packet.json").read_text()
            )
            false_green = json.loads(
                (evidence_dir / "owner_execution_false_green_audit.json").read_text()
            )
            self.assertEqual(
                summary["final_status"],
                "OWNER_EXTERNAL_EXECUTION_NO_EVIDENCE_PRODUCED",
            )
            self.assertTrue(summary["owner_reported_execution"])
            self.assertFalse(summary["safety_interpreted"])
            self.assertFalse(summary["protected_surface_interpreted"])
            self.assertFalse(summary["exit_code_used_as_proof"])
            self.assertFalse(no_safety["launch_admission_interpreted"])
            self.assertEqual(false_green["status"], "ok")

    def test_owner_execution_probe_rejects_missing_handoff_without_traceback(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "native_custom_owner_external_terminal_execution_probe.py"
        with tempfile.TemporaryDirectory(
            dir=repo_root / "audit_results",
            prefix="owner_execution_test_",
        ) as tmpdir:
            evidence_dir = Path(tmpdir) / "owner_execution_result"
            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(repo_root),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--handoff-command-packet",
                    str(Path(tmpdir) / "missing.json"),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            packet = json.loads(result.stderr)
            self.assertEqual(packet["reason_class"], "HANDOFF_COMMAND_PACKET_MISSING")
            self.assertFalse(packet["traceback_emitted"])
            written = json.loads((evidence_dir / "input_error_packet.json").read_text())
            self.assertEqual(written["reason_class"], "HANDOFF_COMMAND_PACKET_MISSING")

    def test_owner_execution_probe_rejects_evidence_dir_outside_repo_without_traceback(
        self,
    ) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "native_custom_owner_external_terminal_execution_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(repo_root),
                    "--evidence-dir",
                    str(Path(tmpdir) / "outside_repo"),
                    "--handoff-command-packet",
                    str(
                        repo_root
                        / "audit_results/wbp_native_custom_external_detached_execution_handoff_2026-05-26/external_detached_command_packet.json"
                    ),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            packet = json.loads(result.stderr)
            self.assertEqual(packet["reason_class"], "EVIDENCE_DIR_OUTSIDE_REPO")
            self.assertFalse(packet["traceback_emitted"])
            self.assertNotIn("Traceback", result.stderr)

    def test_owner_ux_two_lane_success_requires_owner_and_trace(self) -> None:
        waiver = build_machine_ui_waiver_packet(owner_waives_machine_ui=True)
        nonce = build_owner_nonce_prompt_packet(nonce="nonce-123")
        ux = build_owner_manual_ux_check_packet(
            owner_saw_window=True,
            owner_typed_prompt=True,
            owner_saw_response=True,
            machine_ui_waiver_packet=waiver,
        )
        trace = build_wbp_trace_observation_packet(
            trace_packet={
                "request_observed": True,
                "response_observed": True,
                "forwarded_to_wbp": True,
                "path": "/v1/responses",
                "upstream_status": 200,
                "request_body_sha256": "request-hash",
                "response_body_sha256": "response-hash",
                "prompt_body_recorded": False,
                "auth_header_recorded": False,
                "secret_value_recorded": False,
            }
        )
        route = build_native_route_trace_binding_packet(
            owner_nonce_prompt_packet=nonce,
            wbp_trace_observation_packet=trace,
        )
        matrix = build_two_lane_result_matrix(
            owner_manual_ux_check_packet=ux,
            route_trace_binding_packet=route,
            wbp_trace_observation_packet=trace,
        )

        self.assertEqual(ux["ux_status"], "confirmed")
        self.assertEqual(trace["route_status"], "confirmed")
        self.assertTrue(route["route_trace_bound"])
        self.assertEqual(
            matrix["final_status"],
            "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABLE_WITH_OWNER_CONFIRMATION",
        )
        self.assertFalse(matrix["machine_ui_proof_claimed"])
        self.assertFalse(matrix["filesystem_safety_claimed"])

    def test_owner_ux_two_lane_owner_confirmation_does_not_replace_trace(self) -> None:
        waiver = build_machine_ui_waiver_packet(owner_waives_machine_ui=True)
        nonce = build_owner_nonce_prompt_packet(nonce="nonce-123")
        ux = build_owner_manual_ux_check_packet(
            owner_saw_window=True,
            owner_typed_prompt=True,
            owner_saw_response=True,
            machine_ui_waiver_packet=waiver,
        )
        trace = build_wbp_trace_observation_packet(trace_packet=None)
        route = build_native_route_trace_binding_packet(
            owner_nonce_prompt_packet=nonce,
            wbp_trace_observation_packet=trace,
        )
        matrix = build_two_lane_result_matrix(
            owner_manual_ux_check_packet=ux,
            route_trace_binding_packet=route,
            wbp_trace_observation_packet=trace,
        )

        self.assertEqual(trace["route_status"], "missing")
        self.assertFalse(route["route_trace_bound"])
        self.assertEqual(matrix["final_status"], "OWNER_UX_CONFIRMED_ROUTE_UNPROVEN")

    def test_owner_ux_two_lane_trace_does_not_replace_owner_ux(self) -> None:
        waiver = build_machine_ui_waiver_packet(owner_waives_machine_ui=True)
        nonce = build_owner_nonce_prompt_packet(nonce="nonce-123")
        ux = build_owner_manual_ux_check_packet(
            owner_saw_window=True,
            owner_typed_prompt=True,
            owner_saw_response=False,
            machine_ui_waiver_packet=waiver,
        )
        trace = build_wbp_trace_observation_packet(
            trace_packet={
                "request_observed": True,
                "response_observed": True,
                "forwarded_to_wbp": True,
                "path": "/v1/responses",
                "upstream_status": 200,
                "response_body_sha256": "response-hash",
                "prompt_body_recorded": False,
                "auth_header_recorded": False,
                "secret_value_recorded": False,
            }
        )
        route = build_native_route_trace_binding_packet(
            owner_nonce_prompt_packet=nonce,
            wbp_trace_observation_packet=trace,
        )
        matrix = build_two_lane_result_matrix(
            owner_manual_ux_check_packet=ux,
            route_trace_binding_packet=route,
            wbp_trace_observation_packet=trace,
        )

        self.assertEqual(ux["ux_status"], "blocked_no_visible_response")
        self.assertEqual(trace["route_status"], "confirmed")
        self.assertEqual(matrix["final_status"], "ROUTE_CONFIRMED_OWNER_UX_UNCONFIRMED")

    def test_owner_ux_false_green_blocks_raw_prompt_or_auth(self) -> None:
        waiver = build_machine_ui_waiver_packet(owner_waives_machine_ui=True)
        ux = build_owner_manual_ux_check_packet(
            owner_saw_window=True,
            owner_typed_prompt=True,
            owner_saw_response=True,
            machine_ui_waiver_packet=waiver,
        )
        trace = build_wbp_trace_observation_packet(
            trace_packet={
                "request_observed": True,
                "response_observed": True,
                "forwarded_to_wbp": True,
                "path": "/v1/responses",
                "prompt_body_recorded": True,
                "auth_header_recorded": False,
                "secret_value_recorded": False,
            }
        )
        matrix = build_two_lane_result_matrix(
            owner_manual_ux_check_packet=ux,
            route_trace_binding_packet={"route_trace_bound": False},
            wbp_trace_observation_packet=trace,
        )
        audit = build_native_owner_ux_false_green_audit(
            machine_ui_waiver_packet=waiver,
            owner_manual_ux_check_packet=ux,
            wbp_trace_observation_packet=trace,
            two_lane_result_matrix=matrix,
        )

        self.assertEqual(trace["route_status"], "blocked_secret_risk")
        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])

    def test_owner_ux_action_boundary_allows_only_specified_prompt(self) -> None:
        packet = build_owner_ux_action_boundary_packet(
            owner_typed_specified_prompt=True,
            runtime_authority_edited=False,
            provider_or_model_authority_edited=False,
            hidden_cleanup_performed=False,
        )
        violated = build_owner_ux_action_boundary_packet(
            owner_typed_specified_prompt=True,
            provider_or_model_authority_edited=True,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["owner_prompt_action_allowed"])
        self.assertFalse(packet["owner_prompt_action_grants_route_claim"])
        self.assertEqual(violated["status"], "blocked")

    def test_owner_ux_route_blocks_model_failure_without_secret_leak(self) -> None:
        waiver = build_machine_ui_waiver_packet(owner_waives_machine_ui=True)
        nonce = build_owner_nonce_prompt_packet(nonce="nonce-123")
        ux = build_owner_manual_ux_check_packet(
            owner_saw_window=True,
            owner_typed_prompt=True,
            owner_saw_response=True,
            machine_ui_waiver_packet=waiver,
        )
        trace = build_wbp_trace_observation_packet(
            trace_packet={
                "request_observed": True,
                "response_observed": True,
                "forwarded_to_wbp": True,
                "path": "/v1/responses",
                "upstream_status": 503,
                "request_body_sha256": "request-hash",
                "response_body_sha256": "response-hash",
                "prompt_body_recorded": False,
                "auth_header_recorded": False,
                "secret_value_recorded": False,
            }
        )
        route = build_native_route_trace_binding_packet(
            owner_nonce_prompt_packet=nonce,
            wbp_trace_observation_packet=trace,
        )
        matrix = build_two_lane_result_matrix(
            owner_manual_ux_check_packet=ux,
            route_trace_binding_packet=route,
            wbp_trace_observation_packet=trace,
        )

        self.assertEqual(trace["route_status"], "blocked_model_failure")
        self.assertEqual(matrix["final_status"], "OWNER_UX_ROUTE_BLOCKED_MODEL_FAILURE")
        self.assertFalse(matrix["route_trace_confirmed"])

    def test_owner_ux_historical_import_separates_observation_from_fresh_proof(self) -> None:
        imported = build_owner_historical_observation_import_packet(
            owner_confirmation_text=(
                "вижу ответ, конфиг/модель/роут не трогал, hidden cleanup не делал"
            ),
            owner_reported_agent_answered=True,
            owner_reported_config_model_route_untouched=True,
            owner_reported_hidden_cleanup_not_performed=True,
            owner_reported_first_custom_answered=True,
        )
        screenshots = build_screenshot_limit_packet(
            screenshot_count=2,
            screenshots_used_as_narrative_support=True,
        )
        visible = build_owner_visible_response_observation_packet(
            historical_observation_import_packet=imported,
            screenshot_limit_packet=screenshots,
        )
        cleanup = build_owner_cleanup_perception_packet(
            owner_reported_hidden_cleanup_not_performed=True,
            owner_confirmed_cleanup_result=False,
        )

        self.assertEqual(imported["status"], "ok")
        self.assertTrue(imported["historical_only"])
        self.assertFalse(imported["fresh_live_native_launch_claimed"])
        self.assertEqual(visible["status"], "ok")
        self.assertTrue(visible["owner_saw_response"])
        self.assertFalse(visible["machine_observed_response_text_proven"])
        self.assertFalse(cleanup["cleanup_perception_counts_as_filesystem_proof"])
        self.assertFalse(cleanup["filesystem_cleanup_proven"])

    def test_owner_ux_screenshot_limit_blocks_packet_truth_promotion(self) -> None:
        ok = build_screenshot_limit_packet(
            screenshot_count=2,
            screenshots_used_as_narrative_support=True,
        )
        promoted = build_screenshot_limit_packet(
            screenshot_count=1,
            screenshots_used_as_narrative_support=True,
            screenshot_claims_packet_truth=True,
        )
        too_many = build_screenshot_limit_packet(
            screenshot_count=4,
            screenshots_used_as_narrative_support=True,
            max_narrative_screenshots=3,
        )

        self.assertEqual(ok["status"], "ok")
        self.assertFalse(ok["screenshot_counts_as_packet_truth"])
        self.assertEqual(promoted["status"], "blocked")
        self.assertEqual(promoted["reason_class"], "SCREENSHOT_PROMOTED_TO_PACKET_TRUTH")
        self.assertEqual(too_many["status"], "blocked")
        self.assertEqual(too_many["reason_class"], "SCREENSHOT_NARRATIVE_CAP_EXCEEDED")

    def test_owner_ux_historical_route_reference_does_not_reprove_route(self) -> None:
        trace = build_wbp_trace_observation_packet(
            trace_packet={
                "request_observed": True,
                "response_observed": True,
                "forwarded_to_wbp": True,
                "path": "/v1/responses",
                "upstream_status": 200,
                "request_body_sha256": "request-hash",
                "response_body_sha256": "response-hash",
                "prompt_body_recorded": False,
                "auth_header_recorded": False,
                "secret_value_recorded": False,
            }
        )
        reference = build_historical_routing_trace_reference_packet(
            wbp_trace_observation_packet=trace,
            source_trace_path="audit_results/source/source_wbp_trace_packet.json",
            source_closeout_path="audit_results/source/closeout.md",
        )

        self.assertEqual(reference["status"], "ok")
        self.assertTrue(reference["historical_route_trace_referenced"])
        self.assertFalse(reference["routing_reproved_in_this_contour"])
        self.assertFalse(reference["fresh_trace_claimed"])
        self.assertFalse(reference["owner_observation_replaces_trace"])

    def test_owner_ux_historical_false_green_blocks_adjacent_layer_claims(self) -> None:
        imported = build_owner_historical_observation_import_packet(
            owner_confirmation_text="owner saw response",
            owner_reported_agent_answered=True,
            owner_reported_config_model_route_untouched=True,
            owner_reported_hidden_cleanup_not_performed=True,
        )
        screenshots = build_screenshot_limit_packet(
            screenshot_count=1,
            screenshots_used_as_narrative_support=True,
        )
        visible = build_owner_visible_response_observation_packet(
            historical_observation_import_packet=imported,
            screenshot_limit_packet=screenshots,
        )
        cleanup = build_owner_cleanup_perception_packet(
            owner_reported_hidden_cleanup_not_performed=True
        )
        trace = build_wbp_trace_observation_packet(
            trace_packet={
                "request_observed": True,
                "response_observed": True,
                "forwarded_to_wbp": True,
                "path": "/v1/responses",
                "upstream_status": 200,
                "response_body_sha256": "response-hash",
            }
        )
        reference = build_historical_routing_trace_reference_packet(
            wbp_trace_observation_packet=trace,
            source_trace_path="audit_results/source/source_wbp_trace_packet.json",
        )
        layer = build_owner_ux_layer_boundary_packet()
        clean = build_owner_ux_historical_false_green_audit(
            historical_observation_import_packet=imported,
            visible_response_observation_packet=visible,
            cleanup_perception_packet=cleanup,
            screenshot_limit_packet=screenshots,
            historical_routing_trace_reference_packet=reference,
            layer_boundary_packet=layer,
        )
        bad_layer = dict(layer)
        bad_layer["direct_egress_claimed"] = True
        blocked = build_owner_ux_historical_false_green_audit(
            historical_observation_import_packet=imported,
            visible_response_observation_packet=visible,
            cleanup_perception_packet=cleanup,
            screenshot_limit_packet=screenshots,
            historical_routing_trace_reference_packet=reference,
            layer_boundary_packet=bad_layer,
        )

        self.assertEqual(clean["status"], "ok")
        self.assertEqual(blocked["status"], "blocked")
        self.assertTrue(blocked["forbidden_claims_present"])

    def test_owner_ux_readiness_does_not_count_as_live_proof(self) -> None:
        packet = build_owner_ux_readiness_packet(
            native_launch_from_hosted_context_allowed=False,
            owner_confirmation_collected=False,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["native_launch_attempted"])
        self.assertFalse(packet["readiness_counts_as_owner_ux_acceptance"])
        self.assertFalse(packet["readiness_counts_as_routing"])
        self.assertTrue(packet["owner_confirmation_required_for_live_pass"])

    def test_owner_handoff_instruction_hashes_prompt_without_recording_raw_prompt(self) -> None:
        packet = build_owner_handoff_instruction_packet(
            exact_prompt="WBP_OWNER_UX_READINESS_NONCE: reply WBP_OK",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["owner_handoff_required_for_live_ux"])
        self.assertTrue(packet["exact_prompt_sha256"])
        self.assertFalse(packet["exact_prompt_recorded_raw"])
        self.assertFalse(packet["handoff_counts_as_live_proof"])

    def test_provider_marker_observation_limit_is_ui_only(self) -> None:
        packet = build_provider_marker_observation_limit_packet(
            provider_marker_visible=True
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["provider_marker_counts_as_ui_observation_only"])
        self.assertFalse(packet["provider_marker_counts_as_route_proof"])
        self.assertFalse(packet["provider_marker_counts_as_model_availability"])
        self.assertFalse(packet["provider_marker_counts_as_egress_absence"])

    def test_cleanup_perception_limit_does_not_replace_filesystem_proof(self) -> None:
        packet = build_cleanup_perception_limit_packet(
            owner_cleanup_perception_packet={
                "status": "ok",
                "owner_reported_hidden_cleanup_not_performed": True,
            }
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["owner_cleanup_confirmation_collected"])
        self.assertFalse(packet["cleanup_perception_counts_as_filesystem_proof"])
        self.assertFalse(packet["cleanup_perception_counts_as_cleanup_reversibility"])
        self.assertFalse(packet["filesystem_cleanup_proven"])

    def test_historical_or_incidental_route_context_never_proves_route(self) -> None:
        packet = build_historical_or_incidental_route_context_packet(
            historical_routing_trace_reference_packet={"status": "ok"},
            incidental_wbp_request_observed=True,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["historical_or_incidental_context_only"])
        self.assertFalse(packet["fresh_route_reproved_in_this_contour"])
        self.assertFalse(packet["routing_proven"])
        self.assertFalse(packet["response_accepted_by_codex_proven"])
        self.assertFalse(packet["direct_egress_absence_proven"])

    def test_owner_ux_readiness_false_green_audit_blocks_adjacent_claims(self) -> None:
        readiness = build_owner_ux_readiness_packet(
            native_launch_from_hosted_context_allowed=False,
            owner_confirmation_collected=False,
        )
        handoff = build_owner_handoff_instruction_packet(
            exact_prompt="WBP_OWNER_UX_READINESS_NONCE: reply WBP_OK",
        )
        marker = build_provider_marker_observation_limit_packet()
        cleanup = build_cleanup_perception_limit_packet()
        route_context = build_historical_or_incidental_route_context_packet()
        layer = build_owner_ux_layer_boundary_packet()
        clean = build_owner_ux_readiness_false_green_audit(
            readiness_packet=readiness,
            handoff_instruction_packet=handoff,
            provider_marker_limit_packet=marker,
            cleanup_perception_limit_packet=cleanup,
            route_context_packet=route_context,
            layer_boundary_packet=layer,
        )
        bad_layer = dict(layer)
        bad_layer["final_e2e_claimed"] = True
        blocked = build_owner_ux_readiness_false_green_audit(
            readiness_packet=readiness,
            handoff_instruction_packet=handoff,
            provider_marker_limit_packet=marker,
            cleanup_perception_limit_packet=cleanup,
            route_context_packet=route_context,
            layer_boundary_packet=bad_layer,
        )

        self.assertEqual(clean["status"], "ok")
        self.assertFalse(clean["forbidden_claims_present"])
        self.assertEqual(blocked["status"], "blocked")
        self.assertTrue(blocked["forbidden_claims_present"])

    def test_owner_ux_route_confirmation_probe_emits_two_lane_success(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "native_custom_owner_ux_route_confirmation_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=temp_repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            (temp_repo / "README.md").write_text("fixture\n", encoding="utf-8")
            (temp_repo / "audit_results").mkdir()
            (temp_repo / "audit_results" / ".gitkeep").write_text("", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=temp_repo, check=True)
            subprocess.run(["git", "add", "audit_results/.gitkeep"], cwd=temp_repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            evidence_dir = temp_repo / "audit_results" / "owner_ux_route"
            evidence_dir.mkdir(parents=True)
            trace_path = evidence_dir / "source_wbp_trace_packet.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request_observed": True,
                        "response_observed": True,
                        "forwarded_to_wbp": True,
                        "path": "/v1/responses",
                        "upstream_status": 200,
                        "request_body_sha256": "request-hash",
                        "response_body_sha256": "response-hash",
                        "prompt_body_recorded": False,
                        "auth_header_recorded": False,
                        "secret_value_recorded": False,
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--nonce",
                    "nonce-123",
                    "--trace-packet",
                    str(trace_path),
                    "--owner-waives-machine-ui",
                    "--owner-saw-window",
                    "--owner-typed-prompt",
                    "--owner-saw-response",
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((evidence_dir / "owner_ux_route_summary_packet.json").read_text())
            matrix = json.loads((evidence_dir / "two_lane_result_matrix.json").read_text())
            allowed = json.loads(
                (evidence_dir / "native_owner_ux_allowed_claims_matrix.json").read_text()
            )
            self.assertEqual(
                summary["final_status"],
                "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABLE_WITH_OWNER_CONFIRMATION",
            )
            self.assertTrue(matrix["owner_ux_confirmed"])
            self.assertTrue(matrix["route_trace_confirmed"])
            self.assertFalse(allowed["machine_ui_proof_claim_allowed"])
            self.assertFalse(allowed["direct_egress_claim_allowed"])

    def test_owner_ux_route_confirmation_probe_blocks_without_trace(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "native_custom_owner_ux_route_confirmation_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=temp_repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            (temp_repo / "README.md").write_text("fixture\n", encoding="utf-8")
            (temp_repo / "audit_results").mkdir()
            (temp_repo / "audit_results" / ".gitkeep").write_text("", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=temp_repo, check=True)
            subprocess.run(["git", "add", "audit_results/.gitkeep"], cwd=temp_repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            evidence_dir = temp_repo / "audit_results" / "owner_ux_route"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--nonce",
                    "nonce-123",
                    "--owner-waives-machine-ui",
                    "--owner-saw-window",
                    "--owner-typed-prompt",
                    "--owner-saw-response",
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            summary = json.loads((evidence_dir / "owner_ux_route_summary_packet.json").read_text())
            self.assertEqual(summary["final_status"], "OWNER_UX_CONFIRMED_ROUTE_UNPROVEN")
            self.assertTrue(summary["owner_ux_confirmed"])
            self.assertFalse(summary["route_trace_confirmed"])

    def test_owner_ux_historical_acceptance_probe_emits_limited_status(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "native_custom_owner_ux_historical_acceptance_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=temp_repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            (temp_repo / "README.md").write_text("fixture\n", encoding="utf-8")
            (temp_repo / "audit_results").mkdir()
            (temp_repo / "audit_results" / ".gitkeep").write_text("", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=temp_repo, check=True)
            subprocess.run(["git", "add", "audit_results/.gitkeep"], cwd=temp_repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            source_dir = temp_repo / "audit_results" / "source"
            source_dir.mkdir()
            trace_path = source_dir / "source_wbp_trace_packet.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request_observed": True,
                        "response_observed": True,
                        "forwarded_to_wbp": True,
                        "path": "/v1/responses",
                        "upstream_status": 200,
                        "request_body_sha256": "request-hash",
                        "response_body_sha256": "response-hash",
                        "prompt_body_recorded": False,
                        "auth_header_recorded": False,
                        "secret_value_recorded": False,
                    }
                ),
                encoding="utf-8",
            )
            closeout_path = source_dir / "closeout.md"
            closeout_path.write_text("# Source closeout\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", "audit_results/source"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "source evidence"],
                cwd=temp_repo,
                check=True,
                capture_output=True,
            )
            evidence_dir = temp_repo / "audit_results" / "owner_ux_historical"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--source-trace-packet",
                    str(trace_path),
                    "--source-closeout",
                    str(closeout_path),
                    "--owner-confirmation-text",
                    "owner saw response and did not edit config model route",
                    "--owner-reported-agent-answered",
                    "--owner-reported-first-custom-answered",
                    "--owner-reported-config-model-route-untouched",
                    "--owner-reported-hidden-cleanup-not-performed",
                    "--owner-waives-machine-ui",
                    "--screenshot-count",
                    "2",
                    "--screenshots-used-as-narrative-support",
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (
                    evidence_dir / "owner_ux_historical_acceptance_summary_packet.json"
                ).read_text()
            )
            false_green = json.loads(
                (evidence_dir / "native_ux_false_green_audit.json").read_text()
            )
            route_ref = json.loads(
                (
                    evidence_dir / "historical_routing_trace_reference_packet.json"
                ).read_text()
            )
            allowed = json.loads(
                (
                    evidence_dir / "owner_ux_historical_allowed_claims_matrix.json"
                ).read_text()
            )
            self.assertEqual(
                summary["final_status"],
                "CODEX_CUSTOM_NATIVE_OWNER_UX_HISTORICAL_ACCEPTED_WITH_LIMITS",
            )
            self.assertFalse(summary["fresh_native_launch_claimed"])
            self.assertFalse(summary["fresh_route_claimed"])
            self.assertFalse(summary["direct_egress_claimed"])
            self.assertEqual(false_green["status"], "ok")
            self.assertFalse(route_ref["routing_reproved_in_this_contour"])
            self.assertFalse(allowed["fresh_native_launch_claim_allowed"])

    def test_current_codex_delta_marks_missing_root_pid_as_touched(self) -> None:
        packet = classify_current_codex_delta(
            {
                "root_app_pids": [100, 200],
                "default_process_lines": ["100 Codex", "gpu default"],
            },
            {
                "root_app_pids": [200],
                "default_process_lines": ["200 Codex", "gpu default"],
            },
        )
        self.assertTrue(packet["current_codex_touched"])
        self.assertEqual(packet["missing_root_app_pids"], [100])

    def test_idle_baseline_summary_marks_unstable_when_repeated_drift_present(self) -> None:
        windows = [
            {
                "current_codex_delta": {"current_codex_touched": False},
                "protected_surface_recursive_diff": {
                    "surfaces": {
                        "codex_dir": {
                            "diff": {
                                "changed": [{"relative_path": "logs_2.sqlite"}],
                                "created": [],
                                "deleted": [],
                            }
                        }
                    }
                },
            },
            {
                "current_codex_delta": {"current_codex_touched": False},
                "protected_surface_recursive_diff": {
                    "surfaces": {
                        "codex_dir": {
                            "diff": {
                                "changed": [{"relative_path": "logs_2.sqlite"}],
                                "created": [],
                                "deleted": [],
                            }
                        }
                    }
                },
            },
        ]
        summary = summarize_idle_baseline_windows(windows)
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["final_verdict"], "ACTIVE_CURRENT_CODEX_BASELINE_UNSTABLE")
        self.assertTrue(summary["quiescent_current_codex_precondition_required"])
        self.assertEqual(summary["drift_repeatability"], "repeated")

    def test_idle_baseline_summary_requires_quiescent_precondition_when_active_drift_present(
        self,
    ) -> None:
        windows = [
            {
                "current_codex_delta": {"current_codex_touched": False},
                "protected_surface_recursive_diff": {
                    "surfaces": {
                        "default_app_support_codex": {
                            "diff": {
                                "changed": [{"relative_path": "sentry/scope_v3.json"}],
                                "created": [],
                                "deleted": [],
                            }
                        }
                    }
                },
            },
            {
                "current_codex_delta": {"current_codex_touched": False},
                "protected_surface_recursive_diff": {"surfaces": {}},
            },
        ]
        summary = summarize_idle_baseline_windows(windows)
        self.assertEqual(summary["final_verdict"], "ACTIVE_CURRENT_CODEX_BASELINE_UNSTABLE")
        self.assertTrue(summary["quiescent_current_codex_precondition_required"])
        self.assertEqual(summary["drift_repeatability"], "sporadic")

    def test_idle_baseline_contour_does_not_overclaim_filesystem_pass(self) -> None:
        summary = summarize_idle_baseline_windows(
            [
                {
                    "current_codex_delta": {"current_codex_touched": False},
                    "protected_surface_recursive_diff": {"surfaces": {}},
                }
            ]
        )
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["final_verdict"], "INSUFFICIENT_OBSERVATION")
        self.assertEqual(summary["drift_repeatability"], "insufficient")

    def test_quiescent_precondition_packet_blocks_when_default_codex_processes_present(
        self,
    ) -> None:
        packet = classify_quiescent_current_codex_precondition(
            {
                "root_app_pids": [41266],
                "default_process_count": 4,
                "custom_process_count": 0,
                "default_process_lines": ["gpu", "renderer"],
            }
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "CURRENT_CODEX_NOT_QUIESCENT")
        self.assertFalse(packet["quiescent_current_codex_precondition_satisfied"])
        self.assertIn("ROOT_APP_PID_PRESENT", packet["precondition_failures"])
        self.assertIn("DEFAULT_CODEX_PROCESS_PRESENT", packet["precondition_failures"])

    def test_quiescent_precondition_packet_passes_when_no_default_processes_present(
        self,
    ) -> None:
        packet = classify_quiescent_current_codex_precondition(
            {
                "root_app_pids": [],
                "default_process_count": 0,
                "custom_process_count": 0,
                "default_process_lines": [],
            }
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["reason_class"], "")
        self.assertTrue(packet["quiescent_current_codex_precondition_satisfied"])

    def test_quiescent_handoff_blocks_without_operator_admission(self) -> None:
        packet = classify_quiescent_handoff_admission(
            operator_action_performed=False,
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": False
            },
            host_process_chain=[{"command": "/usr/bin/python3"}],
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "QUIESCENT_HANDOFF_NOT_ADMITTED")
        self.assertFalse(packet["same_thread_admissible"])
        self.assertFalse(packet["fresh_context_required"])

    def test_quiescent_handoff_classifies_fresh_context_requirement(self) -> None:
        packet = classify_quiescent_handoff_admission(
            operator_action_performed=False,
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": False
            },
            host_process_chain=[
                {"command": "/Applications/Codex.app/Contents/Resources/codex app-server"},
                {"command": "/Applications/Codex.app/Contents/MacOS/Codex"},
            ],
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["verdict"], "QUIESCENT_HANDOFF_REQUIRES_FRESH_CONTEXT")
        self.assertFalse(packet["same_thread_admissible"])
        self.assertTrue(packet["fresh_context_required"])

    def test_quiescent_handoff_does_not_attempt_live_launch(self) -> None:
        packet = classify_quiescent_handoff_admission(
            operator_action_performed=True,
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": True
            },
            host_process_chain=[{"command": "/usr/bin/python3"}],
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["verdict"], "QUIESCENT_HANDOFF_ADMISSIBLE")
        self.assertTrue(packet["same_thread_admissible"])
        self.assertFalse(packet["fresh_context_required"])

    def test_protected_codex_host_negative_blocks_when_codex_ancestry_detected(self) -> None:
        packet = classify_protected_codex_host_negative(
            [
                {"pid": 100, "ppid": 90, "command": "/usr/bin/python3"},
                {
                    "pid": 90,
                    "ppid": 80,
                    "command": "/Applications/Codex.app/Contents/Resources/codex app-server",
                },
            ]
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "PROTECTED_CODEX_SESSION_DETECTED")
        self.assertTrue(packet["hosted_by_protected_codex_session"])
        self.assertFalse(packet["protected_codex_ancestry_disproven"])

    def test_protected_codex_host_negative_passes_when_codex_ancestry_absent(self) -> None:
        packet = classify_protected_codex_host_negative(
            [{"pid": 100, "ppid": 90, "command": "/usr/bin/python3"}]
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["reason_class"], "")
        self.assertFalse(packet["hosted_by_protected_codex_session"])
        self.assertTrue(packet["protected_codex_ancestry_disproven"])

    def test_protected_codex_host_negative_blocks_when_chain_missing(self) -> None:
        packet = classify_protected_codex_host_negative([])
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "HOST_CHAIN_UNPROVEN")
        self.assertFalse(packet["protected_codex_ancestry_disproven"])

    def test_fresh_context_entry_blocks_when_hosted_by_protected_codex(self) -> None:
        packet = classify_fresh_context_entry(
            host_process_chain=[
                {"command": "/Applications/Codex.app/Contents/Resources/codex app-server"},
                {"command": "/Applications/Codex.app/Contents/MacOS/Codex"},
            ],
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": False
            },
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "FRESH_CONTEXT_NOT_ESTABLISHED")
        self.assertFalse(packet["fresh_context_verified"])
        self.assertFalse(packet["phase7_retry_admissible"])

    def test_fresh_context_entry_blocks_when_quiescent_precondition_fails(self) -> None:
        packet = classify_fresh_context_entry(
            host_process_chain=[{"command": "/usr/bin/python3"}],
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": False
            },
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "QUIESCENT_PRECONDITION_STILL_FAILED")
        self.assertTrue(packet["fresh_context_verified"])
        self.assertFalse(packet["phase7_retry_admissible"])

    def test_fresh_context_entry_does_not_attempt_live_launch(self) -> None:
        packet = classify_fresh_context_entry(
            host_process_chain=[{"command": "/usr/bin/python3"}],
            quiescent_precondition_packet={
                "quiescent_current_codex_precondition_satisfied": True
            },
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["verdict"], "FRESH_CONTEXT_ENTRY_ADMISSIBLE")
        self.assertTrue(packet["phase7_retry_admissible"])

    def test_fresh_context_acquisition_blocks_without_operator_admission(self) -> None:
        packet = classify_fresh_context_acquisition(
            operator_action_performed=False,
            fresh_context_entry_packet={
                "status": "blocked",
                "reason_class": "FRESH_CONTEXT_NOT_ESTABLISHED",
                "fresh_context_verified": False,
                "phase7_retry_admissible": False,
                "verdict": "fresh_context_still_hosted_by_protected_codex",
            },
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "FRESH_CONTEXT_ACQUISITION_NOT_ADMITTED")
        self.assertEqual(packet["verdict"], "operator_mediated_fresh_context_not_provided")
        self.assertFalse(packet["phase7_retry_admissible"])

    def test_fresh_context_acquisition_preserves_entry_reason_when_operator_action_present(
        self,
    ) -> None:
        packet = classify_fresh_context_acquisition(
            operator_action_performed=True,
            fresh_context_entry_packet={
                "status": "blocked",
                "reason_class": "QUIESCENT_PRECONDITION_STILL_FAILED",
                "fresh_context_verified": True,
                "phase7_retry_admissible": False,
                "verdict": "fresh_context_present_but_quiescent_precondition_failed",
            },
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "QUIESCENT_PRECONDITION_STILL_FAILED")
        self.assertEqual(
            packet["verdict"], "fresh_context_present_but_quiescent_precondition_failed"
        )
        self.assertFalse(packet["phase7_retry_admissible"])

    def test_fresh_context_acquisition_passes_when_entry_is_admissible(self) -> None:
        packet = classify_fresh_context_acquisition(
            operator_action_performed=True,
            fresh_context_entry_packet={
                "status": "ok",
                "fresh_context_verified": True,
                "phase7_retry_admissible": True,
            },
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["verdict"], "FRESH_CONTEXT_ENTRY_ADMISSIBLE")
        self.assertTrue(packet["phase7_retry_admissible"])

    def test_ambient_env_context_flags_unexplained_authority(self) -> None:
        packet = collect_ambient_env_context(
            {
                "HOME": "/tmp/home",
                "CODEX_HOME": "/tmp/codex",
                "OPENAI_API_KEY": "secret",
                "HTTP_PROXY": "http://proxy",
            }
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["reason_class"], "AMBIENT_ENV_AUTHORITY_UNEXPLAINED")
        self.assertTrue(packet["ambient_openai_api_key_present"])
        self.assertTrue(packet["ambient_proxy_keys_present"]["HTTP_PROXY"])

    def test_ambient_env_context_passes_without_authority(self) -> None:
        packet = collect_ambient_env_context({"HOME": "/tmp/home", "CODEX_HOME": "/tmp/codex"})
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["reason_class"], "")
        self.assertFalse(packet["ambient_openai_api_key_present"])
        self.assertFalse(packet["unexplained_authority_present"])

    def test_clean_env_strips_host_codex_and_wrapper_context_for_native_launch(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "CODEX_THREAD_ID": "thread-123",
                "CODEX_CI": "1",
                "CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "Codex Desktop",
                "CODEX_SHELL": "1",
                "OPENAI_API_KEY": "secret",
                "OPENAI_BASE_URL": "https://example.invalid/v1",
                "WBP_PROFILE_DIR": "/tmp/ambient-profile",
                "BROWSER_USE_AVAILABLE_BACKENDS": "iab",
                "PYTHONPATH": "/tmp/pythonpath",
                "TMPDIR": "/tmp/ambient-tmp",
                "PATH": "/Users/example/.codex/tmp/arg0/bin:/usr/bin",
            },
            clear=True,
        ):
            env = clean_env()

        self.assertNotIn("CODEX_THREAD_ID", env)
        self.assertNotIn("CODEX_CI", env)
        self.assertNotIn("CODEX_INTERNAL_ORIGINATOR_OVERRIDE", env)
        self.assertNotIn("CODEX_SHELL", env)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("OPENAI_BASE_URL", env)
        self.assertNotIn("WBP_PROFILE_DIR", env)
        self.assertNotIn("BROWSER_USE_AVAILABLE_BACKENDS", env)
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("TMPDIR", env)
        self.assertEqual(env["PATH"], DETERMINISTIC_RUNTIME_PATH)
        self.assertEqual(env["NO_PROXY"], "127.0.0.1,localhost,::1")
        self.assertEqual(env["no_proxy"], "127.0.0.1,localhost,::1")

    def test_launch_native_candidate_passes_sanitized_env_to_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layout = mock.Mock()
            layout.tmp_root = root / "tmp"
            layout.tmp_root.mkdir()
            layout.profile_dir = root / "profile"
            layout.profile_dir.mkdir()
            layout.custom_user_data_dir = root / "electron-user-data"
            layout.launcher_stdout = root / "launcher.stdout.log"
            layout.launcher_stderr = root / "launcher.stderr.log"
            layout.launcher_path = root / "launcher.sh"
            layout.launcher_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            runtime_paths = mock.Mock()
            runtime_paths.managed_dir = root / "managed"
            runtime_paths.stable_config = root / "stable.json"
            captured: dict[str, object] = {}

            class _FakeProcess:
                pid = 43210

                def poll(self) -> int | None:
                    return None

            def fake_popen(*args: object, **kwargs: object) -> _FakeProcess:
                captured["args"] = args
                captured["kwargs"] = kwargs
                return _FakeProcess()

            with (
                mock.patch.dict(
                    os.environ,
                    {
                        "CODEX_THREAD_ID": "thread-123",
                        "CODEX_CI": "1",
                        "OPENAI_BASE_URL": "https://example.invalid/v1",
                        "WBP_PROFILE_DIR": "/tmp/ambient-profile",
                        "BROWSER_USE_AVAILABLE_BACKENDS": "iab",
                        "PATH": "/Users/example/.codex/tmp/arg0/bin:/usr/bin",
                    },
                    clear=True,
                ),
                mock.patch(
                    "wild_boar_proxy.native_filesystem_probe.subprocess.Popen",
                    side_effect=fake_popen,
                ),
                mock.patch(
                    "wild_boar_proxy.native_filesystem_probe.collect_codex_process_inventory",
                    return_value={"custom_process_count": 1},
                ),
            ):
                packet = launch_native_candidate(
                    repo_root=root,
                    layout=layout,
                    real_runtime_paths=runtime_paths,
                    startup_wait_seconds=0.1,
                )

        self.assertTrue(packet["custom_process_observed"])
        self.assertEqual(captured["args"][0][0], str(layout.launcher_path))
        self.assertEqual(captured["args"][0][1], "desktop")
        self.assertEqual(captured["args"][0][2], str(root.resolve(strict=False)))
        env = captured["kwargs"]["env"]
        self.assertNotIn("CODEX_THREAD_ID", env)
        self.assertNotIn("CODEX_CI", env)
        self.assertNotIn("OPENAI_BASE_URL", env)
        self.assertNotIn("BROWSER_USE_AVAILABLE_BACKENDS", env)
        self.assertEqual(env["PATH"], DETERMINISTIC_RUNTIME_PATH)
        self.assertEqual(env["WBP_PROFILE_DIR"], str(layout.profile_dir))
        self.assertEqual(env["WBP_MANAGED_DIR"], str(runtime_paths.managed_dir))
        self.assertEqual(env["WBP_STABLE_CONFIG"], str(runtime_paths.stable_config))
        self.assertEqual(env["WBP_RUNTIME_TMPDIR"], str(layout.tmp_root / "runtime-bind"))
        self.assertEqual(env["WBP_PYTHON_BIN"], sys.executable)
        self.assertEqual(
            env["WBP_ACTIVE_PROJECT_ROOT"],
            str(root.resolve(strict=False)),
        )

    def test_materialize_probe_profile_writes_agent_runtime_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layout = native_fs_probe.create_native_probe_layout(root)
            mirror_context_path = root / "owner-profile" / "wbp-agent-runtime-context.json"
            context = {
                "packet_kind": "codex_custom_native_agent_runtime_context",
                "primary_aliases": ["Codex", "Agent 1"],
                "coding_aliases": ["DIP", "Agent 2"],
                "api_model_id": "wbp-deepseek-chat",
                "allowed_api_route_ids": ["wbp-deepseek-chat"],
                "forbidden_stale_route_ids": ["wbp-deepseek-v3"],
                "deepseek_live_format_check_bridge": {
                    "url_candidates": [
                        "http://127.0.0.1:50555/v1/responses",
                        "http://localhost:50555/v1/responses",
                    ],
                    "curl_no_proxy_required": True,
                },
                "deepseek_live_format_check_file_bridge": {
                    "request_dir": str(root / "file-bridge" / "requests"),
                    "response_dir": str(root / "file-bridge" / "responses"),
                    "preferred_when_socket_connect_fails_with_errno_1": True,
                },
                "deepseek_live_format_check_cli_command": [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy.cli",
                    "external-models",
                    "live-format-check",
                    "--route",
                    "wbp-deepseek-chat",
                    "--json",
                ],
                "secret_value_exposed": False,
            }

            packet = native_fs_probe.materialize_probe_profile(
                layout=layout,
                endpoint="http://127.0.0.1:8788/v1",
                model="gpt-5.5",
                auth_command_path=root / "auth.py",
                local_token="local-token",
                agent_runtime_context=context,
                extra_agent_runtime_context_paths=[mirror_context_path],
            )

            context_path = layout.profile_dir / "wbp-agent-runtime-context.json"
            written = json.loads(context_path.read_text(encoding="utf-8"))
            mirror_written = json.loads(mirror_context_path.read_text(encoding="utf-8"))

        self.assertTrue(packet["agent_runtime_context_written"])
        self.assertEqual(packet["agent_runtime_context_extra_write_count"], 1)
        self.assertTrue(packet["native_alias_context_written"])
        self.assertTrue(packet["context_file_present"])
        self.assertTrue(packet["context_file_sha256_present"])
        self.assertEqual(
            packet["agent_runtime_context_profile_relative_path"],
            "wbp-agent-runtime-context.json",
        )
        self.assertEqual(written["api_model_id"], "wbp-deepseek-chat")
        self.assertEqual(mirror_written, written)
        self.assertEqual(written["coding_aliases"], ["DIP", "Agent 2"])
        self.assertEqual(written["forbidden_stale_route_ids"], ["wbp-deepseek-v3"])
        self.assertTrue(
            written["deepseek_live_format_check_bridge"]["curl_no_proxy_required"]
        )
        self.assertIn(
            "http://localhost:50555/v1/responses",
            written["deepseek_live_format_check_bridge"]["url_candidates"],
        )
        self.assertTrue(
            written["deepseek_live_format_check_file_bridge"][
                "preferred_when_socket_connect_fails_with_errno_1"
            ]
        )
        self.assertTrue(
            written["deepseek_live_format_check_file_bridge"]["request_dir"].endswith(
                "/file-bridge/requests"
            )
        )
        self.assertEqual(
            written["deepseek_live_format_check_cli_command"][1:],
            [
                "-m",
                "wild_boar_proxy.cli",
                "external-models",
                "live-format-check",
                "--route",
                "wbp-deepseek-chat",
                "--json",
            ],
        )
        self.assertNotIn("secret_ref", written)
        self.assertNotIn("local-token", json.dumps(written))
        self.assertEqual(len(packet["agent_runtime_context_sha256"]), 64)

    def test_materialize_probe_profile_preserves_hook_trust_sections_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layout = native_fs_probe.create_native_probe_layout(root)
            layout.profile_dir.mkdir(parents=True, exist_ok=True)
            trust_key = f"{layout.profile_dir / 'hooks.json'}:user_prompt_submit:0:0"
            (layout.profile_dir / "config.toml").write_text(
                'model = "old-model"\n'
                'experimental_bearer_token = "must-not-survive"\n\n'
                "[hooks]\n"
                "enabled = true\n\n"
                "[hooks.state."
                + json.dumps(trust_key)
                + "]\n"
                'trusted_hash = "sha256:'
                + ("1" * 64)
                + '"\n\n'
                "[model_providers.old.auth]\n"
                'command = "must-not-survive"\n',
                encoding="utf-8",
            )

            packet = native_fs_probe.materialize_probe_profile(
                layout=layout,
                endpoint="http://127.0.0.1:8788/v1",
                model="gpt-5.5",
                auth_command_path=root / "auth.py",
                local_token="local-token",
            )
            config_text = (layout.profile_dir / "config.toml").read_text(
                encoding="utf-8"
            )
            auth_wrapper = (
                layout.profile_dir / "managed" / "bin" / "wbp-codex-auth-command"
            )
            auth_wrapper_text = auth_wrapper.read_text(encoding="utf-8")
            stable_config = (
                layout.profile_dir / "managed" / "stable-runtime-config.generated.yaml"
            )
            auth_wrapper_is_file = auth_wrapper.is_file()
            auth_wrapper_is_executable = os.access(auth_wrapper, os.X_OK)
            stable_config_is_file = stable_config.is_file()
            stable_config_text = stable_config.read_text(encoding="utf-8")

        self.assertTrue(packet["hooks_config_sections_preserved"])
        self.assertTrue(packet["auth_command_wrapper_written"])
        self.assertTrue(packet["stable_runtime_token_config_written"])
        self.assertTrue(packet["config_uses_auth_command"])
        self.assertFalse(packet["config_uses_experimental_bearer_token"])
        self.assertEqual(
            packet["hooks_config_preservation_scope"],
            "top_level_hooks_toml_tables_only",
        )
        self.assertIn("[hooks]", config_text)
        self.assertIn("[hooks.state.", config_text)
        self.assertIn('trusted_hash = "sha256:' + ("1" * 64) + '"', config_text)
        self.assertIn('model = "gpt-5.5"', config_text)
        self.assertIn("[model_providers.wbp.auth]", config_text)
        self.assertIn(str(auth_wrapper), config_text)
        self.assertTrue(auth_wrapper_is_file)
        self.assertTrue(auth_wrapper_is_executable)
        self.assertIn("export WBP_STABLE_CONFIG=", auth_wrapper_text)
        self.assertIn(".codex-custom-cli/managed/stable-runtime-config.generated.yaml", auth_wrapper_text)
        self.assertTrue(stable_config_is_file)
        self.assertIn("local-token", stable_config_text)
        self.assertNotIn("old-model", config_text)
        self.assertNotIn("must-not-survive", config_text)
        self.assertNotIn("local-token", config_text)
        self.assertNotIn("experimental_bearer_token", config_text)

    def test_materialize_probe_profile_validates_model_before_writing_config(self) -> None:
        response = mock.MagicMock()
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=None)
        response.status = 200
        response.read.return_value = json.dumps(
            {"data": [{"id": "gpt-5.5"}, {"id": "gpt-5.4"}]}
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layout = native_fs_probe.create_native_probe_layout(root)
            with mock.patch(
                "wild_boar_proxy.native_filesystem_probe.urllib.request.urlopen",
                return_value=response,
            ) as urlopen:
                packet = native_fs_probe.materialize_probe_profile(
                    layout=layout,
                    endpoint="http://127.0.0.1:8788/v1",
                    model="gpt-5.5",
                    auth_command_path=root / "auth.py",
                    local_token="local-token",
                    validate_model_against_endpoint=True,
                )
            config_text = (layout.profile_dir / "config.toml").read_text(
                encoding="utf-8"
            )
            launcher_recognized = repo_managed_default_launcher_recognized(
                layout.launcher_path
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["configured_model_validation_attempted"])
        self.assertTrue(packet["configured_model_available"])
        self.assertTrue(packet["model_config_written"])
        self.assertTrue(packet["auth_command_wrapper_written"])
        self.assertTrue(packet["stable_runtime_token_config_written"])
        self.assertIn('model = "gpt-5.5"', config_text)
        self.assertIn("[model_providers.wbp.auth]", config_text)
        self.assertNotIn("experimental_bearer_token", config_text)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 3.0)
        self.assertTrue(launcher_recognized)

    def test_materialize_probe_profile_blocks_unadvertised_model_without_config_write(self) -> None:
        response = mock.MagicMock()
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=None)
        response.status = 200
        response.read.return_value = json.dumps(
            {"data": [{"id": "gpt-5.5"}, {"id": "gpt-5.4-mini"}]}
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layout = native_fs_probe.create_native_probe_layout(root)
            with mock.patch(
                "wild_boar_proxy.native_filesystem_probe.urllib.request.urlopen",
                return_value=response,
            ):
                packet = native_fs_probe.materialize_probe_profile(
                    layout=layout,
                    endpoint="http://127.0.0.1:8788/v1",
                    model="not-server-issued",
                    auth_command_path=root / "auth.py",
                    local_token="local-token",
                    validate_model_against_endpoint=True,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_NATIVE_CONFIG_MODEL_NOT_IN_MODELS_ENDPOINT",
        )
        self.assertFalse(packet["configured_model_available"])
        self.assertFalse(packet["model_config_written"])
        self.assertFalse((layout.profile_dir / "config.toml").exists())
        self.assertNotIn("local-token", json.dumps(packet, sort_keys=True))

    def test_materialize_probe_profile_repairs_stale_native_model_to_advertised_default(
        self,
    ) -> None:
        response = mock.MagicMock()
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=None)
        response.status = 200
        response.read.return_value = json.dumps(
            {"data": [{"id": "gpt-5.5"}, {"id": "gpt-5.4-mini"}]}
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            layout = native_fs_probe.create_native_probe_layout(root)
            with mock.patch(
                "wild_boar_proxy.native_filesystem_probe.urllib.request.urlopen",
                return_value=response,
            ):
                packet = native_fs_probe.materialize_probe_profile(
                    layout=layout,
                    endpoint="http://127.0.0.1:8788/v1",
                    model="gpt-5.3-codex",
                    auth_command_path=root / "auth.py",
                    local_token="local-token",
                    validate_model_against_endpoint=True,
                )
            config_text = (layout.profile_dir / "config.toml").read_text(
                encoding="utf-8"
            )
            launcher_recognized = repo_managed_default_launcher_recognized(
                layout.launcher_path
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["configured_model_auto_repaired"])
        self.assertTrue(packet["configured_model_stale"])
        self.assertEqual(packet["requested_configured_model_id"], "gpt-5.3-codex")
        self.assertEqual(packet["effective_configured_model_id"], "gpt-5.5")
        self.assertTrue(packet["model_config_written"])
        self.assertIn('model = "gpt-5.5"', config_text)
        self.assertNotIn('model = "gpt-5.3-codex"', config_text)
        self.assertTrue(launcher_recognized)

    def test_external_detached_context_outcome_blocks_when_context_not_proven(self) -> None:
        packet = classify_external_detached_context_outcome(
            host_negative_packet={
                "reason_class": "PROTECTED_CODEX_SESSION_DETECTED",
                "hosted_by_protected_codex_session": True,
                "protected_codex_ancestry_disproven": False,
            },
            precondition_packet={
                "reason_class": "CURRENT_CODEX_NOT_QUIESCENT",
                "quiescent_current_codex_precondition_satisfied": False,
            },
            acquisition_packet={
                "reason_class": "FRESH_CONTEXT_ACQUISITION_NOT_ADMITTED",
                "fresh_context_verified": False,
                "operator_action_required": True,
                "operator_action_performed": False,
                "phase7_retry_admissible": False,
            },
            ambient_env_packet={"status": "ok", "reason_class": ""},
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["final_verdict"], "EXTERNAL_DETACHED_CONTEXT_NOT_PROVEN")
        self.assertEqual(packet["reason_class"], "FRESH_CONTEXT_ACQUISITION_NOT_ADMITTED")

    def test_external_detached_context_outcome_marks_phase7_admissible(self) -> None:
        packet = classify_external_detached_context_outcome(
            host_negative_packet={
                "reason_class": "",
                "hosted_by_protected_codex_session": False,
                "protected_codex_ancestry_disproven": True,
            },
            precondition_packet={
                "reason_class": "",
                "quiescent_current_codex_precondition_satisfied": True,
            },
            acquisition_packet={
                "reason_class": "",
                "fresh_context_verified": True,
                "operator_action_required": True,
                "operator_action_performed": True,
                "phase7_retry_admissible": True,
            },
            ambient_env_packet={"status": "ok", "reason_class": ""},
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_verdict"],
            "EXTERNAL_DETACHED_CONTEXT_PROVEN_AND_PHASE7_ADMISSIBLE",
        )
        self.assertTrue(packet["phase7_retry_admissible"])

    def test_external_detached_context_outcome_preserves_separate_quiescent_blocker(
        self,
    ) -> None:
        packet = classify_external_detached_context_outcome(
            host_negative_packet={
                "reason_class": "",
                "hosted_by_protected_codex_session": False,
                "protected_codex_ancestry_disproven": True,
            },
            precondition_packet={
                "reason_class": "CURRENT_CODEX_NOT_QUIESCENT",
                "quiescent_current_codex_precondition_satisfied": False,
            },
            acquisition_packet={
                "reason_class": "QUIESCENT_PRECONDITION_STILL_FAILED",
                "fresh_context_verified": True,
                "operator_action_required": True,
                "operator_action_performed": True,
                "phase7_retry_admissible": False,
            },
            ambient_env_packet={"status": "ok", "reason_class": ""},
        )
        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["final_verdict"],
            "EXTERNAL_DETACHED_CONTEXT_PROVEN_BUT_PHASE7_NOT_ADMISSIBLE",
        )
        self.assertTrue(packet["protected_codex_ancestry_disproven"])

    def test_detached_egress_command_targets_live_direct_egress_probe(self) -> None:
        repo_root = Path("/tmp/wbp-repo")
        evidence_dir = repo_root / "audit_results" / "egress_EXTERNAL_2026-05-26"
        packet = build_detached_egress_execution_command_packet(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            wait_seconds=45,
        )
        self.assertEqual(packet["status"], "ok")
        self.assertIn("native_custom_direct_egress_classification_probe.py", packet["target_tool"])
        self.assertIn("--mode", packet["argv"])
        self.assertIn("live", packet["argv"])
        self.assertEqual(packet["wait_seconds"], 45)
        self.assertFalse(packet["command_executed"])
        self.assertFalse(packet["native_launch_attempted_from_current_thread"])

    def test_detached_egress_command_admission_and_hash_are_bounded(self) -> None:
        repo_root = Path("/tmp/wbp-repo")
        evidence_dir = repo_root / "audit_results" / "egress_EXTERNAL_2026-05-26"
        command = build_detached_egress_execution_command_packet(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
        )
        admission = build_detached_egress_command_admission_packet(
            command_packet=command,
            repo_root=repo_root,
        )
        command_hash = build_detached_egress_command_hash_packet(
            command_packet=command,
        )
        self.assertEqual(admission["status"], "ok")
        self.assertTrue(admission["evidence_dir_under_audit_results"])
        self.assertTrue(admission["external_evidence_dir_marker_present"])
        self.assertFalse(admission["protected_surfaces_write_allowed"])
        self.assertEqual(command_hash["status"], "ok")
        self.assertTrue(command_hash["hash_covers_argv_cwd_target_and_evidence_dir"])

    def test_detached_egress_import_contract_forbids_phase_a_absence_claim(self) -> None:
        required = build_detached_egress_future_result_required_packets_packet()
        contract = build_detached_egress_future_result_import_contract_packet(
            required_packets_packet=required,
        )
        self.assertIn(
            "native_direct_egress_claim_packet.json",
            contract["required_packets"],
        )
        self.assertFalse(contract["external_result_imported_in_this_contour"])
        self.assertFalse(contract["direct_egress_absence_claim_allowed_in_phase_a"])
        self.assertFalse(contract["api_openai_com_absence_claim_allowed_in_phase_a"])

    def test_detached_egress_false_green_blocks_unadmitted_command(self) -> None:
        admission = {"status": "blocked", "command_executed": False, "external_result_imported": False}
        command_hash = {"status": "ok", "command_sha256": "abc"}
        owner_boundary = build_detached_egress_owner_action_boundary_packet()
        required = build_detached_egress_future_result_required_packets_packet()
        contract = build_detached_egress_future_result_import_contract_packet(
            required_packets_packet=required,
        )
        network_limits = build_network_claim_limits_packet()
        audit = build_detached_egress_handoff_false_green_audit(
            command_admission_packet=admission,
            command_hash_packet=command_hash,
            owner_action_boundary_packet=owner_boundary,
            future_result_import_contract_packet=contract,
            network_claim_limits_packet=network_limits,
        )
        self.assertEqual(audit["status"], "blocked")
        self.assertFalse(audit["direct_egress_absence_claimed"])

    def test_detached_egress_quiescent_requirement_is_handoff_only(self) -> None:
        packet = build_detached_egress_quiescent_requirement_packet()
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["current_hosted_context_must_not_run_live"])
        self.assertFalse(packet["fresh_native_launch_attempted"])
        self.assertFalse(packet["live_network_capture_attempted"])

    def test_detached_egress_handoff_tool_emits_phase_a_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            real_repo = Path(__file__).resolve().parents[1]
            tool_dir = repo_root / "tools"
            tool_dir.mkdir()
            (tool_dir / "native_custom_direct_egress_classification_probe.py").write_text(
                "# placeholder\n",
                encoding="utf-8",
            )
            evidence_dir = repo_root / "audit_results" / "handoff"
            external_evidence_dir = (
                repo_root
                / "audit_results"
                / "wbp_native_custom_detached_egress_execution_EXTERNAL_R2_2026-05-27"
            )
            safety_path = repo_root / "audit_results" / "safety.json"
            safety_path.parent.mkdir(parents=True, exist_ok=True)
            safety_path.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "allowed_final_claim": "NATIVE_CUSTOM_SAFETY_ADMISSION_INSPECTION_ONLY_CLASSIFIED",
                        "native_launch_attempted": False,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            script = real_repo / "tools" / "native_custom_detached_egress_execution_handoff_probe.py"
            process = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--repo-root",
                    str(repo_root),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--external-evidence-dir",
                    str(external_evidence_dir),
                    "--safety-admission-path",
                    str(safety_path),
                    "--ready-final-status",
                    "WBP_DETACHED_NATIVE_CUSTOM_EGRESS_HANDOFF_REFRESH_R2_READY_OWNER_ACTION_REQUIRED",
                    "--skip-git",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            summary = json.loads(
                (evidence_dir / "handoff_summary_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            command = json.loads(
                (evidence_dir / "detached_egress_execution_command_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                summary["final_status"],
                "WBP_DETACHED_NATIVE_CUSTOM_EGRESS_HANDOFF_REFRESH_R2_READY_OWNER_ACTION_REQUIRED",
            )
            self.assertFalse(summary["native_launch_attempted"])
            self.assertEqual(
                summary["external_evidence_dir"],
                str(external_evidence_dir.resolve()),
            )
            self.assertIn("--mode", command["argv"])
            self.assertEqual(command["evidence_dir"], str(external_evidence_dir.resolve()))
            safety_reference = json.loads(
                (evidence_dir / "safety_admission_reference_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(safety_reference["status"], "ok")
            self.assertTrue(safety_reference["reference_only"])

    def test_detached_egress_safety_admission_prerequisite_is_reference_only(self) -> None:
        packet = build_detached_egress_safety_admission_prerequisite_packet(
            source_path="/tmp/admission.json",
            source_packet={
                "status": "ok",
                "allowed_final_claim": "NATIVE_CUSTOM_SAFETY_ADMISSION_INSPECTION_ONLY_CLASSIFIED",
                "native_launch_attempted": False,
            },
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["safety_admission_classified"])
        self.assertFalse(packet["counts_as_native_egress_proof"])

    def test_detached_egress_safety_admission_prerequisite_accepts_refresh_contour(self) -> None:
        packet = build_detached_egress_safety_admission_prerequisite_packet(
            source_path="/tmp/refresh.json",
            source_packet={
                "status": "ok",
                "final_status": "NATIVE_CUSTOM_SAFETY_REFRESH_CLASSIFIED",
                "native_launch_attempted": False,
            },
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["source_final_status"],
            "NATIVE_CUSTOM_SAFETY_REFRESH_CLASSIFIED",
        )
        self.assertTrue(packet["safety_admission_classified"])

    def test_detached_egress_handoff_prerequisite_accepts_r2_ready_status(self) -> None:
        packet = build_detached_egress_handoff_prerequisite_packet(
            handoff_dir=Path("/tmp/handoff"),
            handoff_summary_packet={
                "final_status": "WBP_DETACHED_NATIVE_CUSTOM_EGRESS_HANDOFF_REFRESH_R2_READY_OWNER_ACTION_REQUIRED",
                "external_evidence_dir": "/tmp/evidence",
            },
            command_packet={"status": "ok", "command_executed": False},
            command_hash_packet={"status": "ok", "command_sha256": "abc"},
            command_admission_packet={"status": "ok"},
            import_contract_packet={
                "status": "ok",
                "future_import_must_verify_command_hash": True,
                "future_import_must_verify_json": True,
                "future_import_must_verify_no_secrets": True,
            },
        )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["counts_as_network_claim"])

    def test_detached_egress_handoff_prerequisite_accepts_r3_prompt_required_status(self) -> None:
        packet = build_detached_egress_handoff_prerequisite_packet(
            handoff_dir=Path("/tmp/handoff"),
            handoff_summary_packet={
                "final_status": "WBP_DETACHED_NATIVE_CUSTOM_EGRESS_HANDOFF_R3_READY_OWNER_PROMPT_REQUIRED",
                "external_evidence_dir": "/tmp/evidence",
            },
            command_packet={"status": "ok", "command_executed": False},
            command_hash_packet={"status": "ok", "command_sha256": "abc"},
            command_admission_packet={"status": "ok"},
            import_contract_packet={
                "status": "ok",
                "future_import_must_verify_command_hash": True,
                "future_import_must_verify_json": True,
                "future_import_must_verify_no_secrets": True,
            },
        )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["counts_as_network_claim"])

    def test_persistent_custom_profile_identity_required(self) -> None:
        profile_root = Path("/tmp/wbp-persistent/profile")
        packet = build_persistent_custom_profile_contract_packet(
            profile_id="wbp-custom-main",
            profile_root=profile_root,
            codex_home=profile_root,
            user_data_dir=profile_root / "electron-user-data",
        )
        missing = build_persistent_custom_profile_contract_packet(
            profile_id="",
            profile_root=profile_root,
            codex_home=profile_root,
            user_data_dir=profile_root / "electron-user-data",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["original_codex_profile_runtime_dependency"])
        self.assertEqual(missing["status"], "blocked")

    def test_persistent_custom_launcher_selects_stable_profile(self) -> None:
        profile_root = Path("/tmp/wbp-persistent/profile")
        packet = build_persistent_launcher_selection_packet(
            launcher_path=profile_root / "codex-custom-launch.sh",
            profile_mode="persistent_custom",
            selected_profile_id="wbp-custom-main",
            selected_profile_root=profile_root,
            codex_home=profile_root,
            user_data_dir=profile_root / "electron-user-data",
        )
        fallback = build_persistent_launcher_selection_packet(
            launcher_path=profile_root / "codex-custom-launch.sh",
            profile_mode="ephemeral_custom",
            selected_profile_id="wbp-custom-main",
            selected_profile_root=profile_root,
            codex_home=profile_root,
            user_data_dir=profile_root / "electron-user-data",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["browser_client_override_allowed"])
        self.assertEqual(fallback["status"], "blocked")

    def test_persistent_custom_cleanup_does_not_delete_history(self) -> None:
        profile_root = Path("/tmp/wbp-persistent/profile")
        preserved = build_persistent_cleanup_policy_packet(
            profile_root=profile_root,
            cleanup_attempted=True,
            profile_exists_after_cleanup=True,
        )
        deleted = build_persistent_cleanup_policy_packet(
            profile_root=profile_root,
            cleanup_attempted=True,
            profile_exists_after_cleanup=False,
        )

        self.assertEqual(preserved["status"], "ok")
        self.assertEqual(deleted["status"], "blocked")

    def test_persistent_custom_history_requires_relaunch_proof(self) -> None:
        profile_root = Path("/tmp/wbp-persistent/profile")
        before_identity = build_persistent_custom_profile_identity_packet(
            phase="before",
            profile_id="wbp-custom-main",
            profile_root=profile_root,
            codex_home=profile_root,
            user_data_dir=profile_root / "electron-user-data",
        )
        relaunch_identity = build_persistent_custom_profile_identity_packet(
            phase="relaunch",
            profile_id="wbp-custom-main",
            profile_root=profile_root,
            codex_home=profile_root,
            user_data_dir=profile_root / "electron-user-data",
            expected_profile_id="wbp-custom-main",
            expected_profile_root=profile_root,
        )
        state_diff = {
            "status": "ok",
            "state_classes_observed": ["thread_history"],
        }
        context = build_owner_visible_thread_context_packet(
            owner_visible_prior_thread=True,
            owner_confirmation_collected=True,
        )

        packet = build_thread_history_preservation_packet(
            before_identity_packet=before_identity,
            relaunch_identity_packet=relaunch_identity,
            state_diff_packet=state_diff,
            owner_visible_thread_context_packet=context,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["owner_visible_thread_counted_as_storage_proof"])

    def test_persistent_custom_history_not_proven_by_route_trace(self) -> None:
        profile_root = Path("/tmp/wbp-persistent/profile")
        identity = build_persistent_custom_profile_identity_packet(
            phase="before",
            profile_id="wbp-custom-main",
            profile_root=profile_root,
            codex_home=profile_root,
            user_data_dir=profile_root / "electron-user-data",
        )
        packet = build_thread_history_preservation_packet(
            before_identity_packet=identity,
            relaunch_identity_packet=identity,
            state_diff_packet={"status": "blocked"},
            owner_visible_thread_context_packet=build_owner_visible_thread_context_packet(
                owner_visible_prior_thread=True,
                owner_confirmation_collected=True,
            ),
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["route_trace_counted_as_saved_thread_proof"])

    def test_persistent_r2_profile_state_preserved_does_not_prove_thread_history(self) -> None:
        profile_root = Path("/tmp/wbp-persistent/profile")
        identity = build_persistent_custom_profile_identity_packet(
            phase="before",
            profile_id="wbp-custom-main",
            profile_root=profile_root,
            codex_home=profile_root,
            user_data_dir=profile_root / "electron-user-data",
        )
        relaunch_identity = build_persistent_custom_profile_identity_packet(
            phase="relaunch",
            profile_id="wbp-custom-main",
            profile_root=profile_root,
            codex_home=profile_root,
            user_data_dir=profile_root / "electron-user-data",
            expected_profile_id="wbp-custom-main",
            expected_profile_root=profile_root,
        )
        profile_state = build_persistent_profile_state_preservation_packet(
            before_identity_packet=identity,
            relaunch_identity_packet=relaunch_identity,
            after_action_state_diff_packet={
                "status": "ok",
                "created_count": 1,
                "state_classes_observed": ["user_settings"],
            },
            after_relaunch_state_diff_packet={
                "status": "blocked",
                "created_count": 0,
                "state_classes_observed": [],
            },
        )
        thread_history = build_persistent_thread_history_preservation_r2_packet(
            profile_state_preservation_packet=profile_state,
            state_diff_packet={
                "status": "ok",
                "state_classes_observed": ["user_settings"],
            },
            owner_visible_thread_context_packet=build_owner_visible_thread_context_packet(
                owner_visible_prior_thread=True,
                owner_confirmation_collected=True,
            ),
        )

        self.assertEqual(profile_state["status"], "ok")
        self.assertTrue(profile_state["profile_state_preserved"])
        self.assertFalse(profile_state["counts_as_thread_history_proof"])
        self.assertEqual(thread_history["status"], "blocked")
        self.assertFalse(thread_history["thread_history_preserved"])

    def test_persistent_r2_thread_history_requires_profile_state_first(self) -> None:
        thread_history = build_persistent_thread_history_preservation_r2_packet(
            profile_state_preservation_packet={
                "status": "blocked",
                "profile_state_preserved": False,
            },
            state_diff_packet={
                "status": "ok",
                "state_classes_observed": ["thread_history"],
            },
            owner_visible_thread_context_packet=build_owner_visible_thread_context_packet(
                owner_visible_prior_thread=True,
                owner_confirmation_collected=True,
            ),
        )

        self.assertEqual(thread_history["status"], "blocked")
        self.assertFalse(thread_history["thread_history_preserved"])
        self.assertFalse(thread_history["owner_visible_thread_counted_as_storage_proof"])

    def test_persistent_r2_profile_state_blocks_relaunch_deletion(self) -> None:
        profile_root = Path("/tmp/wbp-persistent/profile")
        identity = build_persistent_custom_profile_identity_packet(
            phase="before",
            profile_id="wbp-custom-main",
            profile_root=profile_root,
            codex_home=profile_root,
            user_data_dir=profile_root / "electron-user-data",
        )
        packet = build_persistent_profile_state_preservation_packet(
            before_identity_packet=identity,
            relaunch_identity_packet=identity,
            after_action_state_diff_packet={
                "status": "ok",
                "created_count": 1,
                "deleted_count": 0,
            },
            after_relaunch_state_diff_packet={
                "status": "ok",
                "created_count": 0,
                "deleted_count": 1,
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["profile_state_preserved"])
        self.assertFalse(packet["after_relaunch_state_kept"])

    def test_persistent_r2_profile_state_allows_relaunch_created_state_without_deletion(self) -> None:
        profile_root = Path("/tmp/wbp-persistent/profile")
        identity = build_persistent_custom_profile_identity_packet(
            phase="before",
            profile_id="wbp-custom-main",
            profile_root=profile_root,
            codex_home=profile_root,
            user_data_dir=profile_root / "electron-user-data",
        )
        packet = build_persistent_profile_state_preservation_packet(
            before_identity_packet=identity,
            relaunch_identity_packet=identity,
            after_action_state_diff_packet={
                "status": "ok",
                "created_count": 1,
                "deleted_count": 0,
            },
            after_relaunch_state_diff_packet={
                "status": "ok",
                "created_count": 2,
                "deleted_count": 0,
            },
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["profile_state_preserved"])
        self.assertTrue(packet["after_relaunch_state_kept"])

    def test_persistent_r2_thread_history_classified_after_profile_state(self) -> None:
        profile_state = {
            "status": "ok",
            "profile_state_preserved": True,
        }
        thread_history = build_persistent_thread_history_preservation_r2_packet(
            profile_state_preservation_packet=profile_state,
            state_diff_packet={
                "status": "ok",
                "state_classes_observed": ["thread_history"],
            },
            owner_visible_thread_context_packet=build_owner_visible_thread_context_packet(
                owner_visible_prior_thread=True,
                owner_confirmation_collected=True,
            ),
        )

        self.assertEqual(thread_history["status"], "ok")
        self.assertTrue(thread_history["thread_history_preserved"])
        self.assertTrue(thread_history["profile_state_preserved"])

    def test_persistent_custom_visible_thread_is_context_only(self) -> None:
        packet = build_owner_visible_thread_context_packet(
            owner_visible_prior_thread=True,
            owner_confirmation_collected=True,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["context_only"])
        self.assertFalse(packet["counts_as_storage_persistence_proof"])

    def test_persistent_custom_original_profile_not_used_as_shortcut(self) -> None:
        scope = build_original_codex_protected_surface_scope_packet()
        drift = build_original_codex_profile_drift_packet(
            before_surfaces={"surfaces": {}},
            after_surfaces={"surfaces": {}},
        )

        self.assertEqual(scope["status"], "ok")
        self.assertFalse(scope["original_codex_runtime_input"])
        self.assertEqual(drift["status"], "ok")

    def test_persistent_custom_concurrent_policy_required(self) -> None:
        ok = build_persistent_concurrent_launch_policy_packet(
            policy="single_writer_only",
            launcher_enforces_policy=True,
        )
        blocked = build_persistent_concurrent_launch_policy_packet(
            policy="",
            launcher_enforces_policy=False,
        )

        self.assertEqual(ok["status"], "ok")
        self.assertEqual(blocked["status"], "blocked")

    def test_persistent_custom_backup_rollback_required(self) -> None:
        profile_root = Path("/tmp/wbp-persistent/profile")
        first_write = build_persistent_backup_rollback_packet(
            profile_root=profile_root,
            backup_root=Path("/tmp/wbp-persistent/backup"),
            profile_existed_before=False,
            backup_created=False,
        )
        existing_without_backup = build_persistent_backup_rollback_packet(
            profile_root=profile_root,
            backup_root=Path("/tmp/wbp-persistent/backup"),
            profile_existed_before=True,
            backup_created=False,
        )

        self.assertEqual(first_write["status"], "ok")
        self.assertEqual(existing_without_backup["status"], "blocked")

    def test_persistent_backup_repair_classifies_thread_history_for_copy(self) -> None:
        packet = classify_backup_surface("sessions/2026/05/thread.jsonl")

        self.assertEqual(packet["decision"], "copy")
        self.assertEqual(packet["surface_class"], "thread_history")

    def test_persistent_backup_repair_excludes_volatile_runtime_cache(self) -> None:
        packet = classify_backup_surface(
            "home/.cache/codex-runtimes/install/payload/node_modules/pkg/index.js"
        )

        self.assertEqual(packet["decision"], "exclude")
        self.assertEqual(packet["surface_class"], "cache_or_incidental_state")
        self.assertEqual(packet["reason"], "volatile_cache_or_runtime_dependency")

    def test_persistent_backup_repair_excludes_auth_surface(self) -> None:
        packet = classify_backup_surface("auth.json")

        self.assertEqual(packet["decision"], "exclude")
        self.assertEqual(packet["surface_class"], "secret_or_auth_surface")

    def test_persistent_custom_sensitive_state_redacted(self) -> None:
        before = {"root": "/tmp/profile", "exists": True, "entries": []}
        after = {
            "root": "/tmp/profile",
            "exists": True,
            "entries": [
                {
                    "relative_path": "threads/history.json",
                    "kind": "file",
                    "size": 12,
                    "mtime_ns": 2,
                    "sha256": "hash",
                }
            ],
        }
        packet = build_persistent_profile_state_diff_packet(
            before_scan=before,
            after_scan=after,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["raw_session_body_recorded"])
        self.assertIn("thread_history", packet["state_classes_observed"])

    def test_persistent_custom_integration_ownership_baseline_classified(self) -> None:
        packet = build_integration_ownership_baseline_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["integration_parity_claimed"])
        self.assertFalse(packet["integration_persistence_proven"])

    def test_persistent_profile_false_green_audit_blocks_visible_thread_overclaim(self) -> None:
        context = build_owner_visible_thread_context_packet(
            owner_visible_prior_thread=True,
            owner_confirmation_collected=True,
        )
        context["counts_as_storage_persistence_proof"] = True
        audit = build_persistent_profile_false_green_audit(
            thread_history_packet={
                "route_trace_counted_as_saved_thread_proof": False,
            },
            owner_visible_thread_context_packet=context,
            cleanup_policy_packet={
                "cleanup_deletes_persistent_profile_by_default": False,
            },
            original_drift_packet={
                "original_codex_runtime_input": False,
            },
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])

    def test_persistent_custom_r2_classifier_passes_inspection_with_two_level_preservation(self) -> None:
        packet = classify_r2_persistent_profile_history_packet(
            execution_mode="inspection",
            profile_state_preservation_packet={
                "status": "ok",
                "profile_state_preserved": True,
            },
            thread_history_preservation_packet={
                "status": "ok",
                "thread_history_preserved": True,
            },
            false_green_audit_packet={"status": "ok"},
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "WBP_PERSISTENT_CUSTOM_PROFILE_HISTORY_R2_CLASSIFIED",
        )
        self.assertTrue(packet["profile_state_preserved"])
        self.assertTrue(packet["thread_history_preserved"])
        self.assertFalse(packet["native_launch_attempted"])
        self.assertFalse(packet["direct_egress_absence_claimed"])
        self.assertFalse(packet["model_availability_claimed"])
        self.assertFalse(packet["keychain_prompt_resolved_claimed"])

    def test_persistent_custom_r2_classifier_blocks_thread_without_profile_state(self) -> None:
        packet = classify_r2_persistent_profile_history_packet(
            execution_mode="inspection",
            profile_state_preservation_packet={
                "status": "ok",
                "profile_state_preserved": True,
            },
            thread_history_preservation_packet={
                "status": "blocked",
                "thread_history_preserved": False,
            },
            false_green_audit_packet={"status": "ok"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["final_status"],
            "WBP_PERSISTENT_CUSTOM_PROFILE_HISTORY_R2_BLOCKED_THREAD_HISTORY_UNPROVEN",
        )
        self.assertTrue(packet["profile_state_preserved"])
        self.assertFalse(packet["thread_history_preserved"])
        self.assertFalse(packet["native_launch_performed"])

    def test_persistent_custom_r2_classifier_admission_mode_allows_no_launch_admission(self) -> None:
        packet = classify_r2_persistent_profile_history_packet(
            execution_mode="admission",
            profile_state_preservation_packet={
                "status": "blocked",
                "profile_state_preserved": False,
            },
            thread_history_preservation_packet={
                "status": "blocked",
                "thread_history_preserved": False,
            },
            false_green_audit_packet={"status": "ok"},
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "WBP_PERSISTENT_CUSTOM_PROFILE_HISTORY_R2_ADMITTED_NO_NATIVE_LAUNCH",
        )
        self.assertTrue(packet["admitted"])
        self.assertFalse(packet["native_launch_attempted"])
        self.assertFalse(packet["runtime_mutation_performed"])

    def test_persistent_r2b_rollback_reference_requires_repair_marker_and_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repair = root / "repair"
            backup_root = root / "wbp-custom-main.backup.20260527T031925Z"
            backup_root.mkdir(parents=True)
            marker = backup_root / ".wbp_backup_complete"
            marker.write_text('{"profile_id":"wbp-custom-main"}\n', encoding="utf-8")
            repair.mkdir()
            (repair / "backup_repair_summary_packet.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY",
                        "timestamped_backup_root": str(backup_root),
                    }
                ),
                encoding="utf-8",
            )
            (repair / "rollback_readiness_packet.json").write_text(
                json.dumps({"status": "ok", "rollback_ready": True}),
                encoding="utf-8",
            )
            (repair / "state_backup_manifest_packet.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "copied_file_count": 3,
                        "raw_content_recorded": False,
                    }
                ),
                encoding="utf-8",
            )
            (repair / "cache_exclusion_manifest_packet.json").write_text(
                json.dumps({"status": "ok", "excluded_count": 7}),
                encoding="utf-8",
            )
            (repair / "timestamped_backup_complete_marker_packet.json").write_text(
                json.dumps({"status": "ok", "marker_path": str(marker)}),
                encoding="utf-8",
            )

            packet = build_r2b_rollback_reference_packet(repair_evidence_dir=repair)

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["rollback_ready"])
        self.assertEqual(packet["copied_state_file_count"], 3)
        self.assertEqual(packet["excluded_cache_entry_count"], 7)
        self.assertTrue(packet["marker_sha256"])
        self.assertFalse(packet["repair_counts_as_thread_history_proof"])
        self.assertFalse(packet["repair_counts_as_route_or_egress_proof"])

    def test_persistent_r2b_rollback_reference_rejects_marker_outside_backup_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repair = root / "repair"
            backup_root = root / "wbp-custom-main.backup.20260527T031925Z"
            outside = root / "outside"
            backup_root.mkdir(parents=True)
            outside.mkdir()
            marker = outside / ".wbp_backup_complete"
            marker.write_text('{"profile_id":"wbp-custom-main"}\n', encoding="utf-8")
            repair.mkdir()
            for name, payload in {
                "backup_repair_summary_packet.json": {
                    "status": "ok",
                    "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY",
                    "timestamped_backup_root": str(backup_root),
                },
                "rollback_readiness_packet.json": {"status": "ok", "rollback_ready": True},
                "state_backup_manifest_packet.json": {
                    "status": "ok",
                    "copied_file_count": 3,
                    "raw_content_recorded": False,
                },
                "cache_exclusion_manifest_packet.json": {
                    "status": "ok",
                    "excluded_count": 7,
                },
                "timestamped_backup_complete_marker_packet.json": {
                    "status": "ok",
                    "marker_path": str(marker),
                },
            }.items():
                (repair / name).write_text(json.dumps(payload), encoding="utf-8")

            packet = build_r2b_rollback_reference_packet(repair_evidence_dir=repair)

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["rollback_ready"])
        self.assertFalse(packet["marker_matches_timestamped_backup_root"])

    def test_persistent_r2b_owner_nonce_packet_is_hash_only(self) -> None:
        nonce = "wbp-secret-nonce-123"
        packet = build_redacted_owner_nonce_prompt_packet(nonce=nonce)
        serialized = json.dumps(packet, sort_keys=True)

        self.assertEqual(packet["status"], "ok")
        self.assertNotIn(nonce, serialized)
        self.assertFalse(packet["nonce_recorded"])
        self.assertFalse(packet["raw_nonce_recorded"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertTrue(packet["nonce_sha256"])
        self.assertTrue(packet["prompt_hash_recorded"])

    def test_persistent_r2b_bounded_manifest_does_not_record_full_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sessions").mkdir()
            (root / "sessions" / "thread.jsonl").write_text("redacted\n", encoding="utf-8")
            (root / "Cache").mkdir()
            (root / "Cache" / "blob").write_text("cache\n", encoding="utf-8")

            packet = collect_bounded_profile_manifest(root, phase="before", sample_limit=1)

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["bounded_manifest"])
        self.assertFalse(packet["full_entry_list_recorded"])
        self.assertFalse(packet["raw_content_recorded"])
        self.assertEqual(len(packet["entries_sample"]), 1)
        self.assertTrue(packet["entries_sample_truncated"])
        self.assertIn("thread_history", packet["state_class_counts"])
        self.assertIn("cache_or_incidental_state", packet["state_class_counts"])
        self.assertTrue(packet["profile_fingerprint_sha256"])

    def test_persistent_r2b_first_launch_stops_before_owner_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_base = root / "profiles"
            profile = profile_base / "wbp-custom-main"
            (profile / "sessions").mkdir(parents=True)
            (profile / "sessions" / "thread.jsonl").write_text("redacted\n", encoding="utf-8")
            repair = root / "repair"
            backup_root = root / "wbp-custom-main.backup.20260527T031925Z"
            backup_root.mkdir()
            marker = backup_root / ".wbp_backup_complete"
            marker.write_text('{"profile_id":"wbp-custom-main"}\n', encoding="utf-8")
            repair.mkdir()
            for name, payload in {
                "backup_repair_summary_packet.json": {
                    "status": "ok",
                    "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY",
                    "timestamped_backup_root": str(backup_root),
                },
                "rollback_readiness_packet.json": {"status": "ok", "rollback_ready": True},
                "state_backup_manifest_packet.json": {
                    "status": "ok",
                    "copied_file_count": 1,
                    "raw_content_recorded": False,
                },
                "cache_exclusion_manifest_packet.json": {
                    "status": "ok",
                    "excluded_count": 1,
                },
                "timestamped_backup_complete_marker_packet.json": {
                    "status": "ok",
                    "marker_path": str(marker),
                },
            }.items():
                (repair / name).write_text(json.dumps(payload), encoding="utf-8")

            with mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.RuntimePaths.from_env",
                return_value=mock.Mock(),
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.emit_local_token",
                return_value="local-token",
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.materialize_probe_profile",
                return_value={"status": "ok"},
            ) as materialize_mock, mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.launch_native_candidate",
                return_value={"custom_process_observed": True, "pid": 123},
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.collect_codex_process_inventory",
                return_value={
                    "status": "ok",
                    "custom_process_count": 0,
                    "custom_process_lines": [],
                    "root_app_pids": [],
                },
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.prepare_isolated_home_keychain",
                return_value={
                    "status": "ok",
                    "machine_error_code": "OK",
                    "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                    "isolated_default_keychain_verified": True,
                    "isolated_search_list_verified": True,
                },
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.scan_protected_surfaces",
                side_effect=[
                    {
                        "surfaces": {
                            "codex_dir": {"root": "/protected", "exists": True, "entries": []}
                        }
                    },
                    {
                        "surfaces": {
                            "codex_dir": {
                                "root": "/protected",
                                "exists": True,
                                "entries": [{"relative_path": "ambient", "kind": "file"}],
                            }
                        }
                    },
                ],
            ):
                packets = build_r2b_first_launch_packets(
                    repo_root=Path("/repo"),
                    evidence_dir=root / "evidence",
                    repair_evidence_dir=repair,
                    profile_id="wbp-custom-main",
                    base_dir=profile_base,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.4-mini",
                    owner_nonce="owner-nonce-value",
                    startup_wait_seconds=0,
                    skip_git=True,
                )

        summary = packets["persistent_custom_profile_history_r2b_summary_packet.json"]
        stop = packets["r2b_owner_action_stop_packet.json"]
        nonce = packets["r2b_owner_nonce_prompt_packet.json"]
        admission = packets["r2b_admission_packet.json"]
        keychain = packets["persistent_r2b_keychain_preflight_first_launch_packet.json"]
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(
            summary["final_status"],
            "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_OWNER_ACTION_REQUIRED",
        )
        self.assertTrue(summary["owner_action_required"])
        self.assertFalse(summary["thread_history_preserved"])
        self.assertFalse(summary["direct_egress_absence_claimed"])
        self.assertEqual(admission["original_drift_status"], "blocked")
        self.assertTrue(admission["original_drift_blocks_filesystem_pass_claim"])
        self.assertFalse(admission["protected_filesystem_pass_claimed"])
        self.assertEqual(keychain["status"], "ok")
        self.assertTrue(keychain["isolated_default_keychain_verified"])
        self.assertTrue(keychain["isolated_search_list_verified"])
        self.assertEqual(summary["keychain_preflight_status"], "ok")
        self.assertTrue(stop["stop_required_before_relaunch_classification"])
        self.assertNotIn("owner-nonce-value", json.dumps(nonce, sort_keys=True))
        materialize_mock.assert_called_once()

    def test_persistent_r2b_relaunch_classify_enforces_owner_marker_before_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            evidence.mkdir()
            profile_base = root / "profiles"
            profile = profile_base / "wbp-custom-main"
            profile.mkdir(parents=True)
            (evidence / "persistent_custom_profile_before_bounded_manifest.json").write_text(
                json.dumps(
                    {
                        "entry_count": 1,
                        "entries_sample": [],
                        "profile_fingerprint_sha256": "before",
                        "max_mtime_ns": 0,
                    }
                ),
                encoding="utf-8",
            )
            (evidence / "r2b_original_codex_before_snapshot.json").write_text(
                json.dumps({"surfaces": {}}),
                encoding="utf-8",
            )
            repair = root / "repair"
            backup_root = root / "wbp-custom-main.backup.20260527T031925Z"
            backup_root.mkdir()
            marker = backup_root / ".wbp_backup_complete"
            marker.write_text('{"profile_id":"wbp-custom-main"}\n', encoding="utf-8")
            repair.mkdir()
            for name, payload in {
                "backup_repair_summary_packet.json": {
                    "status": "ok",
                    "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY",
                    "timestamped_backup_root": str(backup_root),
                },
                "rollback_readiness_packet.json": {"status": "ok", "rollback_ready": True},
                "state_backup_manifest_packet.json": {
                    "status": "ok",
                    "copied_file_count": 1,
                    "raw_content_recorded": False,
                },
                "cache_exclusion_manifest_packet.json": {
                    "status": "ok",
                    "excluded_count": 1,
                },
                "timestamped_backup_complete_marker_packet.json": {
                    "status": "ok",
                    "marker_path": str(marker),
                },
            }.items():
                (repair / name).write_text(json.dumps(payload), encoding="utf-8")

            with mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.terminate_custom_processes"
            ) as terminate_mock, mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.launch_native_candidate"
            ) as launch_mock:
                packets = build_r2b_relaunch_classification_packets(
                    repo_root=Path("/repo"),
                    evidence_dir=evidence,
                    repair_evidence_dir=repair,
                    profile_id="wbp-custom-main",
                    base_dir=profile_base,
                    owner_visible_prior_thread=True,
                    owner_confirmation_collected=True,
                    owner_ready_now=False,
                    prompt_entered=False,
                    nonce_used=False,
                    evidence_dir_preserved=False,
                    startup_wait_seconds=0,
                )

        summary = packets["persistent_custom_profile_history_r2b_summary_packet.json"]
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(
            summary["final_status"],
            "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_OWNER_ACTION_REQUIRED",
        )
        self.assertFalse(summary["native_launch_attempted"])
        self.assertFalse(summary["relaunch_attempted"])
        terminate_mock.assert_not_called()
        launch_mock.assert_not_called()

    def test_persistent_r2b_first_launch_blocks_when_keychain_preflight_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_base = root / "profiles"
            profile = profile_base / "wbp-custom-main"
            (profile / "sessions").mkdir(parents=True)
            (profile / "sessions" / "thread.jsonl").write_text("redacted\n", encoding="utf-8")
            repair = root / "repair"
            backup_root = root / "wbp-custom-main.backup.20260527T031925Z"
            backup_root.mkdir()
            marker = backup_root / ".wbp_backup_complete"
            marker.write_text('{"profile_id":"wbp-custom-main"}\n', encoding="utf-8")
            repair.mkdir()
            for name, payload in {
                "backup_repair_summary_packet.json": {
                    "status": "ok",
                    "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY",
                    "timestamped_backup_root": str(backup_root),
                },
                "rollback_readiness_packet.json": {"status": "ok", "rollback_ready": True},
                "state_backup_manifest_packet.json": {
                    "status": "ok",
                    "copied_file_count": 1,
                    "raw_content_recorded": False,
                },
                "cache_exclusion_manifest_packet.json": {
                    "status": "ok",
                    "excluded_count": 1,
                },
                "timestamped_backup_complete_marker_packet.json": {
                    "status": "ok",
                    "marker_path": str(marker),
                },
            }.items():
                (repair / name).write_text(json.dumps(payload), encoding="utf-8")

            with mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.RuntimePaths.from_env",
                return_value=mock.Mock(),
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.emit_local_token",
                return_value="local-token",
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.materialize_probe_profile",
                return_value={"status": "ok"},
            ) as materialize_mock, mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.launch_native_candidate"
            ) as launch_mock, mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.collect_codex_process_inventory",
                return_value={
                    "status": "ok",
                    "custom_process_count": 0,
                    "custom_process_lines": [],
                    "root_app_pids": [],
                },
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.prepare_isolated_home_keychain",
                return_value={
                    "status": "blocked",
                    "machine_error_code": "KEYCHAIN_PREFLIGHT_BLOCKED",
                    "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                    "isolated_default_keychain_verified": False,
                    "isolated_search_list_verified": False,
                },
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.scan_protected_surfaces",
                side_effect=[
                    {
                        "surfaces": {
                            "codex_dir": {"root": "/protected", "exists": True, "entries": []}
                        }
                    },
                    {
                        "surfaces": {
                            "codex_dir": {"root": "/protected", "exists": True, "entries": []}
                        }
                    },
                ],
            ):
                packets = build_r2b_first_launch_packets(
                    repo_root=Path("/repo"),
                    evidence_dir=root / "evidence",
                    repair_evidence_dir=repair,
                    profile_id="wbp-custom-main",
                    base_dir=profile_base,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.4-mini",
                    owner_nonce="owner-nonce-value",
                    startup_wait_seconds=0,
                    skip_git=True,
                )

        summary = packets["persistent_custom_profile_history_r2b_summary_packet.json"]
        keychain = packets["persistent_r2b_keychain_preflight_first_launch_packet.json"]
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(
            summary["final_status"],
            "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_KEYCHAIN_PREFLIGHT",
        )
        self.assertEqual(keychain["status"], "blocked")
        self.assertEqual(summary["keychain_preflight_status"], "blocked")
        materialize_mock.assert_not_called()
        launch_mock.assert_not_called()

    def test_persistent_r2b_first_launch_blocks_when_same_profile_process_is_already_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_base = root / "profiles"
            profile = profile_base / "wbp-custom-main"
            (profile / "sessions").mkdir(parents=True)
            (profile / "sessions" / "thread.jsonl").write_text("redacted\n", encoding="utf-8")
            repair = root / "repair"
            backup_root = root / "wbp-custom-main.backup.20260527T031925Z"
            backup_root.mkdir()
            marker = backup_root / ".wbp_backup_complete"
            marker.write_text('{"profile_id":"wbp-custom-main"}\n', encoding="utf-8")
            repair.mkdir()
            for name, payload in {
                "backup_repair_summary_packet.json": {
                    "status": "ok",
                    "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY",
                    "timestamped_backup_root": str(backup_root),
                },
                "rollback_readiness_packet.json": {"status": "ok", "rollback_ready": True},
                "state_backup_manifest_packet.json": {
                    "status": "ok",
                    "copied_file_count": 1,
                    "raw_content_recorded": False,
                },
                "cache_exclusion_manifest_packet.json": {
                    "status": "ok",
                    "excluded_count": 1,
                },
                "timestamped_backup_complete_marker_packet.json": {
                    "status": "ok",
                    "marker_path": str(marker),
                },
            }.items():
                (repair / name).write_text(json.dumps(payload), encoding="utf-8")

            with mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.collect_codex_process_inventory",
                return_value={
                    "status": "ok",
                    "custom_process_count": 1,
                    "custom_process_lines": ["123 Codex --user-data-dir=/profiles/wbp-custom-main/electron-user-data"],
                    "root_app_pids": [123],
                },
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.materialize_probe_profile"
            ) as materialize_mock, mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.launch_native_candidate"
            ) as launch_mock, mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.scan_protected_surfaces",
                side_effect=[
                    {
                        "surfaces": {
                            "codex_dir": {"root": "/protected", "exists": True, "entries": []}
                        }
                    },
                    {
                        "surfaces": {
                            "codex_dir": {"root": "/protected", "exists": True, "entries": []}
                        }
                    },
                ],
            ):
                packets = build_r2b_first_launch_packets(
                    repo_root=Path("/repo"),
                    evidence_dir=root / "evidence",
                    repair_evidence_dir=repair,
                    profile_id="wbp-custom-main",
                    base_dir=profile_base,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.4-mini",
                    owner_nonce="owner-nonce-value",
                    startup_wait_seconds=0,
                    skip_git=True,
                )

        summary = packets["persistent_custom_profile_history_r2b_summary_packet.json"]
        gate = packets["persistent_r2b_same_profile_process_gate_before_first_launch_packet.json"]
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(
            summary["final_status"],
            "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_CONCURRENT_PROFILE_PROCESS",
        )
        self.assertEqual(gate["status"], "blocked")
        materialize_mock.assert_not_called()
        launch_mock.assert_not_called()

    def test_persistent_r2b_first_launch_blocks_when_process_inventory_is_unusable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_base = root / "profiles"
            profile = profile_base / "wbp-custom-main"
            (profile / "sessions").mkdir(parents=True)
            (profile / "sessions" / "thread.jsonl").write_text("redacted\n", encoding="utf-8")
            repair = root / "repair"
            backup_root = root / "wbp-custom-main.backup.20260527T031925Z"
            backup_root.mkdir()
            marker = backup_root / ".wbp_backup_complete"
            marker.write_text('{"profile_id":"wbp-custom-main"}\n', encoding="utf-8")
            repair.mkdir()
            for name, payload in {
                "backup_repair_summary_packet.json": {
                    "status": "ok",
                    "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY",
                    "timestamped_backup_root": str(backup_root),
                },
                "rollback_readiness_packet.json": {"status": "ok", "rollback_ready": True},
                "state_backup_manifest_packet.json": {
                    "status": "ok",
                    "copied_file_count": 1,
                    "raw_content_recorded": False,
                },
                "cache_exclusion_manifest_packet.json": {
                    "status": "ok",
                    "excluded_count": 1,
                },
                "timestamped_backup_complete_marker_packet.json": {
                    "status": "ok",
                    "marker_path": str(marker),
                },
            }.items():
                (repair / name).write_text(json.dumps(payload), encoding="utf-8")

            with mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.collect_codex_process_inventory",
                return_value={"status": "ok"},
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.materialize_probe_profile"
            ) as materialize_mock, mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.launch_native_candidate"
            ) as launch_mock, mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.scan_protected_surfaces",
                side_effect=[
                    {
                        "surfaces": {
                            "codex_dir": {"root": "/protected", "exists": True, "entries": []}
                        }
                    },
                    {
                        "surfaces": {
                            "codex_dir": {"root": "/protected", "exists": True, "entries": []}
                        }
                    },
                ],
            ):
                packets = build_r2b_first_launch_packets(
                    repo_root=Path("/repo"),
                    evidence_dir=root / "evidence",
                    repair_evidence_dir=repair,
                    profile_id="wbp-custom-main",
                    base_dir=profile_base,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.4-mini",
                    owner_nonce="owner-nonce-value",
                    startup_wait_seconds=0,
                    skip_git=True,
                )

        summary = packets["persistent_custom_profile_history_r2b_summary_packet.json"]
        gate = packets["persistent_r2b_same_profile_process_gate_before_first_launch_packet.json"]
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(
            summary["final_status"],
            "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_PROCESS_INVENTORY_UNUSABLE",
        )
        self.assertEqual(gate["reason_class"], "PROCESS_INVENTORY_UNUSABLE")
        materialize_mock.assert_not_called()
        launch_mock.assert_not_called()

    def test_persistent_r2b_relaunch_blocks_when_same_profile_process_survives_termination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            evidence.mkdir()
            profile_base = root / "profiles"
            profile = profile_base / "wbp-custom-main"
            profile.mkdir(parents=True)
            (evidence / "persistent_custom_profile_before_bounded_manifest.json").write_text(
                json.dumps(
                    {
                        "entry_count": 1,
                        "entries_sample": [],
                        "profile_fingerprint_sha256": "before",
                        "max_mtime_ns": 0,
                    }
                ),
                encoding="utf-8",
            )
            (evidence / "r2b_original_codex_before_snapshot.json").write_text(
                json.dumps({"surfaces": {}}),
                encoding="utf-8",
            )
            repair = root / "repair"
            backup_root = root / "wbp-custom-main.backup.20260527T031925Z"
            backup_root.mkdir()
            marker = backup_root / ".wbp_backup_complete"
            marker.write_text('{"profile_id":"wbp-custom-main"}\n', encoding="utf-8")
            repair.mkdir()
            for name, payload in {
                "backup_repair_summary_packet.json": {
                    "status": "ok",
                    "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY",
                    "timestamped_backup_root": str(backup_root),
                },
                "rollback_readiness_packet.json": {"status": "ok", "rollback_ready": True},
                "state_backup_manifest_packet.json": {
                    "status": "ok",
                    "copied_file_count": 1,
                    "raw_content_recorded": False,
                },
                "cache_exclusion_manifest_packet.json": {
                    "status": "ok",
                    "excluded_count": 1,
                },
                "timestamped_backup_complete_marker_packet.json": {
                    "status": "ok",
                    "marker_path": str(marker),
                },
            }.items():
                (repair / name).write_text(json.dumps(payload), encoding="utf-8")

            with mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.terminate_custom_processes",
                return_value={"status": "ok"},
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.collect_codex_process_inventory",
                return_value={
                    "status": "ok",
                    "custom_process_count": 1,
                    "custom_process_lines": ["123 Codex --user-data-dir=/profiles/wbp-custom-main/electron-user-data"],
                    "root_app_pids": [123],
                },
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.launch_native_candidate"
            ) as launch_mock:
                packets = build_r2b_relaunch_classification_packets(
                    repo_root=Path("/repo"),
                    evidence_dir=evidence,
                    repair_evidence_dir=repair,
                    profile_id="wbp-custom-main",
                    base_dir=profile_base,
                    owner_visible_prior_thread=True,
                    owner_confirmation_collected=True,
                    owner_ready_now=True,
                    prompt_entered=True,
                    nonce_used=True,
                    evidence_dir_preserved=True,
                    startup_wait_seconds=0,
                )

        summary = packets["persistent_custom_profile_history_r2b_summary_packet.json"]
        gate = packets["persistent_r2b_same_profile_process_gate_before_relaunch_packet.json"]
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(
            summary["final_status"],
            "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_CONCURRENT_PROFILE_PROCESS",
        )
        self.assertEqual(gate["status"], "blocked")
        launch_mock.assert_not_called()

    def test_persistent_r2b_relaunch_blocks_when_keychain_preflight_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            evidence.mkdir()
            profile_base = root / "profiles"
            profile = profile_base / "wbp-custom-main"
            profile.mkdir(parents=True)
            (evidence / "persistent_custom_profile_before_bounded_manifest.json").write_text(
                json.dumps(
                    {
                        "entry_count": 1,
                        "entries_sample": [],
                        "profile_fingerprint_sha256": "before",
                        "max_mtime_ns": 0,
                    }
                ),
                encoding="utf-8",
            )
            (evidence / "r2b_original_codex_before_snapshot.json").write_text(
                json.dumps({"surfaces": {}}),
                encoding="utf-8",
            )
            repair = root / "repair"
            backup_root = root / "wbp-custom-main.backup.20260527T031925Z"
            backup_root.mkdir()
            marker = backup_root / ".wbp_backup_complete"
            marker.write_text('{"profile_id":"wbp-custom-main"}\n', encoding="utf-8")
            repair.mkdir()
            for name, payload in {
                "backup_repair_summary_packet.json": {
                    "status": "ok",
                    "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY",
                    "timestamped_backup_root": str(backup_root),
                },
                "rollback_readiness_packet.json": {"status": "ok", "rollback_ready": True},
                "state_backup_manifest_packet.json": {
                    "status": "ok",
                    "copied_file_count": 1,
                    "raw_content_recorded": False,
                },
                "cache_exclusion_manifest_packet.json": {
                    "status": "ok",
                    "excluded_count": 1,
                },
                "timestamped_backup_complete_marker_packet.json": {
                    "status": "ok",
                    "marker_path": str(marker),
                },
            }.items():
                (repair / name).write_text(json.dumps(payload), encoding="utf-8")

            with mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.terminate_custom_processes",
                return_value={"status": "ok"},
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.collect_codex_process_inventory",
                return_value={
                    "status": "ok",
                    "custom_process_count": 0,
                    "custom_process_lines": [],
                    "root_app_pids": [],
                },
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.prepare_isolated_home_keychain",
                return_value={
                    "status": "blocked",
                    "machine_error_code": "KEYCHAIN_PREFLIGHT_BLOCKED",
                    "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                    "isolated_default_keychain_verified": False,
                    "isolated_search_list_verified": False,
                },
            ), mock.patch(
                "tools.persistent_custom_profile_history_r2b_probe.launch_native_candidate"
            ) as launch_mock:
                packets = build_r2b_relaunch_classification_packets(
                    repo_root=Path("/repo"),
                    evidence_dir=evidence,
                    repair_evidence_dir=repair,
                    profile_id="wbp-custom-main",
                    base_dir=profile_base,
                    owner_visible_prior_thread=True,
                    owner_confirmation_collected=True,
                    owner_ready_now=True,
                    prompt_entered=True,
                    nonce_used=True,
                    evidence_dir_preserved=True,
                    startup_wait_seconds=0,
                )

        summary = packets["persistent_custom_profile_history_r2b_summary_packet.json"]
        keychain = packets["persistent_r2b_keychain_preflight_relaunch_packet.json"]
        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(
            summary["final_status"],
            "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_KEYCHAIN_PREFLIGHT",
        )
        self.assertEqual(keychain["status"], "blocked")
        self.assertEqual(summary["keychain_preflight_status"], "blocked")
        launch_mock.assert_not_called()

    def test_persistent_r2b_historical_quarantine_ignores_known_out_of_scope_dirty_entries(self) -> None:
        repo_root = Path("/repo")
        evidence_dir = repo_root / "audit_results" / "new-contour"
        status_lines = "\n".join(
            [
                " M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stderr.log",
                " M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stdout.log",
                "?? audit_results/_tmp_wbp_catalog_prep_inspect/",
                "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stderr.log",
                "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stdout.log",
                "?? audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27/",
                "?? audit_results/wbp_web_control_surface_actions_wired_and_guarded_r2_2026-05-27/",
                "?? tools/persistent_custom_profile_restoration_correlation_r5_probe.py",
            ]
        )

        with mock.patch(
            "tools.persistent_custom_profile_history_r2b_probe._run",
            return_value=status_lines,
        ):
            quarantined, unexpected = persistent_r2b_probe._historical_quarantine(
                repo_root,
                evidence_dir,
            )

        self.assertEqual(len(quarantined), 8)
        self.assertEqual(unexpected, [])

    def test_persistent_r2c_nonce_prompt_is_hash_only(self) -> None:
        nonce = "wbp-r2c-secret-nonce"
        packet = build_r2c_owner_nonce_prompt_packet(nonce=nonce)
        serialized = json.dumps(packet, sort_keys=True)

        self.assertEqual(packet["status"], "ok")
        self.assertNotIn(nonce, serialized)
        self.assertFalse(packet["nonce_recorded"])
        self.assertFalse(packet["raw_nonce_recorded"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertTrue(packet["prompt_hash_recorded"])

    def test_persistent_r2c_owner_visible_continuity_does_not_claim_storage(self) -> None:
        identity = {
            "status": "ok",
            "persistent_profile_id": "wbp-custom-main",
            "persistent_profile_root": "/tmp/wbp-custom-main",
        }
        visibility = build_r2c_owner_relaunch_visibility_packet(
            owner_relaunch_checked=True,
            same_nonce_thread_visible=True,
            target_window_clear=True,
            evidence_dir_preserved=True,
        )
        storage_context = {
            "status": "ok",
            "storage_level_thread_history_proven": False,
            "with_storage_unproven_required": True,
        }
        classification = build_r2c_thread_continuity_classification_packet(
            before_identity_packet=identity,
            relaunch_identity_packet=identity,
            first_action_packet={"status": "ok"},
            visibility_packet=visibility,
            storage_context_packet=storage_context,
            relaunch_packet={"custom_process_observed": True},
        )
        audit = build_r2c_false_green_audit(
            classification_packet=classification,
            storage_context_packet={**storage_context, "storage_context_only": True},
            visibility_packet=visibility,
        )

        self.assertEqual(classification["status"], "ok")
        self.assertEqual(
            classification["final_status"],
            "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_CLASSIFIED_WITH_STORAGE_UNPROVEN",
        )
        self.assertTrue(classification["owner_visible_thread_continuity_classified"])
        self.assertFalse(classification["storage_level_thread_history_proven"])
        self.assertFalse(classification["profile_state_preservation_proven"])
        self.assertFalse(visibility["owner_visibility_counts_as_storage_proof"])
        self.assertEqual(audit["status"], "ok")

    def test_persistent_r2c_visibility_false_blocks_continuity(self) -> None:
        identity = {
            "status": "ok",
            "persistent_profile_id": "wbp-custom-main",
            "persistent_profile_root": "/tmp/wbp-custom-main",
        }
        visibility = build_r2c_owner_relaunch_visibility_packet(
            owner_relaunch_checked=True,
            same_nonce_thread_visible=False,
            target_window_clear=True,
            evidence_dir_preserved=True,
        )
        classification = build_r2c_thread_continuity_classification_packet(
            before_identity_packet=identity,
            relaunch_identity_packet=identity,
            first_action_packet={"status": "ok"},
            visibility_packet=visibility,
            storage_context_packet={
                "storage_level_thread_history_proven": False,
                "with_storage_unproven_required": True,
            },
            relaunch_packet={"custom_process_observed": True},
        )

        self.assertEqual(classification["status"], "blocked")
        self.assertEqual(
            classification["final_status"],
            "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_BLOCKED",
        )
        self.assertTrue(classification["owner_reported_same_nonce_thread_not_visible"])
        self.assertFalse(classification["owner_visible_thread_continuity_classified"])

    def test_persistent_r2c_unclear_target_window_is_ambiguous(self) -> None:
        identity = {
            "status": "ok",
            "persistent_profile_id": "wbp-custom-main",
            "persistent_profile_root": "/tmp/wbp-custom-main",
        }
        visibility = build_r2c_owner_relaunch_visibility_packet(
            owner_relaunch_checked=True,
            same_nonce_thread_visible=True,
            target_window_clear=False,
            evidence_dir_preserved=True,
        )
        classification = build_r2c_thread_continuity_classification_packet(
            before_identity_packet=identity,
            relaunch_identity_packet=identity,
            first_action_packet={"status": "ok", "target_window_clear": True},
            visibility_packet=visibility,
            storage_context_packet={
                "storage_level_thread_history_proven": False,
                "with_storage_unproven_required": True,
            },
            relaunch_packet={"custom_process_observed": True},
        )

        self.assertEqual(classification["status"], "blocked")
        self.assertEqual(
            classification["final_status"],
            "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_AMBIGUOUS",
        )
        self.assertFalse(classification["target_window_clear"])
        self.assertFalse(classification["owner_visible_thread_continuity_classified"])

    def test_persistent_r2c_storage_context_is_supporting_only(self) -> None:
        before = {
            "entry_count": 1,
            "profile_fingerprint_sha256": "before",
            "changed_since_candidates_sample": [],
        }
        relaunch = {
            "entry_count": 2,
            "profile_fingerprint_sha256": "after",
            "changed_since_candidates_sample": [
                {"relative_path": "sessions/thread.jsonl", "state_class": "thread_history"}
            ],
        }
        packet = build_r2c_storage_context_packet(
            r2b_reference_packet={"prior_profile_state_preserved": False},
            before_manifest=before,
            relaunch_manifest=relaunch,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["storage_context_only"])
        self.assertFalse(packet["storage_level_thread_history_proven"])
        self.assertFalse(packet["storage_profile_state_preservation_proven_by_r2c"])
        self.assertTrue(packet["with_storage_unproven_required"])

    def test_persistent_storage_r3_state_classification_is_path_metadata_only(self) -> None:
        self.assertEqual(
            classify_r3_storage_state_class("electron-user-data/Local Storage/leveldb/000003.log"),
            "session_state",
        )
        self.assertEqual(
            classify_r3_storage_state_class("home/.codex/history.jsonl"),
            "thread_history",
        )
        self.assertEqual(
            classify_r3_storage_state_class(".tmp/bundled-marketplaces/openai-bundled/plugin.json"),
            "integration_state",
        )

    def test_persistent_storage_r3_inventory_records_metadata_not_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "home/.codex").mkdir(parents=True)
            (root / "home/.codex/history.jsonl").write_text("private fixture body", encoding="utf-8")
            (root / "electron-user-data/Local Storage/leveldb").mkdir(parents=True)
            (root / "electron-user-data/Local Storage/leveldb/000003.log").write_text(
                "raw local storage", encoding="utf-8"
            )

            packet = collect_persistent_storage_surface_inventory(root, sample_per_class=10)
            serialized = json.dumps(packet, sort_keys=True)

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["metadata_only"])
        self.assertFalse(packet["raw_content_recorded"])
        self.assertIn("thread_history", packet["observed_state_classes"])
        self.assertIn("session_state", packet["observed_state_classes"])
        self.assertNotIn("private fixture body", serialized)
        self.assertNotIn("raw local storage", serialized)

    def test_persistent_storage_r3_ladder_keeps_candidate_below_durable_proof(self) -> None:
        inventory = {
            "status": "ok",
            "storage_surface_observed": True,
            "state_class_counts": {
                "thread_history": 1,
                "session_state": 1,
                "cache_or_incidental_state": 1,
            },
        }
        matrix = build_persistent_storage_candidate_state_matrix(
            inventory_packet=inventory,
            r2b_reference_packet={"r2b_counts_as_r3_storage_pass": False},
            r2c_reference_packet={"r2c_counts_as_r3_storage_pass": False},
        )
        ladder = build_persistent_storage_proof_ladder_packet(
            inventory_packet=inventory,
            matrix_packet=matrix,
        )

        self.assertEqual(matrix["status"], "ok")
        self.assertTrue(ladder["storage_surface_observed"])
        self.assertTrue(ladder["thread_history_candidate"])
        self.assertFalse(ladder["thread_history_durable_proven"])
        self.assertFalse(ladder["relaunch_restoration_source_proven"])
        self.assertEqual(ladder["current_highest_proven_rung"], "thread_history_candidate")

    def test_persistent_storage_r3_visible_thread_does_not_prove_restoration_source(self) -> None:
        restoration = build_persistent_relaunch_restoration_source_packet(
            r2c_reference_packet={"prior_owner_visible_thread_continuity_classified": True},
            proof_ladder_packet={"relaunch_restoration_source_proven": False},
        )

        self.assertEqual(restoration["status"], "ok")
        self.assertFalse(restoration["owner_visible_thread_counted_as_restoration_source_proof"])
        self.assertTrue(restoration["local_storage_not_proven_remote_or_sync_possible"])
        self.assertFalse(restoration["remote_or_sync_likely_claimed"])

    def test_persistent_storage_r3_false_green_blocks_overclaims(self) -> None:
        classification = {
            "owner_visible_thread_counted_as_storage_proof": True,
            "profile_diff_counted_as_thread_history_proof": False,
            "cache_drift_counted_as_thread_preservation": False,
            "route_proof_claimed": False,
            "direct_egress_absence_claimed": False,
            "model_availability_claimed": False,
            "native_ux_acceptance_claimed": False,
            "final_e2e_claimed": False,
        }
        restoration = {
            "owner_visible_thread_counted_as_restoration_source_proof": False,
            "remote_or_sync_likely_claimed": False,
        }
        matrix = {"rows": []}
        audit = build_persistent_storage_false_green_audit(
            classification_packet=classification,
            restoration_packet=restoration,
            matrix_packet=matrix,
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])

    def test_persistent_storage_r3_classifies_with_limits_not_final_e2e(self) -> None:
        base_ok = {"status": "ok"}
        inventory = {"status": "ok", "storage_surface_observed": True}
        matrix = {"status": "ok"}
        ladder = {
            "status": "ok",
            "state_class_classified": True,
            "thread_history_candidate": True,
            "relaunch_restoration_source_proven": False,
        }
        restoration = {
            "status": "ok",
            "local_storage_restoration_source_proven": False,
        }
        classification = build_persistent_storage_truth_classification_packet(
            sync_packet=base_ok,
            r2b_reference_packet=base_ok,
            r2c_reference_packet=base_ok,
            inventory_packet=inventory,
            matrix_packet=matrix,
            proof_ladder_packet=ladder,
            restoration_packet=restoration,
        )

        self.assertEqual(classification["status"], "ok")
        self.assertEqual(
            classification["final_status"],
            "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_STORAGE_TRUTH_CLASSIFIED_WITH_LIMITS",
        )
        self.assertFalse(classification["storage_level_thread_history_proven"])
        self.assertFalse(classification["native_launch_attempted"])
        self.assertFalse(classification["live_mutation_attempted"])
        self.assertFalse(classification["final_e2e_claimed"])

    def test_persistent_storage_r4_surface_type_classification(self) -> None:
        self.assertEqual(classify_candidate_surface_type("sqlite/codex-dev.db"), "sqlite")
        self.assertEqual(classify_candidate_surface_type("session_index.jsonl"), "jsonl")
        self.assertEqual(classify_candidate_surface_type("config.json"), "json")
        self.assertEqual(
            classify_candidate_surface_type("electron-user-data/Local Storage/leveldb", kind="dir"),
            "leveldb_like",
        )

    def test_persistent_storage_r4_sqlite_schema_records_no_row_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "sessions.sqlite"
            import sqlite3

            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE threads (id TEXT, message TEXT)")
            conn.execute("INSERT INTO threads VALUES ('t1', 'private fixture body')")
            conn.commit()
            conn.close()
            candidate = {
                "relative_path": "sessions.sqlite",
                "surface_type": "sqlite",
                "size": db.stat().st_size,
                "mtime_ns": db.stat().st_mtime_ns,
            }
            packet = inspect_sqlite_schema(root, [candidate])
            serialized = json.dumps(packet, sort_keys=True)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["schema_observed_count"], 1)
        self.assertFalse(packet["row_values_recorded"])
        self.assertFalse(packet["row_count_counts_as_thread_count"])
        self.assertIn("threads", serialized)
        self.assertIn("message", serialized)
        self.assertNotIn("private fixture body", serialized)

    def test_persistent_storage_r4_json_shape_records_no_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "thread.json"
            path.write_text(
                json.dumps({"thread": {"message": "private fixture body", "count": 3}}),
                encoding="utf-8",
            )
            candidate = {
                "relative_path": "thread.json",
                "surface_type": "json",
                "size": path.stat().st_size,
                "mtime_ns": path.stat().st_mtime_ns,
            }
            packet = inspect_json_shapes(root, [candidate])
            serialized = json.dumps(packet, sort_keys=True)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["shape_observed_count"], 1)
        self.assertFalse(packet["raw_values_recorded"])
        self.assertFalse(packet["raw_lines_recorded"])
        self.assertIn("thread", serialized)
        self.assertIn("message", serialized)
        self.assertNotIn("private fixture body", serialized)

    def test_persistent_storage_r4_json_shape_redacts_sensitive_key_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "settings.json"
            path.write_text(
                json.dumps({"custom_api_key": "private fixture body", "thread": {"id": 1}}),
                encoding="utf-8",
            )
            candidate = {
                "relative_path": "settings.json",
                "surface_type": "json",
                "size": path.stat().st_size,
                "mtime_ns": path.stat().st_mtime_ns,
            }
            packet = inspect_json_shapes(root, [candidate])
            serialized = json.dumps(packet, sort_keys=True)

        self.assertEqual(packet["status"], "ok")
        self.assertIn("<sensitive_key_name_redacted>", serialized)
        self.assertNotIn("custom_api_key", serialized)
        self.assertNotIn("private fixture body", serialized)

    def test_persistent_storage_r4_hypothesis_is_not_durable_proof(self) -> None:
        candidate = {
            "status": "ok",
            "candidates": [
                {
                    "relative_path": "sessions.sqlite",
                    "surface_type": "sqlite",
                    "state_class": "session_state",
                }
            ],
        }
        sqlite_packet = {
            "databases": [{"relative_path": "sessions.sqlite", "schema_observed": True}]
        }
        matrix = build_schema_attribution_matrix(
            candidate_packet=candidate,
            sqlite_packet=sqlite_packet,
            json_packet={"surfaces": []},
            opaque_packet={"surfaces": []},
        )
        hypothesis = build_restoration_hypothesis_packet(
            matrix_packet=matrix,
            r3_reference_packet={"r3_counts_as_r4_proof": False},
        )

        self.assertEqual(matrix["status"], "ok")
        self.assertEqual(hypothesis["status"], "ok")
        self.assertEqual(hypothesis["hypothesis_count"], 1)
        self.assertFalse(hypothesis["durable_restoration_proven"])
        self.assertFalse(hypothesis["storage_level_thread_history_proven"])

    def test_persistent_storage_r4_false_green_blocks_row_value_overclaim(self) -> None:
        audit = build_r4_false_green_audit(
            sqlite_packet={
                "row_values_recorded": True,
                "row_count_counts_as_thread_count": False,
            },
            json_packet={"raw_values_recorded": False, "raw_lines_recorded": False},
            opaque_packet={"key_value_dump_recorded": False},
            matrix_packet={"semantic_content_classified": False, "durable_restoration_proven": False},
            hypothesis_packet={
                "durable_restoration_proven": False,
                "remote_or_sync_likely_claimed": False,
            },
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])

    def test_persistent_storage_r4_candidate_selection_is_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "session_index.jsonl").write_text(
                '{"message":"private fixture body"}\n',
                encoding="utf-8",
            )
            packet = select_candidate_surfaces(root)
            serialized = json.dumps(packet, sort_keys=True)

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["metadata_only"])
        self.assertFalse(packet["raw_content_recorded"])
        self.assertNotIn("private fixture body", serialized)

    def test_persistent_restore_r5_nonce_prompt_is_hash_only_and_r5_scoped(self) -> None:
        nonce = "wbp-r5-secret-nonce"
        packet = build_r5_nonce_prompt_packet(nonce=nonce)
        serialized = json.dumps(packet, sort_keys=True)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["packet_kind"], "persistent_restore_r5_nonce_prompt")
        self.assertIn("R5 restoration correlation", packet["prompt_template_shape"])
        self.assertNotIn("R2C", packet["prompt_template_shape"])
        self.assertNotIn(nonce, serialized)
        self.assertFalse(packet["nonce_recorded"])
        self.assertFalse(packet["raw_nonce_recorded"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertTrue(packet["prompt_hash_recorded"])

    def test_persistent_restore_r5_selects_high_signal_hypotheses_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "r4"
            profile = root / "profile"
            evidence.mkdir()
            profile.mkdir()
            (profile / "session_index.jsonl").write_text("private fixture body\n", encoding="utf-8")
            (profile / "sessions/2026/05/27").mkdir(parents=True)
            (profile / "sessions/2026/05/27/rollout.jsonl").write_text(
                "private fixture body\n",
                encoding="utf-8",
            )
            candidate = {
                "metadata_only": True,
                "candidate_count": 4,
                "candidates": [
                    {
                        "relative_path": "auth.json",
                        "surface_type": "json",
                        "state_class": "unknown",
                    },
                    {
                        "relative_path": ".tmp/plugins/example/conversation-to-wiki.json",
                        "surface_type": "json",
                        "state_class": "thread_history",
                    },
                    {
                        "relative_path": "session_index.jsonl",
                        "surface_type": "jsonl",
                        "state_class": "session_state",
                    },
                    {
                        "relative_path": "sessions/2026/05/27/rollout.jsonl",
                        "surface_type": "jsonl",
                        "state_class": "session_state",
                    },
                ],
            }
            hypothesis = {
                "hypothesis_count": 2,
                "hypotheses": [
                    {"relative_path": "session_index.jsonl"},
                    {"relative_path": "sessions/2026/05/27/rollout.jsonl"},
                ],
            }
            (evidence / "persistent_storage_candidate_selection_packet.json").write_text(
                json.dumps(candidate),
                encoding="utf-8",
            )
            (evidence / "persistent_storage_restoration_hypothesis_packet.json").write_text(
                json.dumps(hypothesis),
                encoding="utf-8",
            )

            packet = select_r5_hypotheses(r4_evidence_dir=evidence, profile_root=profile)
            serialized = json.dumps(packet, sort_keys=True)

        selected = {row["relative_path"] for row in packet["selected_hypotheses"]}
        self.assertEqual(packet["status"], "ok")
        self.assertIn("session_index.jsonl", selected)
        self.assertIn("sessions/2026/05/27/rollout.jsonl", selected)
        self.assertFalse(packet["auth_token_secret_surfaces_selected"])
        self.assertFalse(packet["all_r4_hypotheses_treated_equal"])
        self.assertNotIn("auth.json", selected)
        self.assertNotIn(".tmp/plugins/example/conversation-to-wiki.json", selected)
        self.assertNotIn("private fixture body", serialized)

    def test_persistent_restore_r5_visibility_result_separate_from_storage_correlation(self) -> None:
        identity = {
            "status": "ok",
            "persistent_profile_id": "wbp-custom-main",
            "persistent_profile_root": "/tmp/wbp-custom-main",
        }
        visibility = {
            "status": "ok",
            "same_nonce_thread_visible": True,
        }
        result = build_visibility_result_packet(
            before_identity_packet=identity,
            relaunch_identity_packet=identity,
            owner_visibility_packet=visibility,
            relaunch_packet={"custom_process_observed": True},
        )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["owner_visible_thread_continuity_classified"])
        self.assertFalse(result["visibility_result_counts_as_storage_correlation"])
        self.assertFalse(result["visibility_result_counts_as_durable_restoration_proof"])

    def test_persistent_restore_r5_target_delta_does_not_imply_restoration_proof(self) -> None:
        before = {
            "targets": [
                {
                    "relative_path": "session_index.jsonl",
                    "exists": True,
                    "size": 10,
                    "mtime_ns": 100,
                }
            ]
        }
        after = {
            "targets": [
                {
                    "relative_path": "session_index.jsonl",
                    "exists": True,
                    "size": 20,
                    "mtime_ns": 200,
                }
            ]
        }
        relaunch = {
            "targets": [
                {
                    "relative_path": "session_index.jsonl",
                    "exists": True,
                    "size": 20,
                    "mtime_ns": 200,
                }
            ]
        }

        packet = build_r5_target_delta_packet(
            before_manifest=before,
            after_action_manifest=after,
            relaunch_manifest=relaunch,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["changed_target_count"], 1)
        self.assertEqual(packet["retained_target_count"], 1)
        self.assertFalse(packet["target_file_changed_counts_as_participation_proof"])
        self.assertFalse(packet["target_file_retained_counts_as_participation_proof"])
        self.assertFalse(packet["target_delta_rows"][0]["target_delta_counts_as_durable_restoration_proof"])

    def test_persistent_restore_r5_visible_thread_does_not_imply_storage_proof(self) -> None:
        visibility = {
            "status": "ok",
            "owner_visible_thread_continuity_classified": True,
        }
        target_delta = {
            "status": "ok",
            "changed_target_count": 0,
            "retained_target_count": 0,
        }
        packet = build_storage_correlation_result_packet(
            visibility_result_packet=visibility,
            target_delta_packet=target_delta,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["storage_correlation_classified"])
        self.assertFalse(packet["durable_restoration_proven"])
        self.assertFalse(packet["local_only_restoration_source_proven"])
        self.assertFalse(packet["storage_level_thread_history_proven"])

    def test_persistent_restore_r5_false_green_blocks_adjacent_layer_claims(self) -> None:
        classification = {
            "durable_restoration_proven": False,
            "local_only_restoration_source_proven": False,
            "storage_level_thread_history_proven": False,
            "route_proof_claimed": True,
            "direct_egress_absence_claimed": False,
            "model_availability_claimed": False,
            "native_ux_acceptance_claimed": False,
            "original_codex_reversibility_claimed": False,
            "final_e2e_claimed": False,
        }
        audit = build_r5_false_green_audit(
            classification_packet=classification,
            visibility_result_packet={
                "visibility_result_counts_as_durable_restoration_proof": False,
            },
            storage_correlation_packet={
                "durable_restoration_proven": False,
                "local_only_restoration_source_proven": False,
                "storage_level_thread_history_proven": False,
                "remote_sync_cache_or_mixed_remains_possible": True,
            },
            target_delta_packet={
                "durable_restoration_proven": False,
                "local_only_restoration_source_proven": False,
                "storage_level_thread_history_proven": False,
                "target_file_changed_counts_as_participation_proof": False,
                "target_file_retained_counts_as_participation_proof": False,
            },
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])

    def test_persistent_restore_r5_correlation_does_not_promote_local_only_source(self) -> None:
        visibility = {
            "status": "ok",
            "owner_visible_thread_continuity_classified": True,
        }
        storage = {
            "status": "ok",
            "storage_correlation_classified": True,
        }
        classification = build_r5_correlation_classification_packet(
            visibility_result_packet=visibility,
            storage_correlation_packet=storage,
            owner_action_packet={"target_window_clear": True},
            owner_visibility_packet={"target_window_clear": True},
        )

        self.assertEqual(classification["status"], "ok")
        self.assertEqual(
            classification["final_status"],
            "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_LOCAL_RESTORATION_CORRELATION_CLASSIFIED",
        )
        self.assertFalse(classification["durable_restoration_proven"])
        self.assertFalse(classification["local_only_restoration_source_proven"])
        self.assertFalse(classification["storage_level_thread_history_proven"])
        self.assertFalse(classification["route_proof_claimed"])

    def test_external_evidence_validation_accepts_import_derived_alternatives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            external_dir = Path(tmp)
            validation = validate_external_evidence_packets(
                external_evidence_dir=external_dir,
                required_packets=[
                    "domain_attribution_limit_packet.json or import-derived domain attribution limit",
                    "owner_visible_response_context_packet.json or import-derived context-only packet",
                ],
                import_derived_alternatives={
                    "import-derived domain attribution limit": {
                        "packet_kind": "domain_attribution_limit",
                        "status": "ok",
                    },
                    "import-derived context-only packet": {
                        "packet_kind": "owner_visible_response_context",
                        "status": "ok",
                        "context_only": True,
                    },
                },
            )

        self.assertEqual(validation["status"], "ok")
        self.assertEqual(
            validation["alternative_statuses"][
                "domain_attribution_limit_packet.json or import-derived domain attribution limit"
            ],
            "import_derived",
        )
        self.assertEqual(validation["parsed_packet_count"], 2)

    def test_detached_egress_process_binding_accepts_launch_and_observation_packets(self) -> None:
        packet = build_detached_egress_process_binding_validation_packet(
            validation_packet={
                "external_evidence_dir_exists": True,
                "parsed_packets": {
                    "native_custom_launch_packet.json": {
                        "custom_process_observed": True,
                    },
                    "native_process_network_observation_packet.json": {
                        "process_tree_observed": True,
                    },
                    "native_direct_egress_claim_packet.json": {
                        "custom_process_bound": True,
                    },
                },
            }
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["native_process_bound"])
        self.assertFalse(packet["counts_as_native_ux_proof"])

    def test_detached_egress_import_hash_mismatch_blocks(self) -> None:
        repo_root = Path("/tmp/wbp-repo")
        command = build_detached_egress_execution_command_packet(
            repo_root=repo_root,
            evidence_dir=repo_root / "audit_results" / "egress_EXTERNAL_2026-05-26",
        )
        verification = build_detached_egress_command_hash_verification_packet(
            command_packet=command,
            expected_hash_packet={"status": "ok", "command_sha256": "wrong"},
        )

        self.assertEqual(verification["status"], "blocked")
        self.assertFalse(verification["command_hash_matches"])

    def test_detached_egress_missing_external_evidence_blocks_claim(self) -> None:
        repo_root = Path("/tmp/wbp-repo")
        external_dir = repo_root / "audit_results" / "egress_EXTERNAL_2026-05-26"
        command = build_detached_egress_execution_command_packet(
            repo_root=repo_root,
            evidence_dir=external_dir,
        )
        command_hash = build_detached_egress_command_hash_packet(command_packet=command)
        required = build_detached_egress_future_result_required_packets_packet()
        validation = validate_external_evidence_packets(
            external_evidence_dir=external_dir,
            required_packets=required["required_packets"],
        )
        imported = build_detached_egress_external_evidence_import_packet(
            external_evidence_dir=external_dir,
            validation_packet=validation,
        )
        classification = build_detached_egress_network_claim_classification_packet(
            safety_admission_prerequisite_packet={"status": "ok"},
            handoff_prerequisite_packet={"status": "ok"},
            command_hash_verification_packet=(
                build_detached_egress_command_hash_verification_packet(
                    command_packet=command,
                    expected_hash_packet=command_hash,
                )
            ),
            external_evidence_import_packet=imported,
            secret_scan_packet=build_detached_egress_import_secret_scan_packet(
                external_evidence_dir=external_dir,
                matches=[],
            ),
            process_binding_validation_packet=(
                build_detached_egress_process_binding_validation_packet(
                    validation_packet=validation,
                )
            ),
            wbp_trace_validation_packet=build_detached_egress_wbp_trace_validation_packet(
                validation_packet=validation,
            ),
            network_observation_validation_packet=(
                build_detached_egress_network_observation_validation_packet(
                    validation_packet=validation,
                )
            ),
        )

        self.assertEqual(imported["status"], "blocked")
        self.assertEqual(
            classification["final_status"],
            "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_EXTERNAL_EVIDENCE_MISSING",
        )
        self.assertFalse(
            classification[
                "direct_non_wbp_model_egress_absent_within_bounded_window"
            ]
        )

    def test_detached_egress_positive_absence_requires_trace_and_process(self) -> None:
        classification = build_detached_egress_network_claim_classification_packet(
            safety_admission_prerequisite_packet={"status": "ok"},
            handoff_prerequisite_packet={"status": "ok"},
            command_hash_verification_packet={"status": "ok"},
            external_evidence_import_packet={
                "status": "ok",
                "external_evidence_dir_exists": True,
            },
            secret_scan_packet={"status": "ok"},
            process_binding_validation_packet={
                "status": "blocked",
                "native_process_bound": False,
            },
            wbp_trace_validation_packet={"status": "ok", "wbp_trace_confirmed": True},
            network_observation_validation_packet={
                "status": "ok",
                "direct_non_wbp_model_egress_absent_within_bounded_window": True,
            },
        )

        self.assertEqual(
            classification["final_status"],
            "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_PROCESS_BINDING_MISSING",
        )
        self.assertFalse(
            classification[
                "direct_non_wbp_model_egress_absent_within_bounded_window"
            ]
        )

    def test_detached_egress_direct_egress_observed_is_classified(self) -> None:
        classification = build_detached_egress_network_claim_classification_packet(
            safety_admission_prerequisite_packet={"status": "ok"},
            handoff_prerequisite_packet={"status": "ok"},
            command_hash_verification_packet={"status": "ok"},
            external_evidence_import_packet={
                "status": "ok",
                "external_evidence_dir_exists": True,
            },
            secret_scan_packet={"status": "ok"},
            process_binding_validation_packet={
                "status": "ok",
                "native_process_bound": True,
            },
            wbp_trace_validation_packet={"status": "ok", "wbp_trace_confirmed": True},
            network_observation_validation_packet={
                "status": "ok",
                "direct_non_wbp_model_egress_observed": True,
                "direct_non_wbp_model_egress_absent_within_bounded_window": False,
            },
        )

        self.assertEqual(classification["status"], "ok")
        self.assertEqual(
            classification["final_status"],
            "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_OBSERVED",
        )
        self.assertTrue(classification["direct_non_wbp_model_egress_observed"])
        self.assertFalse(
            classification[
                "direct_non_wbp_model_egress_absent_within_bounded_window"
            ]
        )

    def test_detached_egress_import_false_green_blocks_global_absence(self) -> None:
        audit = build_detached_egress_import_false_green_audit(
            classification_packet={
                "final_status": "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_ABSENT_WITH_LIMITS",
                "native_launch_attempted_from_current_thread": False,
                "native_ux_claimed": False,
                "model_availability_reproved": False,
                "original_codex_reversibility_claimed": False,
                "final_e2e_claimed": False,
                "full_network_absence_proven": True,
                "api_openai_com_absence_proven_globally": False,
            },
            external_evidence_import_packet={"external_result_imported": True},
            command_hash_verification_packet={"command_hash_matches": True},
            wbp_trace_validation_packet={"wbp_trace_confirmed": True},
            process_binding_validation_packet={"native_process_bound": True},
            network_observation_validation_packet={
                "direct_non_wbp_model_egress_absent_within_bounded_window": True,
            },
        )

        self.assertEqual(audit["status"], "blocked")
        self.assertTrue(audit["forbidden_claims_present"])

    def test_detached_egress_import_tool_emits_blocked_missing_evidence_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            real_repo = Path(__file__).resolve().parents[1]
            (repo_root / "tools").mkdir()
            (repo_root / "tools" / "native_custom_direct_egress_classification_probe.py").write_text(
                "# placeholder\n",
                encoding="utf-8",
            )
            handoff_dir = repo_root / "audit_results" / "handoff"
            handoff_dir.mkdir(parents=True)
            external_dir = repo_root / "audit_results" / "egress_EXTERNAL_2026-05-26"
            command = build_detached_egress_execution_command_packet(
                repo_root=repo_root,
                evidence_dir=external_dir,
            )
            command_hash = build_detached_egress_command_hash_packet(
                command_packet=command,
            )
            command_admission = build_detached_egress_command_admission_packet(
                command_packet=command,
                repo_root=repo_root,
            )
            required = build_detached_egress_future_result_required_packets_packet()
            import_contract = build_detached_egress_future_result_import_contract_packet(
                required_packets_packet=required,
            )
            packets = {
                "detached_egress_execution_command_packet.json": command,
                "detached_egress_command_hash_packet.json": command_hash,
                "detached_egress_command_admission_packet.json": command_admission,
                "future_result_import_contract_packet.json": import_contract,
                "handoff_summary_packet.json": {
                    "packet_kind": "detached_egress_execution_handoff_summary",
                    "status": "ok",
                    "final_status": "NATIVE_DETACHED_EGRESS_EXECUTION_HANDOFF_READY_OWNER_ACTION_REQUIRED",
                    "external_evidence_dir": str(external_dir),
                },
            }
            for name, packet in packets.items():
                (handoff_dir / name).write_text(
                    json.dumps(packet, sort_keys=True),
                    encoding="utf-8",
                )
            safety_path = repo_root / "audit_results" / "safety.json"
            safety_path.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "allowed_final_claim": "NATIVE_CUSTOM_SAFETY_ADMISSION_INSPECTION_ONLY_CLASSIFIED",
                        "native_launch_attempted": False,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            evidence_dir = repo_root / "audit_results" / "import"
            script = real_repo / "tools" / "detached_native_custom_egress_import_r1_probe.py"
            process = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--repo-root",
                    str(repo_root),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--handoff-dir",
                    str(handoff_dir),
                    "--safety-admission-path",
                    str(safety_path),
                    "--skip-git",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(process.returncode, 0, process.stderr)
            summary = json.loads(
                (
                    evidence_dir
                    / "detached_native_custom_egress_import_summary_packet.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                summary["final_status"],
                "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_EXTERNAL_EVIDENCE_MISSING",
            )
            self.assertTrue(summary["command_hash_matches"])
            self.assertFalse(summary["external_evidence_dir_exists"])
            self.assertFalse(summary["native_launch_attempted_from_current_thread"])
            self.assertFalse(summary["direct_egress_absence_claimed"])


if __name__ == "__main__":
    unittest.main()
