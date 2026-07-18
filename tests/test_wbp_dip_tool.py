# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from wild_boar_proxy.external_models import errors
from wild_boar_proxy.natural_intent_contract import packet_contains_text
from wild_boar_proxy.runtime import RuntimeErrorInfo
from wild_boar_proxy.wbp_dip_tool import (
    DEFAULT_MODEL,
    DEFAULT_SANDBOX,
    PYTHON_BIN_ENV,
    WBP_DIP_TOOL_ACTION_BRIDGE_FAILED,
    WBP_DIP_TOOL_CODEX_EXEC_FAILED,
    WBP_DIP_TOOL_CODEX_NOT_EXECUTABLE,
    WBP_DIP_TOOL_DELEGATE_NOT_PROVEN,
    WBP_DIP_TOOL_DRY_RUN,
    WBP_DIP_TOOL_EXACT_REPLY_MISMATCH,
    WBP_DIP_TOOL_FILE_BRIDGE_NOT_PROVEN,
    WBP_DIP_TOOL_FORBIDDEN_CODEX_EXEC_EVENT,
    WBP_DIP_TOOL_ACTION_BRIDGE_NOT_USED,
    WBP_DIP_TOOL_ACTIVE_PROJECT_ROOT_UNAVAILABLE,
    WBP_DIP_TOOL_CODE_MUTATION_NOT_APPLIED,
    WBP_DIP_TOOL_CODE_VERIFICATION_FAILED,
    WBP_DIP_TOOL_CODE_VERIFICATION_NOT_RUN,
    WBP_DIP_TOOL_LIVE_RESULT_TIMEOUT,
    WBP_DIP_TOOL_LIVE_RESULT_UNSAFE,
    WBP_DIP_TOOL_LIVE_RESULT_UNAVAILABLE,
    WBP_DIP_TOOL_MUTATION_VERIFICATION_NOT_RUN,
    WBP_DIP_TOOL_OK,
    WBP_DIP_TOOL_REPO_BRIDGE_FINAL_ANSWER_MISSING,
    WBP_DIP_TOOL_REPO_BRIDGE_NOT_USED,
    _codex_exec_forbidden_event_reasons,
    _attach_live_result_text_artifact,
    _bridge_timeout_seconds,
    _build_live_result_prompt,
    _command_from_call,
    _dip_work_mode_settings,
    _execute_repo_tool_call,
    _exact_plain_reply_expected_text,
    _explicit_test_command_from_task,
    _effective_live_result_timeout_seconds,
    _file_write_text_from_task,
    _build_repo_context_pack,
    _code_mutation_requested,
    _codex_app_candidates,
    _repo_bridge_timeout_packet,
    _repo_bridge_fields,
    _repo_bridge_bootstrap_calls,
    _repo_verified_json_reply_from_evidence,
    _git_status_repo,
    _listener_auth_smoke,
    _listener_model_matrix_smoke,
    _runtime_healthcheck_smoke,
    _normalize_json_result_for_task,
    _repo_bridge_requested,
    _repo_bridge_prompt,
    _repo_mutation_requested,
    _requested_test_verification_block_reason,
    _resolve_action_command_argv,
    _run_tests,
    _search_repo,
    _select_target_repo_candidate,
    _sha256_text,
    _task_has_readonly_guard,
    build_codex_exec_argv,
    build_delegate_prompt,
    build_wbp_dip_tool_packet,
    default_codex_bin,
    default_python_bin,
    main,
    request_live_result,
    resolve_requested_codex_bin,
)


TASK = "Codex, дай задачу DIP: проверь рабочий инструмент."


def _write_jsonl(path: Path, events: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=True) for event in events) + "\n",
        encoding="utf-8",
    )


def _delegate_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "packet_kind": "wbp_mcp_delegate_to_dip_reality",
        "status": "ok",
        "machine_error_code": "OK",
        "delegate_to_dip_tool_called": True,
        "api_lane_called": True,
        "route_bound_dispatch_proven": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }
    packet.update(overrides)
    return packet


def _live_result(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "status": "ok",
        "machine_error_code": "OK",
        "provider_called": True,
        "result_available": True,
        "source": "external_models_direct",
        "route_allowed": True,
        "route_status": "ok",
        "route_id_sha256": "0" * 64,
        "route_id_recorded": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "result_text": "DIP checked: dispatch is bounded; next step is operator smoke.",
        "provider_recorded": True,
        "provider": "deepseek",
        "effective_model_sha256": "1" * 64,
        "effective_model_recorded": False,
        "runtime_context_bridge_used": False,
        "runtime_context_file_bridge_used": False,
        "bridge_or_file_bridge_used": False,
        "dip_work_mode": "standard",
        "dip_full_work_mode": False,
        "live_result_text_limit": 2400,
        "live_result_output_token_limit": 768,
        "repo_bridge_max_steps": 8,
        "active_project_root_required": False,
        "active_project_root_available": False,
        "active_project_root_source": "",
        "active_project_root_status": "",
        "active_project_root_path_recorded": False,
        "active_project_root_sha256": "",
        "active_project_root_is_wbp_repo": False,
        "active_project_root_git_available": False,
        "active_project_root_fallback_used": False,
        "active_project_root_legacy_target_repo_alias_used": False,
        "target_repo_required": False,
        "target_repo_available": False,
        "target_repo_source": "",
        "target_repo_status": "",
        "target_repo_path_recorded": False,
        "target_repo_sha256": "",
        "target_repo_is_wbp_repo": False,
        "target_repo_git_available": False,
        "target_repo_fallback_used": False,
        "direct_provider_auth_proven": True,
        "direct_provider_response_observed": True,
        "provider_auth_ok": True,
        "bridge_green_counts_as_provider_proof": False,
        "provider_auth_smoke_required_before_full_runner": True,
        "positive_provider_proof_gate_satisfied": True,
        "dip_repo_direct_access": False,
        "dip_repo_tool_bridge_required": False,
        "dip_repo_tool_bridge_available": False,
        "dip_repo_tool_bridge_used": False,
        "dip_action_bridge_required": False,
        "dip_action_bridge_available": False,
        "dip_action_bridge_used": False,
        "dip_action_tool_call_count": 0,
        "dip_action_successful_tool_call_count": 0,
        "dip_action_mutation_applied": False,
        "dip_action_tests_run": False,
        "dip_action_commands_run": False,
        "dip_action_patch_proposed": False,
        "dip_action_patch_applied": False,
        "dip_code_mutation_required": False,
        "dip_code_written": False,
        "dip_code_patch_applied": False,
        "dip_code_verification_required": False,
        "dip_code_verified": False,
        "dip_code_verification_failed": False,
        "dip_code_failed_verification_count": 0,
        "dip_action_mutated_files": [],
        "dip_action_raw_patch_recorded": False,
        "dip_action_raw_command_recorded": False,
        "repo_bridge_readonly": False,
        "repo_bridge_mutation_allowed": True,
        "repo_bridge_mutation_controlled": True,
        "repo_bridge_direct_shell_access": False,
        "repo_bridge_context_pack_used": False,
        "repo_bridge_bootstrap_used": False,
        "repo_bridge_bootstrap_tool_call_count": 0,
        "repo_bridge_context_pack_sha256": "",
        "repo_bridge_context_pack_recorded": False,
        "repo_bridge_tool_call_count": 0,
        "repo_bridge_successful_tool_call_count": 0,
        "repo_bridge_tool_result_sha256s": [],
        "repo_bridge_raw_tool_results_recorded": False,
        "repo_bridge_blocked": False,
        "dip_evidence_trace_available": False,
        "dip_evidence_trace_recorded": False,
        "dip_evidence_trace_count": 0,
        "dip_evidence_trace": [],
        "dip_evidence_trace_raw_output_recorded": False,
    }
    packet.update(overrides)
    return packet


class WbpDipToolTests(unittest.TestCase):
    def test_scratch_code_write_file_is_allowed_with_syntax_check(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            repo = Path(raw_root)
            result = _execute_repo_tool_call(
                {
                    "tool": "write_file",
                    "path": "tmp/wbp-scratch-code/app.py",
                    "text": "def answer():\n    return 42\n",
                },
                repo_root=repo,
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["machine_error_code"], "OK")
            self.assertTrue(result["mutation_applied"])
            self.assertEqual(result["mutated_files"], ["tmp/wbp-scratch-code/app.py"])
            self.assertEqual(
                (repo / "tmp/wbp-scratch-code/app.py").read_text(encoding="utf-8"),
                "def answer():\n    return 42\n",
            )

    def test_product_code_write_file_stays_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            repo = Path(raw_root)
            result = _execute_repo_tool_call(
                {
                    "tool": "write_file",
                    "path": "wild_boar_proxy/unsafe.py",
                    "text": "VALUE = 1\n",
                },
                repo_root=repo,
            )

            self.assertEqual(result["status"], "error")
            self.assertEqual(
                result["machine_error_code"],
                "write_file_code_path_not_allowed",
            )
            self.assertFalse((repo / "wild_boar_proxy/unsafe.py").exists())

    def test_scratch_code_write_file_rolls_back_invalid_python(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            repo = Path(raw_root)
            result = _execute_repo_tool_call(
                {
                    "tool": "write_file",
                    "path": "tmp/wbp-scratch-code/broken.py",
                    "text": "def broken(:\n",
                },
                repo_root=repo,
            )

            self.assertEqual(result["status"], "error")
            self.assertEqual(result["machine_error_code"], "python_syntax_check_failed")
            self.assertTrue(result["rollback_applied"])
            self.assertFalse((repo / "tmp/wbp-scratch-code/broken.py").exists())

    def test_repo_bridge_requested_treats_plain_test_and_verify_as_repo_intent(
        self,
    ) -> None:
        self.assertTrue(
            _repo_bridge_requested(task="DIP: test demo.py", mode="auto")
        )
        self.assertTrue(
            _repo_bridge_requested(task="DIP: verify demo.py", mode="auto")
        )

    def test_code_mutation_requested_keeps_scoped_no_edit_clause_non_readonly(
        self,
    ) -> None:
        self.assertTrue(
            _code_mutation_requested(
                task="fix demo.py but without editing README",
                repo_bridge_required=True,
            )
        )
        self.assertTrue(
            _code_mutation_requested(
                task="fix demo.py, но без правок README",
                repo_bridge_required=True,
            )
        )
        self.assertTrue(
            _code_mutation_requested(
                task="fix app.py. Не трогай файлы вне active repo.",
                repo_bridge_required=True,
            )
        )
        self.assertFalse(
            _code_mutation_requested(
                task="fix app.py, но без правок файлов.",
                repo_bridge_required=True,
            )
        )

    def test_file_artifact_mutation_is_not_code_mutation(self) -> None:
        task = (
            "DIP: через repo bridge создай файл "
            "tmp/wbp-custom-strong/mutation-a.txt с текстом OK, затем прочитай его обратно"
        )

        self.assertTrue(_repo_bridge_requested(task=task, mode="auto"))
        self.assertTrue(
            _repo_mutation_requested(task=task, repo_bridge_required=True)
        )
        self.assertFalse(
            _code_mutation_requested(task=task, repo_bridge_required=True)
        )

    def test_file_artifact_write_bootstrap_preserves_full_relative_path(self) -> None:
        task = (
            "Agent 2: using the repo bridge, create file "
            "tmp/wbp-custom-strong/agent2-en.txt with text WBP_AGENT2_EN_OK, "
            "read it back, and answer JSON with status, changed_files, readback_ok."
        )

        self.assertEqual(
            _file_write_text_from_task(
                task,
                path="tmp/wbp-custom-strong/agent2-en.txt",
            ),
            "WBP_AGENT2_EN_OK",
        )
        calls = _repo_bridge_bootstrap_calls(
            task=task,
            repo_bridge_required=True,
            action_bridge_required=True,
        )

        self.assertEqual(
            calls,
            [
                {
                    "tool": "write_file",
                    "path": "tmp/wbp-custom-strong/agent2-en.txt",
                    "text": "WBP_AGENT2_EN_OK",
                    "origin": "wbp_bootstrap",
                },
                {
                    "tool": "read_file",
                    "path": "tmp/wbp-custom-strong/agent2-en.txt",
                    "origin": "wbp_bootstrap",
                },
            ],
        )

    def test_file_artifact_write_text_stops_before_russian_readback_clause(self) -> None:
        task = (
            "DIP: через repo bridge создай файл "
            "tmp/wbp-custom-strong/mutation-a.txt с текстом "
            "WBP_CHAOS_REPO_MUTATION_FILE_OK_20260629, прочитай его обратно, "
            "и если readback совпал, ответь ровно WBP_CHAOS_REPO_MUTATION_OK_20260629"
        )

        self.assertEqual(
            _file_write_text_from_task(
                task,
                path="tmp/wbp-custom-strong/mutation-a.txt",
            ),
            "WBP_CHAOS_REPO_MUTATION_FILE_OK_20260629",
        )
        calls = _repo_bridge_bootstrap_calls(
            task=task,
            repo_bridge_required=True,
            action_bridge_required=True,
        )

        self.assertEqual(calls[0]["tool"], "write_file")
        self.assertEqual(
            calls[0]["text"], "WBP_CHAOS_REPO_MUTATION_FILE_OK_20260629"
        )

    def test_file_artifact_write_bootstrap_allows_named_scratch_code_path(self) -> None:
        task = (
            "DIP: через repo bridge создай файл tmp/wbp-scratch-code/demo.py "
            "с текстом VALUE = 1, затем прочитай его обратно"
        )

        calls = _repo_bridge_bootstrap_calls(
            task=task,
            repo_bridge_required=True,
            action_bridge_required=True,
        )

        self.assertEqual(
            calls,
            [
                {
                    "tool": "write_file",
                    "path": "tmp/wbp-scratch-code/demo.py",
                    "text": "VALUE = 1",
                    "origin": "wbp_bootstrap",
                },
                {
                    "tool": "read_file",
                    "path": "tmp/wbp-scratch-code/demo.py",
                    "origin": "wbp_bootstrap",
                },
            ],
        )

    def test_file_artifact_write_bootstrap_does_not_shortcut_code_paths(self) -> None:
        task = (
            "DIP: using the repo bridge, create file tmp/generated_probe.py "
            "with text print('unsafe shortcut') and answer JSON."
        )

        calls = _repo_bridge_bootstrap_calls(
            task=task,
            repo_bridge_required=True,
            action_bridge_required=True,
        )

        self.assertEqual(
            calls,
            [
                {
                    "tool": "read_file",
                    "path": "tmp/generated_probe.py",
                    "origin": "wbp_bootstrap",
                }
            ],
        )

    def test_delete_file_bootstrap_allows_named_scratch_code_path(self) -> None:
        task = "DIP: через repo bridge удали файл tmp/wbp-scratch-code/demo.py"

        self.assertTrue(
            _repo_mutation_requested(task=task, repo_bridge_required=True)
        )
        calls = _repo_bridge_bootstrap_calls(
            task=task,
            repo_bridge_required=True,
            action_bridge_required=True,
        )

        self.assertEqual(
            calls,
            [
                {
                    "tool": "delete_file",
                    "path": "tmp/wbp-scratch-code/demo.py",
                    "cleanup_empty_parent": False,
                    "origin": "wbp_bootstrap",
                }
            ],
        )

    def test_delete_file_bootstrap_does_not_shortcut_product_code_paths(self) -> None:
        task = "DIP: через repo bridge удали файл wild_boar_proxy/demo.py"

        calls = _repo_bridge_bootstrap_calls(
            task=task,
            repo_bridge_required=True,
            action_bridge_required=True,
        )

        self.assertFalse(any(call.get("tool") == "delete_file" for call in calls))
        self.assertFalse(any(call.get("tool") == "delete_tree" for call in calls))

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_deletes_named_scratch_code_without_provider_claim(
        self,
        request_json_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            target = repo / "tmp" / "wbp-scratch-code" / "demo.py"
            profile.mkdir()
            target.parent.mkdir(parents=True)
            target.write_text("VALUE = 1\n", encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge удали файл "
                    "tmp/wbp-scratch-code/demo.py и ответь ровно "
                    "WBP_SCRATCH_DELETE_OK"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=1,
            )
            target_absent = not target.exists()

        request_json_mock.assert_not_called()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(result["source"], "repo_bridge_verified_evidence")
        self.assertEqual(result["result_text"], "WBP_SCRATCH_DELETE_OK")
        self.assertFalse(result["provider_called"])
        self.assertTrue(result["dip_action_bridge_required"])
        self.assertTrue(result["dip_mutation_required"])
        self.assertTrue(result["dip_mutation_written"])
        self.assertTrue(result["dip_mutation_readback_verified"])
        self.assertEqual(
            result["dip_action_mutated_files"], ["tmp/wbp-scratch-code/demo.py"]
        )
        self.assertTrue(target_absent)

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_mixed_scratch_create_delete_tree_proves_cleanup(
        self,
        request_json_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            target_dir = repo / "tmp" / "wbp-scratch-code"
            profile.mkdir()
            repo.mkdir()
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge создай файл "
                    "tmp/wbp-scratch-code/demo.py с текстом VALUE = 1, "
                    "прочитай его обратно, затем удали директорию "
                    "tmp/wbp-scratch-code целиком. Если директория отсутствует "
                    "после cleanup, ответь ровно WBP_SCRATCH_TREE_DELETE_OK"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=1,
            )
            target_dir_absent = not target_dir.exists()

        request_json_mock.assert_not_called()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(result["source"], "repo_bridge_verified_evidence")
        self.assertEqual(result["result_text"], "WBP_SCRATCH_TREE_DELETE_OK")
        self.assertFalse(result["provider_called"])
        self.assertTrue(result["dip_action_bridge_required"])
        self.assertTrue(result["dip_mutation_required"])
        self.assertTrue(result["dip_mutation_written"])
        self.assertTrue(result["dip_mutation_readback_verified"])
        self.assertEqual(
            result["dip_action_tool_names"],
            ["write_file", "delete_tree"],
        )
        self.assertEqual(
            result["repo_bridge_bootstrap_tool_names"],
            ["write_file", "read_file", "delete_tree"],
        )
        self.assertTrue(target_dir_absent)

    def test_code_mutation_bootstrap_does_not_run_requested_pytest_before_mutation(
        self,
    ) -> None:
        task = (
            "Builder: через repo bridge создай мини-приложение Python в "
            "tmp/wbp-ultrahard-mini-app. Файл app.py должен содержать код. "
            "Файл test_app.py должен содержать pytest-тесты. Затем через repo bridge read-only "
            "запусти команду python3 -m pytest "
            "tmp/wbp-ultrahard-mini-app/test_app.py -q."
        )

        self.assertTrue(
            _code_mutation_requested(task=task, repo_bridge_required=True)
        )
        calls = _repo_bridge_bootstrap_calls(
            task=task,
            repo_bridge_required=True,
            action_bridge_required=True,
        )

        self.assertTrue(calls)
        self.assertNotEqual(calls[0]["tool"], "run_tests")

    def test_mixed_create_delete_task_does_not_bootstrap_delete_first(self) -> None:
        task = (
            "DIP: через repo bridge создай файл tmp/wbp-manual-matrix/ru-write.txt "
            "с текстом OK, прочитай его обратно, удали файл и ответь JSON"
        )

        calls = _repo_bridge_bootstrap_calls(
            task=task,
            repo_bridge_required=True,
            action_bridge_required=True,
        )

        self.assertTrue(calls)
        self.assertNotEqual(calls[0]["tool"], "delete_file")

    def test_mixed_create_delete_tree_task_bootstraps_cleanup_after_readback(self) -> None:
        task = (
            "DIP: через repo bridge создай файл tmp/wbp-scratch-code/demo.py "
            "с текстом VALUE = 1, прочитай его обратно, затем удали директорию "
            "tmp/wbp-scratch-code целиком"
        )

        calls = _repo_bridge_bootstrap_calls(
            task=task,
            repo_bridge_required=True,
            action_bridge_required=True,
        )

        self.assertEqual(
            [call["tool"] for call in calls],
            ["write_file", "read_file", "delete_tree"],
        )
        self.assertEqual(calls[2]["path"], "tmp/wbp-scratch-code")

    def test_pure_delete_task_still_bootstraps_delete(self) -> None:
        task = (
            "DIP: через repo bridge удали файл "
            "tmp/wbp-custom-strong/mutation-a.txt и ответь JSON"
        )

        calls = _repo_bridge_bootstrap_calls(
            task=task,
            repo_bridge_required=True,
            action_bridge_required=True,
        )

        self.assertEqual(calls[0]["tool"], "delete_file")
        self.assertEqual(calls[0]["path"], "tmp/wbp-custom-strong/mutation-a.txt")

    def test_delete_file_with_empty_directory_cleanup_bootstraps_parent_cleanup(
        self,
    ) -> None:
        task = (
            "DIP: через repo bridge удали файл "
            "tmp/wbp-chaos-rerun/mutation-a.txt и пустую директорию "
            "tmp/wbp-chaos-rerun. После успешной очистки ответь ровно OK"
        )

        calls = _repo_bridge_bootstrap_calls(
            task=task,
            repo_bridge_required=True,
            action_bridge_required=True,
        )

        self.assertEqual(calls[0]["tool"], "delete_file")
        self.assertEqual(calls[0]["path"], "tmp/wbp-chaos-rerun/mutation-a.txt")
        self.assertTrue(calls[0]["cleanup_empty_parent"])

    def test_pure_directory_delete_task_bootstraps_delete_tree(self) -> None:
        task = (
            "DIP: через repo bridge удали директорию "
            "tmp/wbp_custom_ultrahard_app_v1 целиком и ответь JSON"
        )

        calls = _repo_bridge_bootstrap_calls(
            task=task,
            repo_bridge_required=True,
            action_bridge_required=True,
        )

        self.assertEqual(
            calls,
            [
                {
                    "tool": "delete_tree",
                    "path": "tmp/wbp_custom_ultrahard_app_v1",
                    "origin": "wbp_bootstrap",
                }
            ],
        )

    def test_readonly_guard_ignores_readonly_inside_path_token(self) -> None:
        task = (
            "DIP: через repo bridge удали файл "
            "tmp/wbp-custom-strong/mutation-a.txt и "
            "tmp/wbp-custom-strong/readonly-deny.txt если они существуют; "
            "если директория tmp/wbp-custom-strong пустая, удали директорию тоже"
        )

        self.assertFalse(_task_has_readonly_guard(task))
        self.assertTrue(
            _repo_mutation_requested(task=task, repo_bridge_required=True)
        )

    def test_json_reply_normalization_removes_fence_and_json_prefix(self) -> None:
        fenced = _normalize_json_result_for_task(
            {
                "status": "ok",
                "result_text": '```json\n{"status": "ok", "passed_count": 48}\n```',
            },
            task="DIP: верни краткий JSON",
        )
        prefixed = _normalize_json_result_for_task(
            {
                "status": "ok",
                "result_text": 'JSON: {"exists": true, "file": "CANON.md"}',
            },
            task="DIP: ответь ровно JSON",
        )

        self.assertEqual(fenced["result_text"], '{"status":"ok","passed_count":48}')
        self.assertEqual(
            prefixed["result_text"],
            '{"exists":true,"file":"CANON.md"}',
        )
        self.assertTrue(fenced["result_text_sha256"])
        self.assertEqual(fenced["result_text_length"], len(fenced["result_text"]))
        self.assertFalse(fenced["result_text_truncated"])

    def test_json_reply_normalization_compacts_run_tests_summary(self) -> None:
        normalized = _normalize_json_result_for_task(
            {
                "tool": "run_tests",
                "status": "ok",
                "command_exit_code": 0,
                "command_used": "make test-custom-stability",
                "result_text": "...................... [100%]\n22 passed, 4 subtests passed in 2.32s\n",
            },
            task=(
                "DIP: через repo bridge read-only запусти make test-custom-stability "
                "и ответь ровно JSON с полями status, passed_count, subtests_count, "
                "command_used"
            ),
        )

        self.assertEqual(
            json.loads(normalized["result_text"]),
            {
                "status": "ok",
                "passed_count": 22,
                "subtests_count": 4,
                "command_used": "make test-custom-stability",
            },
        )
        self.assertEqual(normalized["result_text_length"], len(normalized["result_text"]))
        self.assertFalse(normalized["result_text_truncated"])

    def test_bridge_timeout_seconds_prefers_requested_timeout_and_drops_old_hard_clamp(
        self,
    ) -> None:
        self.assertEqual(
            _bridge_timeout_seconds(
                60.0,
                configured_timeout=None,
                default=8.0,
            ),
            60.0,
        )
        self.assertEqual(
            _bridge_timeout_seconds(
                60.0,
                configured_timeout=45.0,
                default=2.0,
            ),
            45.0,
        )
        self.assertEqual(
            _bridge_timeout_seconds(
                0.01,
                configured_timeout=45.0,
                default=2.0,
            ),
            0.01,
        )

    def test_codex_exec_forbidden_event_reasons_allows_delegate_to_dip_tool_field(
        self,
    ) -> None:
        events = [
            {
                "type": "item.completed",
                "item": {
                    "type": "mcp_tool_call",
                    "server": "wbp",
                    "tool": "delegate_to_dip",
                    "result": {"structuredContent": _delegate_packet()},
                },
            }
        ]

        self.assertEqual(_codex_exec_forbidden_event_reasons(events), [])

    def test_full_work_mode_gives_code_action_bridge_recovery_budget(self) -> None:
        settings = _dip_work_mode_settings("full")

        self.assertEqual(settings["dip_work_mode"], "full")
        self.assertEqual(settings["repo_bridge_max_steps"], 24)

    def test_single_string_command_args_are_split_for_allowlisted_commands(self) -> None:
        argv = _command_from_call(
            {"args": ["python3 -m unittest tests.test_real_custom_dip_proof_runner"]}
        )

        self.assertEqual(
            argv,
            ["python3", "-m", "unittest", "tests.test_real_custom_dip_proof_runner"],
        )

    def test_action_command_resolves_python3_to_runtime_python(self) -> None:
        with mock.patch.dict(os.environ, {PYTHON_BIN_ENV: "/tmp/wbp-python3.14"}):
            argv = _resolve_action_command_argv(["python3", "-m", "pytest", "-q"])

        self.assertEqual(argv, ["/tmp/wbp-python3.14", "-m", "pytest", "-q"])

    def test_run_tests_resolves_make_when_path_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            repo = root / "repo"
            fake_bin = root / "fake-bin"
            repo.mkdir()
            fake_bin.mkdir()
            fake_make = fake_bin / "make"
            fake_make.write_text(
                "#!/bin/sh\n"
                "printf 'PYTHON=%s\\n' \"$PYTHON\"\n"
                "printf 'CUSTOM_STABILITY_PYTHON=%s\\n' \"$CUSTOM_STABILITY_PYTHON\"\n"
                "printf 'custom stability fake target\\n23 passed, 4 subtests passed in 0.01s\\n'\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake_make.chmod(0o755)

            with (
                mock.patch.dict(os.environ, {"PATH": ""}),
                mock.patch(
                    "wild_boar_proxy.wbp_dip_tool.shutil.which",
                    return_value=str(fake_make),
                ),
            ):
                result = _run_tests(repo, {"args": ["make", "test-custom-stability"]})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        self.assertEqual(result["command_used"], "make test-custom-stability")
        self.assertIn(f"PYTHON={default_python_bin()}", result["result_text"])
        self.assertIn(
            f"CUSTOM_STABILITY_PYTHON={default_python_bin()}",
            result["result_text"],
        )
        self.assertIn("23 passed, 4 subtests passed", result["result_text"])
        self.assertNotIn("No such file", result["result_text"])

    def test_run_tests_uses_runtime_python_when_path_python3_is_wrong(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            repo = root / "repo"
            fake_bin = root / "fake-bin"
            tests_dir = repo / "tests"
            fake_bin.mkdir()
            tests_dir.mkdir(parents=True)
            fake_python = fake_bin / "python3"
            fake_python.write_text(
                "#!/bin/sh\necho wrong-python >&2\nexit 91\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            (tests_dir / "test_runtime_python_probe.py").write_text(
                "def test_runtime_python_probe():\n    assert True\n",
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ,
                {
                    PYTHON_BIN_ENV: sys.executable,
                    "PATH": str(fake_bin),
                },
            ):
                result = _run_tests(
                    repo,
                    {
                        "args": [
                            "python3",
                            "-m",
                            "pytest",
                            "tests/test_runtime_python_probe.py",
                            "-q",
                        ]
                    },
                )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        self.assertEqual(result["command_exit_code"], 0)
        self.assertNotIn("wrong-python", result["result_text"])

    def test_search_repo_falls_back_when_rg_is_not_on_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            repo = Path(raw_root)
            (repo / "demo.py").write_text(
                'VALUE = "ok"\nOTHER = "ignored"\n',
                encoding="utf-8",
            )
            with mock.patch("wild_boar_proxy.wbp_dip_tool.shutil.which", return_value=None):
                result = _search_repo(repo, {"pattern": "VALUE", "glob": "demo.py"})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        self.assertEqual(result["result_line_count"], 1)
        self.assertIn('demo.py:1:VALUE = "ok"', result["result_text"])

    def test_build_codex_exec_argv_uses_custom_codex_mcp_delegate_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            prompt = build_delegate_prompt(task=TASK, expected_alias="DIP")
            argv = build_codex_exec_argv(
                codex_bin=root / "codex",
                python_bin=root / "python3.14",
                repo_root=Path("/repo"),
                model="gpt-5.4",
                sandbox=DEFAULT_SANDBOX,
                prompt=prompt,
                output_jsonl=root / "codex.jsonl",
                output_last_message=root / "last.txt",
                profile_dir=root / "profile",
                entry_evidence_file=root / "entry.json",
            )

        self.assertIn("exec", argv)
        self.assertIn("--json", argv)
        self.assertIn("--sandbox", argv)
        self.assertIn(DEFAULT_SANDBOX, argv)
        self.assertIn("-m", argv)
        self.assertIn("gpt-5.4", argv)
        joined = "\n".join(argv)
        self.assertIn(f'mcp_servers.wbp.command="{root / "python3.14"}"', joined)
        self.assertIn("wild_boar_proxy.mcp_delegate", joined)
        self.assertIn("delegate_to_dip", joined)
        self.assertIn('approval_mode="approve"', joined)
        self.assertIn("WBP_PROFILE_DIR", joined)
        self.assertIn(PYTHON_BIN_ENV, joined)

    def test_build_codex_exec_argv_separates_wbp_root_from_codex_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            control_root = root / "wbp"
            target_repo = root / "target"
            control_root.mkdir()
            target_repo.mkdir()
            argv = build_codex_exec_argv(
                codex_bin=root / "codex",
                python_bin=root / "python3.14",
                wbp_repo_root=control_root,
                codex_cwd=target_repo,
                model="gpt-5.4",
                sandbox=DEFAULT_SANDBOX,
                prompt=build_delegate_prompt(task=TASK, expected_alias="DIP"),
                output_jsonl=root / "codex.jsonl",
                output_last_message=root / "last.txt",
                profile_dir=root / "profile",
                entry_evidence_file=root / "entry.json",
            )

        self.assertEqual(argv[argv.index("--cd") + 1], str(target_repo.resolve()))
        env_arg = next(item for item in argv if item.startswith("mcp_servers.wbp.env="))
        self.assertIn(f'PYTHONPATH="{control_root.resolve()}"', env_arg)
        self.assertNotIn(f'PYTHONPATH="{target_repo.resolve()}"', env_arg)

    def test_default_python_bin_prefers_explicit_runtime_python(self) -> None:
        self.assertEqual(
            default_python_bin({PYTHON_BIN_ENV: "/opt/custom/python3.14"}),
            Path("/opt/custom/python3.14"),
        )

    def test_select_target_repo_candidate_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            active_target = root / "active"
            cli_target = root / "cli"
            env_target = root / "env"
            codex_cwd = root / "cwd"
            for path in (active_target, cli_target, env_target, codex_cwd):
                path.mkdir()

            selected, source = _select_target_repo_candidate(
                active_project_root_arg=str(active_target),
                target_repo_arg=str(cli_target),
                codex_cwd=codex_cwd,
                env={
                    "WBP_ACTIVE_PROJECT_ROOT": str(env_target),
                    "WBP_TARGET_REPO": str(cli_target),
                },
            )
            self.assertEqual(selected, active_target.resolve())
            self.assertEqual(source, "active_project_root_cli_arg")

            selected, source = _select_target_repo_candidate(
                active_project_root_arg=None,
                target_repo_arg=str(cli_target),
                codex_cwd=codex_cwd,
                env={"WBP_ACTIVE_PROJECT_ROOT": str(env_target)},
            )
            self.assertEqual(selected, env_target.resolve())
            self.assertEqual(source, "server_runtime_env")

            selected, source = _select_target_repo_candidate(
                active_project_root_arg=None,
                target_repo_arg=str(cli_target),
                codex_cwd=codex_cwd,
                env={},
            )
            self.assertEqual(selected, cli_target.resolve())
            self.assertEqual(source, "legacy_target_repo_cli_arg")

            selected, source = _select_target_repo_candidate(
                active_project_root_arg=None,
                target_repo_arg=None,
                codex_cwd=codex_cwd,
                env={"WBP_TARGET_REPO": str(env_target)},
            )
            self.assertEqual(selected, env_target.resolve())
            self.assertEqual(source, "legacy_target_repo_env")

            selected, source = _select_target_repo_candidate(
                active_project_root_arg=None,
                target_repo_arg=None,
                codex_cwd=codex_cwd,
                env={},
            )
            self.assertIsNone(selected)
            self.assertEqual(source, "missing")

    def test_live_result_prompt_keeps_standard_mode_bounded(self) -> None:
        prompt = _build_live_result_prompt(
            task="DIP: проверь repo read-only",
            expected_alias="DIP",
        )

        self.assertIn("2-6 concise bullets", prompt)

    def test_live_result_prompt_full_mode_removes_artificial_bullet_limit(self) -> None:
        prompt = _build_live_result_prompt(
            task="DIP: изучи repo и дай полный отчет",
            expected_alias="DIP",
            dip_work_mode="full",
        )

        self.assertIn("complete structured operator answer", prompt)
        self.assertNotIn("2-6 concise bullets", prompt)

    def test_default_codex_bin_uses_attested_official_resolver(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            installed_app = root / "Applications" / "Codex.app"
            installed_bin = installed_app / "Contents" / "Resources" / "codex"
            installed_bin.parent.mkdir(parents=True)
            installed_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            installed_bin.chmod(0o755)

            with mock.patch(
                "wild_boar_proxy.wbp_dip_tool.resolve_official_codex_cli",
                return_value=installed_bin,
            ) as resolver:
                resolved = default_codex_bin({})

        self.assertEqual(resolved, installed_bin)
        resolver.assert_called_once_with({})

    def test_requested_codex_bin_must_resolve_inside_attested_official_app(self) -> None:
        expected = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
        with mock.patch(
            "wild_boar_proxy.wbp_dip_tool.resolve_official_codex_cli",
            return_value=expected,
        ) as resolver:
            resolved = resolve_requested_codex_bin(
                str(expected),
                {"WBP_CODEX_APP_PATH": "/Applications/Untrusted.app"},
            )

        source = resolver.call_args.args[0]
        self.assertNotIn("WBP_CODEX_APP_PATH", source)
        self.assertEqual(source["WBP_CODEX_BIN"], str(expected))
        self.assertEqual(resolved, expected)

    def test_codex_app_candidates_prefer_current_official_native_bundle(self) -> None:
        candidates = _codex_app_candidates({})

        self.assertEqual(candidates[0], Path("/Applications/ChatGPT.app"))
        self.assertIn(Path("/Applications/Codex.app"), candidates)
        self.assertFalse(
            any(candidate.name == "Codex WBP Clean.app" for candidate in candidates)
        )

    def test_codex_app_candidates_accept_only_explicit_official_override(self) -> None:
        override = Path("/Applications/ChatGPT Canary.app")
        candidates = _codex_app_candidates(
            {
                "WBP_CODEX_APP_PATH": str(override),
                "WBP_CODEX_APP_COPY_PATH": "/tmp/legacy-copy.app",
            }
        )

        self.assertEqual(candidates[0], override)
        self.assertNotIn(Path("/tmp/legacy-copy.app"), candidates)

    def test_custom_codex_exec_wrapper_uses_signed_official_resolver(self) -> None:
        wrapper = (
            Path(__file__).resolve().parents[1] / "tools/wbp_custom_codex_exec"
        ).read_text(encoding="utf-8")

        self.assertIn("wild_boar_proxy.official_codex_app --print-cli-path", wrapper)
        self.assertNotIn('candidate="$app_path/Contents/Resources/codex"', wrapper)
        self.assertNotIn('codex_bin="${WBP_CODEX_BIN:-}"', wrapper)

    def test_packet_accepts_only_observed_delegate_api_lane(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            jsonl = root / "codex.jsonl"
            last = root / "last.txt"
            entry = root / "entry.json"
            _write_jsonl(
                jsonl,
                [
                    {
                        "type": "mcp_tool_result",
                        "result": {"structuredContent": _delegate_packet()},
                    },
                    {"type": "assistant_message", "role": "assistant", "text": "ok"},
                ],
            )
            last.write_text("ok\n", encoding="utf-8")
            entry.write_text("{}", encoding="utf-8")

            packet = build_wbp_dip_tool_packet(
                task=TASK,
                expected_alias="DIP",
                codex_exit_code=0,
                codex_exec_jsonl_file=jsonl,
                output_last_message_file=last,
                entry_evidence_file=entry,
                proof_dir=root,
                changed_files=[str(jsonl), str(last), str(entry)],
                secret_values=[TASK],
                live_result=_live_result(),
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(packet["execution_mode"], "chatgpt_plus_api")
        self.assertEqual(packet["selected_mode"], "chatgpt_plus_api")
        self.assertEqual(packet["orchestrator"], "custom_codex_chatgpt")
        self.assertEqual(packet["executor"], "dip_api_route")
        self.assertTrue(packet["runtime_dispatch_mode_truth_recorded"])
        self.assertTrue(packet["dispatch_mode_truth_proven"])
        self.assertTrue(packet["chatgpt_plus_api_mode_proven"])
        self.assertTrue(packet["gpt_api_mode_proven"])
        self.assertFalse(packet["api_only_mode_proven"])
        self.assertTrue(packet["chatgpt_lane_selected"])
        self.assertTrue(packet["api_route_selected"])
        self.assertTrue(packet["chatgpt_lane_called"])
        self.assertTrue(packet["api_route_called"])
        self.assertFalse(packet["wrapper_substitution_used"])
        self.assertFalse(packet["wrapper_substitution_detected"])
        self.assertFalse(packet["wrapper_substitution_allowed"])
        self.assertTrue(packet["delegate_to_dip_proven"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["product_ready"])
        self.assertTrue(packet["live_result_required"])
        self.assertTrue(packet["live_result_available"])
        self.assertTrue(packet["live_result_provider_called"])
        self.assertTrue(packet["direct_provider_auth_proven"])
        self.assertTrue(packet["direct_provider_response_observed"])
        self.assertTrue(packet["positive_provider_proof_gate_satisfied"])
        self.assertFalse(packet["live_result_bridge_or_file_bridge_used"])
        self.assertEqual(
            packet["live_result_text"],
            "DIP checked: dispatch is bounded; next step is operator smoke.",
        )
        self.assertFalse(packet["live_result_route_id_recorded"])
        self.assertFalse(packet["live_result_effective_model_recorded"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["prompt_text_recorded"])
        self.assertFalse(packet_contains_text(packet, TASK))

    def test_packet_exposes_repo_bridge_evidence_without_raw_context(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            jsonl = root / "codex.jsonl"
            last = root / "last.txt"
            entry = root / "entry.json"
            _write_jsonl(
                jsonl,
                [
                    {
                        "type": "mcp_tool_result",
                        "result": {"structuredContent": _delegate_packet()},
                    },
                    {"type": "assistant_message", "role": "assistant", "text": "ok"},
                ],
            )
            last.write_text("ok\n", encoding="utf-8")
            entry.write_text("{}", encoding="utf-8")

            packet = build_wbp_dip_tool_packet(
                task="DIP: изучи репо",
                expected_alias="DIP",
                codex_exit_code=0,
                codex_exec_jsonl_file=jsonl,
                output_last_message_file=last,
                entry_evidence_file=entry,
                proof_dir=root,
                changed_files=[str(jsonl), str(last), str(entry)],
                secret_values=[TASK],
                live_result=_live_result(
                    result_text="Repo report from bridge evidence.",
                    dip_repo_tool_bridge_required=True,
                    dip_repo_tool_bridge_available=True,
                    dip_repo_tool_bridge_used=True,
                    active_project_root_required=True,
                    active_project_root_available=True,
                    active_project_root_source="active_project_root_cli_arg",
                    active_project_root_status="ok",
                    active_project_root_path_recorded=False,
                    active_project_root_sha256="f" * 64,
                    active_project_root_is_wbp_repo=False,
                    active_project_root_git_available=True,
                    active_project_root_fallback_used=False,
                    active_project_root_legacy_target_repo_alias_used=False,
                    target_repo_required=True,
                    target_repo_available=True,
                    target_repo_source="active_project_root_cli_arg",
                    target_repo_status="ok",
                    target_repo_path_recorded=False,
                    target_repo_sha256="f" * 64,
                    target_repo_is_wbp_repo=False,
                    target_repo_git_available=True,
                    target_repo_fallback_used=False,
                    repo_bridge_context_pack_used=True,
                    repo_bridge_context_pack_sha256="a" * 64,
                    repo_bridge_tool_call_count=2,
                    repo_bridge_successful_tool_call_count=2,
                    repo_bridge_tool_result_sha256s=["b" * 64, "c" * 64],
                    dip_action_bridge_required=True,
                    dip_action_bridge_available=True,
                    dip_action_bridge_used=True,
                    dip_action_tool_call_count=2,
                    dip_action_successful_tool_call_count=2,
                    dip_action_mutation_applied=True,
                    dip_action_tests_run=True,
                    dip_action_patch_applied=True,
                    dip_code_mutation_required=True,
                    dip_code_written=True,
                    dip_code_patch_applied=True,
                    dip_code_verification_required=True,
                    dip_code_verified=True,
                    dip_action_mutated_files=["demo.py"],
                    dip_evidence_trace=[
                        {
                            "step": 1,
                            "tool": "apply_patch",
                            "origin": "",
                            "status": "ok",
                            "machine_error_code": "OK",
                            "path": "",
                            "result_text_sha256": "d" * 64,
                            "result_text_truncated": False,
                            "patch_sha256": "e" * 64,
                            "patch_recorded": False,
                            "touched_files": ["demo.py"],
                            "command_sha256": "",
                            "command_recorded": False,
                            "command_exit_code": None,
                            "mutation_applied": True,
                            "mutated_files": ["demo.py"],
                            "raw_result_recorded": False,
                        }
                    ],
                ),
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["dip_repo_tool_bridge_required"])
        self.assertTrue(packet["dip_repo_tool_bridge_available"])
        self.assertTrue(packet["dip_repo_tool_bridge_used"])
        self.assertTrue(packet["active_project_root_required"])
        self.assertTrue(packet["active_project_root_available"])
        self.assertEqual(
            packet["active_project_root_source"],
            "active_project_root_cli_arg",
        )
        self.assertEqual(packet["active_project_root_status"], "ok")
        self.assertFalse(packet["active_project_root_path_recorded"])
        self.assertEqual(packet["active_project_root_sha256"], "f" * 64)
        self.assertFalse(packet["active_project_root_is_wbp_repo"])
        self.assertTrue(packet["active_project_root_git_available"])
        self.assertFalse(packet["active_project_root_fallback_used"])
        self.assertFalse(packet["active_project_root_legacy_target_repo_alias_used"])
        self.assertTrue(packet["target_repo_required"])
        self.assertTrue(packet["target_repo_available"])
        self.assertEqual(packet["target_repo_source"], "active_project_root_cli_arg")
        self.assertEqual(packet["target_repo_status"], "ok")
        self.assertFalse(packet["target_repo_path_recorded"])
        self.assertEqual(packet["target_repo_sha256"], "f" * 64)
        self.assertFalse(packet["target_repo_is_wbp_repo"])
        self.assertTrue(packet["target_repo_git_available"])
        self.assertFalse(packet["target_repo_fallback_used"])
        self.assertFalse(packet["dip_repo_direct_access"])
        self.assertTrue(packet["repo_bridge_context_pack_used"])
        self.assertEqual(packet["repo_bridge_context_pack_sha256"], "a" * 64)
        self.assertFalse(packet["repo_bridge_context_pack_recorded"])
        self.assertEqual(packet["repo_bridge_tool_call_count"], 2)
        self.assertEqual(packet["repo_bridge_successful_tool_call_count"], 2)
        self.assertEqual(packet["repo_bridge_tool_result_sha256s"], ["b" * 64, "c" * 64])
        self.assertFalse(packet["repo_bridge_raw_tool_results_recorded"])
        self.assertFalse(packet["repo_bridge_readonly"])
        self.assertTrue(packet["repo_bridge_mutation_allowed"])
        self.assertTrue(packet["repo_bridge_mutation_controlled"])
        self.assertFalse(packet["repo_bridge_direct_shell_access"])
        self.assertTrue(packet["dip_action_bridge_required"])
        self.assertTrue(packet["dip_action_bridge_available"])
        self.assertTrue(packet["dip_action_bridge_used"])
        self.assertEqual(packet["dip_action_tool_call_count"], 2)
        self.assertEqual(packet["dip_action_successful_tool_call_count"], 2)
        self.assertTrue(packet["dip_action_mutation_applied"])
        self.assertTrue(packet["dip_action_tests_run"])
        self.assertTrue(packet["dip_action_patch_applied"])
        self.assertTrue(packet["dip_code_mutation_required"])
        self.assertTrue(packet["dip_code_written"])
        self.assertTrue(packet["dip_code_patch_applied"])
        self.assertTrue(packet["dip_code_verification_required"])
        self.assertTrue(packet["dip_code_verified"])
        self.assertEqual(packet["dip_action_mutated_files"], ["demo.py"])
        self.assertFalse(packet["dip_action_raw_patch_recorded"])
        self.assertFalse(packet["dip_action_raw_command_recorded"])
        self.assertTrue(packet["dip_evidence_trace_available"])
        self.assertTrue(packet["dip_evidence_trace_recorded"])
        self.assertEqual(packet["dip_evidence_trace_count"], 1)
        self.assertEqual(packet["dip_evidence_trace"][0]["tool"], "apply_patch")
        self.assertEqual(packet["dip_evidence_trace"][0]["mutated_files"], ["demo.py"])
        self.assertFalse(packet["dip_evidence_trace"][0]["raw_result_recorded"])
        self.assertFalse(packet["dip_evidence_trace"][0]["patch_recorded"])

    def test_packet_rejects_proof_only_dispatch_when_live_result_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            jsonl = root / "codex.jsonl"
            last = root / "last.txt"
            entry = root / "entry.json"
            _write_jsonl(
                jsonl,
                [
                    {
                        "type": "mcp_tool_result",
                        "result": {"structuredContent": _delegate_packet()},
                    },
                    {"type": "assistant_message", "role": "assistant", "text": "ok"},
                ],
            )
            last.write_text("ok\n", encoding="utf-8")
            entry.write_text("{}", encoding="utf-8")

            packet = build_wbp_dip_tool_packet(
                task=TASK,
                expected_alias="DIP",
                codex_exit_code=0,
                codex_exec_jsonl_file=jsonl,
                output_last_message_file=last,
                entry_evidence_file=entry,
                proof_dir=root,
                changed_files=[str(jsonl), str(last), str(entry)],
                secret_values=[TASK],
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_LIVE_RESULT_UNAVAILABLE)
        self.assertTrue(packet["delegate_to_dip_proven"])
        self.assertFalse(packet["live_result_available"])
        self.assertIn("live_result_unavailable", packet["blocking_reasons"])

    def test_packet_names_proof_only_dispatch_without_live_result_claim(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            jsonl = root / "codex.jsonl"
            last = root / "last.txt"
            entry = root / "entry.json"
            _write_jsonl(
                jsonl,
                [
                    {
                        "type": "mcp_tool_result",
                        "result": {"structuredContent": _delegate_packet()},
                    },
                    {"type": "assistant_message", "role": "assistant", "text": "ok"},
                ],
            )
            last.write_text("ok\n", encoding="utf-8")
            entry.write_text("{}", encoding="utf-8")

            packet = build_wbp_dip_tool_packet(
                task=TASK,
                expected_alias="DIP",
                codex_exit_code=0,
                codex_exec_jsonl_file=jsonl,
                output_last_message_file=last,
                entry_evidence_file=entry,
                proof_dir=root,
                changed_files=[str(jsonl), str(last), str(entry)],
                secret_values=[TASK],
                require_live_result=False,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertFalse(packet["live_result_required"])
        self.assertFalse(packet["live_result_available"])
        self.assertIn("proof-only dispatch", packet["human_message"])
        self.assertNotIn("live result", packet["human_message"])

    def test_packet_rejects_and_redacts_unsafe_live_result_text(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            jsonl = root / "codex.jsonl"
            last = root / "last.txt"
            entry = root / "entry.json"
            _write_jsonl(
                jsonl,
                [
                    {
                        "type": "mcp_tool_result",
                        "result": {"structuredContent": _delegate_packet()},
                    }
                ],
            )
            last.write_text("ok\n", encoding="utf-8")
            entry.write_text("{}", encoding="utf-8")

            packet = build_wbp_dip_tool_packet(
                task=TASK,
                expected_alias="DIP",
                codex_exit_code=0,
                codex_exec_jsonl_file=jsonl,
                output_last_message_file=last,
                entry_evidence_file=entry,
                proof_dir=root,
                changed_files=[str(jsonl), str(last), str(entry)],
                secret_values=[TASK],
                live_result=_live_result(result_text=TASK),
            )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["live_result_available"])
        self.assertEqual(packet["live_result_text"], "")
        self.assertFalse(packet_contains_text(packet, TASK))

    def test_packet_rejects_unsafe_live_result_flags(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            jsonl = root / "codex.jsonl"
            last = root / "last.txt"
            entry = root / "entry.json"
            _write_jsonl(
                jsonl,
                [
                    {
                        "type": "mcp_tool_result",
                        "result": {"structuredContent": _delegate_packet()},
                    }
                ],
            )
            last.write_text("ok\n", encoding="utf-8")
            entry.write_text("{}", encoding="utf-8")

            packet = build_wbp_dip_tool_packet(
                task=TASK,
                expected_alias="DIP",
                codex_exit_code=0,
                codex_exec_jsonl_file=jsonl,
                output_last_message_file=last,
                entry_evidence_file=entry,
                proof_dir=root,
                changed_files=[str(jsonl), str(last), str(entry)],
                secret_values=[TASK],
                live_result=_live_result(raw_backend_details_exposed=True),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_LIVE_RESULT_UNSAFE)
        self.assertFalse(packet["live_result_available"])
        self.assertEqual(packet["live_result_text"], "")
        self.assertIn("unsafe_packet_secret_leak", packet["blocking_reasons"])

    def test_packet_propagates_live_result_provider_auth_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            jsonl = root / "codex.jsonl"
            last = root / "last.txt"
            entry = root / "entry.json"
            _write_jsonl(
                jsonl,
                [
                    {
                        "type": "mcp_tool_result",
                        "result": {"structuredContent": _delegate_packet()},
                    }
                ],
            )
            last.write_text("ok\n", encoding="utf-8")
            entry.write_text("{}", encoding="utf-8")

            packet = build_wbp_dip_tool_packet(
                task=TASK,
                expected_alias="DIP",
                codex_exit_code=0,
                codex_exec_jsonl_file=jsonl,
                output_last_message_file=last,
                entry_evidence_file=entry,
                proof_dir=root,
                changed_files=[str(jsonl), str(last), str(entry)],
                secret_values=[TASK],
                live_result={
                    "status": "error",
                    "machine_error_code": errors.PROVIDER_AUTH_FAILED,
                    "provider_called": True,
                    "result_available": False,
                    "fallback_used": False,
                    "local_imitation_used": False,
                    "raw_backend_details_exposed": False,
                    "secret_value_exposed": False,
                },
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], errors.PROVIDER_AUTH_FAILED)
        self.assertFalse(packet["live_result_available"])
        self.assertIn("live_result_unavailable", packet["blocking_reasons"])

    def test_packet_classifies_codex_exec_and_delegate_failures(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            jsonl = root / "codex.jsonl"
            last = root / "last.txt"
            entry = root / "entry.json"
            _write_jsonl(jsonl, [{"type": "assistant_message", "role": "assistant"}])
            last.write_text("ok\n", encoding="utf-8")
            entry.write_text("{}", encoding="utf-8")

            codex_failed = build_wbp_dip_tool_packet(
                task=TASK,
                expected_alias="DIP",
                codex_exit_code=7,
                codex_exec_jsonl_file=jsonl,
                output_last_message_file=last,
                entry_evidence_file=entry,
                proof_dir=root,
                changed_files=[str(jsonl), str(last), str(entry)],
                secret_values=[TASK],
            )
            missing_delegate = build_wbp_dip_tool_packet(
                task=TASK,
                expected_alias="DIP",
                codex_exit_code=0,
                codex_exec_jsonl_file=jsonl,
                output_last_message_file=last,
                entry_evidence_file=entry,
                proof_dir=root,
                changed_files=[str(jsonl), str(last), str(entry)],
                secret_values=[TASK],
            )
            codex_missing = build_wbp_dip_tool_packet(
                task=TASK,
                expected_alias="DIP",
                codex_exit_code=None,
                codex_exec_jsonl_file=jsonl,
                output_last_message_file=last,
                entry_evidence_file=entry,
                proof_dir=root,
                codex_executable=False,
                changed_files=[str(jsonl), str(last), str(entry)],
                secret_values=[TASK],
            )

        self.assertEqual(codex_failed["machine_error_code"], WBP_DIP_TOOL_CODEX_EXEC_FAILED)
        self.assertIn("codex_exec_failed", codex_failed["blocking_reasons"])
        self.assertEqual(
            missing_delegate["machine_error_code"],
            WBP_DIP_TOOL_DELEGATE_NOT_PROVEN,
        )
        self.assertIn("delegate_to_dip_not_proven", missing_delegate["blocking_reasons"])
        self.assertEqual(
            codex_missing["machine_error_code"],
            WBP_DIP_TOOL_CODEX_NOT_EXECUTABLE,
        )
        self.assertIn("codex_binary_not_executable", codex_missing["blocking_reasons"])

    def test_packet_rejects_fallback_or_local_imitation(self) -> None:
        for unsafe_field in ("fallback_used", "local_imitation_used"):
            with self.subTest(unsafe_field=unsafe_field):
                with tempfile.TemporaryDirectory() as raw_root:
                    root = Path(raw_root)
                    jsonl = root / "codex.jsonl"
                    last = root / "last.txt"
                    entry = root / "entry.json"
                    _write_jsonl(
                        jsonl,
                        [
                            {
                                "type": "mcp_tool_result",
                                "result": {
                                    "structuredContent": _delegate_packet(
                                        **{unsafe_field: True}
                                    )
                                },
                            }
                        ],
                    )
                    last.write_text("ok\n", encoding="utf-8")
                    entry.write_text("{}", encoding="utf-8")

                    packet = build_wbp_dip_tool_packet(
                        task=TASK,
                        expected_alias="DIP",
                        codex_exit_code=0,
                        codex_exec_jsonl_file=jsonl,
                        output_last_message_file=last,
                        entry_evidence_file=entry,
                        proof_dir=root,
                        changed_files=[str(jsonl), str(last), str(entry)],
                        secret_values=[TASK],
                        live_result=_live_result(),
                    )

                self.assertEqual(packet["status"], "error")
                self.assertFalse(packet["delegate_to_dip_proven"])
                self.assertIn("delegate_to_dip_not_proven", packet["blocking_reasons"])

    def test_packet_rejects_non_delegate_codex_tool_event(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            jsonl = root / "codex.jsonl"
            last = root / "last.txt"
            entry = root / "entry.json"
            _write_jsonl(
                jsonl,
                [
                    {
                        "type": "function_call",
                        "name": "exec_command",
                        "arguments": {"cmd": "tools/wbp_dip"},
                    },
                    {
                        "type": "mcp_tool_result",
                        "result": {"structuredContent": _delegate_packet()},
                    },
                ],
            )
            last.write_text("ok\n", encoding="utf-8")
            entry.write_text("{}", encoding="utf-8")

            packet = build_wbp_dip_tool_packet(
                task=TASK,
                expected_alias="DIP",
                codex_exit_code=0,
                codex_exec_jsonl_file=jsonl,
                output_last_message_file=last,
                entry_evidence_file=entry,
                proof_dir=root,
                changed_files=[str(jsonl), str(last), str(entry)],
                secret_values=[TASK],
                live_result=_live_result(),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            WBP_DIP_TOOL_FORBIDDEN_CODEX_EXEC_EVENT,
        )
        self.assertTrue(packet["codex_exec_forbidden_tool_event_observed"])
        self.assertIn(
            "codex_exec_forbidden_shell_tool_event",
            packet["blocking_reasons"],
        )

    def test_full_mode_packet_writes_artifact_without_inline_text(self) -> None:
        long_text = ("FULLMODE-DIP-REPORT\n" + ("line\n" * 1000)).rstrip()
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            jsonl = root / "codex.jsonl"
            last = root / "last.txt"
            entry = root / "entry.json"
            _write_jsonl(
                jsonl,
                [
                    {
                        "type": "mcp_tool_result",
                        "result": {"structuredContent": _delegate_packet()},
                    },
                    {"type": "assistant_message", "role": "assistant", "text": "ok"},
                ],
            )
            last.write_text("ok\n", encoding="utf-8")
            entry.write_text("{}", encoding="utf-8")

            packet = build_wbp_dip_tool_packet(
                task=TASK,
                expected_alias="DIP",
                codex_exit_code=0,
                codex_exec_jsonl_file=jsonl,
                output_last_message_file=last,
                entry_evidence_file=entry,
                proof_dir=root,
                changed_files=[str(jsonl), str(last), str(entry)],
                secret_values=[TASK],
                live_result=_live_result(
                    result_text=long_text,
                    dip_work_mode="full",
                    dip_full_work_mode=True,
                    live_result_text_limit=64000,
                    live_result_output_token_limit=32768,
                    repo_bridge_max_steps=24,
                ),
                dip_work_mode="full",
            )
            packet = _attach_live_result_text_artifact(
                packet,
                root,
                text_source=long_text,
            )
            artifact = root / "live-result-full-text.txt"
            artifact_text = artifact.read_text(encoding="utf-8")

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["dip_full_work_mode"])
        self.assertEqual(packet["live_result_text"], "")
        self.assertFalse(packet["live_result_text_recorded"])
        self.assertEqual(packet["live_result_text_length"], len(long_text))
        self.assertTrue(packet["live_result_text_sha256"])
        self.assertTrue(packet["live_result_text_artifact_written"])
        self.assertFalse(packet["live_result_text_artifact_path_recorded"])
        self.assertEqual(packet["live_result_text_artifact_filename"], artifact.name)
        self.assertTrue(packet["live_result_text_artifact_sha256"])
        self.assertNotEqual(packet["live_result_text_artifact_sha256"], packet["live_result_text_sha256"])
        self.assertEqual(packet["live_result_text_artifact_bytes"], len(artifact_text.encode("utf-8")))
        self.assertEqual(artifact_text.rstrip("\n"), long_text)
        self.assertFalse(packet_contains_text(packet, long_text))

    def test_tool_dry_run_json_is_single_redacted_packet(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "tools/wbp_dip",
                "--dry-run",
                "--json",
                "--codex-bin",
                "/bin/echo",
                TASK,
            ],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        packet = json.loads(completed.stdout)
        self.assertEqual(packet["packet_kind"], "wbp_dip_working_tool_run")
        self.assertEqual(packet["machine_error_code"], "OFFICIAL_CODEX_APP_PATH_INVALID")
        self.assertEqual(packet["effect"], "probe")
        self.assertFalse(packet["planned_codex_exec"])
        self.assertIn("official_codex_app_not_attested", packet["blocking_reasons"])
        self.assertEqual(packet["dip_work_mode"], "standard")
        self.assertFalse(packet["dip_full_work_mode"])
        self.assertEqual(packet["live_result_text_limit"], 2400)
        self.assertEqual(packet["live_result_output_token_limit"], 768)
        self.assertEqual(packet["repo_bridge_max_steps"], 8)
        self.assertFalse(packet_contains_text(packet, TASK))

    def test_tool_dry_run_full_work_mode_reports_full_packet_limits(self) -> None:
        stdout = StringIO()
        with mock.patch(
            "wild_boar_proxy.wbp_dip_tool.resolve_official_codex_cli",
            return_value=Path(
                "/Applications/ChatGPT.app/Contents/Resources/codex"
            ),
        ), redirect_stdout(stdout):
            exit_code = main(
                [
                    "--dry-run",
                    "--json",
                    "--work-mode",
                    "full",
                    "--codex-bin",
                    "/Applications/ChatGPT.app/Contents/Resources/codex",
                    TASK,
                ]
            )

        self.assertEqual(exit_code, 0)
        packet = json.loads(stdout.getvalue())
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_DRY_RUN)
        self.assertEqual(packet["planned_dip_work_mode"], "full")
        self.assertEqual(packet["dip_work_mode"], "full")
        self.assertTrue(packet["dip_full_work_mode"])
        self.assertEqual(packet["live_result_text_limit"], 64000)
        self.assertEqual(packet["live_result_output_token_limit"], 32768)
        self.assertEqual(packet["repo_bridge_max_steps"], 24)
        self.assertFalse(packet_contains_text(packet, TASK))

    def test_official_resolver_failure_ignores_stale_execution_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            proof_dir = root / "proof"
            proof_dir.mkdir()
            _write_jsonl(
                proof_dir / "codex-exec.jsonl",
                [
                    {
                        "type": "mcp_tool_result",
                        "result": {"structuredContent": _delegate_packet()},
                    }
                ],
            )
            (proof_dir / "last-message.txt").write_text(
                "stale assistant output\n",
                encoding="utf-8",
            )
            (proof_dir / "mcp-entry-evidence.json").write_text(
                json.dumps({"status": "ok"}) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/wbp_dip",
                    "--dry-run",
                    "--json",
                    "--codex-bin",
                    "/bin/echo",
                    "--profile-dir",
                    str(root / "profile"),
                    "--proof-dir",
                    str(proof_dir),
                    TASK,
                ],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 1)
        packet = json.loads(completed.stdout)
        self.assertEqual(packet["machine_error_code"], "OFFICIAL_CODEX_APP_PATH_INVALID")
        self.assertEqual(
            packet["blocking_reasons"],
            ["official_codex_app_not_attested"],
        )
        for field in (
            "custom_codex_exec_invoked",
            "assistant_response_observed",
            "delegate_to_dip_tool_call_observed",
            "delegate_to_dip_proven",
            "api_lane_called",
            "api_route_selected",
            "api_route_called",
            "route_bound_dispatch_proven",
            "codex_exec_jsonl_file_present",
            "output_last_message_file_present",
            "entry_evidence_file_present",
        ):
            self.assertFalse(packet[field], field)
        for field in (
            "codex_exec_jsonl_sha256",
            "output_last_message_sha256",
            "entry_evidence_sha256",
            "delegate_packet_sha256",
        ):
            self.assertEqual(packet[field], "", field)

    @mock.patch("wild_boar_proxy.wbp_dip_tool.resolve_official_codex_cli")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_live_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.subprocess.run")
    def test_main_json_operator_path_returns_working_result_packet(
        self,
        subprocess_run_mock: mock.Mock,
        request_live_result_mock: mock.Mock,
        resolve_codex_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            codex_bin = root / "codex"
            codex_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            codex_bin.chmod(0o755)
            resolve_codex_mock.return_value = codex_bin
            proof_dir = root / "proof"
            profile_dir = root / "profile"
            profile_dir.mkdir()
            (profile_dir / "config.toml").write_text(
                'model = "gpt-5.3-codex"\n',
                encoding="utf-8",
            )

            def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
                stdout = kwargs["stdout"]
                env = kwargs["env"]
                Path(str(env["CODEX_HOME"])).joinpath("config.toml").write_text(
                    'model = "gpt-5.3-codex"\n',
                    encoding="utf-8",
                )
                stdout.write(
                    json.dumps(
                        {
                            "type": "raw_prompt_echo",
                            "prompt": build_delegate_prompt(
                                task=TASK,
                                expected_alias="DIP",
                            ),
                            "task": TASK,
                        },
                        ensure_ascii=True,
                    )
                    + "\n"
                )
                stdout.write(
                    json.dumps(
                        {
                            "type": "mcp_tool_result",
                            "result": {"structuredContent": _delegate_packet()},
                        },
                        ensure_ascii=True,
                    )
                    + "\n"
                )
                return SimpleNamespace(returncode=0)

            subprocess_run_mock.side_effect = fake_run
            request_live_result_mock.return_value = _live_result(
                result_text="DIP operator path returned a useful result."
            )
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--json",
                        "--codex-bin",
                        str(codex_bin),
                        "--profile-dir",
                        str(profile_dir),
                        "--proof-dir",
                        str(proof_dir),
                        "--cd",
                        str(Path(__file__).resolve().parents[1]),
                        TASK,
                    ]
                )
            codex_jsonl = (proof_dir / "codex-exec.jsonl").read_text(encoding="utf-8")
            live_text_artifact = proof_dir / "live-result-full-text.txt"
            live_text_artifact_present = live_text_artifact.is_file()
            live_text_artifact_text = live_text_artifact.read_text(encoding="utf-8")
            profile_config_text = (profile_dir / "config.toml").read_text(
                encoding="utf-8"
            )

        self.assertEqual(exit_code, 0)
        packet = json.loads(stdout.getvalue())
        self.assertEqual(packet["packet_kind"], "wbp_dip_working_tool_run")
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertTrue(packet["custom_codex_exec_invoked"])
        self.assertTrue(packet["delegate_to_dip_tool_call_observed"])
        self.assertTrue(packet["delegate_to_dip_proven"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["live_result_available"])
        self.assertTrue(packet["live_result_provider_called"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["live_result_route_id_recorded"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["prompt_text_recorded"])
        self.assertFalse(packet["command_argv_recorded"])
        self.assertFalse(packet["codex_stdout_recorded"])
        self.assertFalse(packet["codex_stderr_recorded"])
        self.assertFalse(packet["product_ready"])
        self.assertGreater(packet["live_result_text_length"], 0)
        self.assertTrue(packet["profile_config_model_repaired_before_codex_exec"])
        self.assertTrue(packet["profile_config_model_repaired_after_codex_exec"])
        self.assertEqual(packet["profile_config_model_after"], DEFAULT_MODEL)
        self.assertIn(f'model = "{DEFAULT_MODEL}"', profile_config_text)
        self.assertFalse(packet["profile_config_path_recorded"])
        self.assertTrue(packet["live_result_text_artifact_written"])
        self.assertFalse(packet["live_result_text_artifact_path_recorded"])
        self.assertEqual(packet["live_result_text_artifact_filename"], "live-result-full-text.txt")
        self.assertTrue(live_text_artifact_present)
        self.assertEqual(
            live_text_artifact_text.rstrip("\n"),
            packet["live_result_text"],
        )
        for path in packet["changed_files"]:
            self.assertTrue(str(path).startswith(str(proof_dir)))
        self.assertFalse(packet_contains_text(packet, TASK))
        escaped_task = json.dumps(TASK, ensure_ascii=True)[1:-1]
        escaped_prompt = json.dumps(
            build_delegate_prompt(task=TASK, expected_alias="DIP"),
            ensure_ascii=True,
        )[1:-1]
        self.assertNotIn(TASK, codex_jsonl)
        self.assertNotIn(escaped_task, codex_jsonl)
        self.assertNotIn(escaped_prompt, codex_jsonl)
        self.assertIn("<redacted-task-sha256:", codex_jsonl)
        self.assertIn("<redacted-codex-prompt-sha256:", codex_jsonl)

    @mock.patch("wild_boar_proxy.wbp_dip_tool.resolve_official_codex_cli")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_live_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.subprocess.run")
    def test_main_plain_operator_path_prints_useful_result(
        self,
        subprocess_run_mock: mock.Mock,
        request_live_result_mock: mock.Mock,
        resolve_codex_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            codex_bin = root / "codex"
            codex_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            codex_bin.chmod(0o755)
            resolve_codex_mock.return_value = codex_bin

            def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
                stdout = kwargs["stdout"]
                stdout.write(
                    json.dumps(
                        {
                            "type": "mcp_tool_result",
                            "result": {"structuredContent": _delegate_packet()},
                        },
                        ensure_ascii=True,
                    )
                    + "\n"
                )
                return SimpleNamespace(returncode=0)

            subprocess_run_mock.side_effect = fake_run
            request_live_result_mock.return_value = _live_result(
                result_text="DIP plain output is useful."
            )
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--codex-bin",
                        str(codex_bin),
                        "--profile-dir",
                        str(root / "profile"),
                        "--proof-dir",
                        str(root / "proof"),
                        "--cd",
                        str(Path(__file__).resolve().parents[1]),
                        TASK,
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "DIP plain output is useful.\n")

    @mock.patch("wild_boar_proxy.wbp_dip_tool.resolve_official_codex_cli")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_live_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.subprocess.run")
    def test_main_loads_openai_api_key_from_local_token_when_env_missing(
        self,
        subprocess_run_mock: mock.Mock,
        request_live_result_mock: mock.Mock,
        resolve_codex_mock: mock.Mock,
    ) -> None:
        sentinel = "local-runtime-token-123456"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            codex_bin = root / "codex"
            codex_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            codex_bin.chmod(0o755)
            resolve_codex_mock.return_value = codex_bin
            profile_dir = root / "profile"
            managed_dir = profile_dir / "managed"
            profile_dir.mkdir()
            managed_dir.mkdir()
            (profile_dir / "config.toml").write_text(
                "\n".join(
                    [
                        'model = "gpt-5.5"',
                        'model_provider = "cliproxy"',
                        "",
                        "[model_providers.cliproxy]",
                        'base_url = "http://127.0.0.1:8318/v1"',
                        'env_key = "OPENAI_API_KEY"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (managed_dir / "stable-runtime-config.generated.yaml").write_text(
                'secret-key: ""\napi-keys:\n  - "local-runtime-token-123456"\n',
                encoding="utf-8",
            )

            def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
                stdout = kwargs["stdout"]
                env = kwargs["env"]
                self.assertEqual(env.get("OPENAI_API_KEY"), sentinel)
                stdout.write(
                    json.dumps(
                        {
                            "type": "mcp_tool_result",
                            "result": {"structuredContent": _delegate_packet()},
                        },
                        ensure_ascii=True,
                    )
                    + "\n"
                )
                return SimpleNamespace(returncode=0)

            subprocess_run_mock.side_effect = fake_run
            request_live_result_mock.return_value = _live_result(
                result_text="DIP env propagation is working."
            )
            stdout = StringIO()
            with mock.patch.dict("os.environ", {}, clear=False):
                os.environ.pop("OPENAI_API_KEY", None)
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "--json",
                            "--codex-bin",
                            str(codex_bin),
                            "--profile-dir",
                            str(profile_dir),
                            "--proof-dir",
                            str(root / "proof"),
                            TASK,
                        ]
                    )

        self.assertEqual(exit_code, 0)
        packet = json.loads(stdout.getvalue())
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertFalse(packet_contains_text(packet, sentinel))

    @mock.patch("wild_boar_proxy.wbp_dip_tool.resolve_official_codex_cli")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_live_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.subprocess.run")
    def test_main_does_not_inject_local_token_for_non_loopback_provider(
        self,
        subprocess_run_mock: mock.Mock,
        request_live_result_mock: mock.Mock,
        resolve_codex_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            codex_bin = root / "codex"
            codex_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            codex_bin.chmod(0o755)
            resolve_codex_mock.return_value = codex_bin
            profile_dir = root / "profile"
            managed_dir = profile_dir / "managed"
            profile_dir.mkdir()
            managed_dir.mkdir()
            (profile_dir / "config.toml").write_text(
                "\n".join(
                    [
                        'model = "gpt-5.5"',
                        'model_provider = "cliproxy"',
                        "",
                        "[model_providers.cliproxy]",
                        'base_url = "https://example.invalid/v1"',
                        'env_key = "OPENAI_API_KEY"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (managed_dir / "stable-runtime-config.generated.yaml").write_text(
                'secret-key: ""\napi-keys:\n  - "local-runtime-token-should-not-be-used"\n',
                encoding="utf-8",
            )

            def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
                stdout = kwargs["stdout"]
                env = kwargs["env"]
                self.assertNotIn("OPENAI_API_KEY", env)
                stdout.write(
                    json.dumps(
                        {
                            "type": "mcp_tool_result",
                            "result": {"structuredContent": _delegate_packet()},
                        },
                        ensure_ascii=True,
                    )
                    + "\n"
                )
                return SimpleNamespace(returncode=0)

            subprocess_run_mock.side_effect = fake_run
            request_live_result_mock.return_value = _live_result(
                result_text="DIP remote provider path is unchanged."
            )
            stdout = StringIO()
            with mock.patch.dict("os.environ", {}, clear=False):
                os.environ.pop("OPENAI_API_KEY", None)
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "--json",
                            "--codex-bin",
                            str(codex_bin),
                            "--profile-dir",
                            str(profile_dir),
                            "--proof-dir",
                            str(root / "proof"),
                            TASK,
                        ]
                    )

        self.assertEqual(exit_code, 0)
        packet = json.loads(stdout.getvalue())
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_OK)

    @mock.patch("wild_boar_proxy.wbp_dip_tool.resolve_official_codex_cli")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_live_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.subprocess.run")
    def test_main_sets_wbp_stable_config_for_auth_command_profiles(
        self,
        subprocess_run_mock: mock.Mock,
        request_live_result_mock: mock.Mock,
        resolve_codex_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            codex_bin = root / "codex"
            codex_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            codex_bin.chmod(0o755)
            resolve_codex_mock.return_value = codex_bin
            profile_dir = root / "profile"
            managed_dir = profile_dir / "managed"
            profile_dir.mkdir()
            managed_dir.mkdir()
            (profile_dir / "config.toml").write_text(
                "\n".join(
                    [
                        'model = "gpt-5.5"',
                        'model_provider = "wbp"',
                        "",
                        "[model_providers.wbp]",
                        'base_url = "http://127.0.0.1:8318/v1"',
                        'wire_api = "responses"',
                        'requires_openai_auth = false',
                        "",
                        "[model_providers.wbp.auth]",
                        'command = "/repo/wbp_codex_auth_command.py"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            expected_stable_config = os.environ.get(
                "WBP_STABLE_CONFIG",
                str(Path("~/.cli-proxy-api/config.yaml").expanduser()),
            )

            def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
                stdout = kwargs["stdout"]
                env = kwargs["env"]
                self.assertEqual(
                    env.get("WBP_STABLE_CONFIG"),
                    expected_stable_config,
                )
                stdout.write(
                    json.dumps(
                        {
                            "type": "mcp_tool_result",
                            "result": {"structuredContent": _delegate_packet()},
                        },
                        ensure_ascii=True,
                    )
                    + "\n"
                )
                return SimpleNamespace(returncode=0)

            subprocess_run_mock.side_effect = fake_run
            request_live_result_mock.return_value = _live_result(
                result_text="DIP auth.command profile inherits the stable config surface."
            )
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--json",
                        "--codex-bin",
                        str(codex_bin),
                        "--profile-dir",
                        str(profile_dir),
                        "--proof-dir",
                        str(root / "proof"),
                        TASK,
                    ]
                )

        self.assertEqual(exit_code, 0)
        packet = json.loads(stdout.getvalue())
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_OK)

    @mock.patch("wild_boar_proxy.wbp_dip_tool.resolve_official_codex_cli")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_live_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.subprocess.run")
    def test_main_passes_explicit_active_project_root_separate_from_codex_cwd(
        self,
        subprocess_run_mock: mock.Mock,
        request_live_result_mock: mock.Mock,
        resolve_codex_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            codex_bin = root / "codex"
            codex_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            codex_bin.chmod(0o755)
            resolve_codex_mock.return_value = codex_bin
            profile_dir = root / "profile"
            profile_dir.mkdir()
            proof_dir = root / "proof"
            codex_cwd = root / "codex-cwd"
            target_repo = root / "target-repo"
            codex_cwd.mkdir()
            target_repo.mkdir()

            def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
                run_argv = list(args[0])
                stdout = kwargs["stdout"]
                self.assertEqual(
                    kwargs["cwd"],
                    str(Path(__file__).resolve().parents[1]),
                )
                self.assertEqual(
                    run_argv[run_argv.index("--cd") + 1],
                    str(codex_cwd.resolve()),
                )
                self.assertEqual(
                    kwargs["env"]["WBP_ACTIVE_PROJECT_ROOT"],
                    str(target_repo.resolve()),
                )
                self.assertEqual(
                    kwargs["env"]["WBP_TARGET_REPO"],
                    str(target_repo.resolve()),
                )
                env_arg = next(
                    item for item in run_argv if item.startswith("mcp_servers.wbp.env=")
                )
                self.assertIn("WBP_ACTIVE_PROJECT_ROOT", env_arg)
                self.assertIn("WBP_TARGET_REPO", env_arg)
                self.assertIn(str(target_repo.resolve()), env_arg)
                stdout.write(
                    json.dumps(
                        {
                            "type": "mcp_tool_result",
                            "result": {"structuredContent": _delegate_packet()},
                        },
                        ensure_ascii=True,
                    )
                    + "\n"
                )
                return SimpleNamespace(returncode=0)

            subprocess_run_mock.side_effect = fake_run
            request_live_result_mock.return_value = _live_result(
                result_text="DIP target repo output.",
                active_project_root_required=True,
                active_project_root_available=True,
                active_project_root_source="active_project_root_cli_arg",
                active_project_root_status="ok",
                active_project_root_path_recorded=False,
                active_project_root_sha256="9" * 64,
                active_project_root_is_wbp_repo=False,
                active_project_root_git_available=False,
                active_project_root_fallback_used=False,
                active_project_root_legacy_target_repo_alias_used=False,
                target_repo_required=True,
                target_repo_available=True,
                target_repo_source="active_project_root_cli_arg",
                target_repo_status="ok",
                target_repo_path_recorded=False,
                target_repo_sha256="9" * 64,
                target_repo_is_wbp_repo=False,
                target_repo_git_available=False,
                target_repo_fallback_used=False,
            )
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--json",
                        "--codex-bin",
                        str(codex_bin),
                        "--profile-dir",
                        str(profile_dir),
                        "--proof-dir",
                        str(proof_dir),
                        "--repo-bridge",
                        "on",
                        "--cd",
                        str(codex_cwd),
                        "--active-project-root",
                        str(target_repo),
                        TASK,
                    ]
                )

        self.assertEqual(exit_code, 0)
        packet = json.loads(stdout.getvalue())
        live_kwargs = request_live_result_mock.call_args.kwargs
        self.assertEqual(live_kwargs["repo_root"], target_repo.resolve())
        self.assertEqual(live_kwargs["target_repo_source"], "active_project_root_cli_arg")
        self.assertEqual(live_kwargs["wbp_repo_root"], Path(__file__).resolve().parents[1])
        self.assertTrue(packet["active_project_root_required"])
        self.assertTrue(packet["active_project_root_available"])
        self.assertEqual(
            packet["active_project_root_source"],
            "active_project_root_cli_arg",
        )
        self.assertFalse(packet["active_project_root_path_recorded"])
        self.assertFalse(packet["active_project_root_fallback_used"])
        self.assertFalse(packet["active_project_root_legacy_target_repo_alias_used"])
        self.assertTrue(packet["target_repo_required"])
        self.assertTrue(packet["target_repo_available"])
        self.assertEqual(packet["target_repo_source"], "active_project_root_cli_arg")
        self.assertFalse(packet["target_repo_path_recorded"])
        self.assertFalse(packet["target_repo_fallback_used"])
        self.assertNotIn(str(target_repo), json.dumps(packet, ensure_ascii=False))

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_uses_runtime_allowed_route(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        route = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        find_route_mock.return_value = route
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": "DIP result: bounded answer from provider."
                        }
                    }
                ]
            },
        )
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                        "deepseek_live_format_check_file_bridge": {
                            "enabled": True,
                            "request_dir": str(profile / "bridge-requests"),
                            "response_dir": str(profile / "bridge-responses"),
                            "timeout_seconds": 0.01,
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=3.0,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertTrue(result["result_available"])
        self.assertTrue(result["provider_called"])
        self.assertEqual(result["result_text"], "DIP result: bounded answer from provider.")
        self.assertFalse(result["route_id_recorded"])
        self.assertTrue(result["direct_provider_auth_proven"])
        self.assertTrue(result["direct_provider_response_observed"])
        self.assertTrue(result["provider_auth_ok"])
        self.assertTrue(result["positive_provider_proof_gate_satisfied"])
        self.assertFalse(result["bridge_or_file_bridge_used"])
        request_json_mock.assert_called_once()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_rechecks_current_route_before_direct_dispatch(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.side_effect = [
            {
                "route_id": "route-ok",
                "base_url": "https://example.invalid",
                "endpoint_path": "/chat/completions",
                "upstream_model": "deepseek-chat",
                "provider": "deepseek",
                "auth": {"type": "bearer", "secret_ref": "DEEPSEEK_API_KEY"},
                "cost_class": "paid_or_free_limited",
                "enabled": False,
            },
            RuntimeErrorInfo(
                "Route not found: route-ok",
                machine_error_code=errors.ROUTE_NOT_FOUND,
                operator_action="user_action",
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            disabled = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=0.01,
            )
            deleted = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=0.01,
            )

        self.assertEqual(disabled["status"], "error")
        self.assertEqual(disabled["machine_error_code"], errors.ROUTE_DISABLED)
        self.assertFalse(disabled["provider_called"])
        self.assertEqual(deleted["status"], "error")
        self.assertEqual(deleted["machine_error_code"], errors.ROUTE_NOT_FOUND)
        self.assertFalse(deleted["provider_called"])
        provider_headers_mock.assert_not_called()
        request_json_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_retries_transient_invalid_upstream_response(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=502,
                latency_ms=10,
                payload={"error": {"code": "bad_gateway"}},
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": "DIP result after transient retry."
                            }
                        }
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(result["result_text"], "DIP result after transient retry.")
        self.assertEqual(result["direct_provider_attempt_count"], 2)
        self.assertEqual(result["direct_provider_retry_count"], 1)
        self.assertEqual(
            result["direct_provider_retry_policy"],
            "transient_invalid_upstream_only",
        )
        self.assertEqual(request_json_mock.call_count, 2)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_requested_pytest_command_is_required_after_code_mutation(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        patch_text = """diff --git a/tmp/wbp-pytest-required/math_box.py b/tmp/wbp-pytest-required/math_box.py
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/tmp/wbp-pytest-required/math_box.py
@@ -0,0 +1,2 @@
+def inc(value):
+    return value + 1
"""
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "apply_patch",
                                            "patch": patch_text,
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "run_command",
                                            "args": [
                                                "python3",
                                                "-m",
                                                "py_compile",
                                                "tmp/wbp-pytest-required/math_box.py",
                                            ],
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=13,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"status":"ok","marker":"WBP_PYTEST_REQUIRED"}'
                                )
                            }
                        }
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: Create tmp/wbp-pytest-required/math_box.py and "
                    "tmp/wbp-pytest-required/test_math_box.py with minimum 2 "
                    "pytest cases. Run python3 -m pytest "
                    "tmp/wbp-pytest-required/test_math_box.py -q. Return JSON."
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=3.0,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["machine_error_code"],
            WBP_DIP_TOOL_CODE_VERIFICATION_NOT_RUN,
        )
        self.assertEqual(
            result["requested_test_verification_block_reason"],
            "requested_test_command_not_run",
        )
        self.assertTrue(result["dip_code_verified"])
        self.assertFalse(result["result_available"])

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_exact_plain_reply_uses_fast_budget(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={"choices": [{"message": {"content": "WBP_FAST"}}]},
        )
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: ответь ровно WBP_FAST. Без правок файлов.",
                expected_alias="DIP",
                profile_dir=profile,
                repo_bridge_mode="off",
                timeout_seconds=0.01,
            )

        payload = request_json_mock.call_args.kwargs["payload"]
        encoded_payload = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["max_tokens"], 512)
        self.assertIn("Return only this exact string", encoded_payload)
        self.assertIn("WBP_FAST", encoded_payload)
        self.assertNotIn("You are DIP called through", encoded_payload)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["exact_plain_reply_fast_path"])
        self.assertFalse(result["exact_plain_reply_file_bridge_skipped"])
        self.assertFalse(result["file_bridge_skipped"])
        self.assertFalse(result["file_bridge_attempted"])
        self.assertEqual(result["dip_work_mode"], "standard")
        self.assertFalse(result["dip_full_work_mode"])
        self.assertEqual(result["live_result_text_limit"], 512)
        self.assertEqual(result["live_result_output_token_limit"], 512)
        self.assertTrue(result["exact_plain_reply_matched"])
        self.assertFalse(result["exact_plain_reply_expected_text_recorded"])
        self.assertFalse(result["exact_plain_reply_observed_text_recorded"])
        self.assertEqual(result["result_text"], "WBP_FAST")

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_exact_plain_reply_mismatch_fails_closed(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={"choices": [{"message": {"content": "WBP_FAST"}}]},
        )
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: ответь ровно WBP_FAST_96_OK. Без правок файлов.",
                expected_alias="DIP",
                profile_dir=profile,
                repo_bridge_mode="off",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["machine_error_code"],
            WBP_DIP_TOOL_EXACT_REPLY_MISMATCH,
        )
        self.assertTrue(result["provider_called"])
        self.assertTrue(result["exact_plain_reply_fast_path"])
        self.assertFalse(result["exact_plain_reply_file_bridge_skipped"])
        self.assertFalse(result["file_bridge_skipped"])
        self.assertFalse(result["file_bridge_attempted"])
        self.assertFalse(result["exact_plain_reply_matched"])
        self.assertFalse(result["exact_plain_reply_expected_text_recorded"])
        self.assertFalse(result["exact_plain_reply_observed_text_recorded"])
        self.assertFalse(result["result_available"])
        self.assertEqual(result["result_text"], "")
        self.assertEqual(result["result_text_sha256"], "")
        self.assertEqual(result["result_text_length"], 0)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_full_mode_raises_budget_and_text_limit(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        long_text = "x" * 13000
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={"choices": [{"message": {"content": long_text}}]},
        )
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: дай подробный отчет",
                expected_alias="DIP",
                profile_dir=profile,
                repo_bridge_mode="off",
                dip_work_mode="full",
                timeout_seconds=0.01,
            )

        payload = request_json_mock.call_args.kwargs["payload"]
        self.assertEqual(payload["max_tokens"], 32768)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["dip_work_mode"], "full")
        self.assertTrue(result["dip_full_work_mode"])
        self.assertEqual(result["live_result_text_limit"], 64000)
        self.assertEqual(result["live_result_output_token_limit"], 32768)
        self.assertEqual(result["result_text"], long_text)
        self.assertFalse(result["result_text_truncated"])

    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_full_mode_http_bridge_raises_template_budget(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
    ) -> None:
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=5,
            payload={"output_text": "Bridge result from WBP."},
        )
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                        "deepseek_live_format_check_bridge": {
                            "enabled": True,
                            "method": "POST",
                            "model": "route-ok",
                            "response_text_field": "output_text",
                            "request_json_template": {
                                "model": "route-ok",
                                "max_output_tokens": 32,
                                "stream": False,
                            },
                            "url_candidates": ["http://127.0.0.1:50555/v1/responses"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: дай подробный отчет",
                expected_alias="DIP",
                profile_dir=profile,
                repo_bridge_mode="off",
                dip_work_mode="full",
                timeout_seconds=12.5,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source"], "runtime_context_http_bridge")
        self.assertEqual(
            request_json_mock.call_args.kwargs["payload"]["max_output_tokens"],
            32768,
        )
        self.assertAlmostEqual(
            request_json_mock.call_args.kwargs["timeout_seconds"],
            12.5,
            places=2,
        )
        find_route_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_repo_bridge_executes_read_tool_before_final(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        route = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        find_route_mock.return_value = route
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "read_file",
                                            "path": "AGENTS.md",
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=14,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": "DIP report is based on AGENTS.md evidence."
                            }
                        }
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "AGENTS.md").write_text(
                "Custom Codex agents must read runtime context.\n",
                encoding="utf-8",
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: изучи репо и дай отчет",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=1,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(result["result_text"], "DIP report is based on AGENTS.md evidence.")
        self.assertTrue(result["dip_repo_tool_bridge_required"])
        self.assertTrue(result["dip_repo_tool_bridge_available"])
        self.assertTrue(result["dip_repo_tool_bridge_used"])
        self.assertFalse(result["dip_repo_direct_access"])
        self.assertTrue(result["repo_bridge_context_pack_used"])
        self.assertFalse(result["repo_bridge_context_pack_recorded"])
        self.assertTrue(result["repo_bridge_bootstrap_used"])
        self.assertEqual(result["repo_bridge_bootstrap_tool_call_count"], 1)
        self.assertEqual(result["repo_bridge_tool_call_count"], 2)
        self.assertEqual(result["repo_bridge_successful_tool_call_count"], 2)
        self.assertEqual(len(result["repo_bridge_tool_result_sha256s"]), 2)
        self.assertFalse(result["repo_bridge_raw_tool_results_recorded"])
        self.assertTrue(result["repo_bridge_readonly"])
        self.assertFalse(result["repo_bridge_mutation_allowed"])
        self.assertFalse(result["repo_bridge_mutation_controlled"])
        self.assertEqual(request_json_mock.call_count, 2)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._live_result_turn")
    def test_request_live_result_repo_bridge_readonly_synthesizes_exact_from_evidence(
        self,
        live_result_turn_mock: mock.Mock,
    ) -> None:
        expected = "WBP_REPO_READ_EXACT_OK"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "CANON.md").write_text("canon\n", encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge read-only проверь, что CANON.md "
                    f"существует, и ответь ровно {expected}"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=1.0,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(result["result_text"], expected)
        self.assertEqual(result["source"], "repo_bridge_verified_evidence")
        self.assertTrue(result["repo_bridge_final_answer_synthesized"])
        self.assertEqual(result["repo_bridge_tool_names"], ["read_file"])
        self.assertEqual(result["repo_bridge_successful_tool_call_count"], 1)
        self.assertFalse(result["provider_called"])
        live_result_turn_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._live_result_turn")
    def test_request_live_result_repo_bridge_synthesizes_outside_root_policy_exact(
        self,
        live_result_turn_mock: mock.Mock,
    ) -> None:
        expected = "WBP_REPO_OUTSIDE_ROOT_BLOCK_OK"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge read-only оцени, разрешена ли "
                    "запись за пределами active project root. Не создавай файлы. "
                    f"Если outside repo write запрещена и active project root "
                    f"обязателен, ответь ровно {expected}, иначе WBP_FAIL"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=1.0,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(result["result_text"], expected)
        self.assertEqual(result["source"], "repo_bridge_verified_evidence")
        self.assertTrue(result["repo_bridge_final_answer_synthesized"])
        self.assertTrue(result["repo_bridge_readonly"])
        self.assertFalse(result["repo_bridge_mutation_allowed"])
        self.assertFalse(result["provider_called"])
        live_result_turn_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._live_result_turn")
    def test_request_live_result_repo_bridge_provider_exact_without_strong_proof_is_not_gated(
        self,
        live_result_turn_mock: mock.Mock,
    ) -> None:
        expected = "WBP_REPO_READ_EXACT_OK"
        live_result_turn_mock.return_value = _live_result(
            result_text=expected,
            result_text_sha256=_sha256_text(expected),
            result_text_length=len(expected),
            direct_provider_response_observed=False,
            positive_provider_proof_gate_satisfied=False,
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge read-only проверь репозиторий "
                    f"существует, и ответь ровно {expected}"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=1.0,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(result["result_text"], expected)
        self.assertFalse(result.get("exact_plain_reply_matched", False))
        self.assertFalse(result["positive_provider_proof_gate_satisfied"])
        self.assertEqual(result["repo_bridge_tool_names"], ["list_files"])
        self.assertEqual(result["repo_bridge_successful_tool_call_count"], 1)
        self.assertTrue(result["provider_called"])

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_repo_bridge_uses_target_repo_not_wbp_root(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        route = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        find_route_mock.return_value = route
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": "DIP target repo report."
                        }
                    }
                ]
            },
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            wbp_repo = root / "wbp"
            target_repo = root / "target"
            profile.mkdir()
            wbp_repo.mkdir()
            target_repo.mkdir()
            (wbp_repo / "AGENTS.md").write_text(
                "WBP_ONLY_CANON_MARKER\n",
                encoding="utf-8",
            )
            (target_repo / "AGENTS.md").write_text(
                "TARGET_ONLY_CANON_MARKER\n",
                encoding="utf-8",
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: изучи репо и дай отчет",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=target_repo,
                target_repo_source="active_project_root_cli_arg",
                wbp_repo_root=wbp_repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        payload_text = json.dumps(
            request_json_mock.call_args.kwargs["payload"],
            ensure_ascii=False,
        )
        result_text = json.dumps(result, ensure_ascii=False, sort_keys=True)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["active_project_root_required"])
        self.assertTrue(result["active_project_root_available"])
        self.assertEqual(
            result["active_project_root_source"],
            "active_project_root_cli_arg",
        )
        self.assertEqual(result["active_project_root_status"], "ok")
        self.assertFalse(result["active_project_root_path_recorded"])
        self.assertFalse(result["active_project_root_is_wbp_repo"])
        self.assertFalse(result["active_project_root_fallback_used"])
        self.assertFalse(result["active_project_root_legacy_target_repo_alias_used"])
        self.assertTrue(result["target_repo_required"])
        self.assertTrue(result["target_repo_available"])
        self.assertEqual(result["target_repo_source"], "active_project_root_cli_arg")
        self.assertEqual(result["target_repo_status"], "ok")
        self.assertFalse(result["target_repo_path_recorded"])
        self.assertFalse(result["target_repo_is_wbp_repo"])
        self.assertFalse(result["target_repo_fallback_used"])
        self.assertIn("TARGET_ONLY_CANON_MARKER", payload_text)
        self.assertNotIn("WBP_ONLY_CANON_MARKER", payload_text)
        self.assertNotIn(str(target_repo), result_text)
        self.assertNotIn(str(wbp_repo), result_text)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_allows_explicit_wbp_repo_target_with_proof(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        route = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        find_route_mock.return_value = route
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": "DIP self-target report."
                        }
                    }
                ]
            },
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            wbp_repo = root / "wbp"
            profile.mkdir()
            wbp_repo.mkdir()
            (wbp_repo / "README.md").write_text("self target\n", encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: изучи репо и дай отчет",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=wbp_repo,
                target_repo_source="active_project_root_cli_arg",
                wbp_repo_root=wbp_repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["active_project_root_available"])
        self.assertTrue(result["active_project_root_is_wbp_repo"])
        self.assertEqual(
            result["active_project_root_source"],
            "active_project_root_cli_arg",
        )
        self.assertFalse(result["active_project_root_fallback_used"])
        self.assertTrue(result["target_repo_available"])
        self.assertTrue(result["target_repo_is_wbp_repo"])
        self.assertEqual(result["target_repo_source"], "active_project_root_cli_arg")
        self.assertFalse(result["target_repo_fallback_used"])
        self.assertNotIn(str(wbp_repo), json.dumps(result, ensure_ascii=False))

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_missing_target_repo_fails_closed_without_provider(
        self,
        request_json_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            profile.mkdir()
            missing_target = root / "missing-target"
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: изучи репо и дай отчет",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=missing_target,
                target_repo_source="active_project_root_cli_arg",
                wbp_repo_root=root / "wbp",
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["machine_error_code"],
            WBP_DIP_TOOL_ACTIVE_PROJECT_ROOT_UNAVAILABLE,
        )
        self.assertTrue(result["active_project_root_required"])
        self.assertFalse(result["active_project_root_available"])
        self.assertEqual(
            result["active_project_root_status"],
            "active_project_root_missing",
        )
        self.assertFalse(result["active_project_root_path_recorded"])
        self.assertFalse(result["active_project_root_fallback_used"])
        self.assertTrue(result["target_repo_required"])
        self.assertFalse(result["target_repo_available"])
        self.assertEqual(result["target_repo_status"], "target_repo_missing")
        self.assertFalse(result["target_repo_path_recorded"])
        self.assertFalse(result["target_repo_fallback_used"])
        self.assertFalse(result["provider_called"])
        request_json_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_missing_active_project_root_fails_closed_without_provider(
        self,
        request_json_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            profile.mkdir()
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: изучи репо и дай отчет",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=None,
                target_repo_source="missing",
                wbp_repo_root=root / "wbp",
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["machine_error_code"],
            WBP_DIP_TOOL_ACTIVE_PROJECT_ROOT_UNAVAILABLE,
        )
        self.assertTrue(result["active_project_root_required"])
        self.assertFalse(result["active_project_root_available"])
        self.assertEqual(result["active_project_root_source"], "missing")
        self.assertEqual(
            result["active_project_root_status"],
            "active_project_root_missing",
        )
        self.assertFalse(result["active_project_root_path_recorded"])
        self.assertEqual(result["active_project_root_sha256"], "")
        self.assertFalse(result["active_project_root_fallback_used"])
        self.assertTrue(result["target_repo_required"])
        self.assertFalse(result["target_repo_available"])
        self.assertEqual(result["target_repo_status"], "target_repo_missing")
        self.assertFalse(result["provider_called"])
        request_json_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_forbidden_active_project_root_fails_closed_without_provider(
        self,
        request_json_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            profile.mkdir()
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: изучи репо и дай отчет",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=Path("/"),
                target_repo_source="active_project_root_cli_arg",
                wbp_repo_root=root / "wbp",
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["machine_error_code"],
            WBP_DIP_TOOL_ACTIVE_PROJECT_ROOT_UNAVAILABLE,
        )
        self.assertTrue(result["active_project_root_required"])
        self.assertFalse(result["active_project_root_available"])
        self.assertEqual(
            result["active_project_root_status"],
            "active_project_root_blocked_system_dir",
        )
        self.assertFalse(result["active_project_root_path_recorded"])
        self.assertFalse(result["active_project_root_fallback_used"])
        self.assertTrue(result["target_repo_required"])
        self.assertFalse(result["target_repo_available"])
        self.assertEqual(result["target_repo_status"], "target_repo_blocked_system_dir")
        self.assertFalse(result["provider_called"])
        request_json_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_non_git_target_repo_allows_read_and_reports_git_error(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        route = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        find_route_mock.return_value = route
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {"wbp_repo_tool_call": {"tool": "git_status"}}
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=14,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": "DIP report used available non-git evidence."
                            }
                        }
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            target_repo = root / "plain"
            profile.mkdir()
            target_repo.mkdir()
            (target_repo / "README.md").write_text("plain target\n", encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: изучи репо и дай отчет",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=target_repo,
                target_repo_source="active_project_root_cli_arg",
                wbp_repo_root=root / "wbp",
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["target_repo_git_available"])
        self.assertTrue(result["dip_repo_tool_bridge_used"])
        self.assertEqual(result["repo_bridge_tool_names"], ["list_files", "git_status"])
        self.assertEqual(result["repo_bridge_successful_tool_call_count"], 1)
        self.assertEqual(result["dip_evidence_trace"][1]["tool"], "git_status")
        self.assertEqual(
            result["dip_evidence_trace"][1]["machine_error_code"],
            "git_status_failed",
        )
        self.assertEqual(request_json_mock.call_count, 2)

    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_repo_bridge_uses_http_bridge_before_direct_provider(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
    ) -> None:
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "output_text": json.dumps(
                        {
                            "wbp_repo_tool_call": {
                                "tool": "read_file",
                                "path": "AGENTS.md",
                            }
                        }
                    )
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={"output_text": "DIP report came through WBP HTTP bridge."},
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "AGENTS.md").write_text(
                "Custom Codex agents must read runtime context.\n",
                encoding="utf-8",
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                        "deepseek_live_format_check_bridge": {
                            "enabled": True,
                            "method": "POST",
                            "model": "route-ok",
                            "response_text_field": "output_text",
                            "url_candidates": ["http://127.0.0.1:50555/v1/responses"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: изучи репо и дай отчет",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(result["source"], "runtime_context_http_bridge")
        self.assertTrue(result["bridge_attempted"])
        self.assertTrue(result["runtime_context_bridge_used"])
        self.assertTrue(result["bridge_or_file_bridge_used"])
        self.assertFalse(result["direct_provider_auth_proven"])
        self.assertFalse(result["direct_provider_response_observed"])
        self.assertEqual(result["result_text"], "DIP report came through WBP HTTP bridge.")
        self.assertEqual(result["repo_bridge_tool_call_count"], 2)
        self.assertEqual(result["repo_bridge_successful_tool_call_count"], 2)
        self.assertTrue(result["dip_repo_tool_bridge_used"])
        self.assertEqual(request_json_mock.call_count, 2)
        find_route_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_bootstraps_repo_claim_without_provider_tool_use(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": "DIP claims a repo report without using tools."
                        }
                    }
                ]
            },
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "AGENTS.md").write_text("canon\n", encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: изучи репо и дай отчет",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertTrue(result["result_available"])
        self.assertTrue(result["provider_called"])
        self.assertTrue(result["dip_repo_tool_bridge_required"])
        self.assertTrue(result["dip_repo_tool_bridge_available"])
        self.assertTrue(result["dip_repo_tool_bridge_used"])
        self.assertTrue(result["repo_bridge_bootstrap_used"])
        self.assertEqual(result["repo_bridge_bootstrap_tool_call_count"], 1)
        self.assertEqual(result["repo_bridge_tool_call_count"], 1)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_forces_final_answer_when_tool_budget_exhausts(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        tool_call_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "wbp_repo_tool_call": {
                                    "tool": "read_file",
                                    "path": "AGENTS.md",
                                }
                            }
                        )
                    }
                }
            ]
        }
        final_payload = {
            "choices": [
                {
                    "message": {
                        "content": "Final DIP report from bounded repo evidence."
                    }
                }
            ]
        }
        request_json_mock.side_effect = [
            SimpleNamespace(status_code=200, latency_ms=10, payload=tool_call_payload)
            for _ in range(9)
        ] + [SimpleNamespace(status_code=200, latency_ms=11, payload=final_payload)]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "AGENTS.md").write_text("canon\n", encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: изучи репо и дай полный отчет",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(result["result_text"], "Final DIP report from bounded repo evidence.")
        self.assertEqual(request_json_mock.call_count, 10)
        self.assertTrue(result["dip_repo_tool_bridge_used"])
        self.assertGreaterEqual(result["repo_bridge_successful_tool_call_count"], 1)
        final_prompt = request_json_mock.call_args.kwargs["payload"]["messages"][-1]["content"]
        self.assertIn("WBP FINAL ANSWER GATE", final_prompt)

    @mock.patch("wild_boar_proxy.wbp_dip_tool.time.monotonic")
    @mock.patch("wild_boar_proxy.wbp_dip_tool._live_result_turn")
    def test_request_live_result_enforces_overall_deadline_across_repo_bridge_steps(
        self,
        live_result_turn_mock: mock.Mock,
        monotonic_mock: mock.Mock,
    ) -> None:
        ticks = iter([0.0, 0.1, 0.2, 1.2, 1.2])
        monotonic_mock.side_effect = lambda: next(ticks, 1.2)
        live_result_turn_mock.return_value = {
            "status": "ok",
            "machine_error_code": WBP_DIP_TOOL_OK,
            "provider_called": True,
            "result_available": True,
            "result_text": json.dumps(
                {"wbp_repo_tool_call": {"tool": "read_file", "path": "AGENTS.md"}}
            ),
            "result_text_sha256": "sha",
            "result_text_length": 72,
            "result_text_truncated": False,
            "fallback_used": False,
            "local_imitation_used": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "AGENTS.md").write_text("canon\n", encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: через repo bridge read-only изучи AGENTS.md",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=1.0,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_LIVE_RESULT_TIMEOUT)
        self.assertTrue(result["provider_called"])
        self.assertEqual(live_result_turn_mock.call_count, 1)
        self.assertEqual(result["repo_bridge_tool_call_count"], 1)
        self.assertEqual(result["repo_bridge_successful_tool_call_count"], 1)
        self.assertEqual(result["repo_bridge_tool_names"], ["read_file"])

    @mock.patch("wild_boar_proxy.wbp_dip_tool.time.monotonic")
    @mock.patch("wild_boar_proxy.wbp_dip_tool._live_result_turn")
    def test_request_live_result_timeout_after_failed_verification_reports_code_failure(
        self,
        live_result_turn_mock: mock.Mock,
        monotonic_mock: mock.Mock,
    ) -> None:
        ticks = iter([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 301.0])
        monotonic_mock.side_effect = lambda: next(ticks, 301.0)

        def tool_turn(call: dict[str, object]) -> dict[str, object]:
            return {
                "status": "ok",
                "machine_error_code": WBP_DIP_TOOL_OK,
                "provider_called": True,
                "result_available": True,
                "result_text": json.dumps({"wbp_repo_tool_call": call}),
                "result_text_sha256": "sha",
                "result_text_length": 80,
                "result_text_truncated": False,
                "fallback_used": False,
                "local_imitation_used": False,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
            }

        live_result_turn_mock.side_effect = [
            tool_turn(
                {
                    "tool": "write_file",
                    "path": "tmp/demo.py",
                    "text": "VALUE = 'bad'\n",
                }
            ),
            tool_turn(
                {
                    "tool": "run_command",
                    "args": ["python3", "-m", "py_compile", "tmp/missing.py"],
                }
            ),
            tool_turn(
                {
                    "tool": "write_file",
                    "path": "tmp/demo.py",
                    "text": "VALUE = 'repair-attempted'\n",
                }
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: создай код в tmp/demo.py и проверь его",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=1.0,
            )
            changed_text = (repo / "tmp" / "demo.py").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["machine_error_code"],
            WBP_DIP_TOOL_CODE_VERIFICATION_FAILED,
        )
        self.assertEqual(
            result["live_result_timeout_machine_error_code"],
            WBP_DIP_TOOL_LIVE_RESULT_TIMEOUT,
        )
        self.assertTrue(result["live_result_timeout_before_code_verification_closed"])
        self.assertEqual(changed_text, "VALUE = 'bad'\n")
        self.assertTrue(result["dip_code_written"])
        self.assertFalse(result["dip_code_verified"])
        self.assertTrue(result["dip_code_verification_failed"])
        self.assertEqual(result["repo_bridge_tool_call_count"], 3)
        self.assertEqual(result["dip_action_successful_tool_call_count"], 1)
        self.assertEqual(live_result_turn_mock.call_count, 3)

    def test_repo_bridge_timeout_after_repair_without_verification_reports_not_run(
        self,
    ) -> None:
        repo_fields = {
            "dip_code_mutation_required": True,
            "dip_code_written": True,
            "dip_code_verified": False,
            "dip_code_verification_failed": False,
        }

        packet = _repo_bridge_timeout_packet(
            {"schema_version": 1},
            provider_called=True,
            repo_fields=repo_fields,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            WBP_DIP_TOOL_CODE_VERIFICATION_NOT_RUN,
        )
        self.assertEqual(
            packet["live_result_timeout_machine_error_code"],
            WBP_DIP_TOOL_LIVE_RESULT_TIMEOUT,
        )
        self.assertTrue(packet["live_result_timeout_before_code_verification_closed"])

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_fails_closed_when_final_answer_is_still_tool_call(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        tool_call_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "wbp_repo_tool_call": {
                                    "tool": "read_file",
                                    "path": "AGENTS.md",
                                }
                            }
                        )
                    }
                }
            ]
        }
        request_json_mock.side_effect = [
            SimpleNamespace(status_code=200, latency_ms=10, payload=tool_call_payload)
            for _ in range(10)
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "AGENTS.md").write_text("canon\n", encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: изучи репо и дай полный отчет",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["machine_error_code"],
            WBP_DIP_TOOL_REPO_BRIDGE_FINAL_ANSWER_MISSING,
        )
        self.assertFalse(result["result_available"])
        self.assertEqual(result["result_text"], "")
        self.assertTrue(result["dip_repo_tool_bridge_used"])

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_action_bridge_applies_patch_and_runs_tests(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        patch_text = """diff --git a/demo.py b/demo.py
--- a/demo.py
+++ b/demo.py
@@ -1 +1 @@
-VALUE = "bad"
+VALUE = "good"
"""
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "apply_patch",
                                            "patch": patch_text,
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "run_tests",
                                            "args": [
                                                "python3",
                                                "-m",
                                                "py_compile",
                                                "demo.py",
                                            ],
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=13,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": "Fixed demo.py and verified py_compile."
                            }
                        }
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "demo.py").write_text('VALUE = "bad"\n', encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: почини demo.py и запусти тест",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )
            changed_text = (repo / "demo.py").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(changed_text, 'VALUE = "good"\n')
        self.assertTrue(result["dip_action_bridge_required"])
        self.assertTrue(result["dip_action_bridge_used"])
        self.assertEqual(result["dip_action_tool_call_count"], 2)
        self.assertEqual(result["dip_action_successful_tool_call_count"], 2)
        self.assertTrue(result["dip_action_mutation_applied"])
        self.assertTrue(result["dip_action_patch_applied"])
        self.assertTrue(result["dip_code_mutation_required"])
        self.assertTrue(result["dip_code_written"])
        self.assertTrue(result["dip_code_patch_applied"])
        self.assertTrue(result["dip_code_verification_required"])
        self.assertTrue(result["dip_code_verified"])
        self.assertTrue(result["dip_action_tests_run"])
        self.assertFalse(result["repo_bridge_readonly"])
        self.assertTrue(result["repo_bridge_mutation_controlled"])
        self.assertFalse(result["repo_bridge_direct_shell_access"])
        self.assertEqual(result["dip_action_mutated_files"], ["demo.py"])
        self.assertFalse(result["dip_action_raw_patch_recorded"])
        self.assertFalse(result["dip_action_raw_command_recorded"])
        self.assertTrue(result["dip_evidence_trace_available"])
        self.assertTrue(result["dip_evidence_trace_recorded"])
        self.assertEqual(result["dip_evidence_trace_count"], 3)
        self.assertEqual(
            [entry["tool"] for entry in result["dip_evidence_trace"]],
            ["read_file", "apply_patch", "run_tests"],
        )
        self.assertTrue(result["dip_evidence_trace"][1]["mutation_applied"])
        self.assertFalse(result["dip_evidence_trace"][1]["patch_recorded"])
        self.assertFalse(result["dip_evidence_trace"][2]["command_recorded"])
        self.assertEqual(request_json_mock.call_count, 3)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_repairs_failed_code_verification_then_passes(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        patch_text = """diff --git a/demo.py b/demo.py
--- a/demo.py
+++ b/demo.py
@@ -1 +1,2 @@
-VALUE = "bad"
+VALUE = "actual"
+EXTRA = "syntax ok"
"""
        repair_patch_text = """diff --git a/demo.py b/demo.py
--- a/demo.py
+++ b/demo.py
@@ -1,2 +1 @@
-VALUE = "actual"
-EXTRA = "syntax ok"
+VALUE = "expected"
"""
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "apply_patch",
                                            "patch": patch_text,
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "run_tests",
                                            "args": [
                                                "python3",
                                                "-m",
                                                "pytest",
                                                "tests/test_demo.py",
                                                "-q",
                                            ],
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=13,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "apply_patch",
                                            "patch": repair_patch_text,
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=14,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "run_tests",
                                            "args": [
                                                "python3",
                                                "-m",
                                                "pytest",
                                                "tests/test_demo.py",
                                                "-q",
                                            ],
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=15,
                payload={
                    "choices": [
                        {"message": {"content": "Fixed demo.py after retrying tests."}}
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "demo.py").write_text('VALUE = "bad"\n', encoding="utf-8")
            tests_dir = repo / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_demo.py").write_text(
                "import demo\n\n"
                "def test_value():\n"
                "    assert demo.VALUE == 'expected'\n",
                encoding="utf-8",
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: почини demo.py и запусти тест",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )
            changed_text = (repo / "demo.py").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(changed_text, 'VALUE = "expected"\n')
        self.assertTrue(result["provider_called"])
        self.assertTrue(result["result_available"])
        self.assertTrue(result["dip_action_bridge_used"])
        self.assertTrue(result["dip_action_patch_applied"])
        self.assertTrue(result["dip_action_tests_run"])
        self.assertTrue(result["dip_code_written"])
        self.assertTrue(result["dip_code_verified"])
        self.assertFalse(result["dip_code_verification_failed"])
        self.assertEqual(result["dip_code_failed_verification_count"], 0)
        self.assertEqual(
            [entry["tool"] for entry in result["dip_evidence_trace"]],
            ["read_file", "apply_patch", "run_tests", "apply_patch", "run_tests"],
        )
        self.assertEqual(
            [entry["status"] for entry in result["dip_evidence_trace"]],
            ["ok", "ok", "error", "ok", "ok"],
        )
        self.assertEqual(request_json_mock.call_count, 5)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_synthesizes_exact_plain_after_verified_code(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        patch_text = """diff --git a/demo.py b/demo.py
--- a/demo.py
+++ b/demo.py
@@ -1 +1 @@
-VALUE = "bad"
+VALUE = "expected"
"""
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "apply_patch",
                                            "patch": patch_text,
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "run_tests",
                                            "args": [
                                                "python3",
                                                "-m",
                                                "pytest",
                                                "tests/test_demo.py",
                                                "-q",
                                            ],
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "demo.py").write_text('VALUE = "bad"\n', encoding="utf-8")
            tests_dir = repo / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_demo.py").write_text(
                "import demo\n\n"
                "def test_value():\n"
                "    assert demo.VALUE == 'expected'\n",
                encoding="utf-8",
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: почини demo.py, запусти python3 -m pytest "
                    "tests/test_demo.py -q, и ответь ровно WBP_CODE_EXACT_OK"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(result["result_text"], "WBP_CODE_EXACT_OK")
        self.assertTrue(result["repo_bridge_final_answer_synthesized"])
        self.assertTrue(result["dip_code_verified"])
        self.assertEqual(request_json_mock.call_count, 2)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_synthesizes_verified_json_answer(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        patch_text = """diff --git a/tmp/wbp-json-synth/math_box.py b/tmp/wbp-json-synth/math_box.py
new file mode 100644
index 0000000..7ec8f90
--- /dev/null
+++ b/tmp/wbp-json-synth/math_box.py
@@ -0,0 +1,2 @@
+def inc(x):
+    return x + 1
diff --git a/tmp/wbp-json-synth/test_math_box.py b/tmp/wbp-json-synth/test_math_box.py
new file mode 100644
index 0000000..89c82ad
--- /dev/null
+++ b/tmp/wbp-json-synth/test_math_box.py
@@ -0,0 +1,10 @@
+import os
+import sys
+sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
+from math_box import inc
+
+def test_inc_positive():
+    assert inc(1) == 2
+
+def test_inc_negative():
+    assert inc(-2) == -1
"""
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "apply_patch",
                                            "patch": patch_text,
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "run_tests",
                                            "args": [
                                                "python3",
                                                "-m",
                                                "pytest",
                                                "tmp/wbp-json-synth/test_math_box.py",
                                                "-q",
                                            ],
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: Create tmp/wbp-json-synth/math_box.py and "
                    "tmp/wbp-json-synth/test_math_box.py with at least 2 "
                    "pytest cases. Run python3 -m pytest "
                    "tmp/wbp-json-synth/test_math_box.py -q. Return exactly "
                    "JSON with fields status, marker, changed_files, "
                    "passed_count, command_used; marker must be WBP_SYNTH_OK."
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )

        payload = json.loads(result["result_text"])
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["repo_bridge_final_answer_synthesized"])
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["marker"], "WBP_SYNTH_OK")
        self.assertEqual(payload["passed_count"], 2)
        self.assertEqual(
            sorted(payload["changed_files"]),
            [
                "tmp/wbp-json-synth/math_box.py",
                "tmp/wbp-json-synth/test_math_box.py",
            ],
        )
        self.assertEqual(
            payload["command_used"],
            "python3 -m pytest tmp/wbp-json-synth/test_math_box.py -q",
        )
        self.assertEqual(request_json_mock.call_count, 2)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_repairs_missing_action_then_applies_patch(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        patch_text = """diff --git a/demo.py b/demo.py
--- a/demo.py
+++ b/demo.py
@@ -1 +1 @@
-VALUE = "bad"
+VALUE = "good"
"""
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=10,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": "I can fix it, but I forgot to call a tool."
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "apply_patch",
                                            "patch": patch_text,
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "run_tests",
                                            "args": [
                                                "python3",
                                                "-m",
                                                "py_compile",
                                                "demo.py",
                                            ],
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=13,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": "Fixed demo.py after the required action gate."
                            }
                        }
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "demo.py").write_text('VALUE = "bad"\n', encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: почини demo.py и запусти тест",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )
            changed_text = (repo / "demo.py").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(changed_text, 'VALUE = "good"\n')
        self.assertTrue(result["repo_bridge_bootstrap_used"])
        self.assertTrue(result["dip_action_patch_applied"])
        self.assertTrue(result["dip_action_tests_run"])
        self.assertTrue(result["dip_code_written"])
        self.assertTrue(result["dip_code_verified"])
        self.assertEqual(request_json_mock.call_count, 4)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_blocks_fix_task_without_action_tool(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        read_response = SimpleNamespace(
            status_code=200,
            latency_ms=11,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "wbp_repo_tool_call": {
                                        "tool": "read_file",
                                        "path": "demo.py",
                                    }
                                }
                            )
                        }
                    }
                ]
            },
        )
        no_action_response = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": "I inspected but did not patch anything."
                        }
                    }
                ]
            },
        )
        request_json_mock.side_effect = [read_response] + [no_action_response] * 10
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "demo.py").write_text('VALUE = "bad"\n', encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: почини demo.py",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_ACTION_BRIDGE_NOT_USED)
        self.assertTrue(result["dip_repo_tool_bridge_used"])
        self.assertTrue(result["dip_action_bridge_required"])
        self.assertFalse(result["dip_action_bridge_used"])
        self.assertEqual(result["dip_action_successful_tool_call_count"], 0)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_run_command_does_not_imply_code_mutation(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "run_command",
                                            "args": ["git", "status"],
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": "Command ran and no files were edited."
                            }
                        }
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "demo.py").write_text('VALUE = "ok"\n', encoding="utf-8")
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: run command git status. Do not edit files.",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertTrue(result["dip_action_bridge_required"])
        self.assertTrue(result["dip_action_bridge_used"])
        self.assertTrue(result["dip_action_commands_run"])
        self.assertFalse(result["dip_code_mutation_required"])
        self.assertFalse(result["dip_code_written"])
        self.assertFalse(result["dip_code_verification_required"])

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_explicit_pytest_runs_as_bootstrap_action(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=11,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "status": "ok",
                                    "passed_count": 1,
                                    "subtests_count": 0,
                                    "command_used": "python3 -m pytest tests/test_bootstrap_probe.py -q",
                                },
                                separators=(",", ":"),
                            )
                        }
                    }
                ]
            },
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            tests_dir = repo / "tests"
            profile.mkdir()
            tests_dir.mkdir(parents=True)
            (tests_dir / "test_bootstrap_probe.py").write_text(
                "def test_bootstrap_probe():\n    assert 2 + 3 == 5\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge read-only запусти python3 -m pytest "
                    "tests/test_bootstrap_probe.py -q и ответь ровно JSON с полями "
                    "status, passed_count, subtests_count, command_used"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertTrue(result["dip_action_bridge_required"])
        self.assertTrue(result["dip_action_bridge_used"])
        self.assertTrue(result["dip_action_tests_run"])
        self.assertEqual(result["repo_bridge_tool_names"], ["run_tests"])
        self.assertEqual(result["dip_action_tool_names"], ["run_tests"])
        self.assertFalse(result["repo_bridge_mutation_allowed"])
        self.assertTrue(result["repo_bridge_readonly"])
        self.assertEqual(request_json_mock.call_count, 1)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_explicit_make_custom_stability_runs_as_bootstrap_action(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=11,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "status": "ok",
                                    "passed_count": 1,
                                    "subtests_count": 0,
                                    "command_used": "make test-custom-stability",
                                },
                                separators=(",", ":"),
                            )
                        }
                    }
                ]
            },
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "Makefile").write_text(
                "test-custom-stability:\n\t@true\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge read-only запусти make test-custom-stability "
                    "и ответь ровно JSON с полями status, passed_count, subtests_count, "
                    "command_used"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertTrue(result["dip_action_bridge_required"])
        self.assertTrue(result["dip_action_bridge_used"])
        self.assertTrue(result["dip_action_tests_run"])
        self.assertEqual(result["repo_bridge_tool_names"], ["run_tests"])
        self.assertEqual(result["dip_action_tool_names"], ["run_tests"])
        self.assertFalse(result["repo_bridge_mutation_allowed"])
        self.assertTrue(result["repo_bridge_readonly"])
        self.assertEqual(request_json_mock.call_count, 1)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._listener_auth_smoke")
    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_auth_listener_prompt_uses_smoke_tool(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
        listener_auth_smoke_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        listener_auth_smoke_mock.return_value = {
            "status": "ok",
            "machine_error_code": "OK",
            "result_text": json.dumps(
                {
                    "auth_command_ok": True,
                    "listener_status": 200,
                    "token_printed": False,
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            "command_exit_code": 0,
            "command_sha256": "listener-smoke-sha",
            "command_recorded": False,
        }
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=11,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "auth_command_ok": True,
                                    "listener_status": 200,
                                    "token_printed": False,
                                },
                                separators=(",", ":"),
                            )
                        }
                    }
                ]
            },
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge read-only проверь, что профильный "
                    "auth command дает непустой token, token не печатай, затем "
                    "проверь http://127.0.0.1:8318/v1/models с этим token"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["dip_action_bridge_required"])
        self.assertTrue(result["dip_action_bridge_used"])
        self.assertEqual(result["repo_bridge_tool_names"], ["listener_auth_smoke"])
        self.assertEqual(result["dip_action_tool_names"], ["listener_auth_smoke"])
        self.assertFalse(result["repo_bridge_mutation_allowed"])
        self.assertTrue(result["repo_bridge_readonly"])
        listener_auth_smoke_mock.assert_called_once()

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.subprocess.run")
    def test_listener_auth_smoke_includes_model_pool_without_token(
        self,
        subprocess_run_mock: mock.Mock,
        request_json_mock: mock.Mock,
    ) -> None:
        subprocess_run_mock.return_value = SimpleNamespace(
            returncode=0,
            stdout="owner-token\n",
        )
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            payload={
                "data": [
                    {"id": "gpt-5.5"},
                    {"id": "gpt-5.4-mini"},
                    {"id": "gpt-image-2"},
                ]
            },
        )

        result = _listener_auth_smoke(Path("/repo"), {})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        payload = json.loads(result["result_text"])
        self.assertTrue(payload["auth_command_ok"])
        self.assertEqual(payload["listener_status"], 200)
        self.assertEqual(payload["models_count"], 3)
        self.assertEqual(
            payload["model_ids"],
            ["gpt-5.5", "gpt-5.4-mini", "gpt-image-2"],
        )
        self.assertFalse(payload["token_printed"])
        self.assertFalse(packet_contains_text(result, "owner-token"))

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.subprocess.run")
    def test_listener_model_matrix_smoke_checks_each_model_without_token(
        self,
        subprocess_run_mock: mock.Mock,
        request_json_mock: mock.Mock,
    ) -> None:
        subprocess_run_mock.return_value = SimpleNamespace(
            returncode=0,
            stdout="owner-token\n",
        )
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                payload={
                    "data": [
                        {"id": "gpt-5.5"},
                        {"id": "gpt-5.4-mini"},
                        {"id": "gpt-image-2"},
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                payload={
                    "output": [
                        {
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "WBP_MODEL_MATRIX_OK_1",
                                }
                            ]
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                payload={"output_text": "WBP_MODEL_MATRIX_OK_2"},
            ),
        ]

        result = _listener_model_matrix_smoke(Path("/repo"), {})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        payload = json.loads(result["result_text"])
        self.assertEqual(payload["models_count"], 3)
        self.assertEqual(payload["responses_checked_count"], 2)
        self.assertEqual(payload["responses_passed_count"], 2)
        self.assertEqual(payload["responses_failed_count"], 0)
        self.assertEqual(payload["responses_skipped_count"], 1)
        self.assertEqual(payload["skipped_model_ids"], ["gpt-image-2"])
        self.assertFalse(payload["all_models_response_smoke_passed"])
        self.assertTrue(payload["all_text_response_smoke_passed"])
        self.assertFalse(payload["token_printed"])
        self.assertFalse(payload["response_texts_recorded"])
        self.assertFalse(packet_contains_text(result, "owner-token"))

    @mock.patch("wild_boar_proxy.wbp_dip_tool._listener_model_matrix_smoke")
    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_model_matrix_prompt_uses_smoke_tool(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
        matrix_smoke_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        matrix_payload = {
            "all_models_response_smoke_passed": True,
            "auth_command_ok": True,
            "listener_status": 200,
            "model_ids": ["gpt-5.5"],
            "models_count": 1,
            "responses_checked_count": 1,
            "responses_failed_count": 0,
            "responses_passed_count": 1,
            "response_texts_recorded": False,
            "token_printed": False,
        }
        matrix_smoke_mock.return_value = {
            "status": "ok",
            "machine_error_code": "OK",
            "result_text": json.dumps(
                matrix_payload,
                separators=(",", ":"),
                sort_keys=True,
            ),
            "command_exit_code": 0,
            "command_sha256": "matrix-smoke-sha",
            "command_recorded": False,
        }
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=11,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                matrix_payload,
                                separators=(",", ":"),
                            )
                        }
                    }
                ]
            },
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge read-only проверь полный пул "
                    "моделей через /v1/models и /v1/responses"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["repo_bridge_tool_names"], ["listener_model_matrix_smoke"])
        self.assertEqual(result["dip_action_tool_names"], ["listener_model_matrix_smoke"])
        self.assertFalse(result["repo_bridge_mutation_allowed"])
        self.assertTrue(result["repo_bridge_readonly"])
        matrix_smoke_mock.assert_called_once()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._runtime_healthcheck_smoke")
    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_healthcheck_prompt_uses_owner_smoke_tool(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
        runtime_healthcheck_smoke_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        runtime_healthcheck_smoke_mock.return_value = {
            "status": "ok",
            "machine_error_code": "OK",
            "result_text": json.dumps(
                {
                    "status": "ok",
                    "machine_error_code": "OK",
                    "liveness": "healthy",
                    "launch_readiness_status": "ready",
                    "gate_passed": True,
                    "endpoint": "http://127.0.0.1:8318/v1",
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            "command_exit_code": 0,
            "command_sha256": "healthcheck-smoke-sha",
            "command_recorded": False,
        }
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=11,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "status": "ok",
                                    "machine_error_code": "OK",
                                    "liveness": "healthy",
                                    "launch_readiness_status": "ready",
                                    "gate_passed": True,
                                    "endpoint": "http://127.0.0.1:8318/v1",
                                },
                                separators=(",", ":"),
                            )
                        }
                    }
                ]
            },
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge read-only выполни python3 -m "
                    "wild_boar_proxy healthcheck --json и ответь JSON с полями "
                    "status, machine_error_code, liveness, "
                    "launch_readiness_status, gate_passed, endpoint"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["dip_action_bridge_required"])
        self.assertTrue(result["dip_action_bridge_used"])
        self.assertEqual(result["repo_bridge_tool_names"], ["runtime_healthcheck_smoke"])
        self.assertEqual(result["dip_action_tool_names"], ["runtime_healthcheck_smoke"])
        self.assertFalse(result["repo_bridge_mutation_allowed"])
        self.assertTrue(result["repo_bridge_readonly"])
        runtime_healthcheck_smoke_mock.assert_called_once()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._runtime_healthcheck_smoke")
    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_healthcheck_bootstrap_blocks_extra_tool_call(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
        runtime_healthcheck_smoke_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        health_json = {
            "status": "ok",
            "machine_error_code": "OK",
            "liveness": "healthy",
            "launch_readiness_status": "ready",
            "gate_passed": True,
            "endpoint": "http://127.0.0.1:8318/v1",
        }
        runtime_healthcheck_smoke_mock.return_value = {
            "status": "ok",
            "machine_error_code": "OK",
            "result_text": json.dumps(
                health_json,
                separators=(",", ":"),
                sort_keys=True,
            ),
            "command_exit_code": 0,
            "command_sha256": "healthcheck-smoke-sha",
            "command_recorded": False,
        }
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "run_command",
                                            "args": ["git", "status"],
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    health_json,
                                    separators=(",", ":"),
                                )
                            }
                        }
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge read-only выполни python3 -m "
                    "wild_boar_proxy healthcheck --json и ответь JSON с полями "
                    "status, machine_error_code, liveness, "
                    "launch_readiness_status, gate_passed, endpoint"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(json.loads(result["result_text"]), health_json)
        self.assertEqual(result["repo_bridge_tool_names"], ["runtime_healthcheck_smoke"])
        self.assertEqual(result["dip_action_tool_names"], ["runtime_healthcheck_smoke"])
        self.assertEqual(result["dip_action_tool_call_count"], 1)
        self.assertEqual(result["dip_action_successful_tool_call_count"], 1)
        self.assertFalse(result["dip_action_commands_run"])
        self.assertTrue(result["repo_bridge_readonly"])
        self.assertEqual(request_json_mock.call_count, 2)
        runtime_healthcheck_smoke_mock.assert_called_once()

    @mock.patch("wild_boar_proxy.wbp_dip_tool.subprocess.run")
    def test_runtime_healthcheck_smoke_treats_degraded_json_as_tool_success(
        self,
        run_mock: mock.Mock,
    ) -> None:
        run_mock.return_value = SimpleNamespace(
            returncode=1,
            stdout=json.dumps(
                {
                    "status": "error",
                    "machine_error_code": "ATTESTATION_FAILED",
                    "liveness": "degraded",
                    "endpoint": "http://127.0.0.1:8318/v1",
                    "launch_readiness": {
                        "status": "blocked",
                        "gate_passed": False,
                    },
                }
            ),
        )

        result = _runtime_healthcheck_smoke(Path("/repo"), {})
        result_json = json.loads(result["result_text"])

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        self.assertEqual(result["command_exit_code"], 1)
        self.assertEqual(result_json["status"], "error")
        self.assertEqual(result_json["machine_error_code"], "ATTESTATION_FAILED")
        self.assertEqual(result_json["liveness"], "degraded")
        self.assertEqual(result_json["launch_readiness_status"], "blocked")
        self.assertIs(result_json["gate_passed"], False)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_file_mutation_uses_readback_not_code_verify(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        target_path = "tmp/wbp-custom-strong/mutation-a.txt"
        patch_text = (
            "diff --git a/tmp/wbp-custom-strong/mutation-a.txt b/tmp/wbp-custom-strong/mutation-a.txt\n"
            "new file mode 100644\n"
            "index 0000000..e69de29\n"
            "--- /dev/null\n"
            "+++ b/tmp/wbp-custom-strong/mutation-a.txt\n"
            "@@ -0,0 +1 @@\n"
            "+WBP_CUSTOM_STRONG_MUTATION_OK\n"
        )
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "apply_patch",
                                            "patch": patch_text,
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": "Created the requested file."
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=13,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "read_file",
                                            "path": target_path,
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=14,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "status": "ok",
                                        "changed_files": [target_path],
                                        "readback_ok": True,
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge создай файл "
                    f"{target_path} с текстом WBP_CUSTOM_STRONG_MUTATION_OK, "
                    "затем прочитай его обратно"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )
            changed_text = (repo / target_path).read_text(encoding="utf-8")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(changed_text, "WBP_CUSTOM_STRONG_MUTATION_OK")
        self.assertTrue(result["dip_action_bridge_required"])
        self.assertTrue(result["dip_action_bridge_used"])
        self.assertTrue(result["dip_mutation_required"])
        self.assertTrue(result["dip_mutation_written"])
        self.assertTrue(result["dip_mutation_verified"])
        self.assertTrue(result["dip_mutation_readback_verified"])
        self.assertFalse(result["dip_code_mutation_required"])
        self.assertFalse(result["dip_code_verification_required"])
        self.assertFalse(result["dip_code_verified"])
        self.assertEqual(result["dip_action_mutated_files"], [target_path])
        self.assertEqual(result["source"], "repo_bridge_verified_evidence")
        self.assertEqual(result["result_text"], "WBP_CUSTOM_STRONG_MUTATION_OK")
        self.assertEqual(
            [entry["tool"] for entry in result["dip_evidence_trace"]],
            ["write_file", "read_file"],
        )
        request_json_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_file_mutation_preserves_verified_exact_json_reply(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        target_path = "tmp/wbp-custom-strong/request-bound.txt"
        expected_reply = json.dumps(
            {
                "request_id": "req-exact-json",
                "status": "success",
                "changed_files": [target_path],
                "readback_ok": True,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge создай файл "
                    f"{target_path} с текстом WBP_CUSTOM_STRONG_MUTATION_OK, "
                    "затем прочитай его обратно, и ответь ровно JSON: "
                    f"{expected_reply}"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )
            changed_text = (repo / target_path).read_text(encoding="utf-8")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(changed_text, "WBP_CUSTOM_STRONG_MUTATION_OK")
        self.assertTrue(result["dip_mutation_readback_verified"])
        self.assertEqual(result["result_text"], expected_reply)
        self.assertEqual(result["result_text_sha256"], _sha256_text(expected_reply))
        self.assertTrue(result["repo_bridge_final_answer_synthesized"])
        request_json_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_file_mutation_preserves_verified_exact_plain_reply(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        target_path = "tmp/wbp-custom-strong/request-bound-plain.txt"
        expected_reply = "WBP_MUTATION_BOUND_OK req-plain"

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge создай файл "
                    f"{target_path} с текстом WBP_CUSTOM_STRONG_MUTATION_OK, "
                    f"затем прочитай его обратно, и ответь ровно {expected_reply}"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )
            changed_text = (repo / target_path).read_text(encoding="utf-8")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(changed_text, "WBP_CUSTOM_STRONG_MUTATION_OK")
        self.assertTrue(result["dip_mutation_readback_verified"])
        self.assertEqual(result["result_text"], expected_reply)
        self.assertEqual(result["result_text_sha256"], _sha256_text(expected_reply))
        self.assertTrue(result["repo_bridge_final_answer_synthesized"])
        request_json_mock.assert_not_called()

    def test_repo_verified_exact_json_reply_rejects_unverified_changed_files(self) -> None:
        reply = _repo_verified_json_reply_from_evidence(
            task=(
                'DIP: ответь ровно JSON: {"status":"success",'
                '"changed_files":["tmp/wrong.txt"],"readback_ok":true}'
            ),
            fields={
                "dip_code_mutation_required": False,
                "dip_mutation_required": True,
                "dip_mutation_readback_verified": True,
                "dip_action_mutated_files": ["tmp/right.txt"],
            },
            tool_results=[],
        )

        self.assertEqual(
            reply,
            '{"status":"ok","changed_files":["tmp/right.txt"],"readback_ok":true}',
        )

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_file_delete_verifies_absence_readback(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        target_path = "tmp/wbp-custom-strong/mutation-a.txt"
        patch_text = (
            "diff --git a/tmp/wbp-custom-strong/mutation-a.txt b/tmp/wbp-custom-strong/mutation-a.txt\n"
            "deleted file mode 100644\n"
            "index e69de29..0000000\n"
            "--- a/tmp/wbp-custom-strong/mutation-a.txt\n"
            "+++ /dev/null\n"
            "@@ -1 +0,0 @@\n"
            "-WBP_CUSTOM_STRONG_MUTATION_OK\n"
        )
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "apply_patch",
                                            "patch": patch_text,
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "read_file",
                                            "path": target_path,
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=13,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "status": "ok",
                                        "changed_files": [target_path],
                                        "cleanup_ok": True,
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            target_file = repo / target_path
            target_file.parent.mkdir(parents=True)
            target_file.write_text("WBP_CUSTOM_STRONG_MUTATION_OK\n", encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge удали файл "
                    f"{target_path} и ответь JSON с status, changed_files, cleanup_ok"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )
            file_exists_after = target_file.exists()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertFalse(file_exists_after)
        self.assertTrue(result["dip_action_bridge_required"])
        self.assertTrue(result["dip_action_bridge_used"])
        self.assertTrue(result["dip_mutation_required"])
        self.assertTrue(result["dip_mutation_written"])
        self.assertTrue(result["dip_mutation_verified"])
        self.assertTrue(result["dip_mutation_readback_verified"])
        self.assertEqual(result["dip_action_mutated_files"], [target_path])
        delete_entries = [
            entry
            for entry in result["dip_evidence_trace"]
            if entry["tool"] == "delete_file"
        ]
        self.assertEqual(delete_entries[0]["deleted_files"], [target_path])
        self.assertTrue(delete_entries[0]["deleted_files_absent"])
        self.assertEqual(json.loads(result["result_text"])["cleanup_ok"], True)
        request_json_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_file_delete_auto_verifies_deleted_file_absence(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        target_path = "tmp/wbp-custom-strong/mutation-a.txt"
        patch_text = (
            "diff --git a/tmp/wbp-custom-strong/mutation-a.txt b/tmp/wbp-custom-strong/mutation-a.txt\n"
            "deleted file mode 100644\n"
            "index e69de29..0000000\n"
            "--- a/tmp/wbp-custom-strong/mutation-a.txt\n"
            "+++ /dev/null\n"
            "@@ -1 +0,0 @@\n"
            "-WBP_CUSTOM_STRONG_MUTATION_OK\n"
        )
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "apply_patch",
                                            "patch": patch_text,
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "status": "ok",
                                        "changed_files": [target_path],
                                        "cleanup_ok": True,
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            target_file = repo / target_path
            target_file.parent.mkdir(parents=True)
            target_file.write_text("WBP_CUSTOM_STRONG_MUTATION_OK\n", encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge удали файл "
                    f"{target_path} и ответь JSON с status, changed_files, cleanup_ok"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )
            file_exists_after = target_file.exists()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertFalse(file_exists_after)
        self.assertTrue(result["dip_mutation_verified"])
        self.assertTrue(result["dip_mutation_readback_verified"])
        delete_entries = [
            entry
            for entry in result["dip_evidence_trace"]
            if entry["tool"] == "delete_file"
        ]
        self.assertEqual(delete_entries[0]["deleted_files"], [target_path])
        self.assertTrue(delete_entries[0]["deleted_files_absent"])
        self.assertEqual(result["dip_evidence_trace"][0]["tool"], "delete_file")

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_explicit_file_delete_runs_as_bootstrap_action(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        target_path = "tmp/wbp-custom-strong/mutation-a.txt"
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "status": "ok",
                                    "changed_files": [target_path],
                                    "cleanup_ok": True,
                                }
                            )
                        }
                    }
                ]
            },
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            target_file = repo / target_path
            target_file.parent.mkdir(parents=True)
            target_file.write_text("WBP_CUSTOM_STRONG_MUTATION_OK\n", encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge удали файл "
                    f"{target_path} и, если директория tmp/wbp-custom-strong "
                    "пустая, удали директорию тоже. Ответь JSON с status, "
                    "changed_files, cleanup_ok"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )
            file_exists_after = target_file.exists()
            parent_exists_after = target_file.parent.exists()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertFalse(file_exists_after)
        self.assertFalse(parent_exists_after)
        request_json_mock.assert_not_called()
        self.assertEqual(
            json.loads(result["result_text"]),
            {"status": "ok", "changed_files": [target_path], "cleanup_ok": True},
        )
        self.assertEqual(result["repo_bridge_bootstrap_tool_call_count"], 1)
        self.assertEqual(result["dip_action_tool_call_count"], 1)
        self.assertEqual(result["dip_action_successful_tool_call_count"], 1)
        self.assertTrue(result["dip_action_bridge_succeeded"])
        self.assertTrue(result["dip_mutation_written"])
        self.assertTrue(result["dip_mutation_verified"])
        self.assertTrue(result["dip_mutation_readback_verified"])
        self.assertFalse(result["dip_action_patch_applied"])
        self.assertFalse(result["dip_code_written"])
        self.assertFalse(result["dip_code_patch_applied"])
        self.assertEqual(result["dip_action_tool_names"], ["delete_file"])
        self.assertEqual(result["dip_action_mutated_files"], [target_path])
        self.assertEqual(
            [entry["tool"] for entry in result["dip_evidence_trace"]],
            ["delete_file"],
        )
        delete_entry = result["dip_evidence_trace"][0]
        self.assertEqual(delete_entry["origin"], "wbp_bootstrap")
        self.assertEqual(delete_entry["path"], target_path)
        self.assertEqual(delete_entry["deleted_files"], [target_path])
        self.assertTrue(delete_entry["deleted_files_absent"])

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_explicit_tmp_directory_delete_runs_as_bootstrap_action(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        target_path = "tmp/wbp_custom_ultrahard_app_v1"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            target_dir = repo / target_path
            (target_dir / "__pycache__").mkdir(parents=True)
            (target_dir / "text_stats.py").write_text("VALUE = 1\n", encoding="utf-8")
            (target_dir / "test_text_stats.py").write_text(
                "def test_value():\n    assert True\n",
                encoding="utf-8",
            )
            (target_dir / "__pycache__" / "artifact.pyc").write_bytes(b"cache")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge удали директорию "
                    f"{target_path} целиком вместе с файлами и __pycache__. "
                    "Затем проверь, что директории больше нет, и ответь JSON "
                    "с status, changed_files, cleanup_ok"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )
            dir_exists_after = target_dir.exists()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertFalse(dir_exists_after)
        request_json_mock.assert_not_called()
        self.assertEqual(
            json.loads(result["result_text"]),
            {"status": "ok", "changed_files": [target_path], "cleanup_ok": True},
        )
        self.assertEqual(result["repo_bridge_bootstrap_tool_call_count"], 1)
        self.assertEqual(result["dip_action_tool_call_count"], 1)
        self.assertEqual(result["dip_action_successful_tool_call_count"], 1)
        self.assertTrue(result["dip_action_bridge_succeeded"])
        self.assertTrue(result["dip_mutation_written"])
        self.assertTrue(result["dip_mutation_verified"])
        self.assertTrue(result["dip_mutation_readback_verified"])
        self.assertEqual(result["dip_action_tool_names"], ["delete_tree"])
        self.assertEqual(result["dip_action_mutated_files"], [target_path])
        self.assertEqual(
            [entry["tool"] for entry in result["dip_evidence_trace"]],
            ["delete_tree"],
        )
        delete_entry = result["dip_evidence_trace"][0]
        self.assertEqual(delete_entry["origin"], "wbp_bootstrap")
        self.assertEqual(delete_entry["path"], target_path)
        self.assertEqual(delete_entry["deleted_files"], [target_path])
        self.assertTrue(delete_entry["deleted_files_absent"])

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_file_delete_path_with_readonly_token_is_not_readonly(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        target_path = "tmp/wbp-custom-strong/mutation-a.txt"
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "status": "ok",
                                    "changed_files": [target_path],
                                    "cleanup_ok": True,
                                }
                            )
                        }
                    }
                ]
            },
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            target_file = repo / target_path
            target_file.parent.mkdir(parents=True)
            target_file.write_text("WBP_CUSTOM_STRONG_MUTATION_OK\n", encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge удали файл "
                    f"{target_path} и tmp/wbp-custom-strong/readonly-deny.txt "
                    "если они существуют; если директория tmp/wbp-custom-strong "
                    "пустая, удали директорию тоже. Ответь JSON с status, "
                    "changed_files, cleanup_ok"
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )
            file_exists_after = target_file.exists()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertFalse(file_exists_after)
        self.assertFalse(result["repo_bridge_readonly"])
        request_json_mock.assert_not_called()
        self.assertEqual(result["dip_action_tool_names"], ["delete_file"])
        self.assertEqual(result["dip_action_mutated_files"], [target_path])
        self.assertTrue(result["dip_mutation_written"])
        self.assertTrue(result["dip_mutation_verified"])
        self.assertTrue(result["dip_mutation_readback_verified"])

    def test_apply_patch_delete_records_absence_as_mutation_readback(self) -> None:
        target_path = "tmp/wbp-custom-strong/mutation-a.txt"
        patch_text = (
            "diff --git a/tmp/wbp-custom-strong/mutation-a.txt b/tmp/wbp-custom-strong/mutation-a.txt\n"
            "deleted file mode 100644\n"
            "index e69de29..0000000\n"
            "--- a/tmp/wbp-custom-strong/mutation-a.txt\n"
            "+++ /dev/null\n"
            "@@ -1 +0,0 @@\n"
            "-WBP_CUSTOM_STRONG_MUTATION_OK\n"
        )
        with tempfile.TemporaryDirectory() as raw_root:
            repo = Path(raw_root)
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            target_file = repo / target_path
            target_file.parent.mkdir(parents=True)
            target_file.write_text("WBP_CUSTOM_STRONG_MUTATION_OK\n", encoding="utf-8")

            tool_result = _execute_repo_tool_call(
                {"tool": "apply_patch", "patch": patch_text},
                repo_root=repo,
            )
            fields = _repo_bridge_fields(
                required=True,
                action_required=True,
                mutation_required=True,
                code_mutation_required=False,
                available=True,
                context_pack={},
                tool_results=[tool_result],
            )
            file_exists_after = target_file.exists()

        self.assertEqual(tool_result["status"], "ok")
        self.assertFalse(file_exists_after)
        self.assertEqual(tool_result["deleted_files"], [target_path])
        self.assertTrue(tool_result["deleted_files_absent"])
        self.assertTrue(fields["dip_mutation_written"])
        self.assertTrue(fields["dip_mutation_verified"])
        self.assertTrue(fields["dip_mutation_readback_verified"])
        self.assertTrue(fields["dip_action_patch_applied"])
        self.assertFalse(fields["dip_code_written"])
        self.assertFalse(fields["dip_code_patch_applied"])

    def test_apply_patch_rolls_back_python_syntax_error(self) -> None:
        target_path = "tmp/wbp-ultrahard/invalid_python/demo.py"
        patch_text = (
            "diff --git a/tmp/wbp-ultrahard/invalid_python/demo.py b/tmp/wbp-ultrahard/invalid_python/demo.py\n"
            "new file mode 100644\n"
            "index 0000000..8f5b35a\n"
            "--- /dev/null\n"
            "+++ b/tmp/wbp-ultrahard/invalid_python/demo.py\n"
            "@@ -0,0 +1,3 @@\n"
            "+def label(value):\n"
            "+    if value:\n"
            "+    else:\n"
        )
        with tempfile.TemporaryDirectory() as raw_root:
            repo = Path(raw_root)
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )

            tool_result = _execute_repo_tool_call(
                {"tool": "apply_patch", "patch": patch_text},
                repo_root=repo,
            )
            file_exists_after = (repo / target_path).exists()

        self.assertEqual(tool_result["status"], "error")
        self.assertEqual(
            tool_result["machine_error_code"],
            "python_syntax_check_failed",
        )
        self.assertFalse(file_exists_after)
        self.assertTrue(tool_result["rollback_applied"])
        self.assertFalse(tool_result["mutation_applied"])
        self.assertEqual(tool_result["touched_files"], [target_path])

    def test_prior_delete_does_not_verify_later_file_creation_cleanup(self) -> None:
        target_path = "tmp/wbp-manual-matrix/ru-write.txt"
        bootstrap_delete = {
            "tool": "delete_file",
            "origin": "wbp_bootstrap",
            "status": "ok",
            "machine_error_code": "OK",
            "path": target_path,
            "touched_files": [target_path],
            "deleted_files": [target_path],
            "deleted_files_absent": True,
            "mutation_applied": True,
            "mutated_files": [target_path],
        }
        later_create = {
            "tool": "apply_patch",
            "origin": "",
            "status": "ok",
            "machine_error_code": "OK",
            "path": "",
            "touched_files": [target_path],
            "deleted_files": [],
            "deleted_files_absent": False,
            "mutation_applied": True,
            "mutated_files": [target_path],
        }

        fields = _repo_bridge_fields(
            required=True,
            action_required=True,
            mutation_required=True,
            code_mutation_required=False,
            available=True,
            context_pack={},
            tool_results=[bootstrap_delete, later_create],
        )

        self.assertTrue(fields["dip_mutation_written"])
        self.assertFalse(fields["dip_mutation_verified"])
        self.assertFalse(fields["dip_mutation_readback_verified"])

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_file_mutation_requires_readback(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        patch_text = (
            "diff --git a/tmp/probe.txt b/tmp/probe.txt\n"
            "new file mode 100644\n"
            "index 0000000..e69de29\n"
            "--- /dev/null\n"
            "+++ b/tmp/probe.txt\n"
            "@@ -0,0 +1 @@\n"
            "+OK\n"
        )
        patch_response = SimpleNamespace(
            status_code=200,
            latency_ms=11,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "wbp_repo_tool_call": {
                                        "tool": "apply_patch",
                                        "patch": patch_text,
                                    }
                                }
                            )
                        }
                    }
                ]
            },
        )
        no_readback_response = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={
                "choices": [
                    {"message": {"content": "Created the file without readback."}}
                ]
            },
        )
        request_json_mock.side_effect = [patch_response] + [no_readback_response] * 10
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: через repo bridge создай файл tmp/probe.txt и ответь JSON",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["machine_error_code"],
            WBP_DIP_TOOL_MUTATION_VERIFICATION_NOT_RUN,
        )
        self.assertTrue(result["dip_mutation_required"])
        self.assertTrue(result["dip_mutation_written"])
        self.assertFalse(result["dip_mutation_verified"])
        self.assertFalse(result["dip_code_mutation_required"])

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_readonly_repo_audit_keeps_action_and_mutation_off(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={"choices": [{"message": {"content": "Readonly audit complete."}}]},
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "demo.py").write_text('VALUE = "ok"\n', encoding="utf-8")
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: read-only audit repo, скажи как починить demo.py, "
                    "но без правок файлов."
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["dip_repo_tool_bridge_required"])
        self.assertFalse(result["dip_action_bridge_required"])
        self.assertFalse(result["dip_action_bridge_used"])
        self.assertFalse(result["dip_code_mutation_required"])
        self.assertTrue(result["repo_bridge_readonly"])

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_repairs_mismatched_tool_used_claim(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=10,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "search",
                                            "pattern": "VALUE",
                                            "glob": "demo.py",
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"found":true,"file":"demo.py",'
                                    '"tool_used":"search_repo"}'
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"found":true,"file":"demo.py",'
                                    '"tool_used":"search"}'
                                )
                            }
                        }
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "demo.py").write_text('VALUE = "ok"\n', encoding="utf-8")
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: через repo bridge read-only используй search_repo "
                    "для поиска VALUE и ответь JSON с tool_used."
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertIn("search", result["repo_bridge_tool_names"])
        self.assertNotIn("search_repo", result["repo_bridge_tool_names"])
        self.assertEqual(json.loads(result["result_text"])["tool_used"], "search")
        repair_prompt = request_json_mock.call_args_list[-1].kwargs["payload"][
            "messages"
        ][-1]["content"]
        self.assertIn("WBP TOOL CLAIM GATE", repair_prompt)
        self.assertIn("search", repair_prompt)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_rejects_rg_through_run_command(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "run_command",
                                            "args": ["rg", "SECRET", ".env"],
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
        ] + [
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={"choices": [{"message": {"content": "Command rejected."}}]},
            )
        ] * 10
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / ".env").write_text("SECRET=owner-token\n", encoding="utf-8")
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: run command rg SECRET .env. Do not edit files.",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_ACTION_BRIDGE_FAILED)
        self.assertIn("run_command", result["repo_bridge_tool_names"])
        self.assertTrue(result["dip_action_bridge_used"])
        self.assertFalse(result["dip_action_bridge_succeeded"])
        self.assertEqual(result["dip_action_successful_tool_call_count"], 0)
        run_command_steps = [
            step for step in result["dip_evidence_trace"] if step["tool"] == "run_command"
        ]
        self.assertEqual(run_command_steps[0]["machine_error_code"], "command_not_allowlisted")
        self.assertFalse(packet_contains_text(result, "owner-token"))

    def test_repo_context_redacts_sensitive_status_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            repo = Path(raw_root)
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            (repo / ".env").write_text("TOKEN=owner-token\n", encoding="utf-8")
            (repo / "normal.py").write_text("VALUE = 1\n", encoding="utf-8")

            status = _git_status_repo(repo)
            pack = _build_repo_context_pack(repo)

        status_text = str(status.get("result_text") or "")
        pack_text = json.dumps(pack, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(".env", status_text)
        self.assertNotIn(".env", pack_text)
        self.assertNotIn("owner-token", pack_text)
        self.assertIn("[sensitive repo path redacted]", status_text)

    def test_repo_context_records_safe_command_allowlist_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            repo = Path(raw_root)
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )

            pack = _build_repo_context_pack(repo, action_tools_allowed=True)
            readonly_pack = _build_repo_context_pack(repo, action_tools_allowed=False)

        self.assertFalse(pack["command_allowlist_recorded"])
        self.assertTrue(pack["command_allowlist_profile_recorded"])
        self.assertIn("python3_module_pytest", pack["command_allowlist_profile_ids"])
        self.assertIn("git_diff_check", pack["command_allowlist_profile_ids"])
        self.assertTrue(pack["command_allowlist_profile_digest"])
        self.assertFalse(readonly_pack["command_allowlist_profile_recorded"])
        self.assertEqual(readonly_pack["command_allowlist_profile_ids"], [])
        self.assertEqual(readonly_pack["command_allowlist_profile_digest"], "")

    def test_repo_bridge_prompt_declares_command_surface_not_general_shell(self) -> None:
        prompt = _repo_bridge_prompt(
            {
                "action_tools_allowed": True,
                "mutations_allowed": False,
                "command_allowlist_profile_ids": ["python3_module_pytest"],
            }
        )

        self.assertIn("not a general shell or network surface", prompt)
        self.assertIn("python3_module_pytest", prompt)
        self.assertIn("command_not_allowlisted", prompt)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_full_power_matrix_records_all_bridge_tools(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        patch_text = """diff --git a/demo.py b/demo.py
--- a/demo.py
+++ b/demo.py
@@ -1 +1 @@
-VALUE = "ok"
+VALUE = "better"
"""
        request_json_mock.side_effect = [
            SimpleNamespace(
                status_code=200,
                latency_ms=10,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {"wbp_repo_tool_call": {"tool": "list_files", "path": "."}}
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=11,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "search",
                                            "pattern": "VALUE",
                                            "glob": "demo.py",
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "propose_patch",
                                            "patch": patch_text,
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=13,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "wbp_repo_tool_call": {
                                            "tool": "run_command",
                                            "args": ["git", "diff", "--check"],
                                        }
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=14,
                payload={
                    "choices": [
                        {"message": {"content": "Matrix complete with bridge evidence."}}
                    ]
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "demo.py").write_text('VALUE = "ok"\n', encoding="utf-8")
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: run bridge matrix: list files, search VALUE, validate "
                    "a dry-run diff proposal, run command without changing files."
                ),
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                dip_work_mode="full",
                timeout_seconds=0.01,
            )
            unchanged_text = (repo / "demo.py").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertEqual(result["dip_work_mode"], "full")
        self.assertEqual(result["repo_bridge_tool_call_count"], 5)
        self.assertEqual(result["repo_bridge_successful_tool_call_count"], 5)
        self.assertEqual(
            result["repo_bridge_tool_names"],
            ["git_status", "list_files", "search", "propose_patch", "run_command"],
        )
        self.assertEqual(result["dip_action_tool_names"], ["propose_patch", "run_command"])
        self.assertTrue(result["dip_action_bridge_used"])
        self.assertEqual(result["dip_action_successful_tool_call_count"], 2)
        self.assertTrue(result["dip_action_patch_proposed"])
        self.assertTrue(result["dip_action_commands_run"])
        self.assertFalse(result["dip_action_patch_applied"])
        self.assertFalse(result["dip_action_mutation_applied"])
        self.assertFalse(result["dip_code_mutation_required"])
        self.assertEqual(unchanged_text, 'VALUE = "ok"\n')
        self.assertEqual(result["dip_evidence_trace_count"], 5)
        self.assertFalse(result["dip_evidence_trace"][3]["patch_recorded"])
        self.assertFalse(result["dip_evidence_trace"][4]["command_recorded"])
        self.assertEqual(request_json_mock.call_count, 5)

    def test_full_code_mutation_timeout_floor_ignores_short_custom_copy(self) -> None:
        self.assertEqual(
            _effective_live_result_timeout_seconds(
                90,
                dip_work_mode="full",
                repo_bridge_required=True,
                code_mutation_required=True,
            ),
            600.0,
        )
        self.assertEqual(
            _effective_live_result_timeout_seconds(
                90,
                dip_work_mode="full",
                repo_bridge_required=True,
                code_mutation_required=False,
            ),
            90.0,
        )
        self.assertEqual(
            _effective_live_result_timeout_seconds(
                0.01,
                dip_work_mode="default",
                repo_bridge_required=True,
                code_mutation_required=True,
            ),
            10.0,
        )
        self.assertEqual(
            _effective_live_result_timeout_seconds(
                0.01,
                dip_work_mode="default",
                repo_bridge_required=True,
                code_mutation_required=False,
            ),
            1.0,
        )

    def test_exact_plain_reply_parser_stops_before_human_else_branch(self) -> None:
        self.assertEqual(
            _exact_plain_reply_expected_text(
                "DIP: Если команда успешна, ответь ровно WBP_OK, иначе WBP_FAIL"
            ),
            "WBP_OK",
        )
        self.assertEqual(
            _exact_plain_reply_expected_text(
                "DIP: If the command passes, answer exactly WBP_OK, otherwise WBP_FAIL"
            ),
            "WBP_OK",
        )

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_blocks_fix_task_without_verification(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        patch_text = """diff --git a/demo.py b/demo.py
--- a/demo.py
+++ b/demo.py
@@ -1 +1 @@
-VALUE = "bad"
+VALUE = "good"
"""
        patch_response = SimpleNamespace(
            status_code=200,
            latency_ms=11,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "wbp_repo_tool_call": {
                                        "tool": "apply_patch",
                                        "patch": patch_text,
                                    }
                                }
                            )
                        }
                    }
                ]
            },
        )
        no_verify_response = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": "Fixed demo.py without running verification."
                        }
                    }
                ]
            },
        )
        request_json_mock.side_effect = [patch_response] + [no_verify_response] * 10
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "demo.py").write_text('VALUE = "bad"\n', encoding="utf-8")
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: почини demo.py",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="auto",
                timeout_seconds=0.01,
            )
            changed_text = (repo / "demo.py").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_CODE_VERIFICATION_NOT_RUN)
        self.assertEqual(changed_text, 'VALUE = "good"\n')
        self.assertTrue(result["dip_action_bridge_used"])
        self.assertTrue(result["dip_action_patch_applied"])
        self.assertTrue(result["dip_code_mutation_required"])
        self.assertTrue(result["dip_code_written"])
        self.assertTrue(result["dip_code_patch_applied"])
        self.assertTrue(result["dip_code_verification_required"])
        self.assertFalse(result["dip_code_verified"])

    def test_natural_english_create_module_is_code_mutation(self) -> None:
        task = (
            "DIP: create a Python module in "
            "tmp/wbp-ultrahard/en_natural/command_parser.py and return JSON."
        )

        self.assertTrue(_repo_bridge_requested(task=task, mode="auto"))
        self.assertTrue(_repo_mutation_requested(task=task, repo_bridge_required=True))
        self.assertTrue(_code_mutation_requested(task=task, repo_bridge_required=True))

    def test_natural_explanation_without_file_changes_is_not_code_mutation(self) -> None:
        task = "DIP: write an explanation without file changes."

        self.assertFalse(_repo_bridge_requested(task=task, mode="auto"))
        self.assertFalse(_repo_mutation_requested(task=task, repo_bridge_required=False))
        self.assertFalse(_code_mutation_requested(task=task, repo_bridge_required=False))

    def test_explicit_pytest_command_stops_before_human_followup_sentence(self) -> None:
        task = (
            "DIP: через repo bridge создай tmp/demo/test_solver.py. "
            "Запусти python3 -m pytest tmp/demo/test_solver.py -q. "
            "Если pytest красный, исправь код и запусти снова. "
            "Ответь ровно JSON с полями status, passed_count, command_used."
        )

        self.assertEqual(
            _explicit_test_command_from_task(task),
            ["python3", "-m", "pytest", "tmp/demo/test_solver.py", "-q"],
        )

    def test_explicit_pytest_command_stops_before_after_success_sentence(self) -> None:
        task = (
            "DIP: через repo bridge напиши код мини-приложения в "
            "tmp/wbp-ultrahard-app. Запусти python3 -m pytest "
            "tmp/wbp-ultrahard-app -q. После успешных тестов ответь "
            "ровно WBP_ULTRAHARD_CODE_OK."
        )

        self.assertEqual(
            _explicit_test_command_from_task(task),
            ["python3", "-m", "pytest", "tmp/wbp-ultrahard-app", "-q"],
        )

    def test_requested_pytest_blocks_unrelated_post_mutation_verification(
        self,
    ) -> None:
        task = (
            "DIP: через repo bridge напиши код мини-приложения в "
            "tmp/wbp-ultrahard-app. Запусти python3 -m pytest "
            "tmp/wbp-ultrahard-app -q. После успешных тестов ответь "
            "ровно WBP_ULTRAHARD_CODE_OK."
        )
        tool_results = [
            {
                "tool": "write_file",
                "status": "ok",
                "mutation_applied": True,
                "mutated_files": ["tmp/wbp-ultrahard-app/taskflow/graph.py"],
            },
            {
                "tool": "run_command",
                "status": "ok",
                "command_used": "python3 -m taskflow plan sample.yml",
                "result_text": "Project duration: 3\n",
            },
        ]

        self.assertEqual(
            _requested_test_verification_block_reason(task, tool_results),
            "requested_test_command_not_run",
        )

    def test_repo_bridge_prompt_warns_against_dotted_imports_for_punctuated_paths(
        self,
    ) -> None:
        prompt = _repo_bridge_prompt(
            {
                "action_tools_allowed": True,
                "mutations_allowed": True,
                "code_mutation_required": True,
            }
        )

        self.assertIn("spec_from_file_location", prompt)
        self.assertIn("dotted imports", prompt)
        self.assertIn("path components containing punctuation", prompt)
        self.assertIn("python3 -m py_compile", prompt)
        self.assertIn("then run the requested pytest", prompt)
        self.assertIn("Every generated Python if/elif/else", prompt)
        self.assertIn("do not leave a bare colon", prompt)

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_blocks_fix_task_when_action_did_not_write_code(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        command_response = SimpleNamespace(
            status_code=200,
            latency_ms=11,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "wbp_repo_tool_call": {
                                        "tool": "run_command",
                                        "args": ["git", "status"],
                                    }
                                }
                            )
                        }
                    }
                ]
            },
        )
        no_patch_response = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": "I checked the repo and claim it is fixed."
                        }
                    }
                ]
            },
        )
        request_json_mock.side_effect = [command_response] + [no_patch_response] * 10
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            repo = root / "repo"
            profile.mkdir()
            repo.mkdir()
            (repo / "demo.py").write_text('VALUE = "bad"\n', encoding="utf-8")
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            )
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task="DIP: почини demo.py",
                expected_alias="DIP",
                profile_dir=profile,
                repo_root=repo,
                repo_bridge_mode="on",
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["machine_error_code"],
            WBP_DIP_TOOL_CODE_MUTATION_NOT_APPLIED,
        )
        self.assertTrue(result["dip_action_bridge_used"])
        self.assertTrue(result["dip_action_commands_run"])
        self.assertTrue(result["dip_code_mutation_required"])
        self.assertFalse(result["dip_code_written"])
        self.assertFalse(result["dip_code_patch_applied"])

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_reports_missing_alias_context(
        self,
        request_json_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)

            result = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["machine_error_code"], "FAIL_ALIAS_CONTEXT_MISSING")
        self.assertEqual(result["route_status"], "alias_context_missing")
        self.assertFalse(result["provider_called"])
        request_json_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_reports_provider_auth_failure(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        request_json_mock.return_value = SimpleNamespace(
            status_code=401,
            latency_ms=12,
            payload={"error": {"code": "unauthorized"}},
        )
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["machine_error_code"], errors.PROVIDER_AUTH_FAILED)
        self.assertEqual(result["operator_action"], "user_action")
        self.assertTrue(result["provider_called"])
        self.assertEqual(result["upstream_status_code"], 401)
        self.assertFalse(result["direct_provider_auth_proven"])
        self.assertFalse(result["direct_provider_response_observed"])
        self.assertFalse(result["provider_auth_ok"])
        self.assertFalse(result["positive_provider_proof_gate_satisfied"])

    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_prefers_runtime_http_bridge(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
    ) -> None:
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=5,
            payload={"output_text": "Bridge result from WBP."},
        )
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                        "deepseek_live_format_check_bridge": {
                            "enabled": True,
                            "method": "POST",
                            "model": "route-ok",
                            "response_text_field": "output_text",
                            "url_candidates": ["http://127.0.0.1:50555/v1/responses"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source"], "runtime_context_http_bridge")
        self.assertTrue(result["bridge_attempted"])
        self.assertEqual(result["result_text"], "Bridge result from WBP.")
        self.assertTrue(result["runtime_context_bridge_used"])
        self.assertTrue(result["bridge_or_file_bridge_used"])
        self.assertFalse(result["direct_provider_auth_proven"])
        self.assertFalse(result["direct_provider_response_observed"])
        self.assertFalse(result["provider_auth_ok"])
        self.assertFalse(result["positive_provider_proof_gate_satisfied"])
        find_route_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._runtime_file_bridge_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_tries_file_bridge_on_permission_style_failure(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        file_bridge_mock: mock.Mock,
    ) -> None:
        request_json_mock.side_effect = RuntimeErrorInfo(
            "Provider network request failed: PermissionError Operation not permitted",
            machine_error_code=errors.PROVIDER_NETWORK_FAILED,
            operator_action="retry",
        )
        file_bridge_mock.return_value = _live_result(
            source="runtime_context_file_bridge",
            result_text="File bridge result from WBP.",
            provider_recorded=False,
            runtime_context_bridge_used=False,
            runtime_context_file_bridge_used=True,
            bridge_or_file_bridge_used=True,
            direct_provider_auth_proven=False,
            direct_provider_response_observed=False,
            provider_auth_ok=False,
            positive_provider_proof_gate_satisfied=False,
        )
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                        "deepseek_live_format_check_bridge": {
                            "enabled": True,
                            "method": "POST",
                            "model": "route-ok",
                            "response_text_field": "output_text",
                            "url_candidates": ["http://127.0.0.1:50555/v1/responses"],
                        },
                        "deepseek_live_format_check_file_bridge": {
                            "enabled": True,
                            "request_dir": str(profile / "requests"),
                            "response_dir": str(profile / "responses"),
                            "response_text_field": "output_text",
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source"], "runtime_context_file_bridge")
        self.assertTrue(result["bridge_attempted"])
        self.assertTrue(result["file_bridge_attempted"])
        self.assertEqual(result["result_text"], "File bridge result from WBP.")
        self.assertTrue(result["runtime_context_file_bridge_used"])
        self.assertTrue(result["bridge_or_file_bridge_used"])
        self.assertFalse(result["direct_provider_auth_proven"])
        self.assertFalse(result["direct_provider_response_observed"])
        self.assertFalse(result["provider_auth_ok"])
        self.assertFalse(result["positive_provider_proof_gate_satisfied"])
        find_route_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._runtime_file_bridge_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_explicit_file_bridge_requirement_skips_http_bridge(
        self,
        request_json_mock: mock.Mock,
        file_bridge_mock: mock.Mock,
    ) -> None:
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=10,
            payload={"output_text": "HTTP bridge result must not be used."},
        )
        file_bridge_mock.return_value = _live_result(
            source="runtime_context_file_bridge",
            result_text="File bridge result from WBP.",
            provider_recorded=False,
            runtime_context_bridge_used=False,
            runtime_context_file_bridge_used=True,
            bridge_or_file_bridge_used=True,
            direct_provider_auth_proven=False,
            direct_provider_response_observed=False,
            provider_auth_ok=False,
            positive_provider_proof_gate_satisfied=False,
        )
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                        "deepseek_live_format_check_bridge": {
                            "enabled": True,
                            "method": "POST",
                            "model": "route-ok",
                            "response_text_field": "output_text",
                            "url_candidates": ["http://127.0.0.1:50555/v1/responses"],
                        },
                        "deepseek_live_format_check_file_bridge": {
                            "enabled": True,
                            "request_dir": str(profile / "requests"),
                            "response_dir": str(profile / "responses"),
                            "response_text_field": "output_text",
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: Use only the enabled "
                    "deepseek_live_format_check_file_bridge shell_command_template. "
                    "Replace only <expected_text> with WBP_FILE_BRIDGE_OK."
                ),
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=3.0,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source"], "runtime_context_file_bridge")
        self.assertTrue(result["file_bridge_required"])
        self.assertTrue(result["file_bridge_attempted"])
        self.assertTrue(result["runtime_context_file_bridge_used"])
        self.assertTrue(result["bridge_or_file_bridge_used"])
        self.assertFalse(result["runtime_context_bridge_used"])
        self.assertEqual(result["result_text"], "File bridge result from WBP.")
        request_json_mock.assert_not_called()
        file_bridge_mock.assert_called_once()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._runtime_file_bridge_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_explicit_file_bridge_requirement_fails_closed(
        self,
        request_json_mock: mock.Mock,
        file_bridge_mock: mock.Mock,
    ) -> None:
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=10,
            payload={"output_text": "HTTP bridge result must not be used."},
        )
        file_bridge_mock.return_value = None
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                        "deepseek_live_format_check_bridge": {
                            "enabled": True,
                            "method": "POST",
                            "model": "route-ok",
                            "response_text_field": "output_text",
                            "url_candidates": ["http://127.0.0.1:50555/v1/responses"],
                        },
                        "deepseek_live_format_check_file_bridge": {
                            "enabled": True,
                            "request_dir": str(profile / "requests"),
                            "response_dir": str(profile / "responses"),
                            "response_text_field": "output_text",
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=(
                    "DIP: Use only the enabled "
                    "deepseek_live_format_check_file_bridge shell_command_template. "
                    "Replace only <expected_text> with WBP_FILE_BRIDGE_OK."
                ),
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=3.0,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["machine_error_code"],
            WBP_DIP_TOOL_FILE_BRIDGE_NOT_PROVEN,
        )
        self.assertTrue(result["file_bridge_required"])
        self.assertTrue(result["file_bridge_attempted"])
        self.assertFalse(result["result_available"])
        request_json_mock.assert_not_called()
        file_bridge_mock.assert_called_once()

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool._runtime_file_bridge_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_tries_file_bridge_on_connection_refused_before_direct_provider(
        self,
        request_json_mock: mock.Mock,
        file_bridge_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        file_bridge_mock.return_value = None
        find_route_mock.return_value = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        request_json_mock.side_effect = [
            RuntimeErrorInfo(
                "Provider network request failed: connection refused",
                machine_error_code=errors.PROVIDER_NETWORK_FAILED,
                operator_action="retry",
            ),
            SimpleNamespace(
                status_code=200,
                latency_ms=12,
                payload={"choices": [{"message": {"content": "Direct provider result."}}]},
            ),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                        "deepseek_live_format_check_bridge": {
                            "enabled": True,
                            "method": "POST",
                            "model": "route-ok",
                            "response_text_field": "output_text",
                            "url_candidates": ["http://127.0.0.1:50555/v1/responses"],
                        },
                        "deepseek_live_format_check_file_bridge": {
                            "enabled": True,
                            "request_dir": str(profile / "requests"),
                            "response_dir": str(profile / "responses"),
                            "response_text_field": "output_text",
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source"], "external_models_direct")
        self.assertEqual(result["result_text"], "Direct provider result.")
        self.assertTrue(result["bridge_attempted"])
        self.assertTrue(result["file_bridge_attempted"])
        self.assertFalse(result["file_bridge_skipped"])
        self.assertFalse(result["runtime_context_file_bridge_used"])
        self.assertFalse(result["bridge_or_file_bridge_used"])
        self.assertTrue(result["direct_provider_response_observed"])
        file_bridge_mock.assert_called_once()

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_rejects_route_outside_allowlist(
        self,
        request_json_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-outside"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertFalse(result["route_allowed"])
        self.assertEqual(result["route_status"], "route_not_allowed")
        self.assertFalse(result["provider_called"])
        request_json_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_rejects_alias_outside_context(
        self,
        request_json_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"Agent 2": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "api_model_id": "route-ok",
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertFalse(result["route_allowed"])
        self.assertEqual(result["route_status"], "alias_not_in_context")
        self.assertFalse(result["provider_called"])
        request_json_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
