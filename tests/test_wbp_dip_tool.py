# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
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
    WBP_DIP_TOOL_ACTION_BRIDGE_NOT_USED,
    WBP_DIP_TOOL_CODE_MUTATION_NOT_APPLIED,
    WBP_DIP_TOOL_CODE_VERIFICATION_NOT_RUN,
    WBP_DIP_TOOL_LIVE_RESULT_UNSAFE,
    WBP_DIP_TOOL_LIVE_RESULT_UNAVAILABLE,
    WBP_DIP_TOOL_OK,
    WBP_DIP_TOOL_REPO_BRIDGE_NOT_USED,
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
    }
    packet.update(overrides)
    return packet


class WbpDipToolTests(unittest.TestCase):
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

    def test_default_python_bin_prefers_explicit_runtime_python(self) -> None:
        self.assertEqual(
            default_python_bin({PYTHON_BIN_ENV: "/opt/custom/python3.14"}),
            Path("/opt/custom/python3.14"),
        )

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
                ),
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["dip_repo_tool_bridge_required"])
        self.assertTrue(packet["dip_repo_tool_bridge_available"])
        self.assertTrue(packet["dip_repo_tool_bridge_used"])
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

            def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
                stdout = kwargs["stdout"]
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
                        str(root / "profile"),
                        "--proof-dir",
                        str(proof_dir),
                        "--cd",
                        str(Path(__file__).resolve().parents[1]),
                        TASK,
                    ]
                )
            codex_jsonl = (proof_dir / "codex-exec.jsonl").read_text(encoding="utf-8")

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
        self.assertTrue(result["repo_bridge_mutation_allowed"])
        self.assertEqual(request_json_mock.call_count, 2)

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
                                            "args": ["rg", "VALUE", "demo.py"],
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
                task="DIP: run command rg VALUE demo.py. Do not edit files.",
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
                                        "args": ["rg", "VALUE", "demo.py"],
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
