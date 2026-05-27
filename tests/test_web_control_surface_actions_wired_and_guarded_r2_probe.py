# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.web_control_surface_actions_wired_and_guarded_r2_probe import (
    build_false_green_audit,
    build_packets,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class WebControlSurfaceActionsWiredAndGuardedR2ProbeTests(unittest.TestCase):
    def test_probe_builds_required_packets_with_truthful_statuses(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        expected_statuses = {
            "web_control_surface_matrix_packet.json": "ok",
            "readonly_live_action_boundary_packet.json": "ok",
            "auth_authority_boundary_packet.json": "ok",
            "route_account_mutation_guard_packet.json": "ok",
            "cost_guard_packet.json": "ok",
            "disabled_reason_matrix_packet.json": "ok",
            "action_verification_results_packet.json": "ok",
            "false_green_audit.json": "ok",
        }
        self.assertEqual(set(packets), set(expected_statuses))
        for name, status in expected_statuses.items():
            self.assertEqual(packets[name]["status"], status, name)

    def test_matrix_and_boundary_capture_current_runtime_truth(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        matrix = packets["web_control_surface_matrix_packet.json"]
        readonly = packets["readonly_live_action_boundary_packet.json"]

        rows = {row["ui_action"]: row for row in matrix["rows"]}
        self.assertEqual(matrix["required_action_count"], 33)
        self.assertEqual(matrix["unwired_actions"], [])
        self.assertEqual(
            rows["api_route_credential_check"]["wiring"],
            "wired_to_adapter_command_surface",
        )
        self.assertEqual(
            rows["account_login_status"]["wiring"],
            "wired_to_adapter_command_surface",
        )
        self.assertTrue(readonly["parked_actions_blocked_with_packet_reason"])
        self.assertIn("account_login_status", readonly["parked_actions"])
        self.assertIn("api_route_credential_check", readonly["parked_actions"])
        self.assertEqual(readonly["unexpected_live_available_actions"], [])

    def test_action_verification_and_false_green_audit_capture_current_truth(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        verification = packets["action_verification_results_packet.json"]
        disabled = packets["disabled_reason_matrix_packet.json"]
        audit = packets["false_green_audit.json"]

        self.assertEqual(verification["failed_checks"], [])
        check_by_name = {row["name"]: row for row in verification["checks"]}
        self.assertTrue(check_by_name["live_readonly_account_login_status_blocked"]["passed"])
        self.assertEqual(
            check_by_name["live_readonly_account_login_status_blocked"]["status"],
            "integration_failure",
        )
        self.assertEqual(
            check_by_name["live_readonly_account_login_status_blocked"]["machine_error_code"],
            "RUNTIME_LIVE_ACTION_CHAIN_PARKED",
        )
        self.assertTrue(check_by_name["sandbox_account_login_status_requires_contract"]["passed"])
        self.assertEqual(
            check_by_name["sandbox_account_login_status_requires_contract"]["status"],
            "integration_failure",
        )
        self.assertEqual(
            check_by_name["sandbox_account_login_status_requires_contract"]["machine_error_code"],
            "UI_SANDBOX_ACTION_PREFLIGHT_REQUIRED",
        )
        self.assertTrue(check_by_name["sandbox_api_route_credential_check_packet_backed"]["passed"])
        self.assertEqual(
            check_by_name["sandbox_api_route_credential_check_packet_backed"]["status"],
            "integration_failure",
        )
        self.assertEqual(
            check_by_name["sandbox_api_route_credential_check_packet_backed"]["machine_error_code"],
            "UI_API_ROUTE_CONNECT_SERVER_OWNED_SOURCE_UNPROVEN",
        )
        self.assertEqual(disabled["missing_reason_entries"], [])
        self.assertEqual(audit["blocked_packets"], [])
        self.assertEqual(audit["findings"], [])
        sandbox_rows = {row["ui_action"]: row for row in disabled["rows"]["sandbox_no_contract"]}
        self.assertEqual(
            sandbox_rows["account_login_status"]["disabled_reason_code"],
            "UI_SANDBOX_ACTION_PREFLIGHT_REQUIRED",
        )
        self.assertEqual(
            sandbox_rows["api_route_credential_check"]["disabled_reason_code"],
            "UI_SANDBOX_ACTION_PREFLIGHT_REQUIRED",
        )

    def test_false_green_audit_blocks_when_required_packets_block(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "audit_results") as tmp:
            packets = build_packets(REPO_ROOT, Path(tmp))

        mutated = dict(packets)
        mutated["action_verification_results_packet.json"] = {
            **mutated["action_verification_results_packet.json"],
            "status": "blocked",
            "failed_checks": ["forced_failure"],
        }
        audit = build_false_green_audit(mutated)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn("blocked_packets_present", audit["findings"])
        self.assertIn(
            "action_verification_results_packet.json",
            audit["blocked_packets"],
        )


if __name__ == "__main__":
    unittest.main()
