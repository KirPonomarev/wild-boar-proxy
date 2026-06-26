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
from wild_boar_proxy.e2e_mode_matrix import (
    E2E_MODE_MATRIX_BLOCKED,
    E2E_MODE_MATRIX_FILE_NAME,
    E2E_MODE_MATRIX_OK,
    E2E_MODE_MATRIX_PACKET_KIND,
    run_e2e_mode_matrix_command,
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


def _base_safety() -> dict[str, object]:
    return {
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "active_project_root_path_recorded": False,
        "active_project_root_fallback_used": False,
        "active_project_root_legacy_target_repo_alias_used": False,
        "wrapper_substitution_used": False,
        "wrapper_substitution_detected": False,
        "wrapper_substitution_allowed": False,
    }


def _active_root_fields(
    *,
    required: bool = False,
    available: bool = False,
    is_wbp_repo: bool = False,
    sha: str = "",
) -> dict[str, object]:
    return {
        "active_project_root_required": required,
        "active_project_root_available": available,
        "active_project_root_source": "active_project_root_cli_arg" if required else "",
        "active_project_root_status": "ok" if available else "",
        "active_project_root_sha256": sha,
        "active_project_root_is_wbp_repo": is_wbp_repo,
        "active_project_root_git_available": available,
        "active_project_root_path_recorded": False,
        "active_project_root_fallback_used": False,
        "active_project_root_legacy_target_repo_alias_used": False,
    }


def _target_repo_fields(
    *,
    required: bool = False,
    available: bool = False,
    is_wbp_repo: bool = False,
    sha: str = "",
) -> dict[str, object]:
    return {
        "target_repo_required": required,
        "target_repo_available": available,
        "target_repo_source": "active_project_root_cli_arg" if required else "",
        "target_repo_status": "ok" if available else "",
        "target_repo_sha256": sha,
        "target_repo_is_wbp_repo": is_wbp_repo,
        "target_repo_git_available": available,
        "target_repo_path_recorded": False,
        "target_repo_fallback_used": False,
    }


def _gpt_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "packet_kind": "custom_codex_native_response_matrix",
        "status": "ok",
        "machine_error_code": "OK",
        "execution_mode": "chatgpt_only",
        "selected_mode": "chatgpt_only",
        "runtime_dispatch_mode_truth_recorded": True,
        "dispatch_mode_truth_proven": True,
        "orchestrator": "custom_codex_chatgpt",
        "executor": "custom_codex_chatgpt",
        "chatgpt_lane_selected": True,
        "api_route_selected": False,
        "chatgpt_lane_called": True,
        "api_route_called": False,
        "chatgpt_only_mode_proven": True,
        "gpt_mode_proven": True,
        "api_only_mode_proven": False,
        "api_mode_proven": False,
        "chatgpt_plus_api_mode_proven": False,
        "gpt_api_mode_proven": False,
        "native_response_matrix_proven": True,
        "all_cases_proven": True,
        "positive_case_count": 1,
        "raw_dom_exposed": False,
        "text_value_captured": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        **_base_safety(),
        **_active_root_fields(),
    }
    packet.update(overrides)
    return packet


def _api_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "packet_kind": "wbp_controlled_api_dispatch_proof",
        "status": "ok",
        "machine_error_code": "OK",
        "execution_mode": "api_only",
        "selected_mode": "api_only",
        "runtime_dispatch_mode_truth_recorded": True,
        "dispatch_mode_truth_proven": True,
        "orchestrator": "api_route",
        "executor": "api_route",
        "chatgpt_lane_selected": False,
        "api_route_selected": True,
        "chatgpt_lane_called": False,
        "api_route_called": True,
        "chatgpt_only_mode_proven": False,
        "gpt_mode_proven": False,
        "api_only_mode_proven": True,
        "api_mode_proven": True,
        "chatgpt_plus_api_mode_proven": False,
        "gpt_api_mode_proven": False,
        "dispatch_proven": True,
        "router_dispatch_admitted": True,
        "api_lane_adapter_called": True,
        "api_lane_dispatch_admitted": True,
        "route_bound_dispatch_attempted": True,
        "route_bound_dispatch_proven": True,
        "controlled_provider_called": True,
        "controlled_provider_response_proven": True,
        "provider_response_proven": True,
        "route_candidate_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "native_codex_subagent_used_as_dip": False,
        **_base_safety(),
        **_active_root_fields(),
    }
    packet.update(overrides)
    return packet


def _gpt_api_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "packet_kind": "wbp_gpt_api_dip_acceptance_gate",
        "status": "ok",
        "machine_error_code": "OK",
        "execution_mode": "chatgpt_plus_api",
        "selected_mode": "chatgpt_plus_api",
        "runtime_dispatch_mode_truth_recorded": True,
        "dispatch_mode_truth_proven": True,
        "orchestrator": "custom_codex_chatgpt",
        "executor": "dip_api_route",
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
        "feature_ready": True,
        "gpt_api_dip_ready": True,
        "dip_action_bridge_proven": True,
        "dip_code_written": True,
        "dip_code_verified": True,
        "api_backed_custom_codex_dip_feature_ready": True,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "blocking_reasons": [],
        **_base_safety(),
        **_active_root_fields(required=True, available=True, sha="a" * 64),
    }
    packet.update(overrides)
    return packet


def _dip_packet(
    *,
    root_required: bool = False,
    root_available: bool = False,
    is_wbp_repo: bool = False,
    sha: str = "",
    repo_audit: bool = False,
    code_edit: bool = False,
    readonly: bool = False,
    **overrides: object,
) -> dict[str, object]:
    packet: dict[str, object] = {
        "packet_kind": "wbp_dip_working_tool_run",
        "status": "ok",
        "machine_error_code": "OK",
        "execution_mode": "chatgpt_plus_api",
        "selected_mode": "chatgpt_plus_api",
        "runtime_dispatch_mode_truth_recorded": True,
        "dispatch_mode_truth_proven": True,
        "orchestrator": "custom_codex_chatgpt",
        "executor": "dip_api_route",
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
        "delegate_to_dip_proven": True,
        "api_lane_called": True,
        "route_bound_dispatch_proven": True,
        "live_result_available": True,
        "direct_provider_auth_proven": True,
        "direct_provider_response_observed": True,
        "provider_auth_ok": True,
        "positive_provider_proof_gate_satisfied": True,
        "native_codex_subagent_used_as_dip": False,
        "command_argv_recorded": False,
        "codex_stdout_recorded": False,
        "codex_stderr_recorded": False,
        "dip_repo_direct_access": False,
        "repo_bridge_direct_shell_access": False,
        "dip_action_raw_patch_recorded": False,
        "dip_action_raw_command_recorded": False,
        "repo_bridge_context_pack_recorded": False,
        "repo_bridge_raw_tool_results_recorded": False,
        "live_result_route_id_recorded": False,
        "live_result_raw_backend_details_exposed": False,
        "live_result_secret_value_exposed": False,
        "blocking_reasons": [],
        "dip_repo_tool_bridge_required": repo_audit or code_edit,
        "dip_repo_tool_bridge_available": repo_audit or code_edit,
        "dip_repo_tool_bridge_used": repo_audit or code_edit,
        "repo_bridge_successful_tool_call_count": 2 if repo_audit or code_edit else 0,
        "dip_action_bridge_required": code_edit,
        "dip_action_bridge_available": code_edit,
        "dip_action_bridge_used": code_edit,
        "dip_action_successful_tool_call_count": 2 if code_edit else 0,
        "dip_action_mutation_applied": code_edit,
        "dip_action_tests_run": code_edit,
        "dip_action_patch_applied": code_edit,
        "dip_code_written": code_edit,
        "dip_code_patch_applied": code_edit,
        "dip_code_verified": code_edit,
        "repo_bridge_readonly": readonly,
        "repo_bridge_mutation_allowed": code_edit,
        "repo_bridge_mutation_controlled": code_edit,
        **_base_safety(),
        **_active_root_fields(
            required=root_required,
            available=root_available,
            is_wbp_repo=is_wbp_repo,
            sha=sha,
        ),
        **_target_repo_fields(
            required=root_required,
            available=root_available,
            is_wbp_repo=is_wbp_repo,
            sha=sha,
        ),
    }
    packet.update(overrides)
    return packet


def _direct_reply_proof(
    *,
    alias: str = "DIP",
    text: str = "direct reply ok",
    kind: str = "wbp_api_agent_direct_reply",
    auto_router: bool = False,
    repo_bridge_mode: str = "off",
    repo_bridge_required: bool = False,
    repo_bridge_available: bool = False,
    repo_bridge_used: bool = False,
    **overrides: object,
) -> dict[str, object]:
    packet: dict[str, object] = {
        "packet_kind": kind,
        "status": "ok",
        "machine_error_code": "OK",
        "execution_mode": "api_only",
        "selected_mode": "api_only",
        "runtime_dispatch_mode_truth_recorded": True,
        "dispatch_mode_truth_proven": True,
        "orchestrator": "api_route",
        "executor": "api_route",
        "chatgpt_lane_selected": False,
        "api_route_selected": True,
        "chatgpt_lane_called": False,
        "api_route_called": True,
        "chatgpt_only_mode_proven": False,
        "gpt_mode_proven": False,
        "api_only_mode_proven": True,
        "api_mode_proven": True,
        "chatgpt_plus_api_mode_proven": False,
        "gpt_api_mode_proven": False,
        "selected_alias": alias,
        "selected_slot": "dip",
        "selected_alias_lane": "api_route",
        "runtime_context_file_present": True,
        "runtime_context_file_read": True,
        "alias_context_read": True,
        "selected_api_route_id_recorded": False,
        "selected_route_id_allowed": True,
        "allowed_api_route_ids_enforced": True,
        "forbidden_stale_route_ids_enforced": True,
        "forbidden_stale_route_ids_count": 1,
        "route_bound_dispatch_proven": True,
        "controlled_dispatch_proven": True,
        "api_agent_direct_reply_proven": True,
        "api_agent_direct_reply_text_recorded": True,
        "api_agent_provider_called": True,
        "direct_provider_response_observed": True,
        "provider_auth_ok": True,
        "positive_provider_proof_gate_satisfied": True,
        "provider_response_proven": True,
        "repo_bridge_mode": repo_bridge_mode,
        "repo_bridge_required": repo_bridge_required,
        "repo_bridge_available": repo_bridge_available,
        "repo_bridge_used": repo_bridge_used,
        "direct_api_reply_block": True,
        "reply_block_kind": "api_agent_direct_reply",
        "reply_author_alias": alias,
        "reply_agent_id": "dip",
        "reply_lane": "api_route",
        "reply_provider_label": "deepseek",
        "reply_text": text,
        "direct_reply_text": text,
        "final_answer_was_repo_tool_call": False,
        "reply_proof_summary": {
            "route_bound_dispatch_proven": True,
            "controlled_dispatch_proven": True,
            "api_agent_provider_called": True,
            "api_agent_response_observed": True,
            "provider_response_proven": True,
            "final_answer_was_repo_tool_call": False,
            "fallback_used": False,
            "local_imitation_used": False,
            "tools_wbp_dip_invoked": False,
            "dip_run_invoked": False,
            "codex_exec_invoked": False,
            "native_codex_subagent_used_as_dip": False,
        },
        "gpt_orchestrator_used": False,
        "codex_exec_invoked": False,
        "tools_wbp_dip_invoked": False,
        "dip_run_invoked": False,
        "wrapper_shopping_used": False,
        "wrapper_substitution_used": False,
        "wrapper_substitution_detected": False,
        "wrapper_substitution_allowed": False,
        "native_codex_subagent_used_as_dip": False,
        "file_mutation_attempted": False,
        "blocking_reasons": [],
        **_base_safety(),
        **_active_root_fields(
            required=repo_bridge_required,
            available=repo_bridge_available,
            sha="r" * 64 if repo_bridge_available else "",
        ),
        **_target_repo_fields(
            required=repo_bridge_required,
            available=repo_bridge_available,
            sha="r" * 64 if repo_bridge_available else "",
        ),
    }
    if auto_router:
        packet.update(
            {
                "auto_router_used": True,
                "auto_router_proven": True,
                "auto_router_decision": "api_direct_reply",
                "auto_router_fail_closed": False,
                "auto_router_unknown_alias_blocked": False,
                "auto_router_ambiguous_alias_blocked": False,
                "direct_reply_selected": True,
                "direct_reply_proven": True,
                "natural_alias_command_detected": True,
            }
        )
    packet.update(overrides)
    return packet


def _write_packet(root: Path, name: str, packet: dict[str, object]) -> Path:
    path = root / name
    path.write_text(json.dumps(packet, sort_keys=True), encoding="utf-8")
    return path


class E2EModeMatrixTests(unittest.TestCase):
    def _run(
        self,
        root: Path,
        *,
        gpt: dict[str, object] | None = None,
        api: dict[str, object] | None = None,
        gpt_api: dict[str, object] | None = None,
        dip_ping: dict[str, object] | None = None,
        dip_repo_audit_dummy: dict[str, object] | None = None,
        dip_repo_audit_wbp: dict[str, object] | None = None,
        dip_code_edit_tests_dummy: dict[str, object] | None = None,
        api_agent_direct_reply: dict[str, object] | None = None,
        api_agent_custom_alias: dict[str, object] | None = None,
        proof_dir: Path | None = None,
    ) -> dict[str, object]:
        files = {
            "gpt": _write_packet(root, "gpt.json", gpt or _gpt_packet()),
            "api": _write_packet(root, "api.json", api or _api_packet()),
            "gpt_api": _write_packet(
                root,
                "gpt_api.json",
                gpt_api or _gpt_api_packet(),
            ),
            "dip_ping": _write_packet(
                root,
                "dip_ping.json",
                dip_ping or _dip_packet(),
            ),
            "dip_repo_audit_dummy": _write_packet(
                root,
                "dip_repo_audit_dummy.json",
                dip_repo_audit_dummy
                or _dip_packet(
                    root_required=True,
                    root_available=True,
                    is_wbp_repo=False,
                    sha="d" * 64,
                    repo_audit=True,
                    readonly=True,
                ),
            ),
            "dip_repo_audit_wbp": _write_packet(
                root,
                "dip_repo_audit_wbp.json",
                dip_repo_audit_wbp
                or _dip_packet(
                    root_required=True,
                    root_available=True,
                    is_wbp_repo=True,
                    sha="w" * 64,
                    repo_audit=True,
                    readonly=True,
                ),
            ),
            "dip_code_edit_tests_dummy": _write_packet(
                root,
                "dip_code_edit_tests_dummy.json",
                dip_code_edit_tests_dummy
                or _dip_packet(
                    root_required=True,
                    root_available=True,
                    is_wbp_repo=False,
                    sha="d" * 64,
                    repo_audit=True,
                    code_edit=True,
                    readonly=False,
                ),
            ),
            "api_agent_direct_reply": _write_packet(
                root,
                "api_agent_direct_reply.json",
                api_agent_direct_reply or _direct_reply_proof(),
            ),
            "api_agent_custom_alias": _write_packet(
                root,
                "api_agent_custom_alias.json",
                api_agent_custom_alias
                or _direct_reply_proof(
                    alias="Кодер",
                    text="custom alias ok",
                    kind="wbp_api_agent_auto_router",
                    auto_router=True,
                ),
            ),
        }
        return run_e2e_mode_matrix_command(
            paths=_paths(root),
            gpt_proof_file=str(files["gpt"]),
            api_proof_file=str(files["api"]),
            gpt_api_proof_file=str(files["gpt_api"]),
            dip_ping_proof_file=str(files["dip_ping"]),
            dip_repo_audit_dummy_proof_file=str(files["dip_repo_audit_dummy"]),
            dip_repo_audit_wbp_proof_file=str(files["dip_repo_audit_wbp"]),
            dip_code_edit_tests_dummy_proof_file=str(
                files["dip_code_edit_tests_dummy"]
            ),
            api_agent_direct_reply_proof_file=str(files["api_agent_direct_reply"]),
            api_agent_custom_alias_proof_file=str(files["api_agent_custom_alias"]),
            proof_dir=str(proof_dir) if proof_dir else None,
        )

    def test_positive_matrix_requires_all_modes_and_writes_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof_dir = root / "proof"
            packet = self._run(root, proof_dir=proof_dir)
            persisted = json.loads(
                (proof_dir / E2E_MODE_MATRIX_FILE_NAME).read_text(encoding="utf-8")
            )

        self.assertEqual(packet, persisted)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], E2E_MODE_MATRIX_OK)
        self.assertEqual(packet["packet_kind"], E2E_MODE_MATRIX_PACKET_KIND)
        self.assertTrue(packet["e2e_mode_matrix_ready"])
        self.assertTrue(packet["feature_ready"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["gate_runs_live_dispatch"])
        self.assertFalse(packet["gate_reads_audit_history"])
        self.assertEqual(packet["row_count"], 9)
        self.assertTrue(packet["all_required_rows_green"])
        self.assertEqual(set(packet["row_status_by_name"].values()), {"ok"})
        self.assertTrue(packet["api_agent_direct_reply_ready"])
        self.assertTrue(packet["api_agent_custom_alias_ready"])
        self.assertTrue(packet["dummy_and_wbp_roots_distinct"])
        self.assertFalse(packet["wbp_repo_mutation_allowed"])
        self.assertFalse(packet["wbp_repo_mutation_observed"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertEqual(packet["effect"], EFFECT_MUTATE)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_missing_row_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            good = self._run(root)
            missing = root / "missing.json"
            packet = run_e2e_mode_matrix_command(
                paths=_paths(root),
                gpt_proof_file=str(root / "gpt.json"),
                api_proof_file=str(root / "api.json"),
                gpt_api_proof_file=str(root / "gpt_api.json"),
                dip_ping_proof_file=str(root / "dip_ping.json"),
                dip_repo_audit_dummy_proof_file=str(root / "dip_repo_audit_dummy.json"),
                dip_repo_audit_wbp_proof_file=str(root / "dip_repo_audit_wbp.json"),
                dip_code_edit_tests_dummy_proof_file=str(missing),
                api_agent_direct_reply_proof_file=str(
                    root / "api_agent_direct_reply.json"
                ),
                api_agent_custom_alias_proof_file=str(
                    root / "api_agent_custom_alias.json"
                ),
            )

        self.assertEqual(good["status"], "ok")
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], E2E_MODE_MATRIX_BLOCKED)
        self.assertFalse(packet["e2e_mode_matrix_ready"])
        self.assertIn(
            "dip_code_edit_tests_dummy_file_missing",
            packet["blocking_reasons"],
        )

    def test_blocks_wbp_repo_mutation_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                dip_code_edit_tests_dummy=_dip_packet(
                    root_required=True,
                    root_available=True,
                    is_wbp_repo=True,
                    sha="w" * 64,
                    repo_audit=True,
                    code_edit=True,
                    readonly=False,
                ),
            )

        self.assertEqual(packet["status"], "error")
        self.assertTrue(packet["wbp_repo_mutation_observed"])
        self.assertIn(
            "dip_code_edit_tests_dummy_active_project_root_is_wbp_repo_not_expected",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "dip_code_edit_tests_dummy_wbp_repo_mutation_not_allowed",
            packet["blocking_reasons"],
        )

    def test_blocks_readonly_audit_that_mutates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                dip_repo_audit_wbp=_dip_packet(
                    root_required=True,
                    root_available=True,
                    is_wbp_repo=True,
                    sha="w" * 64,
                    repo_audit=True,
                    code_edit=True,
                    readonly=False,
                ),
            )

        self.assertEqual(packet["status"], "error")
        self.assertIn(
            "dip_repo_audit_wbp_repo_bridge_readonly_not_true",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "dip_repo_audit_wbp_dip_action_bridge_required_not_false",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "dip_repo_audit_wbp_dip_code_written_not_false",
            packet["blocking_reasons"],
        )

    def test_blocks_missing_direct_api_reply_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            good = self._run(root)
            missing = root / "missing-direct.json"
            packet = run_e2e_mode_matrix_command(
                paths=_paths(root),
                gpt_proof_file=str(root / "gpt.json"),
                api_proof_file=str(root / "api.json"),
                gpt_api_proof_file=str(root / "gpt_api.json"),
                dip_ping_proof_file=str(root / "dip_ping.json"),
                dip_repo_audit_dummy_proof_file=str(root / "dip_repo_audit_dummy.json"),
                dip_repo_audit_wbp_proof_file=str(root / "dip_repo_audit_wbp.json"),
                dip_code_edit_tests_dummy_proof_file=str(
                    root / "dip_code_edit_tests_dummy.json"
                ),
                api_agent_direct_reply_proof_file=str(missing),
                api_agent_custom_alias_proof_file=str(
                    root / "api_agent_custom_alias.json"
                ),
            )

        self.assertEqual(good["status"], "ok")
        self.assertEqual(packet["status"], "error")
        self.assertIn(
            "api_agent_direct_reply_file_missing",
            packet["blocking_reasons"],
        )

    def test_blocks_custom_alias_row_that_only_proves_default_dip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                api_agent_custom_alias=_direct_reply_proof(
                    alias="DIP",
                    kind="wbp_api_agent_auto_router",
                    auto_router=True,
                ),
            )

        self.assertEqual(packet["status"], "error")
        self.assertIn(
            "api_agent_custom_alias_custom_alias_not_proven",
            packet["blocking_reasons"],
        )

    def test_blocks_direct_api_reply_without_runtime_context_route_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                api_agent_direct_reply=_direct_reply_proof(
                    alias_context_read=False,
                    runtime_context_file_read=False,
                    selected_route_id_allowed=False,
                    allowed_api_route_ids_enforced=False,
                    forbidden_stale_route_ids_enforced=False,
                    forbidden_stale_route_ids_count=0,
                ),
            )

        self.assertEqual(packet["status"], "error")
        self.assertIn(
            "api_agent_direct_reply_alias_context_read_not_true",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "api_agent_direct_reply_runtime_context_file_read_not_true",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "api_agent_direct_reply_selected_route_id_allowed_not_true",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "api_agent_direct_reply_allowed_api_route_ids_enforced_not_true",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "api_agent_direct_reply_forbidden_stale_route_ids_enforced_not_true",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "api_agent_direct_reply_forbidden_stale_route_ids_count_not_positive",
            packet["blocking_reasons"],
        )

    def test_accepts_plain_direct_api_reply_without_active_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                api_agent_direct_reply=_direct_reply_proof(),
                api_agent_custom_alias=_direct_reply_proof(
                    alias="Кодер",
                    kind="wbp_api_agent_auto_router",
                    auto_router=True,
                ),
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["api_agent_direct_reply_ready"])
        self.assertTrue(packet["api_agent_custom_alias_ready"])
        self.assertEqual(packet["blocking_reasons"], [])

    def test_accepts_repo_bridge_direct_api_reply_with_active_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                api_agent_direct_reply=_direct_reply_proof(
                    repo_bridge_mode="on",
                    repo_bridge_required=True,
                    repo_bridge_available=True,
                    repo_bridge_used=True,
                ),
                api_agent_custom_alias=_direct_reply_proof(
                    alias="Кодер",
                    kind="wbp_api_agent_auto_router",
                    auto_router=True,
                    repo_bridge_mode="on",
                    repo_bridge_required=True,
                    repo_bridge_available=True,
                    repo_bridge_used=True,
                ),
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["blocking_reasons"], [])

    def test_blocks_custom_alias_without_runtime_context_route_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                api_agent_custom_alias=_direct_reply_proof(
                    alias="Кодер",
                    kind="wbp_api_agent_auto_router",
                    auto_router=True,
                    alias_context_read=False,
                    runtime_context_file_present=False,
                    selected_route_id_allowed=False,
                    allowed_api_route_ids_enforced=False,
                    forbidden_stale_route_ids_enforced=False,
                    forbidden_stale_route_ids_count=0,
                ),
            )

        self.assertEqual(packet["status"], "error")
        self.assertIn(
            "api_agent_custom_alias_alias_context_read_not_true",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "api_agent_custom_alias_runtime_context_file_present_not_true",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "api_agent_custom_alias_selected_route_id_allowed_not_true",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "api_agent_custom_alias_allowed_api_route_ids_enforced_not_true",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "api_agent_custom_alias_forbidden_stale_route_ids_enforced_not_true",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "api_agent_custom_alias_forbidden_stale_route_ids_count_not_positive",
            packet["blocking_reasons"],
        )

    def test_blocks_api_packet_with_chatgpt_mode_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                api=_api_packet(
                    execution_mode="chatgpt_only",
                    selected_mode="chatgpt_only",
                    chatgpt_only_mode_proven=True,
                    api_only_mode_proven=False,
                    api_mode_proven=False,
                ),
            )

        self.assertEqual(packet["status"], "error")
        self.assertIn("api_execution_mode_not_expected", packet["blocking_reasons"])
        self.assertIn("api_api_only_mode_proven_not_true", packet["blocking_reasons"])

    def test_blocks_wrapper_or_raw_root_leak_in_any_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(
                Path(temp_dir),
                dip_ping=_dip_packet(
                    wrapper_substitution_used=True,
                    active_project_root_path_recorded=True,
                    fallback_used=True,
                ),
            )

        self.assertEqual(packet["status"], "error")
        self.assertIn(
            "dip_ping_wrapper_substitution_used_not_false",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "dip_ping_active_project_root_path_recorded_not_false",
            packet["blocking_reasons"],
        )
        self.assertIn("dip_ping_fallback_used_not_false", packet["blocking_reasons"])

    def test_cli_wires_e2e_mode_matrix(self) -> None:
        with mock.patch.object(
            cli_mod,
            "run_e2e_mode_matrix_command",
            return_value={"status": "ok", "exit_code": 0},
        ) as mocked:
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                rc = cli_mod.main(
                    [
                        "codex-runner",
                        "e2e-mode-matrix",
                        "--gpt-proof-file",
                        "/tmp/gpt.json",
                        "--api-proof-file",
                        "/tmp/api.json",
                        "--gpt-api-proof-file",
                        "/tmp/gpt-api.json",
                        "--dip-ping-proof-file",
                        "/tmp/dip-ping.json",
                        "--dip-repo-audit-dummy-proof-file",
                        "/tmp/dip-audit-dummy.json",
                        "--dip-repo-audit-wbp-proof-file",
                        "/tmp/dip-audit-wbp.json",
                        "--dip-code-edit-tests-dummy-proof-file",
                        "/tmp/dip-edit-dummy.json",
                        "--api-agent-direct-reply-proof-file",
                        "/tmp/direct-reply.json",
                        "--api-agent-custom-alias-proof-file",
                        "/tmp/custom-alias.json",
                        "--json",
                    ]
                )

        self.assertEqual(rc, 0)
        self.assertTrue(mocked.called)
        self.assertIsNone(mocked.call_args.kwargs["proof_dir"])
        self.assertEqual(mocked.call_args.kwargs["gpt_proof_file"], "/tmp/gpt.json")
        self.assertEqual(
            mocked.call_args.kwargs["api_agent_direct_reply_proof_file"],
            "/tmp/direct-reply.json",
        )
        self.assertEqual(
            mocked.call_args.kwargs["api_agent_custom_alias_proof_file"],
            "/tmp/custom-alias.json",
        )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")

    def test_cli_effect_is_read_without_proof_dir(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "codex-runner",
                "e2e-mode-matrix",
                "--gpt-proof-file",
                "/tmp/gpt.json",
                "--api-proof-file",
                "/tmp/api.json",
                "--gpt-api-proof-file",
                "/tmp/gpt-api.json",
                "--dip-ping-proof-file",
                "/tmp/dip-ping.json",
                "--dip-repo-audit-dummy-proof-file",
                "/tmp/dip-audit-dummy.json",
                "--dip-repo-audit-wbp-proof-file",
                "/tmp/dip-audit-wbp.json",
                "--dip-code-edit-tests-dummy-proof-file",
                "/tmp/dip-edit-dummy.json",
                "--api-agent-direct-reply-proof-file",
                "/tmp/direct-reply.json",
                "--api-agent-custom-alias-proof-file",
                "/tmp/custom-alias.json",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), EFFECT_READ)


if __name__ == "__main__":
    unittest.main()
