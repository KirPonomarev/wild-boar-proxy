# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest
from pathlib import Path

from wild_boar_proxy.native_launch_contract import (
    ADMISSION_IDENTITY_FIELDS,
    ADMISSION_TARGET_CANDIDATE_SOURCES,
    CLIENT_ALLOWED_COMMAND_FIELDS,
    CLIENT_FORBIDDEN_AUTHORITY_FIELDS,
    COMMON_PACKET_REQUIRED_FIELDS,
    CUSTOM_PACKET_REQUIRED_FIELDS,
    NATIVE_LAUNCH_MODES,
    ORIGINAL_PACKET_REQUIRED_FIELDS,
    build_native_custom_preflight_packet,
    build_native_launch_admission_packet,
    build_native_launch_cleanup_contract_packet,
    build_native_launch_contract_packet,
    build_native_launch_identity_fields_packet,
    build_native_launch_write_surface_packet,
    build_native_original_preflight_packet,
    validate_native_launch_command,
    validate_native_launch_packet,
)


ROOT = Path(__file__).resolve().parents[1]


def complete_custom_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "schema_version": 1,
        "claim_id": "claim-custom",
        "launch_mode": "CODEX_CUSTOM_NATIVE_APP",
        "wbp_action_id": "act-custom",
        "process_id": 1234,
        "process_lineage": ["wbp", "Codex.app"],
        "window_id_or_title": "Codex Custom",
        "profile_dir": "<redacted-custom-profile>",
        "codex_home": "<redacted-custom-codex-home>",
        "route_endpoint": "http://127.0.0.1:8320/v1",
        "trace_id": "trace-custom",
        "cleanup_command": "server_owned_cleanup",
        "current_codex_touched": False,
        "process_started": True,
        "window_observed": True,
        "native_window_usable": True,
        "prompt_surface_observed": True,
        "route_trace_bound": True,
        "workbench_ready": False,
        "protected_baseline_only": False,
        "isolated_home": True,
        "isolated_codex_home": True,
        "isolated_profile_dir": True,
        "server_owned_route_configuration": True,
    }
    packet.update(overrides)
    return packet


def complete_original_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "schema_version": 1,
        "claim_id": "claim-original",
        "launch_mode": "ORIGINAL_CODEX_VIA_WBP",
        "wbp_action_id": "act-original",
        "process_id": 4321,
        "process_lineage": ["wbp", "Codex.app"],
        "window_id_or_title": "Codex",
        "profile_dir": "<redacted-original-profile>",
        "codex_home": "<redacted-original-codex-home>",
        "route_endpoint": "http://127.0.0.1:8320/v1",
        "trace_id": "trace-original",
        "cleanup_command": "server_owned_cleanup",
        "current_codex_touched": False,
        "process_started": True,
        "window_observed": True,
        "native_window_usable": True,
        "prompt_surface_observed": True,
        "route_trace_bound": True,
        "workbench_ready": False,
        "protected_baseline_only": False,
        "ordinary_codex_app_identity": True,
        "temporary_wbp_route_config": True,
        "permanent_user_config_mutated": False,
        "custom_home_present": False,
        "custom_codex_home_present": False,
        "before_profile_hash": "hash-a",
        "during_wbp_route_config": "temporary",
        "after_cleanup_profile_hash": "hash-a",
        "restart_without_wbp_status": "ok",
    }
    packet.update(overrides)
    return packet


def native_command(mode: str = "CODEX_CUSTOM_NATIVE_APP", **overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "schema_version": 1,
        "command_id": "cmd-native",
        "launch_mode": mode,
    }
    packet.update(overrides)
    return packet


def complete_custom_admission_plan(**overrides: object) -> dict[str, object]:
    plan: dict[str, object] = {
        "target_candidate_source": "repo_or_server_owned_launcher_candidate",
        "isolated_home_plan": True,
        "isolated_codex_home_plan": True,
        "isolated_profile_data_dir_plan": True,
        "server_planned_route_endpoint": True,
        "port_separation_plan": True,
        "cleanup_command_plan": True,
        "rollback_expectation_declared": True,
        "current_codex_snapshot_plan": True,
        "write_surfaces_declared": True,
        "declared_write_surfaces": [
            "server_owned_temp_home",
            "server_owned_temp_codex_home",
            "server_owned_profile_dir",
            "launch_receipt",
        ],
    }
    plan.update(overrides)
    return plan


def complete_original_admission_plan(**overrides: object) -> dict[str, object]:
    plan: dict[str, object] = {
        "ordinary_codex_app_identity_candidate": True,
        "temporary_wbp_route_config_plan": True,
        "permanent_user_config_mutation_blocked": True,
        "custom_home_blocked": True,
        "custom_codex_home_blocked": True,
        "before_profile_config_hash_plan": True,
        "cleanup_command_plan": True,
        "restart_without_wbp_proof_plan": True,
        "rollback_expectation_declared": True,
        "write_surfaces_declared": True,
        "declared_write_surfaces": [
            "server_owned_temporary_routing_config",
            "launch_receipt",
            "cleanup_receipt",
        ],
    }
    plan.update(overrides)
    return plan


class NativeLaunchContractTests(unittest.TestCase):
    def test_contract_accepts_exactly_two_modes(self) -> None:
        contract = build_native_launch_contract_packet()

        self.assertEqual(contract["status"], "ok")
        self.assertEqual(tuple(contract["allowed_launch_modes"]), NATIVE_LAUNCH_MODES)
        self.assertEqual(
            set(contract["allowed_launch_modes"]),
            {"CODEX_CUSTOM_NATIVE_APP", "ORIGINAL_CODEX_VIA_WBP"},
        )
        self.assertFalse(contract["live_launch_performed"])
        self.assertFalse(contract["runtime_mutation_performed"])
        self.assertFalse(contract["ui_mutation_performed"])

    def test_json_contract_artifacts_parse_and_match_modes(self) -> None:
        for filename in (
            "native_launch_contract.json",
            "native_launch_command_schema.json",
            "native_launch_packet_schema.json",
        ):
            artifact = json.loads((ROOT / filename).read_text(encoding="utf-8"))
            self.assertEqual(
                set(artifact["allowed_launch_modes"]),
                {"CODEX_CUSTOM_NATIVE_APP", "ORIGINAL_CODEX_VIA_WBP"},
            )

    def test_json_schemas_match_python_contract_constants(self) -> None:
        command_schema = json.loads(
            (ROOT / "native_launch_command_schema.json").read_text(encoding="utf-8")
        )
        packet_schema = json.loads(
            (ROOT / "native_launch_packet_schema.json").read_text(encoding="utf-8")
        )

        self.assertEqual(
            set(command_schema["client_allowed_fields"]),
            CLIENT_ALLOWED_COMMAND_FIELDS,
        )
        self.assertEqual(
            set(command_schema["client_forbidden_authority_fields"]),
            CLIENT_FORBIDDEN_AUTHORITY_FIELDS,
        )
        self.assertEqual(
            set(packet_schema["common_required_fields"]),
            COMMON_PACKET_REQUIRED_FIELDS,
        )
        self.assertEqual(
            set(packet_schema["mode_required_fields"]["CODEX_CUSTOM_NATIVE_APP"]),
            CUSTOM_PACKET_REQUIRED_FIELDS,
        )
        self.assertEqual(
            set(packet_schema["mode_required_fields"]["ORIGINAL_CODEX_VIA_WBP"]),
            ORIGINAL_PACKET_REQUIRED_FIELDS,
        )

    def test_command_requires_schema_command_and_mode_fields(self) -> None:
        packet = validate_native_launch_command({"launch_mode": "CODEX_CUSTOM_NATIVE_APP"})

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(
            packet["machine_error_code"],
            "NATIVE_LAUNCH_COMMAND_MISSING_FIELD",
        )
        self.assertEqual(packet["missing_fields"], ["schema_version", "command_id"])

    def test_command_rejects_unknown_launch_mode(self) -> None:
        packet = validate_native_launch_command(
            {
                "schema_version": 1,
                "command_id": "cmd-1",
                "launch_mode": "WEB_WORKBENCH",
            }
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "NATIVE_LAUNCH_MODE_UNKNOWN")
        self.assertFalse(packet["accepted"])

    def test_command_rejects_browser_backend_route_and_env_authority_fields(self) -> None:
        packet = validate_native_launch_command(
            {
                "schema_version": 1,
                "command_id": "cmd-1",
                "launch_mode": "CODEX_CUSTOM_NATIVE_APP",
                "route_id": "browser-route",
                "backend_id": "browser-backend",
                "env": {"CODEX_HOME": "/tmp/browser-codex-home"},
            }
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(
            packet["machine_error_code"],
            "NATIVE_LAUNCH_COMMAND_FORBIDDEN_FIELD",
        )
        self.assertIn("route_id", packet["forbidden_fields"])
        self.assertIn("backend_id", packet["forbidden_fields"])
        self.assertIn("env", packet["forbidden_fields"])
        self.assertIn("env.CODEX_HOME", packet["forbidden_fields"])
        self.assertFalse(packet["live_launch_performed"])

    def test_valid_minimal_command_accepts_mode_choice_only(self) -> None:
        packet = validate_native_launch_command(
            {
                "schema_version": 1,
                "command_id": "cmd-1",
                "launch_mode": "ORIGINAL_CODEX_VIA_WBP",
                "operator_intent": "launch-original-via-wbp",
            }
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["accepted"])
        self.assertFalse(packet["runtime_mutation_performed"])

    def test_custom_packet_requires_isolated_home_codex_home_and_profile(self) -> None:
        packet = validate_native_launch_packet(
            complete_custom_packet(
                isolated_home=False,
                isolated_codex_home=False,
                isolated_profile_dir=False,
            )
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertIn("custom_requires_isolated_home", packet["failed_checks"])
        self.assertIn("custom_requires_isolated_codex_home", packet["failed_checks"])
        self.assertIn("custom_requires_isolated_profile_dir", packet["failed_checks"])

    def test_custom_packet_requires_current_codex_untouched(self) -> None:
        packet = validate_native_launch_packet(complete_custom_packet(current_codex_touched=True))

        self.assertEqual(packet["status"], "rejected")
        self.assertIn("current_codex_must_remain_untouched", packet["failed_checks"])

    def test_original_packet_forbids_custom_home_codex_home_and_permanent_config_mutation(self) -> None:
        packet = validate_native_launch_packet(
            complete_original_packet(
                custom_home_present=True,
                custom_codex_home_present=True,
                permanent_user_config_mutated=True,
            )
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertIn("original_forbids_custom_home", packet["failed_checks"])
        self.assertIn("original_forbids_custom_codex_home", packet["failed_checks"])
        self.assertIn(
            "original_forbids_permanent_user_config_mutation",
            packet["failed_checks"],
        )

    def test_original_packet_requires_cleanup_restart_proof_fields(self) -> None:
        packet = validate_native_launch_packet(
            complete_original_packet(
                after_cleanup_profile_hash="hash-b",
                restart_without_wbp_status="blocked",
            )
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertIn("original_requires_profile_hash_restored", packet["failed_checks"])
        self.assertIn("original_requires_restart_without_wbp_ok", packet["failed_checks"])

    def test_process_only_packet_cannot_satisfy_native_launch(self) -> None:
        packet = validate_native_launch_packet(
            complete_custom_packet(
                window_observed=False,
                native_window_usable=False,
                prompt_surface_observed=False,
                route_trace_bound=False,
            )
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertIn("window_observed_required", packet["failed_checks"])
        self.assertIn("native_window_usability_required", packet["failed_checks"])
        self.assertIn("route_trace_binding_required", packet["failed_checks"])

    def test_workbench_only_packet_cannot_satisfy_native_launch(self) -> None:
        packet = validate_native_launch_packet(complete_custom_packet(workbench_ready=True))

        self.assertEqual(packet["status"], "rejected")
        self.assertIn("workbench_ready_cannot_satisfy_native_launch", packet["failed_checks"])

    def test_protected_baseline_only_packet_cannot_satisfy_original_via_wbp(self) -> None:
        packet = validate_native_launch_packet(
            complete_original_packet(
                protected_baseline_only=True,
                temporary_wbp_route_config=False,
            )
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertIn(
            "protected_baseline_only_is_not_original_via_wbp",
            packet["failed_checks"],
        )
        self.assertIn("original_requires_temporary_wbp_route_config", packet["failed_checks"])

    def test_complete_contract_examples_validate_without_live_launch(self) -> None:
        for packet in (
            validate_native_launch_packet(complete_custom_packet()),
            validate_native_launch_packet(complete_original_packet()),
        ):
            self.assertEqual(packet["status"], "ok")
            self.assertTrue(packet["accepted"])
            self.assertFalse(packet["live_launch_performed"])
            self.assertFalse(packet["runtime_mutation_performed"])
            self.assertFalse(packet["ui_mutation_performed"])

    def test_admission_target_sources_are_limited(self) -> None:
        self.assertEqual(
            set(ADMISSION_TARGET_CANDIDATE_SOURCES),
            {
                "repo_or_server_owned_launcher_candidate",
                "owner_admitted_external_app_candidate",
            },
        )

    def test_custom_admission_accepts_safe_server_owned_plan_without_live_launch(self) -> None:
        packet = build_native_custom_preflight_packet(
            native_command(),
            complete_custom_admission_plan(),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["admission_status"], "admitted")
        self.assertTrue(packet["admitted"])
        self.assertEqual(packet["launch_mode"], "CODEX_CUSTOM_NATIVE_APP")
        self.assertFalse(packet["live_launch_performed"])
        self.assertFalse(packet["runtime_mutation_performed"])
        self.assertFalse(packet["ui_mutation_performed"])
        self.assertFalse(packet["identity_chain_proven"])
        self.assertFalse(packet["native_launch_complete"])
        self.assertEqual(packet["process_proof_status"], "not_attempted")
        self.assertEqual(packet["window_proof_status"], "not_attempted")
        self.assertEqual(packet["route_inference_status"], "not_attempted")
        self.assertTrue(packet["identity_chain_fields_reserved"])
        self.assertEqual(packet["identity_chain_required_fields"], list(ADMISSION_IDENTITY_FIELDS))
        self.assertTrue(packet["target_candidate_path_redacted"])
        self.assertTrue(packet["route_endpoint_redacted"])

    def test_custom_admission_allows_owner_admitted_external_candidate_source(self) -> None:
        packet = build_native_custom_preflight_packet(
            native_command(),
            complete_custom_admission_plan(
                target_candidate_source="owner_admitted_external_app_candidate"
            ),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["target_candidate_source"],
            "owner_admitted_external_app_candidate",
        )

    def test_custom_admission_rejects_browser_authority_fields(self) -> None:
        packet = build_native_custom_preflight_packet(
            native_command(
                route_id="browser-route",
                endpoint="http://127.0.0.1:1",
                env={"HOME": "/tmp/browser"},
                token="raw",
            ),
            complete_custom_admission_plan(),
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(
            packet["machine_error_code"],
            "NATIVE_LAUNCH_COMMAND_FORBIDDEN_FIELD",
        )
        command = packet["command_validation_packet"]
        self.assertIn("route_id", command["forbidden_fields"])
        self.assertIn("endpoint", command["forbidden_fields"])
        self.assertIn("env.HOME", command["forbidden_fields"])
        self.assertIn("token", command["forbidden_fields"])
        self.assertFalse(packet["live_launch_performed"])

    def test_custom_admission_blocks_missing_isolation_cleanup_rollback_and_writes(self) -> None:
        packet = build_native_custom_preflight_packet(
            native_command(),
            complete_custom_admission_plan(
                isolated_home_plan=False,
                isolated_codex_home_plan=False,
                isolated_profile_data_dir_plan=False,
                cleanup_command_plan=False,
                rollback_expectation_declared=False,
                declared_write_surfaces=[],
            ),
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["admitted"])
        self.assertIn("custom_requires_isolated_home_plan", packet["failed_checks"])
        self.assertIn("custom_requires_isolated_codex_home_plan", packet["failed_checks"])
        self.assertIn("custom_requires_isolated_profile_data_dir_plan", packet["failed_checks"])
        self.assertIn("cleanup_command_plan_required", packet["failed_checks"])
        self.assertIn("rollback_expectation_required", packet["failed_checks"])
        self.assertIn("write_surfaces_required", packet["failed_checks"])

    def test_custom_admission_requires_classified_target_route_port_and_snapshot_plan(self) -> None:
        packet = build_native_custom_preflight_packet(
            native_command(),
            complete_custom_admission_plan(
                target_candidate_source="browser_supplied",
                server_planned_route_endpoint=False,
                port_separation_plan=False,
                current_codex_snapshot_plan=False,
            ),
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn(
            "custom_requires_classified_target_candidate_source",
            packet["failed_checks"],
        )
        self.assertIn("custom_requires_server_planned_route_endpoint", packet["failed_checks"])
        self.assertIn("custom_requires_port_separation_plan", packet["failed_checks"])
        self.assertIn("custom_requires_current_codex_snapshot_plan", packet["failed_checks"])

    def test_original_admission_accepts_safe_plan_without_claiming_launch(self) -> None:
        packet = build_native_original_preflight_packet(
            native_command("ORIGINAL_CODEX_VIA_WBP"),
            complete_original_admission_plan(),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["admission_status"], "admitted")
        self.assertTrue(packet["admitted"])
        self.assertEqual(packet["launch_mode"], "ORIGINAL_CODEX_VIA_WBP")
        self.assertFalse(packet["identity_chain_proven"])
        self.assertFalse(packet["live_process_observed"])
        self.assertFalse(packet["native_window_observed"])
        self.assertFalse(packet["route_trace_bound"])
        self.assertFalse(packet["native_launch_complete"])
        self.assertTrue(packet["identity_chain_fields_reserved"])

    def test_original_admission_blocks_permanent_config_and_custom_home_risks(self) -> None:
        packet = build_native_original_preflight_packet(
            native_command("ORIGINAL_CODEX_VIA_WBP"),
            complete_original_admission_plan(
                permanent_user_config_mutation_blocked=False,
                custom_home_blocked=False,
                custom_codex_home_blocked=False,
            ),
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn(
            "original_requires_permanent_config_mutation_blocked",
            packet["failed_checks"],
        )
        self.assertIn("original_requires_custom_home_blocked", packet["failed_checks"])
        self.assertIn("original_requires_custom_codex_home_blocked", packet["failed_checks"])

    def test_original_admission_requires_temporary_route_cleanup_and_restart_plan(self) -> None:
        packet = build_native_original_preflight_packet(
            native_command("ORIGINAL_CODEX_VIA_WBP"),
            complete_original_admission_plan(
                temporary_wbp_route_config_plan=False,
                cleanup_command_plan=False,
                restart_without_wbp_proof_plan=False,
            ),
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn(
            "original_requires_temporary_wbp_route_config_plan",
            packet["failed_checks"],
        )
        self.assertIn("cleanup_command_plan_required", packet["failed_checks"])
        self.assertIn("original_requires_restart_without_wbp_proof_plan", packet["failed_checks"])

    def test_admission_mode_mismatch_is_rejected(self) -> None:
        packet = build_native_custom_preflight_packet(
            native_command("ORIGINAL_CODEX_VIA_WBP"),
            complete_custom_admission_plan(),
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(
            packet["machine_error_code"],
            "NATIVE_LAUNCH_ADMISSION_MODE_MISMATCH",
        )

    def test_admission_packet_reports_missing_plan_fields(self) -> None:
        packet = build_native_launch_admission_packet(
            native_command(),
            {},
            expected_mode="CODEX_CUSTOM_NATIVE_APP",
            required_plan_fields={"cleanup_command_plan", "rollback_expectation_declared"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["missing_plan_fields"],
            ["cleanup_command_plan", "rollback_expectation_declared"],
        )

    def test_write_surface_packet_requires_declared_surfaces(self) -> None:
        blocked = build_native_launch_write_surface_packet("CODEX_CUSTOM_NATIVE_APP", [])
        admitted = build_native_launch_write_surface_packet(
            "CODEX_CUSTOM_NATIVE_APP",
            ["server_owned_temp_home", "launch_receipt"],
        )

        self.assertEqual(blocked["status"], "blocked")
        self.assertFalse(blocked["write_surfaces_declared"])
        self.assertEqual(admitted["status"], "ok")
        self.assertTrue(admitted["write_surfaces_declared"])
        self.assertFalse(admitted["browser_supplied_write_surfaces_allowed"])

    def test_cleanup_contract_packet_requires_cleanup_and_rollback(self) -> None:
        packet = build_native_launch_cleanup_contract_packet(
            "ORIGINAL_CODEX_VIA_WBP",
            cleanup_command_planned=True,
            rollback_expectation_declared=False,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["cleanup_contract_required"])
        self.assertTrue(packet["rollback_required"])

    def test_identity_fields_packet_reserves_but_does_not_prove_identity(self) -> None:
        packet = build_native_launch_identity_fields_packet("CODEX_CUSTOM_NATIVE_APP")

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["identity_chain_fields_reserved"])
        self.assertFalse(packet["identity_chain_proven"])
        self.assertFalse(packet["live_process_observed"])
        self.assertFalse(packet["native_window_observed"])
        self.assertFalse(packet["route_trace_bound"])


if __name__ == "__main__":
    unittest.main()
