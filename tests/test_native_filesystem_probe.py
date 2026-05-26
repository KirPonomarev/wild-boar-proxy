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
    build_machine_ui_waiver_packet,
    build_native_owner_ux_false_green_audit,
    build_native_direct_egress_capability_packet,
    build_native_direct_egress_claim_packet,
    build_native_direct_egress_false_green_audit,
    build_native_route_trace_binding_packet,
    build_owner_manual_ux_check_packet,
    build_owner_nonce_prompt_packet,
    build_owner_ux_action_boundary_packet,
    build_owner_ux_historical_false_green_audit,
    build_owner_ux_layer_boundary_packet,
    build_owner_action_boundary_packet,
    build_owner_visible_response_observation_packet,
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
    scan_tree,
    summarize_idle_baseline_windows,
    validate_external_evidence_packets,
)


class NativeFilesystemProbeTests(unittest.TestCase):
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
        self.assertIn("requires_openai_auth = false", config)
        self.assertNotIn("experimental_bearer_token", config)

    def test_provider_config_bearer_branch_is_explicit_auth_surface(self) -> None:
        with mock.patch(
            "wild_boar_proxy.native_filesystem_probe._cli_proxy_api_key",
            return_value="fixture-token",
        ):
            config = build_provider_config(
                endpoint="http://127.0.0.1:8318/v1",
                model="gpt-5.4-mini",
                auth_command_path=Path("/repo/wbp_codex_auth_command.py"),
            )

        self.assertIn('experimental_bearer_token = "fixture-token"', config)
        self.assertNotIn("[model_providers.wbp.auth]", config)
        self.assertIn('wire_api = "responses"', config)

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


if __name__ == "__main__":
    unittest.main()
