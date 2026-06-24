# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy.command_effects import EFFECT_MUTATE, EFFECT_READ
from wild_boar_proxy.core import packets
from wild_boar_proxy.gpt_api_dip_acceptance_gate import (
    GPT_API_DIP_ACCEPTANCE_BLOCKED,
    GPT_API_DIP_ACCEPTANCE_FILE_NAME,
    GPT_API_DIP_ACCEPTANCE_OK,
    GPT_API_DIP_ACCEPTANCE_PACKET_KIND,
    run_gpt_api_dip_acceptance_gate_command,
)
from wild_boar_proxy.runtime import RuntimePaths


def _paths(root: Path) -> RuntimePaths:
    profile = root / "profile"
    managed = profile / "managed"
    return RuntimePaths(
        profile_dir=profile,
        managed_dir=managed,
        stable_config=root / "stable-config.yaml",
        auth_file=profile / "auth.json",
        config_toml=profile / "config.toml",
        runtime_mode_file=profile / "runtime-mode.txt",
        runtime_effective_mode_file=profile / "runtime-effective-mode.txt",
        registry_file=managed / "backend-registry.json",
        state_file=managed / "supervisor-state.json",
        managed_config_file=managed / "managed-config.yaml",
        launcher_script=managed / "stable-runtime-launcher.sh",
        sync_script=managed / "supervisor-sync.sh",
        accounts_bin=root / "bin" / "codex-accounts",
        onboard_bin=root / "bin" / "codex-account-onboard",
        lock_file=managed / "wild-boar-proxy.lock",
        launcher_lock_file=managed / "stable-runtime-launch.lock",
        repair_target_inventory_dir=managed / "stable-repair-target",
        repair_target_reference_file=managed / "approved-repair-target.json",
        target_switch_transaction_file=managed / "target-switch-transaction.json",
        stable_runtime_generated_config_file=managed / "stable-runtime-generated.yaml",
    )


def _fresh_sealed_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "packet_kind": "wbp_fresh_sealed_e2e_proof",
        "status": "ok",
        "machine_error_code": "OK",
        "fresh_sealed_e2e_proven": True,
        "fresh_runtime_proof_sealed": True,
        "core_dispatch_proven": True,
        "core_runtime_proof_sealed": True,
        "fresh_live_custom_codex_e2e_proven": True,
        "full_runtime_diagnostics_passed": True,
        "native_custom_codex_visible_flow_proven": True,
        "full_runtime_dispatch_proven": True,
        "custom_codex_flow_proven": True,
        "user_prompt_submit_hook_ran": True,
        "api_lane_called": True,
        "dispatch_proven": True,
        "codex_working_flow_delivery_proven": True,
        "custom_codex_ui_visibility_proven": True,
        "strict_admission_proven": True,
        "external_freshness_proven": True,
        "proof_admission_sealed": True,
        "feature_runtime_proof_sealed": True,
        "wrong_digest_negative_proven": True,
        "freshness_anchor_bound_to_runner": True,
        "freshness_anchor_bound_to_admission": True,
        "freshness_anchor_bound_to_seal": True,
        "blocking_reasons": [],
        "full_runtime_diagnostic_blocking_reasons": [],
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }
    packet.update(overrides)
    return packet


def _dip_feature_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "packet_kind": "wbp_repeatable_real_custom_dip_proof_runner",
        "status": "ok",
        "machine_error_code": "OK",
        "api_backed_custom_codex_auth_session_proven": True,
        "api_backed_custom_codex_flow_proven": True,
        "api_backed_custom_codex_flow_is_not_ui_session": True,
        "custom_codex_dip_feature_ready": True,
        "feature_ready": True,
        "feature_ready_mode": "api_key_backed_custom_codex_dip",
        "feature_ready_does_not_require_ui_session": True,
        "feature_ready_does_not_prove_product_ready": True,
        "auth_session_machine_error_code": "WBP_CUSTOM_CODEX_API_KEY_ONLY",
        "api_key_only": True,
        "auth_session_api_key_only": True,
        "auth_session_hook_ready": True,
        "auth_session_expected_user_data_observed": True,
        "auth_session_app_server_bound_to_expected_user_data": True,
        "work_mode_proven": True,
        "work_mode_uses_full_dip_work_mode": True,
        "delegate_to_dip_proven": True,
        "api_lane_called": True,
        "route_bound_dispatch_proven": True,
        "live_result_available": True,
        "direct_provider_auth_proven": True,
        "direct_provider_response_observed": True,
        "provider_auth_ok": True,
        "positive_provider_proof_gate_satisfied": True,
        "api_key_only_counts_as_ui_session": False,
        "auth_session_logged_in_ui_session_proven": False,
        "logged_in_ui_session_proven": False,
        "custom_codex_ui_session_ready": False,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "blocking_reasons": [],
        "api_backed_custom_codex_gate_failures": [],
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "raw_task_recorded": False,
        "tool_call_arguments_recorded": False,
        "command_argv_recorded": False,
        "codex_stdout_recorded": False,
        "codex_stderr_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "live_result_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }
    packet.update(overrides)
    return packet


def _dip_action_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "packet_kind": "wbp_dip_working_tool_run",
        "status": "ok",
        "machine_error_code": "OK",
        "delegate_to_dip_proven": True,
        "api_lane_called": True,
        "route_bound_dispatch_proven": True,
        "live_result_available": True,
        "direct_provider_auth_proven": True,
        "direct_provider_response_observed": True,
        "provider_auth_ok": True,
        "positive_provider_proof_gate_satisfied": True,
        "dip_repo_tool_bridge_required": True,
        "dip_repo_tool_bridge_available": True,
        "dip_repo_tool_bridge_used": True,
        "repo_bridge_successful_tool_call_count": 2,
        "dip_action_bridge_required": True,
        "dip_action_bridge_available": True,
        "dip_action_bridge_used": True,
        "dip_action_successful_tool_call_count": 2,
        "dip_action_mutation_applied": True,
        "dip_action_tests_run": True,
        "dip_action_patch_applied": True,
        "dip_code_mutation_required": False,
        "dip_code_written": True,
        "dip_code_patch_applied": True,
        "dip_code_verification_required": False,
        "dip_code_verified": True,
        "repo_bridge_mutation_allowed": True,
        "repo_bridge_mutation_controlled": True,
        "dip_repo_direct_access": False,
        "repo_bridge_readonly": False,
        "repo_bridge_direct_shell_access": False,
        "dip_action_raw_patch_recorded": False,
        "dip_action_raw_command_recorded": False,
        "repo_bridge_context_pack_recorded": False,
        "repo_bridge_raw_tool_results_recorded": False,
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "command_argv_recorded": False,
        "codex_stdout_recorded": False,
        "codex_stderr_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "live_result_route_id_recorded": False,
        "live_result_raw_backend_details_exposed": False,
        "live_result_secret_value_exposed": False,
    }
    packet.update(overrides)
    return packet


def _write_packet(root: Path, name: str, packet: dict[str, object]) -> Path:
    path = root / name
    path.write_text(json.dumps(packet, sort_keys=True), encoding="utf-8")
    return path


class GptApiDipAcceptanceGateTests(unittest.TestCase):
    def _run(
        self,
        root: Path,
        *,
        fresh: dict[str, object] | None = None,
        feature: dict[str, object] | None = None,
        action: dict[str, object] | None = None,
        proof_dir: Path | None = None,
    ) -> dict[str, object]:
        fresh_file = _write_packet(root, "fresh.json", fresh or _fresh_sealed_packet())
        feature_file = _write_packet(root, "feature.json", feature or _dip_feature_packet())
        action_file = _write_packet(root, "action.json", action or _dip_action_packet())
        return run_gpt_api_dip_acceptance_gate_command(
            paths=_paths(root),
            fresh_sealed_proof_file=str(fresh_file),
            dip_feature_proof_file=str(feature_file),
            dip_action_proof_file=str(action_file),
            proof_dir=str(proof_dir) if proof_dir else None,
        )

    def test_positive_joins_full_runtime_dip_feature_and_code_action_proofs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof_dir = root / "proof"
            packet = self._run(root, proof_dir=proof_dir)
            persisted = json.loads(
                (proof_dir / GPT_API_DIP_ACCEPTANCE_FILE_NAME).read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(packet, persisted)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], GPT_API_DIP_ACCEPTANCE_OK)
        self.assertEqual(packet["packet_kind"], GPT_API_DIP_ACCEPTANCE_PACKET_KIND)
        self.assertTrue(packet["feature_ready"])
        self.assertTrue(packet["gpt_api_dip_ready"])
        self.assertTrue(packet["custom_codex_ui_visibility_proven"])
        self.assertTrue(packet["native_custom_codex_visible_flow_proven"])
        self.assertTrue(packet["api_backed_custom_codex_dip_feature_ready"])
        self.assertTrue(packet["api_key_only"])
        self.assertFalse(packet["api_key_only_counts_as_ui_session"])
        self.assertFalse(packet["logged_in_ui_session_proven"])
        self.assertFalse(packet["custom_codex_ui_session_ready"])
        self.assertTrue(packet["dip_action_bridge_proven"])
        self.assertTrue(packet["dip_code_written"])
        self.assertTrue(packet["dip_code_verified"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["gate_runs_live_dispatch"])
        self.assertFalse(packet["gate_reads_audit_history"])
        self.assertFalse(packet["input_file_paths_recorded"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertEqual(packet["effect"], EFFECT_MUTATE)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_status_ok_fresh_packet_without_full_runtime_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                fresh=_fresh_sealed_packet(full_runtime_dispatch_proven=False),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], GPT_API_DIP_ACCEPTANCE_BLOCKED)
        self.assertFalse(packet["feature_ready"])
        self.assertIn(
            "fresh_sealed_full_runtime_dispatch_proven_not_true",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packet["effect"], EFFECT_READ)

    def test_blocks_api_key_only_packet_claiming_ui_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                feature=_dip_feature_packet(
                    api_key_only_counts_as_ui_session=True,
                    logged_in_ui_session_proven=True,
                ),
            )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["feature_ready"])
        self.assertIn(
            "dip_feature_api_key_only_counts_as_ui_session_not_false",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "dip_feature_logged_in_ui_session_proven_not_false",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["logged_in_ui_session_proven"])
        self.assertFalse(packet["custom_codex_ui_session_ready"])

    def test_blocks_dip_action_without_code_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                action=_dip_action_packet(
                    dip_action_tests_run=False,
                    dip_code_verified=False,
                ),
            )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["feature_ready"])
        self.assertFalse(packet["dip_action_bridge_proven"])
        self.assertTrue(packet["dip_code_written"])
        self.assertFalse(packet["dip_code_verified"])
        self.assertIn(
            "dip_action_dip_action_tests_run_not_true",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "dip_action_dip_code_verified_not_true",
            packet["blocking_reasons"],
        )

    def test_blocks_wrong_packet_kind_even_when_flags_are_green(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                action=_dip_action_packet(packet_kind="wbp_other_packet"),
            )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["feature_ready"])
        self.assertIn("dip_action_packet_kind_not_expected", packet["blocking_reasons"])

    def test_blocks_missing_required_safety_flags(self) -> None:
        feature = _dip_feature_packet()
        del feature["raw_provider_response_recorded"]
        del feature["secret_value_exposed"]
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(Path(temp_dir), feature=feature)

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["feature_ready"])
        self.assertIn(
            "dip_feature_raw_provider_response_recorded_not_false",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "dip_feature_secret_value_exposed_not_false",
            packet["blocking_reasons"],
        )

    def test_cli_wires_acceptance_gate(self) -> None:
        with mock.patch.object(
            cli_mod,
            "run_gpt_api_dip_acceptance_gate_command",
            return_value={"status": "ok", "exit_code": 0},
        ) as mocked:
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                rc = cli_mod.main(
                    [
                        "codex-runner",
                        "gpt-api-dip-acceptance-gate",
                        "--fresh-sealed-proof-file",
                        "/tmp/fresh.json",
                        "--dip-feature-proof-file",
                        "/tmp/feature.json",
                        "--dip-action-proof-file",
                        "/tmp/action.json",
                        "--json",
                    ]
                )

        self.assertEqual(rc, 0)
        self.assertTrue(mocked.called)
        self.assertEqual(mocked.call_args.kwargs["proof_dir"], None)
        self.assertEqual(
            mocked.call_args.kwargs["fresh_sealed_proof_file"],
            "/tmp/fresh.json",
        )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")


if __name__ == "__main__":
    unittest.main()
