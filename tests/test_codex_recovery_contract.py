# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy.codex_recovery_contract import (
    build_custom_recovery_admitted_session_actions_packet,
    build_custom_recovery_contract_packet,
    build_custom_recovery_rollback_apply_admission_dry_run_packet,
    build_custom_recovery_rollback_apply_bounded_live_packet,
    build_custom_recovery_rollback_apply_live_preflight_packet,
    build_custom_recovery_rollback_point_create_admission_packet,
    build_custom_recovery_rollback_point_create_live_packet,
    build_custom_recovery_rollback_point_dry_run_packet,
    build_custom_recovery_rollback_point_verify_packet,
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


def rollback_point_create_admission_packet() -> dict[str, object]:
    contract = build_custom_recovery_contract_packet(
        original_status={"status": "ok"},
        custom_status={"status": "ok"},
        accounts_readonly=ok_readonly("accounts_readonly"),
        api_readonly=ok_readonly("api_connections_readonly"),
    )
    process_owner = build_custom_recovery_rollback_process_owner_contract_packet(
        contract_packet=contract,
    )
    dry_run = build_custom_recovery_rollback_point_dry_run_packet(
        rollback_process_owner_contract=process_owner,
    )
    return build_custom_recovery_rollback_point_create_admission_packet(
        rollback_point_dry_run_contract=dry_run,
    )


def recovery_contract_packet() -> dict[str, object]:
    return build_custom_recovery_contract_packet(
        original_status={"status": "ok"},
        custom_status={"status": "ok"},
        accounts_readonly=ok_readonly("accounts_readonly"),
        api_readonly=ok_readonly("api_connections_readonly"),
    )


def rollback_process_owner_contract_packet() -> dict[str, object]:
    return build_custom_recovery_rollback_process_owner_contract_packet(
        contract_packet=recovery_contract_packet(),
    )


def rollback_point_verify_packet(root: Path) -> dict[str, object]:
    build_custom_recovery_rollback_point_create_live_packet(
        rollback_point_create_admission=rollback_point_create_admission_packet(),
        browser_payload={},
        artifact_root=root,
    )
    return build_custom_recovery_rollback_point_verify_packet(artifact_root=root)


def rollback_apply_admission_dry_run_packet(root: Path) -> dict[str, object]:
    return build_custom_recovery_rollback_apply_admission_dry_run_packet(
        rollback_point_verify=rollback_point_verify_packet(root),
        recovery_contract=recovery_contract_packet(),
        rollback_process_owner_contract=rollback_process_owner_contract_packet(),
        sessions_packet={"status": "ok", "session_count": 0, "sessions": []},
    )


def rollback_apply_live_preflight_packet(root: Path) -> dict[str, object]:
    return build_custom_recovery_rollback_apply_live_preflight_packet(
        rollback_apply_admission_dry_run=rollback_apply_admission_dry_run_packet(root),
    )


def stable_digest(payload: dict[str, object]) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def rewrite_artifact(path: Path, payload: dict[str, object]) -> None:
    payload = dict(payload)
    payload.pop("artifact_payload_sha256", None)
    payload["artifact_payload_sha256"] = stable_digest(payload)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


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

    def test_rollback_point_create_admission_ready_without_current_write(self) -> None:
        contract = build_custom_recovery_contract_packet(
            original_status={"status": "ok"},
            custom_status={"status": "ok"},
            accounts_readonly=ok_readonly("accounts_readonly"),
            api_readonly=ok_readonly("api_connections_readonly"),
        )
        process_owner = build_custom_recovery_rollback_process_owner_contract_packet(
            contract_packet=contract,
        )
        dry_run = build_custom_recovery_rollback_point_dry_run_packet(
            rollback_process_owner_contract=process_owner,
        )

        packet = build_custom_recovery_rollback_point_create_admission_packet(
            rollback_point_dry_run_contract=dry_run,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "ROLLBACK_POINT_CREATE_ADMISSION_READY")
        self.assertEqual(
            packet["claim_scope"],
            "custom_codex_recovery_rollback_point_create_admission_only",
        )
        self.assertTrue(packet["rollback_point_dry_run_contract_valid"])
        self.assertTrue(packet["rollback_point_create_admission_defined"])
        self.assertTrue(packet["rollback_point_create_admitted"])
        self.assertEqual(packet["rollback_point_create_admitted_scope"], "next_contour_only")
        self.assertFalse(packet["rollback_point_create_admitted_for_current_contour"])
        self.assertFalse(packet["rollback_point_create_performed"])
        self.assertFalse(packet["rollback_point_created"])
        self.assertFalse(packet["snapshot_file_created"])
        self.assertFalse(packet["filesystem_write_performed"])
        self.assertTrue(packet["write_surface_machine_check_performed"])
        self.assertTrue(packet["write_surfaces_all_eligible"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertFalse(packet["rollback_live_ready"])
        self.assertFalse(packet["recovery_operator_ready"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertFalse(packet["original_codex_touched"])
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
        self.assertEqual(
            packet["allowed_write_surface_ids"],
            [
                "owned_temp_session_root",
                "owned_wbp_runtime_state",
                "owned_generated_recovery_artifact",
            ],
        )
        for surface in packet["allowed_write_surfaces"]:
            self.assertTrue(surface["machine_check_performed"])
            self.assertTrue(surface["exists_or_parent_exists"])
            self.assertTrue(surface["under_controlled_root"])
            self.assertTrue(surface["current_codex_excluded"])
            self.assertTrue(surface["original_codex_excluded"])
            self.assertTrue(surface["auth_material_excluded"])
            self.assertTrue(surface["arbitrary_path_excluded"])
            self.assertFalse(surface["filesystem_write_performed"])
            self.assertFalse(surface["write_admitted_for_current_contour"])
            self.assertTrue(surface["eligible_for_next_contour"])
        for forbidden_surface in (
            "current_codex_home",
            "current_codex_process",
            "auth_material",
            "arbitrary_path",
        ):
            self.assertIn(forbidden_surface, packet["forbidden_surfaces"])
        actions = {action["id"]: action for action in packet["actions"]}
        self.assertEqual(actions["rollback_point_create"]["status"], "admission_ready")
        self.assertTrue(actions["rollback_point_create"]["admitted"])
        self.assertFalse(actions["rollback_point_create"]["admitted_for_current_contour"])
        self.assertFalse(actions["rollback_point_create"]["mutation_allowed"])
        self.assertFalse(actions["rollback_point_create"]["browser_payload_allowed"])
        self.assertFalse(actions["rollback_point_create"]["performed"])
        self.assertEqual(actions["rollback_apply"]["status"], "disabled")
        self.assertFalse(actions["rollback_apply"]["admitted"])
        self.assertEqual(
            packet["result_token"],
            "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_ADMISSION_READY",
        )
        self.assertEqual(
            packet["next_contour"],
            "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_LIVE_PASS",
        )
        self.assertFalse(packet["next_contour_claimed"])

    def test_rollback_point_create_admission_rejects_shallow_green_dry_run(self) -> None:
        packet = build_custom_recovery_rollback_point_create_admission_packet(
            rollback_point_dry_run_contract={
                "status": "ok",
                "machine_error_code": "ROLLBACK_POINT_DRY_RUN_CONTRACT",
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "ROLLBACK_POINT_CREATE_ADMISSION_BLOCKED")
        self.assertEqual(packet["block_reason_code"], "ROLLBACK_POINT_DRY_RUN_CONTRACT_REQUIRED")
        self.assertFalse(packet["rollback_point_dry_run_contract_valid"])
        self.assertTrue(packet["rollback_point_create_admission_defined"])
        self.assertFalse(packet["rollback_point_create_admitted"])
        self.assertFalse(packet["rollback_point_create_admitted_for_current_contour"])
        self.assertFalse(packet["rollback_point_create_performed"])
        self.assertFalse(packet["rollback_point_created"])
        self.assertFalse(packet["snapshot_file_created"])
        self.assertFalse(packet["filesystem_write_performed"])
        self.assertFalse(packet["write_surface_machine_check_performed"])
        self.assertFalse(packet["write_surfaces_all_eligible"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertFalse(packet["recovery_operator_ready"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertFalse(packet["browser_payload_allowed"])

    def test_rollback_point_create_admission_blocks_for_forbidden_surface(self) -> None:
        contract = build_custom_recovery_contract_packet(
            original_status={"status": "ok"},
            custom_status={"status": "ok"},
            accounts_readonly=ok_readonly("accounts_readonly"),
            api_readonly=ok_readonly("api_connections_readonly"),
        )
        process_owner = build_custom_recovery_rollback_process_owner_contract_packet(
            contract_packet=contract,
        )
        dry_run = build_custom_recovery_rollback_point_dry_run_packet(
            rollback_process_owner_contract=process_owner,
        )
        forged_dry_run = {
            **dry_run,
            "allowed_write_surface_ids": [
                "owned_temp_session_root",
                "current_codex_home",
                "owned_generated_recovery_artifact",
            ],
            "allowed_write_surfaces": [
                *dry_run["allowed_write_surfaces"][:1],
                {
                    "id": "current_codex_home",
                    "owner": "codex_custom_session_manager",
                    "status": "contract_metadata_only",
                    "filesystem_write_admitted": False,
                    "machine_checked": False,
                },
                *dry_run["allowed_write_surfaces"][2:],
            ],
        }

        packet = build_custom_recovery_rollback_point_create_admission_packet(
            rollback_point_dry_run_contract=forged_dry_run,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["rollback_point_dry_run_contract_valid"])
        self.assertFalse(packet["rollback_point_create_admitted"])
        self.assertFalse(packet["write_surfaces_all_eligible"])
        self.assertFalse(packet["rollback_point_created"])
        self.assertFalse(packet["filesystem_write_performed"])
        forbidden = {
            surface["surface_id"]: surface
            for surface in packet["allowed_write_surfaces"]
        }
        self.assertIn("current_codex_home", forbidden)
        self.assertFalse(forbidden["current_codex_home"]["current_codex_excluded"])
        self.assertFalse(forbidden["current_codex_home"]["eligible_for_next_contour"])

    def test_rollback_point_create_live_creates_redacted_owned_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packet = build_custom_recovery_rollback_point_create_live_packet(
                rollback_point_create_admission=rollback_point_create_admission_packet(),
                browser_payload={},
                artifact_root=Path(tmp),
            )

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["machine_error_code"], "ROLLBACK_POINT_CREATE_LIVE_READY")
            self.assertEqual(
                packet["claim_scope"],
                "custom_codex_recovery_rollback_point_create_live_only",
            )
            self.assertEqual(
                packet["result_token"],
                "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_LIVE_READY",
            )
            self.assertTrue(packet["rollback_point_create_admission_valid"])
            self.assertTrue(packet["rollback_point_create_admitted"])
            self.assertTrue(packet["rollback_point_create_admitted_for_current_contour"])
            self.assertTrue(packet["rollback_point_create_performed"])
            self.assertTrue(packet["rollback_point_created"])
            self.assertTrue(packet["filesystem_write_performed"])
            self.assertEqual(packet["filesystem_write_scope"], "owned_generated_recovery_artifact")
            self.assertEqual(packet["selected_write_surface_id"], "owned_generated_recovery_artifact")
            self.assertTrue(packet["rollback_point_artifact_path_redacted"])
            self.assertTrue(packet["rollback_point_artifact_digest_present"])
            self.assertRegex(packet["rollback_point_artifact_sha256"], r"^[0-9a-f]{64}$")
            self.assertNotIn(str(tmp), str(packet))
            artifact = json.loads(next(Path(tmp).glob("crp-*.json")).read_text(encoding="utf-8"))
            self.assertRegex(artifact["artifact_payload_sha256"], r"^[0-9a-f]{64}$")
            manifest = json.loads(
                (Path(tmp) / "_rollback_point_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["artifact_kind"],
                "custom_codex_recovery_rollback_point_manifest",
            )
            self.assertRegex(manifest["manifest_payload_sha256"], r"^[0-9a-f]{64}$")
            self.assertFalse(packet["snapshot_file_created"])
            self.assertFalse(packet["rollback_apply_admitted"])
            self.assertFalse(packet["rollback_apply_performed"])
            self.assertFalse(packet["rollback_completed"])
            self.assertFalse(packet["rollback_live_ready"])
            self.assertFalse(packet["recovery_operator_ready"])
            self.assertFalse(packet["current_codex_touched"])
            self.assertFalse(packet["original_codex_touched"])
            self.assertFalse(packet["auth_material_touched"])
            self.assertFalse(packet["secret_value_recorded"])
            self.assertEqual(len(list(Path(tmp).glob("crp-*.json"))), 1)
            actions = {action["id"]: action for action in packet["actions"]}
            self.assertTrue(actions["rollback_point_create"]["performed"])
            self.assertFalse(actions["rollback_apply"]["performed"])
            self.assertFalse(actions["process_kill"]["performed"])
            selected_surfaces = [
                surface
                for surface in packet["allowed_write_surfaces"]
                if surface["surface_id"] == "owned_generated_recovery_artifact"
            ]
            self.assertEqual(len(selected_surfaces), 1)
            self.assertTrue(selected_surfaces[0]["filesystem_write_performed"])
            self.assertTrue(selected_surfaces[0]["write_admitted_for_current_contour"])

    def test_rollback_point_create_live_rejects_browser_payload_without_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packet = build_custom_recovery_rollback_point_create_live_packet(
                rollback_point_create_admission=rollback_point_create_admission_packet(),
                browser_payload={"path": "/tmp/forbidden", "session_id": "ccs-forbidden"},
                artifact_root=Path(tmp),
            )

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(
                packet["machine_error_code"],
                "ROLLBACK_POINT_CREATE_FORBIDDEN_BROWSER_FIELD",
            )
            self.assertIn("path", packet["forbidden_fields"])
            self.assertIn("session_id", packet["forbidden_fields"])
            self.assertFalse(packet["rollback_point_create_admission_valid"])
            self.assertFalse(packet["rollback_point_create_performed"])
            self.assertFalse(packet["rollback_point_created"])
            self.assertFalse(packet["filesystem_write_performed"])
            self.assertEqual(list(Path(tmp).glob("*.json")), [])

    def test_rollback_point_verify_succeeds_after_bounded_create(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            create = build_custom_recovery_rollback_point_create_live_packet(
                rollback_point_create_admission=rollback_point_create_admission_packet(),
                browser_payload={},
                artifact_root=Path(tmp),
            )
            packet = build_custom_recovery_rollback_point_verify_packet(artifact_root=Path(tmp))

            self.assertEqual(create["status"], "ok")
            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["machine_error_code"], "ROLLBACK_POINT_VERIFY_READY")
            self.assertEqual(
                packet["claim_scope"],
                "custom_codex_recovery_rollback_point_verify_only",
            )
            self.assertEqual(
                packet["result_token"],
                "CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_VERIFY_READY",
            )
            self.assertTrue(packet["rollback_point_verify_performed"])
            self.assertTrue(packet["rollback_point_verified"])
            self.assertTrue(packet["rollback_point_present"])
            self.assertEqual(
                packet["rollback_point_selection_source"],
                "server_owned_latest_valid_artifact",
            )
            self.assertFalse(packet["rollback_point_selection_ambiguous"])
            self.assertTrue(packet["rollback_point_artifact_id_present"])
            self.assertTrue(packet["rollback_point_artifact_path_redacted"])
            self.assertTrue(packet["rollback_point_digest_verified"])
            self.assertTrue(packet["rollback_point_payload_digest_verified"])
            self.assertTrue(packet["rollback_point_source_admission_digest_present"])
            self.assertTrue(packet["rollback_point_manifest_verified"])
            self.assertTrue(packet["rollback_point_provenance_verified"])
            self.assertTrue(packet["rollback_point_schema_valid"])
            self.assertTrue(packet["rollback_point_kind_valid"])
            self.assertTrue(packet["rollback_point_surface_verified"])
            self.assertTrue(packet["filesystem_read_performed"])
            self.assertEqual(packet["filesystem_read_scope"], "owned_generated_recovery_artifact")
            self.assertFalse(packet["filesystem_write_performed"])
            self.assertFalse(packet["rollback_apply_admitted"])
            self.assertFalse(packet["rollback_apply_ready"])
            self.assertFalse(packet["rollback_apply_performed"])
            self.assertFalse(packet["rollback_completed"])
            self.assertFalse(packet["rollback_live_ready"])
            self.assertFalse(packet["recovery_operator_ready"])
            self.assertFalse(packet["current_codex_touched"])
            self.assertFalse(packet["original_codex_touched"])
            self.assertFalse(packet["auth_material_touched"])
            self.assertFalse(packet["secret_value_recorded"])
            self.assertNotIn(str(tmp), str(packet))

    def test_rollback_point_verify_blocks_without_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packet = build_custom_recovery_rollback_point_verify_packet(artifact_root=Path(tmp))

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(packet["machine_error_code"], "ROLLBACK_POINT_VERIFY_NOT_FOUND")
            self.assertFalse(packet["rollback_point_present"])
            self.assertFalse(packet["filesystem_read_performed"])
            self.assertFalse(packet["filesystem_write_performed"])

    def test_rollback_point_verify_rejects_browser_payload_without_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_custom_recovery_rollback_point_create_live_packet(
                rollback_point_create_admission=rollback_point_create_admission_packet(),
                browser_payload={},
                artifact_root=Path(tmp),
            )
            packet = build_custom_recovery_rollback_point_verify_packet(
                artifact_root=Path(tmp),
                browser_payload={"artifact_id": "browser", "path": "/tmp/forbidden"},
            )

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(
                packet["machine_error_code"],
                "ROLLBACK_POINT_VERIFY_BROWSER_FIELD_REJECTED",
            )
            self.assertIn("artifact_id", packet["forbidden_fields"])
            self.assertIn("path", packet["forbidden_fields"])
            self.assertFalse(packet["filesystem_read_performed"])
            self.assertFalse(packet["filesystem_write_performed"])

    def test_rollback_point_verify_rejects_malformed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "crp-bad.json").write_text("{", encoding="utf-8")
            packet = build_custom_recovery_rollback_point_verify_packet(artifact_root=Path(tmp))

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(packet["machine_error_code"], "ROLLBACK_POINT_VERIFY_SCHEMA_INVALID")
            self.assertTrue(packet["filesystem_read_performed"])
            self.assertFalse(packet["rollback_point_verified"])

    def test_rollback_point_verify_rejects_unmanifested_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "schema_version": 1,
                "artifact_kind": "custom_codex_recovery_rollback_point",
                "created_at_utc": "2026-05-24T00:00:00Z",
                "claim_scope": "custom_codex_recovery_rollback_point_create_live_only",
                "source_admission_sha256": "a" * 64,
                "write_surface_id": "owned_generated_recovery_artifact",
                "write_surface_scope": "server_owned_generated_recovery_artifact",
                "current_codex_touched": False,
                "original_codex_touched": False,
                "auth_material_touched": False,
                "secret_value_recorded": False,
                "rollback_apply_admitted": False,
                "recovery_operator_ready": False,
            }
            rewrite_artifact(Path(tmp) / "crp-unmanifested.json", payload)

            packet = build_custom_recovery_rollback_point_verify_packet(artifact_root=Path(tmp))

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(
                packet["machine_error_code"],
                "ROLLBACK_POINT_VERIFY_PROVENANCE_MISSING",
            )
            self.assertFalse(packet["rollback_point_verified"])

    def test_rollback_point_verify_rejects_provenance_manifest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            create = build_custom_recovery_rollback_point_create_live_packet(
                rollback_point_create_admission=rollback_point_create_admission_packet(),
                browser_payload={},
                artifact_root=Path(tmp),
            )
            path = Path(tmp) / f"{create['rollback_point_artifact_id']}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["source_admission_sha256"] = "f" * 64
            rewrite_artifact(path, payload)

            packet = build_custom_recovery_rollback_point_verify_packet(artifact_root=Path(tmp))

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(
                packet["machine_error_code"],
                "ROLLBACK_POINT_VERIFY_PROVENANCE_MISMATCH",
            )
            self.assertFalse(packet["rollback_point_verified"])

    def test_rollback_point_verify_rejects_missing_or_invalid_created_at(self) -> None:
        for value in (None, "not-a-timestamp"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                create = build_custom_recovery_rollback_point_create_live_packet(
                    rollback_point_create_admission=rollback_point_create_admission_packet(),
                    browser_payload={},
                    artifact_root=Path(tmp),
                )
                path = Path(tmp) / f"{create['rollback_point_artifact_id']}.json"
                payload = json.loads(path.read_text(encoding="utf-8"))
                if value is None:
                    payload.pop("created_at_utc", None)
                else:
                    payload["created_at_utc"] = value
                rewrite_artifact(path, payload)

                packet = build_custom_recovery_rollback_point_verify_packet(
                    artifact_root=Path(tmp)
                )

                self.assertEqual(packet["status"], "blocked")
                self.assertEqual(
                    packet["machine_error_code"],
                    "ROLLBACK_POINT_VERIFY_TIMESTAMP_INVALID",
                )
                self.assertFalse(packet["rollback_point_verified"])

    def test_rollback_point_verify_rejects_wrong_schema_and_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rewrite_artifact(
                Path(tmp) / "crp-wrong-schema.json",
                {
                    "schema_version": 2,
                    "artifact_kind": "custom_codex_recovery_rollback_point",
                    "created_at_utc": "2026-05-24T00:00:00Z",
                },
            )
            schema_packet = build_custom_recovery_rollback_point_verify_packet(
                artifact_root=Path(tmp)
            )
            self.assertEqual(
                schema_packet["machine_error_code"],
                "ROLLBACK_POINT_VERIFY_SCHEMA_INVALID",
            )

        with tempfile.TemporaryDirectory() as tmp:
            rewrite_artifact(
                Path(tmp) / "crp-wrong-kind.json",
                {
                    "schema_version": 1,
                    "artifact_kind": "wrong_kind",
                    "created_at_utc": "2026-05-24T00:00:00Z",
                },
            )
            kind_packet = build_custom_recovery_rollback_point_verify_packet(
                artifact_root=Path(tmp)
            )
            self.assertEqual(
                kind_packet["machine_error_code"],
                "ROLLBACK_POINT_VERIFY_KIND_INVALID",
            )

    def test_rollback_point_verify_rejects_missing_provenance_wrong_surface_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            create = build_custom_recovery_rollback_point_create_live_packet(
                rollback_point_create_admission=rollback_point_create_admission_packet(),
                browser_payload={},
                artifact_root=Path(tmp),
            )
            path = Path(tmp) / f"{create['rollback_point_artifact_id']}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload.pop("source_admission_sha256", None)
            rewrite_artifact(path, payload)
            provenance_packet = build_custom_recovery_rollback_point_verify_packet(
                artifact_root=Path(tmp)
            )
            self.assertEqual(
                provenance_packet["machine_error_code"],
                "ROLLBACK_POINT_VERIFY_PROVENANCE_MISSING",
            )

        with tempfile.TemporaryDirectory() as tmp:
            create = build_custom_recovery_rollback_point_create_live_packet(
                rollback_point_create_admission=rollback_point_create_admission_packet(),
                browser_payload={},
                artifact_root=Path(tmp),
            )
            path = Path(tmp) / f"{create['rollback_point_artifact_id']}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["write_surface_id"] = "current_codex_home"
            rewrite_artifact(path, payload)
            surface_packet = build_custom_recovery_rollback_point_verify_packet(
                artifact_root=Path(tmp)
            )
            self.assertEqual(
                surface_packet["machine_error_code"],
                "ROLLBACK_POINT_VERIFY_FORBIDDEN_SURFACE",
            )

        with tempfile.TemporaryDirectory() as tmp:
            create = build_custom_recovery_rollback_point_create_live_packet(
                rollback_point_create_admission=rollback_point_create_admission_packet(),
                browser_payload={},
                artifact_root=Path(tmp),
            )
            path = Path(tmp) / f"{create['rollback_point_artifact_id']}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["artifact_payload_sha256"] = "0" * 64
            path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            digest_packet = build_custom_recovery_rollback_point_verify_packet(
                artifact_root=Path(tmp)
            )
            self.assertEqual(
                digest_packet["machine_error_code"],
                "ROLLBACK_POINT_VERIFY_DIGEST_MISMATCH",
            )

    def test_rollback_point_verify_rejects_touch_and_secret_claims(self) -> None:
        for field, expected_error in (
            ("current_codex_touched", "CURRENT_CODEX_TOUCHED"),
            ("original_codex_touched", "ORIGINAL_CODEX_TOUCHED"),
            ("auth_material_touched", "ROLLBACK_POINT_VERIFY_SECRET_LEAK_DETECTED"),
            ("secret_value_recorded", "ROLLBACK_POINT_VERIFY_SECRET_LEAK_DETECTED"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                create = build_custom_recovery_rollback_point_create_live_packet(
                    rollback_point_create_admission=rollback_point_create_admission_packet(),
                    browser_payload={},
                    artifact_root=Path(tmp),
                )
                path = Path(tmp) / f"{create['rollback_point_artifact_id']}.json"
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload[field] = True
                rewrite_artifact(path, payload)
                packet = build_custom_recovery_rollback_point_verify_packet(artifact_root=Path(tmp))
                self.assertEqual(packet["machine_error_code"], expected_error)
                self.assertFalse(packet["rollback_point_verified"])

    def test_rollback_point_verify_rejects_ambiguous_latest_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = build_custom_recovery_rollback_point_create_live_packet(
                rollback_point_create_admission=rollback_point_create_admission_packet(),
                browser_payload={},
                artifact_root=Path(tmp),
            )
            second = build_custom_recovery_rollback_point_create_live_packet(
                rollback_point_create_admission=rollback_point_create_admission_packet(),
                browser_payload={},
                artifact_root=Path(tmp),
            )
            first_path = Path(tmp) / f"{first['rollback_point_artifact_id']}.json"
            second_path = Path(tmp) / f"{second['rollback_point_artifact_id']}.json"
            first_payload = json.loads(first_path.read_text(encoding="utf-8"))
            second_payload = json.loads(second_path.read_text(encoding="utf-8"))
            second_payload["created_at_utc"] = first_payload["created_at_utc"]
            rewrite_artifact(second_path, second_payload)

            packet = build_custom_recovery_rollback_point_verify_packet(artifact_root=Path(tmp))

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(
                packet["machine_error_code"],
                "ROLLBACK_POINT_VERIFY_AMBIGUOUS_SELECTION",
            )
            self.assertTrue(packet["rollback_point_selection_ambiguous"])
            self.assertFalse(packet["rollback_point_verified"])

    def test_rollback_apply_admission_dry_run_evaluates_after_verified_point(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            verify = rollback_point_verify_packet(Path(tmp))
            packet = build_custom_recovery_rollback_apply_admission_dry_run_packet(
                rollback_point_verify=verify,
                recovery_contract=recovery_contract_packet(),
                rollback_process_owner_contract=rollback_process_owner_contract_packet(),
                sessions_packet={"status": "ok", "session_count": 0, "sessions": []},
            )

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(
                packet["machine_error_code"],
                "ROLLBACK_APPLY_ADMISSION_DRY_RUN_EVALUATED",
            )
            self.assertEqual(
                packet["claim_scope"],
                "custom_codex_recovery_rollback_apply_admission_dry_run_only",
            )
            self.assertEqual(
                packet["result_token"],
                "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_ADMISSION_DRY_RUN_EVALUATED",
            )
            self.assertTrue(packet["rollback_apply_admission_evaluated"])
            self.assertEqual(
                packet["rollback_apply_admission_result"],
                "eligible_for_next_contour",
            )
            self.assertTrue(packet["rollback_apply_admission_eligible_for_next_contour"])
            self.assertEqual(packet["rollback_apply_admission_scope"], "dry_run_next_contour_only")
            self.assertTrue(packet["rollback_point_verify_required"])
            self.assertTrue(packet["rollback_point_verify_valid"])
            self.assertTrue(packet["rollback_point_verified"])
            self.assertTrue(packet["rollback_point_manifest_verified"])
            self.assertTrue(packet["rollback_point_provenance_verified"])
            self.assertTrue(packet["rollback_point_digest_verified"])
            self.assertTrue(packet["rollback_point_surface_verified"])
            self.assertTrue(packet["recovery_contract_readonly_sources_ok"])
            self.assertTrue(packet["rollback_process_owner_contract_ok"])
            self.assertTrue(packet["session_state_read_performed"])
            self.assertEqual(packet["session_state_status"], "ok")
            self.assertTrue(packet["write_surface_machine_check_performed"])
            self.assertTrue(packet["write_surfaces_all_eligible"])
            self.assertFalse(packet["filesystem_read_performed"])
            self.assertFalse(packet["filesystem_write_performed"])
            self.assertFalse(packet["rollback_apply_admitted"])
            self.assertFalse(packet["rollback_apply_ready"])
            self.assertFalse(packet["rollback_apply_performed"])
            self.assertFalse(packet["rollback_completed"])
            self.assertFalse(packet["rollback_live_ready"])
            self.assertFalse(packet["process_kill_performed"])
            self.assertFalse(packet["recovery_operator_ready"])
            self.assertFalse(packet["current_codex_touched"])
            self.assertFalse(packet["original_codex_touched"])
            self.assertFalse(packet["auth_material_touched"])
            self.assertFalse(packet["secret_value_recorded"])
            self.assertEqual(packet["browser_payload_allowed_keys"], [])
            self.assertIn("artifact_id", packet["forbidden_browser_fields"])
            self.assertIn("digest", packet["forbidden_browser_fields"])
            actions = {action["id"]: action for action in packet["actions"]}
            self.assertEqual(actions["rollback_apply_admission_dry_run"]["status"], "evaluated")
            self.assertEqual(
                actions["rollback_apply_admission_dry_run"]["result"],
                "eligible_for_next_contour",
            )
            self.assertFalse(actions["rollback_apply"]["admitted"])
            self.assertFalse(actions["rollback_apply"]["ready"])
            self.assertFalse(actions["rollback_apply"]["performed"])

    def test_rollback_apply_admission_dry_run_blocks_without_verified_point(self) -> None:
        packet = build_custom_recovery_rollback_apply_admission_dry_run_packet(
            rollback_point_verify={
                "status": "blocked",
                "machine_error_code": "ROLLBACK_POINT_VERIFY_NOT_FOUND",
            },
            recovery_contract=recovery_contract_packet(),
            rollback_process_owner_contract=rollback_process_owner_contract_packet(),
            sessions_packet={"status": "ok", "session_count": 0, "sessions": []},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "ROLLBACK_APPLY_ADMISSION_DRY_RUN_BLOCKED",
        )
        self.assertEqual(packet["block_reason_code"], "ROLLBACK_POINT_VERIFY_NOT_FOUND")
        self.assertEqual(packet["rollback_apply_admission_result"], "not_eligible")
        self.assertFalse(packet["rollback_apply_admission_eligible_for_next_contour"])
        self.assertFalse(packet["rollback_point_verify_valid"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertFalse(packet["rollback_apply_ready"])
        self.assertFalse(packet["rollback_apply_performed"])
        self.assertFalse(packet["filesystem_write_performed"])
        self.assertFalse(packet["process_kill_performed"])

    def test_rollback_apply_admission_dry_run_rejects_browser_payload_without_read(self) -> None:
        packet = build_custom_recovery_rollback_apply_admission_dry_run_packet(
            rollback_point_verify=None,
            browser_payload={
                "artifact_id": "browser",
                "artifact_path": "/tmp/artifact",
                "backend_id": "browser-backend",
                "route_id": "browser-route",
                "path": "/tmp/forbidden",
                "digest": "browser",
                "session_id": "ccs-browser",
                "CODEX_HOME": "/tmp/codex",
                "HOME": "/tmp/home",
                "auth": "browser-auth",
                "token": "browser-token",
                "api_key": "browser-key",
                "secret": "browser-secret",
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "ROLLBACK_APPLY_ADMISSION_BROWSER_FIELD_REJECTED",
        )
        self.assertIn("artifact_id", packet["forbidden_fields"])
        self.assertIn("artifact_path", packet["forbidden_fields"])
        self.assertIn("backend_id", packet["forbidden_fields"])
        self.assertIn("route_id", packet["forbidden_fields"])
        self.assertIn("path", packet["forbidden_fields"])
        self.assertIn("digest", packet["forbidden_fields"])
        self.assertIn("session_id", packet["forbidden_fields"])
        self.assertIn("CODEX_HOME", packet["forbidden_fields"])
        self.assertIn("HOME", packet["forbidden_fields"])
        self.assertIn("auth", packet["forbidden_fields"])
        self.assertIn("token", packet["forbidden_fields"])
        self.assertIn("api_key", packet["forbidden_fields"])
        self.assertIn("secret", packet["forbidden_fields"])
        self.assertFalse(packet["rollback_point_verify_valid"])
        self.assertFalse(packet["filesystem_read_performed"])
        self.assertFalse(packet["filesystem_write_performed"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertFalse(packet["rollback_apply_performed"])

    def test_rollback_apply_admission_dry_run_blocks_touch_and_secret_verify(self) -> None:
        for field, expected_error in (
            ("current_codex_touched", "CURRENT_CODEX_TOUCHED"),
            ("original_codex_touched", "ORIGINAL_CODEX_TOUCHED"),
            ("auth_material_touched", "ROLLBACK_POINT_VERIFY_SECRET_LEAK_DETECTED"),
            ("secret_value_recorded", "ROLLBACK_POINT_VERIFY_SECRET_LEAK_DETECTED"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                verify = rollback_point_verify_packet(Path(tmp))
                path = Path(tmp) / f"{verify['rollback_point_artifact_id']}.json"
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload[field] = True
                rewrite_artifact(path, payload)
                blocked_verify = build_custom_recovery_rollback_point_verify_packet(
                    artifact_root=Path(tmp)
                )

                packet = build_custom_recovery_rollback_apply_admission_dry_run_packet(
                    rollback_point_verify=blocked_verify,
                    recovery_contract=recovery_contract_packet(),
                    rollback_process_owner_contract=rollback_process_owner_contract_packet(),
                    sessions_packet={"status": "ok", "session_count": 0, "sessions": []},
                )

                self.assertEqual(packet["status"], "blocked")
                self.assertEqual(packet["block_reason_code"], expected_error)
                self.assertFalse(packet["rollback_point_verify_valid"])
                self.assertFalse(packet["rollback_apply_admitted"])
                self.assertFalse(packet["rollback_apply_ready"])
                self.assertFalse(packet["rollback_apply_performed"])
                self.assertFalse(packet["filesystem_write_performed"])
                self.assertFalse(packet["process_kill_performed"])

    def test_rollback_apply_live_preflight_evaluates_after_dry_run_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dry_run = rollback_apply_admission_dry_run_packet(Path(tmp))
            packet = build_custom_recovery_rollback_apply_live_preflight_packet(
                rollback_apply_admission_dry_run=dry_run,
            )

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(
                packet["machine_error_code"],
                "ROLLBACK_APPLY_LIVE_PREFLIGHT_EVALUATED",
            )
            self.assertEqual(
                packet["claim_scope"],
                "custom_codex_recovery_rollback_apply_live_preflight_only",
            )
            self.assertEqual(
                packet["result_token"],
                "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_LIVE_PREFLIGHT_EVALUATED",
            )
            self.assertTrue(packet["rollback_apply_live_preflight_evaluated"])
            self.assertEqual(
                packet["rollback_apply_live_preflight_result"],
                "eligible_for_bounded_apply_contour",
            )
            self.assertTrue(packet["rollback_apply_live_preflight_eligible_for_next_contour"])
            self.assertEqual(
                packet["rollback_apply_live_preflight_scope"],
                "preflight_next_contour_only",
            )
            self.assertTrue(packet["rollback_apply_dry_run_required"])
            self.assertTrue(packet["rollback_apply_dry_run_eligible"])
            self.assertTrue(packet["rollback_point_verified"])
            self.assertTrue(packet["future_write_surfaces_declared"])
            self.assertTrue(packet["future_write_surfaces_all_owned"])
            self.assertTrue(packet["future_write_surface_machine_check_performed"])
            self.assertEqual(packet["rollback_target_class"], "owned_generated_recovery_artifact")
            self.assertFalse(packet["rollback_target_browser_supplied"])
            self.assertTrue(packet["current_codex_excluded"])
            self.assertTrue(packet["original_codex_excluded"])
            self.assertTrue(packet["auth_material_excluded"])
            self.assertTrue(packet["arbitrary_path_rejected"])
            self.assertTrue(packet["process_kill_not_admitted"])
            self.assertTrue(packet["source_filesystem_read_performed"])
            self.assertEqual(
                packet["source_filesystem_read_scope"],
                "owned_generated_recovery_artifact",
            )
            self.assertTrue(packet["filesystem_read_performed"])
            self.assertEqual(
                packet["filesystem_read_scope"],
                "owned_generated_recovery_artifact",
            )
            self.assertFalse(packet["filesystem_write_performed"])
            self.assertFalse(packet["rollback_apply_admitted"])
            self.assertFalse(packet["rollback_apply_ready"])
            self.assertFalse(packet["rollback_apply_performed"])
            self.assertFalse(packet["rollback_completed"])
            self.assertFalse(packet["rollback_live_ready"])
            self.assertFalse(packet["process_kill_performed"])
            self.assertFalse(packet["recovery_operator_ready"])
            self.assertFalse(packet["current_codex_touched"])
            self.assertFalse(packet["original_codex_touched"])
            self.assertFalse(packet["auth_material_touched"])
            self.assertFalse(packet["secret_value_recorded"])
            self.assertEqual(packet["browser_payload_allowed_keys"], [])
            self.assertIn("artifact_id", packet["forbidden_browser_fields"])
            self.assertIn("digest", packet["forbidden_browser_fields"])
            actions = {action["id"]: action for action in packet["actions"]}
            self.assertEqual(actions["rollback_apply_live_preflight"]["status"], "evaluated")
            self.assertEqual(
                actions["rollback_apply_live_preflight"]["result"],
                "eligible_for_bounded_apply_contour",
            )
            self.assertFalse(actions["rollback_apply"]["admitted"])
            self.assertFalse(actions["rollback_apply"]["ready"])
            self.assertFalse(actions["rollback_apply"]["performed"])
            self.assertFalse(actions["process_kill"]["admitted"])
            self.assertFalse(actions["process_kill"]["performed"])

    def test_rollback_apply_live_preflight_blocks_without_dry_run_eligible(self) -> None:
        packet = build_custom_recovery_rollback_apply_live_preflight_packet(
            rollback_apply_admission_dry_run={
                "status": "blocked",
                "machine_error_code": "ROLLBACK_APPLY_ADMISSION_DRY_RUN_BLOCKED",
                "block_reason_code": "ROLLBACK_POINT_VERIFY_NOT_FOUND",
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "ROLLBACK_APPLY_LIVE_PREFLIGHT_BLOCKED")
        self.assertEqual(packet["block_reason_code"], "ROLLBACK_POINT_VERIFY_NOT_FOUND")
        self.assertEqual(packet["rollback_apply_live_preflight_result"], "not_eligible")
        self.assertFalse(packet["rollback_apply_live_preflight_eligible_for_next_contour"])
        self.assertFalse(packet["rollback_apply_dry_run_eligible"])
        self.assertFalse(packet["rollback_point_verified"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertFalse(packet["rollback_apply_ready"])
        self.assertFalse(packet["rollback_apply_performed"])
        self.assertFalse(packet["filesystem_write_performed"])
        self.assertFalse(packet["process_kill_performed"])

    def test_rollback_apply_live_preflight_rejects_browser_payload_without_read(self) -> None:
        packet = build_custom_recovery_rollback_apply_live_preflight_packet(
            rollback_apply_admission_dry_run=None,
            browser_payload={
                "artifact_id": "browser",
                "path": "/tmp/forbidden",
                "digest": "browser",
                "session_id": "ccs-browser",
            },
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "ROLLBACK_APPLY_LIVE_PREFLIGHT_BROWSER_FIELD_REJECTED",
        )
        self.assertIn("artifact_id", packet["forbidden_fields"])
        self.assertIn("path", packet["forbidden_fields"])
        self.assertIn("digest", packet["forbidden_fields"])
        self.assertIn("session_id", packet["forbidden_fields"])
        self.assertFalse(packet["rollback_apply_dry_run_eligible"])
        self.assertFalse(packet["source_filesystem_read_performed"])
        self.assertFalse(packet["filesystem_read_performed"])
        self.assertFalse(packet["filesystem_write_performed"])
        self.assertFalse(packet["rollback_apply_admitted"])
        self.assertFalse(packet["rollback_apply_performed"])

    def test_rollback_apply_live_preflight_blocks_touched_dry_run_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dry_run = rollback_apply_admission_dry_run_packet(Path(tmp))
            dry_run["current_codex_touched"] = True
            packet = build_custom_recovery_rollback_apply_live_preflight_packet(
                rollback_apply_admission_dry_run=dry_run,
            )

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(packet["machine_error_code"], "ROLLBACK_APPLY_LIVE_PREFLIGHT_BLOCKED")
            self.assertFalse(packet["rollback_apply_dry_run_eligible"])
            self.assertFalse(packet["rollback_apply_admitted"])
            self.assertFalse(packet["rollback_apply_ready"])
            self.assertFalse(packet["rollback_apply_performed"])
            self.assertFalse(packet["filesystem_write_performed"])
            self.assertFalse(packet["process_kill_performed"])

    def test_rollback_apply_bounded_live_writes_receipt_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preflight = rollback_apply_live_preflight_packet(root)
            packet = build_custom_recovery_rollback_apply_bounded_live_packet(
                rollback_apply_live_preflight=preflight,
                browser_payload={},
                artifact_root=root,
            )

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(
                packet["machine_error_code"],
                "ROLLBACK_APPLY_BOUNDED_LIVE_PERFORMED",
            )
            self.assertEqual(
                packet["claim_scope"],
                "custom_codex_recovery_rollback_apply_bounded_live_only",
            )
            self.assertEqual(
                packet["result_token"],
                "CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_BOUNDED_LIVE_PERFORMED",
            )
            self.assertTrue(packet["rollback_apply_preflight_required"])
            self.assertTrue(packet["rollback_apply_preflight_valid"])
            self.assertTrue(packet["rollback_apply_bounded_live_performed"])
            self.assertTrue(packet["rollback_apply_receipt_created"])
            self.assertTrue(packet["rollback_apply_receipt_path_redacted"])
            self.assertTrue(packet["rollback_apply_receipt_digest_present"])
            self.assertRegex(packet["rollback_apply_receipt_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(packet["rollback_apply_receipt_provenance_verified"])
            self.assertTrue(packet["rollback_apply_receipt_payload_digest_verified"])
            self.assertTrue(packet["source_preflight_sha256_present"])
            self.assertTrue(packet["rollback_point_verified"])
            self.assertTrue(packet["filesystem_read_performed"])
            self.assertEqual(packet["filesystem_read_scope"], "owned_generated_recovery_artifact")
            self.assertTrue(packet["filesystem_write_performed"])
            self.assertEqual(packet["filesystem_write_scope"], "owned_generated_recovery_artifact")
            self.assertTrue(packet["rollback_apply_admitted"])
            self.assertTrue(packet["rollback_apply_ready"])
            self.assertTrue(packet["rollback_apply_performed"])
            self.assertEqual(
                packet["rollback_apply_completed_scope"],
                "bounded_apply_receipt_only",
            )
            self.assertTrue(packet["rollback_completed"])
            self.assertFalse(packet["rollback_live_ready"])
            self.assertFalse(packet["recovery_operator_ready"])
            self.assertFalse(packet["process_kill_performed"])
            self.assertFalse(packet["current_codex_touched"])
            self.assertFalse(packet["original_codex_touched"])
            self.assertFalse(packet["current_codex_home_touched"])
            self.assertFalse(packet["auth_material_touched"])
            self.assertFalse(packet["secret_value_recorded"])
            self.assertEqual(packet["browser_payload_allowed_keys"], [])
            self.assertIn("artifact_id", packet["forbidden_browser_fields"])
            self.assertIn("digest", packet["forbidden_browser_fields"])
            self.assertNotIn("/tmp/", json.dumps(packet))
            actions = {action["id"]: action for action in packet["actions"]}
            self.assertEqual(actions["rollback_apply"]["status"], "performed")
            self.assertTrue(actions["rollback_apply"]["performed"])
            self.assertEqual(
                actions["rollback_apply"]["completed_scope"],
                "bounded_apply_receipt_only",
            )
            self.assertFalse(actions["process_kill"]["performed"])
            self.assertFalse((root / "_rollback_apply_receipt_manifest.json").exists())
            receipt_path = root / f"{packet['rollback_apply_receipt_id']}.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(
                receipt["artifact_kind"],
                "custom_codex_recovery_rollback_apply_receipt",
            )
            self.assertEqual(
                receipt["claim_scope"],
                "custom_codex_recovery_rollback_apply_bounded_live_only",
            )
            self.assertEqual(receipt["source_preflight_sha256"], stable_digest(preflight))
            self.assertEqual(
                receipt["source_rollback_point_ref"],
                packet["source_rollback_point_ref"],
            )
            self.assertFalse(receipt["current_codex_touched"])
            self.assertFalse(receipt["original_codex_touched"])
            self.assertFalse(receipt["auth_material_touched"])
            self.assertFalse(receipt["secret_value_recorded"])
            self.assertFalse(receipt["process_kill_performed"])
            self.assertFalse(receipt["recovery_operator_ready"])

    def test_rollback_apply_bounded_live_blocks_missing_preflight_without_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packet = build_custom_recovery_rollback_apply_bounded_live_packet(
                rollback_apply_live_preflight=None,
                browser_payload={},
                artifact_root=Path(tmp),
            )

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(
                packet["machine_error_code"],
                "ROLLBACK_APPLY_PREFLIGHT_NOT_ELIGIBLE",
            )
            self.assertFalse(packet["rollback_apply_preflight_valid"])
            self.assertFalse(packet["rollback_apply_bounded_live_performed"])
            self.assertFalse(packet["rollback_apply_performed"])
            self.assertFalse(packet["filesystem_read_performed"])
            self.assertFalse(packet["filesystem_write_performed"])
            self.assertFalse(packet["process_kill_performed"])
            self.assertFalse(packet["recovery_operator_ready"])

    def test_rollback_apply_bounded_live_blocks_touched_or_written_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for field, value in (
                ("current_codex_touched", True),
                ("original_codex_touched", True),
                ("auth_material_touched", True),
                ("filesystem_write_performed", True),
                ("recovery_operator_ready", True),
            ):
                preflight = rollback_apply_live_preflight_packet(root)
                preflight[field] = value
                packet = build_custom_recovery_rollback_apply_bounded_live_packet(
                    rollback_apply_live_preflight=preflight,
                    browser_payload={},
                    artifact_root=root,
                )

                self.assertEqual(packet["status"], "blocked")
                self.assertEqual(
                    packet["machine_error_code"],
                    "ROLLBACK_APPLY_PREFLIGHT_NOT_ELIGIBLE",
                )
                self.assertFalse(packet["rollback_apply_performed"])
                self.assertFalse(packet["filesystem_write_performed"])
                self.assertFalse(packet["process_kill_performed"])

    def test_rollback_apply_bounded_live_rejects_browser_payload_without_read_or_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packet = build_custom_recovery_rollback_apply_bounded_live_packet(
                rollback_apply_live_preflight=None,
                browser_payload={
                    "artifact_id": "browser",
                    "artifact_path": "/tmp/artifact",
                    "backend_id": "browser-backend",
                    "route_id": "browser-route",
                    "path": "/tmp/forbidden",
                    "snapshot_path": "/tmp/snapshot",
                    "rollback_target": "/tmp/target",
                    "digest": "browser",
                    "session_id": "ccs-browser",
                    "pid": "123",
                    "process_id": "456",
                    "CODEX_HOME": "/tmp/codex",
                    "HOME": "/tmp/home",
                    "auth": "browser-auth",
                    "token": "browser-token",
                    "api_key": "browser-key",
                    "secret": "browser-secret",
                },
                artifact_root=Path(tmp),
            )

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(
                packet["machine_error_code"],
                "ROLLBACK_APPLY_BROWSER_FIELD_REJECTED",
            )
            for field in (
                "artifact_id",
                "artifact_path",
                "backend_id",
                "route_id",
                "path",
                "snapshot_path",
                "rollback_target",
                "digest",
                "session_id",
                "pid",
                "process_id",
                "CODEX_HOME",
                "HOME",
                "auth",
                "token",
                "api_key",
                "secret",
            ):
                self.assertIn(field, packet["forbidden_fields"])
            self.assertFalse(packet["rollback_apply_preflight_valid"])
            self.assertFalse(packet["rollback_apply_performed"])
            self.assertFalse(packet["filesystem_read_performed"])
            self.assertFalse(packet["filesystem_write_performed"])
            self.assertFalse(packet["process_kill_performed"])
            self.assertFalse(packet["recovery_operator_ready"])

    def test_rollback_point_create_live_rejects_shallow_admission_without_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packet = build_custom_recovery_rollback_point_create_live_packet(
                rollback_point_create_admission={
                    "status": "ok",
                    "machine_error_code": "ROLLBACK_POINT_CREATE_ADMISSION_READY",
                },
                browser_payload={},
                artifact_root=Path(tmp),
            )

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(
                packet["machine_error_code"],
                "ROLLBACK_POINT_CREATE_ADMISSION_INVALID",
            )
            self.assertFalse(packet["rollback_point_create_admission_valid"])
            self.assertFalse(packet["rollback_point_create_performed"])
            self.assertFalse(packet["rollback_point_created"])
            self.assertFalse(packet["filesystem_write_performed"])
            self.assertEqual(list(Path(tmp).glob("*.json")), [])

    def test_rollback_point_create_live_rejects_non_object_payload_without_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packet = build_custom_recovery_rollback_point_create_live_packet(
                rollback_point_create_admission=rollback_point_create_admission_packet(),
                browser_payload=[],  # type: ignore[arg-type]
                artifact_root=Path(tmp),
            )

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(
                packet["machine_error_code"],
                "ROLLBACK_POINT_CREATE_FORBIDDEN_BROWSER_FIELD",
            )
            self.assertEqual(packet["forbidden_fields"], ["invalid_body"])
            self.assertFalse(packet["rollback_point_create_admission_valid"])
            self.assertFalse(packet["rollback_point_create_performed"])
            self.assertFalse(packet["rollback_point_created"])
            self.assertFalse(packet["filesystem_write_performed"])
            self.assertEqual(list(Path(tmp).glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
