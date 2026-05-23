# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy.codex_launch_modes import (
    build_custom_status_packet,
    build_launch_modes_packet,
    build_original_launch_dry_run_packet,
    build_original_status_packet,
    forbidden_original_fields,
)


class CodexLaunchModesTests(unittest.TestCase):
    def test_launch_modes_split_original_and_custom_without_global_green(self) -> None:
        packet = build_launch_modes_packet({"claim_gate": {"status": "blocked"}})

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["claim_gate_status"], "blocked")
        modes = {mode["id"]: mode for mode in packet["modes"]}
        self.assertFalse(modes["original_codex"]["proxy_enabled"])
        self.assertFalse(modes["original_codex"]["custom_home"])
        self.assertEqual(modes["original_codex"]["launch_claim_scope"], "dry_run_guard_only")
        self.assertTrue(modes["codex_custom"]["proxy_enabled"])
        self.assertFalse(modes["codex_custom"]["custom_session_available"])
        self.assertEqual(modes["codex_custom"]["launch_claim_scope"], "readonly_readiness_only")

    def test_original_status_forbids_proxy_custom_home_and_mutation(self) -> None:
        packet = build_original_status_packet()

        self.assertEqual(packet["mode_id"], "original_codex")
        self.assertFalse(packet["proxy_injection_allowed"])
        self.assertFalse(packet["custom_home_allowed"])
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
        self.assertFalse(packet["custom_session_available"])
        self.assertEqual(packet["last_process_isolation_proof"]["status"], "passed")
        self.assertFalse(packet["last_process_isolation_proof"]["fresh_truth"])


if __name__ == "__main__":
    unittest.main()
