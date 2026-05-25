# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest
from pathlib import Path

from wild_boar_proxy.native_launch_contract import (
    CLIENT_ALLOWED_COMMAND_FIELDS,
    CLIENT_FORBIDDEN_AUTHORITY_FIELDS,
    COMMON_PACKET_REQUIRED_FIELDS,
    CUSTOM_PACKET_REQUIRED_FIELDS,
    NATIVE_LAUNCH_MODES,
    ORIGINAL_PACKET_REQUIRED_FIELDS,
    build_native_launch_contract_packet,
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


if __name__ == "__main__":
    unittest.main()
