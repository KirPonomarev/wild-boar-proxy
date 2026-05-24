# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy.codex_launch_modes import (
    build_custom_launch_dry_run_packet,
    build_custom_status_packet,
    build_launch_modes_packet,
    build_original_launch_dry_run_packet,
    build_original_status_packet,
    build_safe_app_copy_launch_dry_run_packet,
    build_safe_app_copy_launch_live_packet,
    forbidden_app_copy_launch_fields,
    forbidden_custom_launch_fields,
    forbidden_original_fields,
)


class CodexLaunchModesTests(unittest.TestCase):
    def test_launch_modes_split_original_and_custom_without_global_green(self) -> None:
        packet = build_launch_modes_packet({"claim_gate": {"status": "blocked"}})

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["claim_gate_status"], "blocked")
        modes = {mode["id"]: mode for mode in packet["modes"]}
        self.assertFalse(modes["original_codex"]["proxy_enabled"])
        self.assertFalse(modes["original_codex"]["proxy_allowed"])
        self.assertFalse(modes["original_codex"]["custom_home"])
        self.assertFalse(modes["original_codex"]["custom_codex_home_allowed"])
        self.assertEqual(modes["original_codex"]["launch_claim_scope"], "dry_run_guard_only")
        self.assertTrue(modes["codex_custom"]["proxy_enabled"])
        self.assertTrue(modes["codex_custom"]["proxy_allowed"])
        self.assertTrue(modes["codex_custom"]["custom_codex_home_required"])
        self.assertFalse(modes["codex_custom"]["current_codex_home_allowed"])
        self.assertTrue(modes["codex_custom"]["launch_dry_run_available"])
        self.assertFalse(modes["codex_custom"]["custom_session_available"])
        self.assertEqual(modes["codex_custom"]["launch_claim_scope"], "readonly_readiness_only")
        self.assertFalse(modes["safe_app_copy"]["proxy_enabled"])
        self.assertFalse(modes["safe_app_copy"]["current_home_allowed"])
        self.assertFalse(modes["safe_app_copy"]["current_codex_home_allowed"])
        self.assertTrue(modes["safe_app_copy"]["launch_dry_run_available"])
        self.assertFalse(modes["safe_app_copy"]["live_launch_available"])
        self.assertEqual(
            modes["safe_app_copy"]["launch_claim_scope"],
            "separate_app_copy_dry_run_only",
        )

    def test_original_status_forbids_proxy_custom_home_and_mutation(self) -> None:
        packet = build_original_status_packet()

        self.assertEqual(packet["mode_id"], "original_codex")
        self.assertFalse(packet["proxy_injection_allowed"])
        self.assertFalse(packet["proxy_allowed"])
        self.assertFalse(packet["custom_home_allowed"])
        self.assertFalse(packet["custom_codex_home_allowed"])
        self.assertFalse(packet["mutation_allowed"])
        self.assertEqual(packet["browser_payload_allowed_keys"], [])
        self.assertEqual(packet["launch_claim_scope"], "status_only")

    def test_original_dry_run_accepts_empty_payload_only(self) -> None:
        packet = build_original_launch_dry_run_packet({})

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["dry_run"])
        self.assertTrue(packet["dispatch_plan_safe"])
        self.assertFalse(packet["proxy_env_injected"])
        self.assertFalse(packet["custom_home_injected"])
        self.assertFalse(packet["model_override_injected"])
        self.assertFalse(packet["route_or_backend_injected"])

    def test_original_dry_run_rejects_model_route_path_home_and_proxy_fields(self) -> None:
        packet = build_original_launch_dry_run_packet(
            {
                "model_id": "gpt-5.3-codex",
                "route_id": "route",
                "path": "/tmp/path",
                "CODEX_HOME": "/tmp/custom",
                "HTTP_PROXY": "http://127.0.0.1:1",
            }
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertFalse(packet["dispatch_plan_safe"])
        self.assertEqual(
            packet["forbidden_fields"],
            ["model_id", "route_id", "path", "CODEX_HOME", "HTTP_PROXY"],
        )

    def test_forbidden_original_fields_rejects_unknown_keys_too(self) -> None:
        self.assertEqual(forbidden_original_fields({"dry_run": True}), ["dry_run"])

    def test_custom_launch_dry_run_is_isolated_zero_token_readiness_only(self) -> None:
        packet = build_custom_launch_dry_run_packet({})

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["dry_run"])
        self.assertTrue(packet["custom_launch_plan_safe"])
        self.assertFalse(packet["real_launch_attempted"])
        self.assertFalse(packet["prompt_attempted"])
        self.assertEqual(packet["token_burn"], 0)
        self.assertEqual(packet["launch_claim_scope"], "dry_run_readiness_only")
        self.assertTrue(packet["custom_codex_home_required"])
        self.assertFalse(packet["current_codex_home_allowed"])
        self.assertFalse(packet["isolation_plan"]["current_codex_home_allowed"])
        self.assertEqual(packet["current_codex_touch_risk"], "blocked_by_contract")

    def test_custom_launch_dry_run_rejects_browser_controlled_model_route_home_and_base_url(self) -> None:
        packet = build_custom_launch_dry_run_packet(
            {
                "model": "gpt-5.3-codex",
                "route_id": "route",
                "backend_id": "backend",
                "openai_base_url": "http://127.0.0.1:8318/v1",
                "codex_home": "/tmp/home",
                "nested": {"path": "/tmp/path"},
            }
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertFalse(packet["custom_launch_plan_safe"])
        self.assertFalse(packet["real_launch_attempted"])
        self.assertFalse(packet["prompt_attempted"])
        self.assertEqual(packet["token_burn"], 0)
        self.assertEqual(
            packet["forbidden_fields"],
            ["model", "route_id", "backend_id", "openai_base_url", "codex_home", "nested", "nested.path"],
        )

    def test_forbidden_custom_launch_fields_rejects_unknown_keys_too(self) -> None:
        self.assertEqual(forbidden_custom_launch_fields({"dry_run": True}), ["dry_run"])

    def test_safe_app_copy_dry_run_is_server_issued_and_does_not_launch(self) -> None:
        packet = build_safe_app_copy_launch_dry_run_packet({})

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["machine_error_code"],
            "WEB_SAFE_APP_COPY_LAUNCH_DRY_RUN_READY",
        )
        self.assertTrue(packet["dry_run"])
        self.assertFalse(packet["launch_performed"])
        self.assertTrue(packet["server_issued_plan"])
        self.assertFalse(packet["browser_forbidden_fields_rejected"])
        self.assertTrue(packet["browser_forbidden_fields_absent"])
        self.assertTrue(packet["browser_forbidden_field_policy_enforced"])
        self.assertFalse(packet["live_launch_admitted"])
        self.assertTrue(packet["app_path_redacted"])
        self.assertTrue(packet["isolated_profile_root_redacted"])
        self.assertTrue(packet["isolated_data_dir_redacted"])
        self.assertEqual(packet["isolated_port_source"], "server_allocated")
        self.assertTrue(packet["isolated_port_redacted"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertFalse(packet["current_codex_home_touched"])
        self.assertFalse(packet["uses_current_home"])
        self.assertFalse(packet["uses_current_codex_home"])
        self.assertFalse(packet["proxy_env_injected"])
        self.assertFalse(packet["raw_path_exposed"])
        self.assertFalse(packet["raw_pid_exposed"])
        self.assertFalse(packet["raw_env_exposed"])
        self.assertEqual(packet["final_verdict"], "WEB_SAFE_APP_COPY_LAUNCH_DRY_RUN_READY")

    def test_safe_app_copy_dry_run_rejects_browser_controlled_launch_fields(self) -> None:
        packet = build_safe_app_copy_launch_dry_run_packet(
            {
                "path": "/tmp/app",
                "profile_root": "/tmp/profile",
                "port": 1234,
                "env": {"HOME": "/tmp/home"},
                "pid": 99,
                "token": "raw",
            }
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "WEB_SAFE_APP_COPY_LAUNCH_BROWSER_FIELD_REJECTED",
        )
        self.assertTrue(packet["browser_forbidden_fields_rejected"])
        self.assertFalse(packet["browser_forbidden_fields_absent"])
        self.assertFalse(packet["launch_performed"])
        self.assertFalse(packet["server_issued_plan"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertEqual(
            packet["forbidden_fields"],
            ["path", "profile_root", "port", "env", "env.HOME", "pid", "token"],
        )

    def test_safe_app_copy_live_launch_blocks_until_owner_contract(self) -> None:
        packet = build_safe_app_copy_launch_live_packet({})

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "WEB_SAFE_APP_COPY_LAUNCH_NOT_ADMITTED",
        )
        self.assertFalse(packet["launch_performed"])
        self.assertFalse(packet["live_launch_admitted"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertTrue(packet["pid_not_exposed_to_browser"])
        self.assertEqual(packet["cleanup_or_stop_instruction"], "no_process_launched")
        self.assertEqual(packet["final_verdict"], "WEB_SAFE_APP_COPY_LAUNCH_LIVE_BLOCKED")
        self.assertEqual(packet["dry_run_final_verdict"], "WEB_SAFE_APP_COPY_LAUNCH_DRY_RUN_READY")

    def test_safe_app_copy_live_launch_rejects_browser_fields(self) -> None:
        packet = build_safe_app_copy_launch_live_packet(
            {"app_path": "/tmp/app", "CODEX_HOME": "/tmp/codex-home", "auth": "raw"}
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "WEB_SAFE_APP_COPY_LAUNCH_BROWSER_FIELD_REJECTED",
        )
        self.assertTrue(packet["browser_forbidden_fields_rejected"])
        self.assertFalse(packet["browser_forbidden_fields_absent"])
        self.assertFalse(packet["launch_performed"])
        self.assertEqual(packet["forbidden_fields"], ["app_path", "CODEX_HOME", "auth"])

    def test_forbidden_app_copy_launch_fields_rejects_unknown_keys_too(self) -> None:
        self.assertEqual(forbidden_app_copy_launch_fields({"dry_run": True}), ["dry_run"])

    def test_custom_status_treats_previous_isolation_proof_as_not_fresh_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_path = Path(temp_dir) / "process_isolation_proof.json"
            proof_path.write_text(
                json.dumps(
                    {
                        "protected_surfaces_unchanged": True,
                        "tmp_root_removed": True,
                        "run_result": {"status": "ok", "final_message": "OK"},
                    }
                ),
                encoding="utf-8",
            )

            packet = build_custom_status_packet(
                {
                    "claim_gate": {"status": "blocked"},
                    "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
                },
                proof_path=proof_path,
            )

        self.assertEqual(packet["status"], "degraded")
        self.assertEqual(packet["machine_error_code"], "CLAIM_GATE_BLOCKED")
        self.assertTrue(packet["operator_surface_ready"])
        self.assertTrue(packet["server_issued_models_visible"])
        self.assertEqual(packet["claim_gate_status"], "blocked")
        self.assertFalse(packet["current_codex_home_allowed"])
        self.assertEqual(packet["current_codex_touch_risk"], "blocked_by_contract")
        self.assertFalse(packet["custom_session_available"])
        self.assertEqual(packet["last_process_isolation_proof"]["status"], "passed")
        self.assertFalse(packet["last_process_isolation_proof"]["fresh_truth"])


if __name__ == "__main__":
    unittest.main()
