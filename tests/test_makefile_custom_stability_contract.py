# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MakefileCustomStabilityContractTests(unittest.TestCase):
    def test_custom_stability_target_models_custom_ui_environment_regressions(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("test-custom-stability:", makefile)
        self.assertIn('PATH="/usr/bin:/bin"', makefile)
        self.assertIn("WBP_PYTHON_BIN", makefile)
        self.assertIn("CUSTOM_STABILITY_PYTHON", makefile)
        self.assertIn(
            "test_run_tests_uses_runtime_python_when_path_python3_is_wrong",
            makefile,
        )
        self.assertIn(
            "test_json_reply_normalization_compacts_run_tests_summary",
            makefile,
        )
        self.assertIn(
            "test_run_tests_resolves_make_when_path_is_empty",
            makefile,
        )
        self.assertIn("test_search_repo_falls_back_when_rg_is_not_on_path", makefile)
        self.assertIn(
            "test_request_live_result_explicit_pytest_runs_as_bootstrap_action",
            makefile,
        )
        self.assertIn(
            "test_request_live_result_explicit_make_custom_stability_runs_as_bootstrap_action",
            makefile,
        )
        self.assertIn(
            "test_request_live_result_healthcheck_bootstrap_blocks_extra_tool_call",
            makefile,
        )
        self.assertIn(
            "test_runtime_healthcheck_smoke_treats_degraded_json_as_tool_success",
            makefile,
        )
        self.assertIn(
            "test_listener_auth_smoke_includes_model_pool_without_token",
            makefile,
        )
        self.assertIn(
            "test_listener_model_matrix_smoke_checks_each_model_without_token",
            makefile,
        )
        self.assertIn(
            "test_request_live_result_model_matrix_prompt_uses_smoke_tool",
            makefile,
        )
        self.assertIn(
            "test_request_live_result_file_delete_verifies_absence_readback",
            makefile,
        )
        self.assertIn(
            "test_request_live_result_file_delete_auto_verifies_deleted_file_absence",
            makefile,
        )
        self.assertIn(
            "test_request_live_result_explicit_file_delete_runs_as_bootstrap_action",
            makefile,
        )
        self.assertIn(
            "test_apply_patch_delete_records_absence_as_mutation_readback",
            makefile,
        )
        self.assertIn(
            "test_request_live_result_repairs_mismatched_tool_used_claim",
            makefile,
        )
        self.assertIn(
            "test_cli_direct_reply_promotes_explicit_repo_action_to_full_work_mode",
            makefile,
        )
        self.assertIn(
            "test_auto_router_preserves_repo_bridge_flags_from_direct_reply_packet",
            makefile,
        )
        self.assertIn("test_unknown_leading_alias_fails_closed_without_api_call", makefile)
        self.assertIn("test_auto_route_marks_exact_json_output_passthrough", makefile)
        self.assertIn(
            "test_packet_does_not_record_screenshot_path_by_default",
            makefile,
        )
        self.assertIn(
            "test_hybrid_openai_compat_adapter_blocks_unknown_addressed_alias_before_downstream",
            makefile,
        )
        self.assertIn(
            "test_custom_bootloader_requires_auto_route_for_unknown_leading_labels",
            makefile,
        )

    def test_custom_bootloader_requires_auto_route_for_unknown_leading_labels(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        command_api = (ROOT / "COMMAND_API.md").read_text(encoding="utf-8")

        for text in (agents, command_api):
            with self.subTest(source=("AGENTS.md" if text is agents else "COMMAND_API.md")):
                self.assertIn("short agent-like", text)
                self.assertIn("DIPP:", text)
                self.assertIn("Ghost:", text)
                self.assertIn("auto-route", text)
                self.assertIn("unknown", text.casefold())

    def test_custom_bootloader_documents_primary_exact_native_gpt_proof(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        command_api = (ROOT / "COMMAND_API.md").read_text(encoding="utf-8")

        for text in (agents, command_api):
            with self.subTest(source=("AGENTS.md" if text is agents else "COMMAND_API.md")):
                normalized = " ".join(text.split())
                self.assertTrue(
                    "primary ChatGPT alias" in normalized
                    or "ChatGPT/primary lane" in normalized
                )
                self.assertIn("auto-route-output", normalized)
                self.assertIn("native GPT", normalized)
                self.assertIn("must not synthesize", normalized)
                self.assertIn("visible", normalized)
                self.assertIn("repo_bridge_evidence_response_proven=true", normalized)
                self.assertIn("non-exact direct reply text is not", normalized)


if __name__ == "__main__":
    unittest.main()
