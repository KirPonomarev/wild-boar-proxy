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
    GPT_API_DIP_ACCEPTANCE_PACKET_KIND,
)
from wild_boar_proxy.gpt_api_dip_product_ready_gate import (
    GPT_API_DIP_PRODUCT_READY_BLOCKED,
    GPT_API_DIP_PRODUCT_READY_FILE_NAME,
    GPT_API_DIP_PRODUCT_READY_OK,
    GPT_API_DIP_PRODUCT_READY_PACKET_KIND,
    run_gpt_api_dip_product_ready_gate_command,
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


def _acceptance_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "packet_kind": GPT_API_DIP_ACCEPTANCE_PACKET_KIND,
        "status": "ok",
        "machine_error_code": "OK",
        "feature_ready": True,
        "feature_ready_mode": "gpt_api_dip_custom_codex",
        "gpt_api_dip_ready": True,
        "execution_mode": "chatgpt_plus_api",
        "selected_mode": "chatgpt_plus_api",
        "dispatch_mode_truth_source": "gpt_api_dip_acceptance_gate_join",
        "runtime_dispatch_mode_truth_recorded": True,
        "dispatch_mode_truth_proven": True,
        "orchestrator": "custom_codex_chatgpt",
        "executor": "dip_api_route",
        "orchestrator_lane": "custom_codex_chatgpt",
        "executor_lane": "dip_api_route",
        "chatgpt_lane_selected": True,
        "api_route_selected": True,
        "chatgpt_lane_called": True,
        "api_route_called": True,
        "chatgpt_only_mode_proven": False,
        "gpt_mode_proven": False,
        "api_only_mode_proven": False,
        "api_mode_proven": False,
        "chatgpt_plus_api_mode_proven": True,
        "gpt_api_mode_proven": True,
        "dip_action_bridge_proven": True,
        "dip_code_written": True,
        "dip_code_verified": True,
        "custom_codex_ui_visibility_proven": True,
        "native_custom_codex_visible_flow_proven": True,
        "full_runtime_dispatch_proven": True,
        "fresh_sealed_e2e_proven": True,
        "api_backed_custom_codex_dip_feature_ready": True,
        "api_backed_custom_codex_auth_session_proven": True,
        "api_key_only": True,
        "api_key_only_counts_as_ui_session": False,
        "logged_in_ui_session_proven": False,
        "custom_codex_ui_session_ready": False,
        "gate_runs_live_dispatch": False,
        "gate_reads_audit_history": False,
        "input_file_paths_recorded": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "active_project_root_required": True,
        "active_project_root_available": True,
        "active_project_root_source": "active_project_root_cli_arg",
        "active_project_root_status": "ok",
        "active_project_root_path_recorded": False,
        "active_project_root_sha256": "9" * 64,
        "active_project_root_is_wbp_repo": False,
        "active_project_root_git_available": True,
        "active_project_root_fallback_used": False,
        "active_project_root_legacy_target_repo_alias_used": False,
        "target_repo_required": True,
        "target_repo_available": True,
        "target_repo_fallback_used": False,
        "wrapper_substitution_used": False,
        "wrapper_substitution_detected": False,
        "wrapper_substitution_allowed": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "fresh_sealed_failures": [],
        "dip_feature_failures": [],
        "dip_action_failures": [],
        "blocking_reasons": [],
    }
    packet.update(overrides)
    return packet


def _write_packet(root: Path, packet: dict[str, object]) -> Path:
    path = root / "acceptance.json"
    path.write_text(json.dumps(packet), encoding="utf-8")
    return path


class GptApiDipProductReadyGateTests(unittest.TestCase):
    def _run(
        self,
        root: Path,
        *,
        acceptance: dict[str, object] | None = None,
        proof_dir: Path | None = None,
    ) -> dict[str, object]:
        acceptance_file = _write_packet(root, acceptance or _acceptance_packet())
        return run_gpt_api_dip_product_ready_gate_command(
            paths=_paths(root),
            acceptance_gate_file=str(acceptance_file),
            proof_dir=str(proof_dir) if proof_dir else None,
        )

    def test_positive_promotes_feature_scope_to_product_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof_dir = root / "proof"
            packet = self._run(root, proof_dir=proof_dir)
            persisted = json.loads(
                (proof_dir / GPT_API_DIP_PRODUCT_READY_FILE_NAME).read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(packet, persisted)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], GPT_API_DIP_PRODUCT_READY_OK)
        self.assertEqual(packet["packet_kind"], GPT_API_DIP_PRODUCT_READY_PACKET_KIND)
        self.assertEqual(packet["execution_mode"], "chatgpt_plus_api")
        self.assertEqual(packet["selected_mode"], "chatgpt_plus_api")
        self.assertEqual(packet["orchestrator"], "custom_codex_chatgpt")
        self.assertEqual(packet["executor"], "dip_api_route")
        self.assertTrue(packet["runtime_dispatch_mode_truth_recorded"])
        self.assertTrue(packet["dispatch_mode_truth_proven"])
        self.assertTrue(packet["chatgpt_plus_api_mode_proven"])
        self.assertTrue(packet["gpt_api_mode_proven"])
        self.assertTrue(packet["chatgpt_lane_selected"])
        self.assertTrue(packet["api_route_selected"])
        self.assertTrue(packet["chatgpt_lane_called"])
        self.assertTrue(packet["api_route_called"])
        self.assertTrue(packet["active_project_root_required"])
        self.assertTrue(packet["active_project_root_available"])
        self.assertEqual(
            packet["active_project_root_source"],
            "active_project_root_cli_arg",
        )
        self.assertEqual(packet["active_project_root_status"], "ok")
        self.assertFalse(packet["active_project_root_path_recorded"])
        self.assertEqual(packet["active_project_root_sha256"], "9" * 64)
        self.assertFalse(packet["active_project_root_fallback_used"])
        self.assertFalse(packet["active_project_root_legacy_target_repo_alias_used"])
        self.assertTrue(packet["target_repo_required"])
        self.assertTrue(packet["target_repo_available"])
        self.assertFalse(packet["target_repo_fallback_used"])
        self.assertFalse(packet["wrapper_substitution_used"])
        self.assertFalse(packet["wrapper_substitution_detected"])
        self.assertFalse(packet["wrapper_substitution_allowed"])
        self.assertTrue(packet["feature_ready"])
        self.assertTrue(packet["gpt_api_dip_ready"])
        self.assertTrue(packet["product_ready"])
        self.assertEqual(
            packet["product_ready_scope"],
            "gpt_api_dip_custom_codex_feature",
        )
        self.assertTrue(packet["product_ready_is_feature_scoped"])
        self.assertFalse(packet["production_release_ready"])
        self.assertEqual(packet["production_release_claim"], "not_made")
        self.assertFalse(packet["distribution_release_ready"])
        self.assertTrue(packet["does_not_prove_distribution_release"])
        self.assertTrue(packet["dip_code_written"])
        self.assertTrue(packet["dip_code_verified"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertEqual(packet["effect"], EFFECT_MUTATE)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_acceptance_product_ready_overclaim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                acceptance=_acceptance_packet(product_ready=True),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            GPT_API_DIP_PRODUCT_READY_BLOCKED,
        )
        self.assertFalse(packet["product_ready"])
        self.assertIn(
            "acceptance_product_ready_not_false",
            packet["blocking_reasons"],
        )
        self.assertEqual(packet["effect"], EFFECT_READ)

    def test_blocks_missing_dip_code_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                acceptance=_acceptance_packet(dip_code_verified=False),
            )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["product_ready"])
        self.assertIn(
            "acceptance_dip_code_verified_not_true",
            packet["blocking_reasons"],
        )

    def test_blocks_acceptance_input_file_path_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                acceptance=_acceptance_packet(input_file_paths_recorded=True),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            GPT_API_DIP_PRODUCT_READY_BLOCKED,
        )
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["input_file_paths_recorded"])
        self.assertIn(
            "acceptance_input_file_paths_recorded_not_false",
            packet["blocking_reasons"],
        )

    def test_cli_wires_product_ready_gate(self) -> None:
        with mock.patch.object(
            cli_mod,
            "run_gpt_api_dip_product_ready_gate_command",
            return_value={"status": "ok", "exit_code": 0},
        ) as mocked:
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                rc = cli_mod.main(
                    [
                        "codex-runner",
                        "gpt-api-dip-product-ready-gate",
                        "--acceptance-gate-file",
                        "/tmp/acceptance.json",
                        "--proof-dir",
                        "/tmp/proof",
                        "--json",
                    ]
                )

        self.assertEqual(rc, 0)
        self.assertTrue(mocked.called)
        self.assertEqual(
            mocked.call_args.kwargs["acceptance_gate_file"],
            "/tmp/acceptance.json",
        )
        self.assertEqual(mocked.call_args.kwargs["proof_dir"], "/tmp/proof")
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")


if __name__ == "__main__":
    unittest.main()
