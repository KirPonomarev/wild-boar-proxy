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
    WBP_DIP_TOOL_CODEX_EXEC_FAILED,
    WBP_DIP_TOOL_CODEX_NOT_EXECUTABLE,
    WBP_DIP_TOOL_DELEGATE_NOT_PROVEN,
    WBP_DIP_TOOL_DRY_RUN,
    WBP_DIP_TOOL_FORBIDDEN_CODEX_EXEC_EVENT,
    WBP_DIP_TOOL_ACTION_BRIDGE_NOT_USED,
    WBP_DIP_TOOL_ACTIVE_PROJECT_ROOT_UNAVAILABLE,
    WBP_DIP_TOOL_CODE_MUTATION_NOT_APPLIED,
    WBP_DIP_TOOL_CODE_VERIFICATION_NOT_RUN,
    WBP_DIP_TOOL_LIVE_RESULT_UNSAFE,
    WBP_DIP_TOOL_LIVE_RESULT_UNAVAILABLE,
    WBP_DIP_TOOL_OK,
    WBP_DIP_TOOL_REPO_BRIDGE_FINAL_ANSWER_MISSING,
    WBP_DIP_TOOL_REPO_BRIDGE_NOT_USED,
    _codex_exec_forbidden_event_reasons,
    _attach_live_result_text_artifact,
    _build_live_result_prompt,
    _command_from_call,
    _dip_work_mode_settings,
    _build_repo_context_pack,
    _git_status_repo,
    _select_target_repo_candidate,
    build_codex_exec_argv,
    build_delegate_prompt,
    build_wbp_dip_tool_packet,
    default_codex_bin,
    default_python_bin,
    main,
    request_live_result,
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

    def test_default_codex_bin_falls_back_to_available_app_binary(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            missing_app = root / "missing" / "Codex WBP Clean.app"
            installed_app = root / "Applications" / "Codex.app"
            installed_bin = installed_app / "Contents" / "Resources" / "codex"
            installed_bin.parent.mkdir(parents=True)
            installed_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            installed_bin.chmod(0o755)

            with mock.patch(
                "wild_boar_proxy.wbp_dip_tool._codex_app_candidates",
                return_value=[missing_app, installed_app],
            ):
                resolved = default_codex_bin({})

        self.assertEqual(resolved, installed_bin)

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

        self.assertEqual(completed.returncode, 0)
        packet = json.loads(completed.stdout)
        self.assertEqual(packet["packet_kind"], "wbp_dip_working_tool_run")
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_DRY_RUN)
        self.assertEqual(packet["effect"], "probe")
        self.assertTrue(packet["planned_codex_exec"])
        self.assertEqual(packet["planned_model"], DEFAULT_MODEL)
        self.assertEqual(packet["planned_sandbox"], DEFAULT_SANDBOX)
        self.assertEqual(packet["dip_work_mode"], "standard")
        self.assertFalse(packet["dip_full_work_mode"])
        self.assertEqual(packet["live_result_text_limit"], 2400)
        self.assertEqual(packet["live_result_output_token_limit"], 768)
        self.assertEqual(packet["repo_bridge_max_steps"], 8)
        self.assertFalse(packet_contains_text(packet, TASK))

    def test_tool_dry_run_full_work_mode_reports_full_packet_limits(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "tools/wbp_dip",
                "--dry-run",
                "--json",
                "--work-mode",
                "full",
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

        self.assertEqual(completed.returncode, 0)
        packet = json.loads(completed.stdout)
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_DRY_RUN)
        self.assertEqual(packet["planned_dip_work_mode"], "full")
        self.assertEqual(packet["dip_work_mode"], "full")
        self.assertTrue(packet["dip_full_work_mode"])
        self.assertEqual(packet["live_result_text_limit"], 64000)
        self.assertEqual(packet["live_result_output_token_limit"], 32768)
        self.assertEqual(packet["repo_bridge_max_steps"], 24)
        self.assertFalse(packet_contains_text(packet, TASK))

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_live_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.subprocess.run")
    def test_main_json_operator_path_returns_working_result_packet(
        self,
        subprocess_run_mock: mock.Mock,
        request_live_result_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            codex_bin = root / "codex"
            codex_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            codex_bin.chmod(0o755)
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

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_live_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.subprocess.run")
    def test_main_plain_operator_path_prints_useful_result(
        self,
        subprocess_run_mock: mock.Mock,
        request_live_result_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            codex_bin = root / "codex"
            codex_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            codex_bin.chmod(0o755)

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

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_live_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.subprocess.run")
    def test_main_loads_openai_api_key_from_local_token_when_env_missing(
        self,
        subprocess_run_mock: mock.Mock,
        request_live_result_mock: mock.Mock,
    ) -> None:
        sentinel = "local-runtime-token-123456"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            codex_bin = root / "codex"
            codex_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            codex_bin.chmod(0o755)
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

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_live_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.subprocess.run")
    def test_main_does_not_inject_local_token_for_non_loopback_provider(
        self,
        subprocess_run_mock: mock.Mock,
        request_live_result_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            codex_bin = root / "codex"
            codex_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            codex_bin.chmod(0o755)
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

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_live_result")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.subprocess.run")
    def test_main_passes_explicit_active_project_root_separate_from_codex_cwd(
        self,
        subprocess_run_mock: mock.Mock,
        request_live_result_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            codex_bin = root / "codex"
            codex_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            codex_bin.chmod(0o755)
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
                timeout_seconds=0.01,
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
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_ACTION_BRIDGE_NOT_USED)
        self.assertIn("run_command", result["repo_bridge_tool_names"])
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
    def test_request_live_result_tries_file_bridge_before_direct_provider(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        file_bridge_mock: mock.Mock,
    ) -> None:
        request_json_mock.side_effect = RuntimeErrorInfo(
            "Provider network request failed: refused",
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
