# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest

from wild_boar_proxy.codex_recovery_contract import (
    build_custom_recovery_admitted_session_actions_packet,
    build_custom_recovery_contract_packet,
    build_custom_recovery_rollback_point_dry_run_packet,
    build_custom_recovery_rollback_process_owner_contract_packet,
)


def ok_readonly(source: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "ok",
        "source": source,
        "primary_truth_ok": True,
        "summary": {"machine_error_code": "OK"},
    }


class CodexRecoveryContractTests(unittest.TestCase):
    def test_contract_is_dry_run_only_even_when_readonly_sources_are_ok(self) -> None:
        packet = build_custom_recovery_contract_packet(
            original_status={"status": "ok"},
            custom_status={"status": "ok"},
            accounts_readonly=ok_readonly("accounts_readonly"),
            api_readonly=ok_readonly("api_connections_readonly"),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "RECOVERY_CONTRACT_DRY_RUN_ONLY")
        self.assertEqual(packet["claim_scope"], "custom_codex_recovery_contract_dry_run_only")
        self.assertTrue(packet["contract_aggregator_only"])
        self.assertFalse(packet["contract_endpoint_mutation_allowed"])
        self.assertFalse(packet["recovery_live_ready"])
        self.assertFalse(packet["operator_ready_claimed"])
        self.assertFalse(packet["rollback_claimed"])
        self.assertFalse(packet["process_kill_claimed"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["browser_payload_allowed"])
        self.assertEqual(packet["browser_payload_allowed_keys"], [])
        self.assertIn("CODEX_HOME", packet["forbidden_browser_fields"])
        self.assertIn("HOME", packet["forbidden_browser_fields"])
        self.assertTrue(packet["dangerous_actions_disabled"])
        self.assertTrue(packet["diagnostics_support_artifact_only"])
        self.assertFalse(packet["fresh_truth"])
        self.assertTrue(packet["historical_isolation_proof_only"])
        self.assertTrue(packet["readonly_sources"]["accounts_readonly_ok"])
        self.assertTrue(packet["readonly_sources"]["api_readonly_ok"])

        actions = {action["id"]: action for action in packet["actions"]}
        self.assertEqual(actions["stop_selected_custom_session"]["status"], "admitted")
        self.assertEqual(actions["cleanup_owned_session_root"]["status"], "admitted")
        self.assertEqual(actions["rollback_readiness"]["status"], "dry_run_only")
        self.assertFalse(actions["rollback_readiness"]["mutation_allowed"])
        self.assertEqual(
            actions["stuck_process_kill_readiness"]["disabled_reason_code"],
            "PROCESS_KILL_CONTRACT_NOT_ADMITTED",
        )
        self.assertEqual(actions["cleanup_arbitrary_path"]["status"], "disabled")
        self.assertEqual(actions["touch_original_codex_profile"]["status"], "disabled")
        self.assertEqual(packet["next_contour"], "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_DRY_RUN_PASS")

    def test_readonly_integration_failure_blocks_contract_status(self) -> None:
        packet = build_custom_recovery_contract_packet(
            original_status={"status": "ok"},
            custom_status={"status": "ok"},
            accounts_readonly={
                "status": "integration_failure",
                "primary_truth_ok": False,
                "summary": {"machine_error_code": "UI_ACCOUNTS_READONLY_FETCH_FAILED"},
            },
            api_readonly=ok_readonly("api_connections_readonly"),
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "RECOVERY_CONTRACT_DRY_RUN_ONLY")
        self.assertEqual(
            packet["contract_block_reason_code"],
            "RECOVERY_CONTRACT_READONLY_SOURCE_FAILED",
        )
        self.assertFalse(packet["readonly_sources"]["accounts_readonly_ok"])
        self.assertTrue(packet["readonly_sources"]["api_readonly_ok"])
        self.assertFalse(packet["recovery_live_ready"])

    def test_admitted_session_actions_ready_requires_contract_and_server_session(self) -> None:
        contract = build_custom_recovery_contract_packet(
            original_status={"status": "ok"},
            custom_status={"status": "ok"},
            accounts_readonly=ok_readonly("accounts_readonly"),
            api_readonly=ok_readonly("api_connections_readonly"),
        )
        sessions = {
            "status": "ok",
            "session_count": 1,
            "sessions": [
                {
                    "session_id": "ccs-test-session",
                    "session_root_scope": "owned_temp_session_root",
                    "current_codex_home_used": False,
                    "model_server_issued": True,
                    "selection_proven": True,
                    "cleanup_state": "active",
                }
            ],
        }

        packet = build_custom_recovery_admitted_session_actions_packet(
            contract_packet=contract,
            sessions_packet=sessions,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "ADMITTED_SESSION_ACTIONS_READY")
        self.assertEqual(
            packet["claim_scope"],
            "custom_codex_recovery_admitted_session_actions_only",
        )
        self.assertTrue(packet["session_admitted_actions_ready"])
        self.assertTrue(packet["selected_session_cancel_ready"])
        self.assertTrue(packet["owned_session_cleanup_ready"])
        self.assertTrue(packet["selected_session_packet_valid"])
        self.assertFalse(packet["contract_endpoint_mutation_allowed"])
        self.assertFalse(packet["browser_payload_allowed"])
        self.assertEqual(packet["browser_payload_allowed_keys"], [])
        self.assertIn("backend_id", packet["forbidden_browser_fields"])
        self.assertFalse(packet["recovery_operator_ready"])
        self.assertFalse(packet["operator_ready_claimed"])
        self.assertFalse(packet["rollback_operator_ready"])
        self.assertFalse(packet["rollback_claimed"])
        self.assertFalse(packet["process_kill_operator_ready"])
        self.assertFalse(packet["process_kill_claimed"])
        self.assertTrue(packet["diagnostics_support_artifact_only"])
        self.assertFalse(packet["diagnostics_counted_as_recovery_action"])
        self.assertFalse(packet["readonly_checks_counted_as_mutation"])
        self.assertFalse(packet["session_create_counted_as_recovery_action"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertFalse(packet["current_codex_home_touched"])
        self.assertFalse(packet["arbitrary_path_accepted"])
        self.assertTrue(packet["dangerous_actions_disabled"])
        self.assertFalse(packet["dangerous_action_mutation_allowed"])
        actions = {action["id"]: action for action in packet["actions"]}
        self.assertTrue(actions["stop_selected_custom_session"]["ready"])
        self.assertTrue(actions["cleanup_owned_session_root"]["ready"])
        self.assertFalse(actions["rollback_readiness"]["ready"])
        self.assertFalse(actions["stuck_process_kill_readiness"]["ready"])
        self.assertFalse(packet["next_contour_claimed"])

    def test_admitted_session_actions_block_without_selected_session(self) -> None:
        contract = build_custom_recovery_contract_packet(
            original_status={"status": "ok"},
            custom_status={"status": "ok"},
            accounts_readonly=ok_readonly("accounts_readonly"),
            api_readonly=ok_readonly("api_connections_readonly"),
        )

        packet = build_custom_recovery_admitted_session_actions_packet(
            contract_packet=contract,
            sessions_packet={"status": "ok", "session_count": 0, "sessions": []},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "ADMITTED_SESSION_ACTIONS_BLOCKED")
        self.assertEqual(packet["block_reason_code"], "SELECTED_SESSION_REQUIRED")
        self.assertFalse(packet["session_admitted_actions_ready"])
        self.assertFalse(packet["selected_session_cancel_ready"])
        self.assertFalse(packet["owned_session_cleanup_ready"])
        self.assertFalse(packet["recovery_operator_ready"])
        self.assertFalse(packet["rollback_operator_ready"])
        self.assertFalse(packet["process_kill_operator_ready"])

    def test_admitted_session_actions_block_on_readonly_contract_failure(self) -> None:
        contract = build_custom_recovery_contract_packet(
            original_status={"status": "ok"},
            custom_status={"status": "blocked"},
            accounts_readonly=ok_readonly("accounts_readonly"),
            api_readonly=ok_readonly("api_connections_readonly"),
        )
        sessions = {
            "status": "ok",
            "session_count": 1,
            "sessions": [
                {
                    "session_id": "ccs-test-session",
                    "session_root_scope": "owned_temp_session_root",
                    "current_codex_home_used": False,
                    "model_server_issued": True,
                    "selection_proven": True,
                    "cleanup_state": "active",
                }
            ],
        }

        packet = build_custom_recovery_admitted_session_actions_packet(
            contract_packet=contract,
            sessions_packet=sessions,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["block_reason_code"],
            "RECOVERY_CONTRACT_READONLY_SOURCE_FAILED",
        )
        self.assertFalse(packet["session_admitted_actions_ready"])
        self.assertFalse(packet["selected_session_cancel_ready"])
        self.assertFalse(packet["owned_session_cleanup_ready"])
        self.assertFalse(packet["contract_readonly_sources_ok"])
        self.assertFalse(packet["recovery_operator_ready"])
        self.assertFalse(packet["rollback_operator_ready"])
        self.assertFalse(packet["process_kill_operator_ready"])

    def test_rollback_process_owner_contract_is_dry_run_only(self) -> None:
        contract = build_custom_recovery_contract_packet(
            original_status={"status": "ok"},
            custom_status={"status": "ok"},
            accounts_readonly=ok_readonly("accounts_readonly"),
            api_readonly=ok_readonly("api_connections_readonly"),
        )

        packet = build_custom_recovery_rollback_process_owner_contract_packet(
            contract_packet=contract,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "ROLLBACK_PROCESS_OWNER_DRY_RUN_CONTRACT")
        self.assertEqual(
            packet["claim_scope"],
            "custom_codex_recovery_rollback_process_owner_dry_run_contract_only",
        )
        self.assertTrue(packet["rollback_contract_defined"])
        self.assertFalse(packet["rollback_live_ready"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertTrue(packet["rollback_point_required"])
        self.assertFalse(packet["rollback_point_present"])
        self.assertTrue(packet["rollback_write_surfaces_required"])
        self.assertFalse(packet["rollback_write_surfaces_declared"])
        self.assertTrue(packet["rollback_verification_packet_required"])
        self.assertFalse(packet["rollback_verification_packet_present"])
        self.assertTrue(packet["process_owner_contract_defined"])
        self.assertFalse(packet["process_kill_live_ready"])
        self.assertFalse(packet["process_kill_admitted"])
        self.assertTrue(packet["owned_process_identity_required"])
        self.assertFalse(packet["owned_process_identity_present"])
        self.assertTrue(packet["current_codex_process_exclusion_required"])
        self.assertFalse(packet["current_codex_process_excluded"])
        self.assertFalse(packet["current_codex_process_candidate"])
        self.assertFalse(packet["recovery_operator_ready"])
        self.assertFalse(packet["operator_ready_claimed"])
        self.assertFalse(packet["rollback_operator_ready"])
        self.assertFalse(packet["rollback_claimed"])
        self.assertFalse(packet["process_kill_operator_ready"])
        self.assertFalse(packet["process_kill_claimed"])
        self.assertTrue(packet["diagnostics_support_artifact_only"])
        self.assertFalse(packet["diagnostics_counted_as_recovery_action"])
        self.assertFalse(packet["readonly_checks_counted_as_mutation"])
        self.assertFalse(packet["session_create_counted_as_recovery_action"])
        self.assertFalse(packet["contract_endpoint_mutation_allowed"])
        self.assertFalse(packet["browser_payload_allowed"])
        self.assertEqual(packet["browser_payload_allowed_keys"], [])
        self.assertIn("path", packet["forbidden_browser_fields"])
        self.assertIn("pid", packet["forbidden_browser_fields"])
        self.assertIn("process_id", packet["forbidden_browser_fields"])
        self.assertIn("CODEX_HOME", packet["forbidden_browser_fields"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertFalse(packet["current_codex_home_touched"])
        self.assertFalse(packet["arbitrary_path_accepted"])
        self.assertFalse(packet["arbitrary_process_kill_allowed"])
        self.assertFalse(packet["arbitrary_path_cleanup_allowed"])
        self.assertTrue(packet["dangerous_actions_disabled"])
        self.assertFalse(packet["dangerous_action_mutation_allowed"])
        prerequisites = {item["id"]: item for item in packet["prerequisites"]}
        self.assertFalse(prerequisites["rollback_point"]["present"])
        self.assertTrue(prerequisites["rollback_point"]["blocks_live_ready"])
        self.assertFalse(prerequisites["rollback_point"]["blocks_contract_definition"])
        self.assertFalse(prerequisites["current_codex_process_exclusion"]["present"])
        actions = {action["id"]: action for action in packet["actions"]}
        self.assertFalse(actions["rollback_readiness"]["live_ready"])
        self.assertFalse(actions["rollback_readiness"]["admitted"])
        self.assertFalse(actions["stuck_process_kill_readiness"]["live_ready"])
        self.assertFalse(actions["stuck_process_kill_readiness"]["admitted"])
        self.assertFalse(actions["cleanup_arbitrary_path"]["admitted"])
        self.assertEqual(packet["next_contour"], "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_DRY_RUN_PASS")
        self.assertFalse(packet["next_contour_claimed"])

    def test_rollback_process_owner_contract_blocks_if_base_actions_are_missing(self) -> None:
        packet = build_custom_recovery_rollback_process_owner_contract_packet(
            contract_packet={
                "status": "ok",
                "rollback_claimed": False,
                "process_kill_claimed": False,
                "dangerous_actions_disabled": True,
                "browser_payload_allowed": False,
                "readonly_sources": {},
                "actions": [],
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "ROLLBACK_PROCESS_OWNER_CONTRACT_INCOMPLETE")
        self.assertEqual(packet["block_reason_code"], "ROLLBACK_PROCESS_OWNER_ACTIONS_MISSING")
        self.assertFalse(packet["rollback_contract_defined"])
        self.assertFalse(packet["process_owner_contract_defined"])
        self.assertFalse(packet["rollback_live_ready"])
        self.assertFalse(packet["process_kill_live_ready"])
        self.assertFalse(packet["recovery_operator_ready"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertFalse(packet["process_kill_admitted"])

    def test_rollback_point_dry_run_contract_is_metadata_only_without_writes(self) -> None:
        contract = build_custom_recovery_contract_packet(
            original_status={"status": "ok"},
            custom_status={"status": "ok"},
            accounts_readonly=ok_readonly("accounts_readonly"),
            api_readonly=ok_readonly("api_connections_readonly"),
        )
        process_owner = build_custom_recovery_rollback_process_owner_contract_packet(
            contract_packet=contract,
        )

        packet = build_custom_recovery_rollback_point_dry_run_packet(
            rollback_process_owner_contract=process_owner,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "ROLLBACK_POINT_DRY_RUN_CONTRACT")
        self.assertEqual(packet["claim_scope"], "custom_codex_recovery_rollback_point_dry_run_only")
        self.assertEqual(
            packet["contract_endpoint"],
            "/api/codex/custom/recovery/rollback-point-dry-run",
        )
        self.assertFalse(packet["contract_endpoint_mutation_allowed"])
        self.assertFalse(packet["browser_payload_allowed"])
        self.assertEqual(packet["browser_payload_allowed_keys"], [])
        for forbidden_field in (
            "path",
            "snapshot_path",
            "rollback_target",
            "pid",
            "process_id",
            "CODEX_HOME",
            "HOME",
        ):
            self.assertIn(forbidden_field, packet["forbidden_browser_fields"])
        self.assertTrue(packet["rollback_point_contract_defined"])
        self.assertFalse(packet["rollback_point_present"])
        self.assertFalse(packet["rollback_point_create_admitted"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertFalse(packet["rollback_live_ready"])
        self.assertTrue(packet["rollback_write_surfaces_contract_defined"])
        self.assertFalse(packet["rollback_write_surfaces_machine_checked"])
        self.assertTrue(packet["rollback_write_surfaces_dry_run_checked"])
        self.assertTrue(packet["rollback_verification_packet_defined"])
        self.assertFalse(packet["rollback_verification_packet_present"])
        self.assertFalse(packet["recovery_operator_ready"])
        self.assertFalse(packet["operator_ready_claimed"])
        self.assertFalse(packet["rollback_operator_ready"])
        self.assertFalse(packet["rollback_claimed"])
        self.assertFalse(packet["process_kill_operator_ready"])
        self.assertFalse(packet["process_kill_claimed"])
        self.assertFalse(packet["process_kill_live_ready"])
        self.assertFalse(packet["process_kill_admitted"])
        self.assertFalse(packet["filesystem_write_performed"])
        self.assertFalse(packet["snapshot_file_created"])
        self.assertFalse(packet["snapshot_create_admitted"])
        self.assertFalse(packet["snapshot_target_browser_supplied"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["current_codex_home_touched"])
        self.assertFalse(packet["current_codex_home_allowed_surface"])
        self.assertFalse(packet["auth_material_allowed_surface"])
        self.assertFalse(packet["arbitrary_path_accepted"])
        self.assertFalse(packet["arbitrary_path_allowed_surface"])
        self.assertTrue(packet["dangerous_actions_disabled"])
        self.assertFalse(packet["dangerous_action_mutation_allowed"])
        self.assertEqual(
            packet["allowed_write_surface_ids"],
            [
                "owned_temp_session_root",
                "owned_wbp_runtime_state",
                "owned_generated_recovery_artifact",
            ],
        )
        self.assertNotIn("current_codex_home", packet["allowed_write_surface_ids"])
        for surface in packet["allowed_write_surfaces"]:
            self.assertEqual(surface["status"], "contract_metadata_only")
            self.assertFalse(surface["filesystem_write_admitted"])
            self.assertFalse(surface["machine_checked"])
        for forbidden_surface in (
            "current_codex_home",
            "current_codex_process",
            "auth_material",
            "token_store",
            "arbitrary_path",
            "external_api_route_secret",
        ):
            self.assertIn(forbidden_surface, packet["forbidden_surfaces"])
        actions = {action["id"]: action for action in packet["actions"]}
        self.assertEqual(actions["rollback_point_create"]["status"], "dry_run_only")
        self.assertFalse(actions["rollback_point_create"]["mutation_allowed"])
        self.assertFalse(actions["rollback_point_create"]["browser_payload_allowed"])
        self.assertFalse(actions["rollback_point_create"]["admitted"])
        self.assertEqual(actions["rollback_apply"]["status"], "disabled")
        self.assertFalse(actions["rollback_apply"]["mutation_allowed"])
        self.assertFalse(actions["rollback_apply"]["admitted"])
        self.assertEqual(
            packet["next_contour"],
            "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_ADMISSION_PASS",
        )
        self.assertFalse(packet["next_contour_claimed"])

    def test_rollback_point_dry_run_blocks_without_process_owner_contract(self) -> None:
        packet = build_custom_recovery_rollback_point_dry_run_packet(
            rollback_process_owner_contract={"status": "blocked"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "ROLLBACK_PROCESS_OWNER_CONTRACT_REQUIRED")
        self.assertEqual(packet["block_reason_code"], "ROLLBACK_PROCESS_OWNER_CONTRACT_REQUIRED")
        self.assertFalse(packet["rollback_point_contract_defined"])
        self.assertFalse(packet["rollback_point_create_admitted"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertFalse(packet["rollback_live_ready"])
        self.assertTrue(packet["rollback_write_surfaces_contract_defined"])
        self.assertFalse(packet["rollback_write_surfaces_machine_checked"])
        self.assertTrue(packet["rollback_write_surfaces_dry_run_checked"])
        self.assertTrue(packet["rollback_verification_packet_defined"])
        self.assertFalse(packet["filesystem_write_performed"])
        self.assertFalse(packet["snapshot_file_created"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["browser_payload_allowed"])
        self.assertTrue(packet["dangerous_actions_disabled"])

    def test_rollback_point_dry_run_rejects_shallow_green_process_owner_packet(self) -> None:
        packet = build_custom_recovery_rollback_point_dry_run_packet(
            rollback_process_owner_contract={
                "status": "ok",
                "machine_error_code": "ROLLBACK_PROCESS_OWNER_DRY_RUN_CONTRACT",
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "ROLLBACK_PROCESS_OWNER_CONTRACT_REQUIRED")
        self.assertFalse(packet["rollback_point_contract_defined"])
        self.assertFalse(packet["rollback_point_present"])
        self.assertFalse(packet["rollback_point_create_admitted"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertFalse(packet["rollback_live_ready"])
        self.assertFalse(packet["filesystem_write_performed"])
        self.assertFalse(packet["snapshot_file_created"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["browser_payload_allowed"])
        self.assertTrue(packet["dangerous_actions_disabled"])

    def test_rollback_point_dry_run_rejects_green_packet_without_source_actions(self) -> None:
        contract = build_custom_recovery_contract_packet(
            original_status={"status": "ok"},
            custom_status={"status": "ok"},
            accounts_readonly=ok_readonly("accounts_readonly"),
            api_readonly=ok_readonly("api_connections_readonly"),
        )
        process_owner = build_custom_recovery_rollback_process_owner_contract_packet(
            contract_packet=contract,
        )
        forged_process_owner = {
            **process_owner,
            "readonly_sources": {
                "original_status_ok": True,
                "custom_status_ok": True,
                "accounts_readonly_ok": True,
                "api_readonly_ok": True,
            },
            "actions": [],
        }

        packet = build_custom_recovery_rollback_point_dry_run_packet(
            rollback_process_owner_contract=forged_process_owner,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "ROLLBACK_PROCESS_OWNER_CONTRACT_REQUIRED")
        self.assertFalse(packet["rollback_point_contract_defined"])
        self.assertFalse(packet["rollback_point_create_admitted"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertFalse(packet["rollback_live_ready"])
        self.assertFalse(packet["filesystem_write_performed"])
        self.assertFalse(packet["snapshot_file_created"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertFalse(packet["browser_payload_allowed"])


if __name__ == "__main__":
    unittest.main()
