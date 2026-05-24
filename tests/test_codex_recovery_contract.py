# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest

from wild_boar_proxy.codex_recovery_contract import (
    build_custom_recovery_admitted_session_actions_packet,
    build_custom_recovery_contract_packet,
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


if __name__ == "__main__":
    unittest.main()
