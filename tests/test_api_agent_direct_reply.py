import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import api_agent_direct_reply as direct
from wild_boar_proxy import cli
from wild_boar_proxy.core import packets
from wild_boar_proxy.runtime import RuntimePaths


ROUTE_ID = "wbp-deepseek-v4-pro-max"


def _active_project_root_for_test() -> Path:
    return Path(tempfile.gettempdir()).resolve(strict=False)


def _runtime_context(*, custom_alias: str | None = None) -> dict[str, object]:
    dip_aliases = ["DIP", "Agent 2", "2"]
    if custom_alias:
        dip_aliases.append(custom_alias)
    alias_to_agent_id = {
        "Codex": "codex",
        "Agent 1": "codex",
        "1": "codex",
        "DIP": "dip",
        "Agent 2": "dip",
        "2": "dip",
    }
    if custom_alias:
        alias_to_agent_id[custom_alias] = "dip"
    return {
        "packet_kind": "codex_custom_native_agent_runtime_context",
        "context_truth_source": "server_launch_selection_packet",
        "agent_bindings_status": "ok",
        "agent_bindings": [
            {
                "agent_id": "codex",
                "display_name": "Codex",
                "role": "orchestrator",
                "aliases": ["Codex", "Agent 1", "1"],
                "lane": "primary_chatgpt",
                "enabled": True,
                "model_id": "gpt-5.5",
                "allowed_actions": ["plan", "inspect"],
            },
            {
                "agent_id": "dip",
                "display_name": "DIP",
                "role": "coding_agent",
                "aliases": dip_aliases,
                "lane": "api_route",
                "enabled": True,
                "route_id": ROUTE_ID,
                "allowed_actions": ["implementation_help"],
            },
        ],
        "alias_to_agent_id": alias_to_agent_id,
        "agent_id_to_route": {"dip": ROUTE_ID},
        "agent_id_to_model": {"codex": "gpt-5.5"},
        "allowed_api_route_ids": [ROUTE_ID],
        "route_providers": {ROUTE_ID: "deepseek"},
        "forbidden_stale_route_ids": ["wbp-deepseek-v3"],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _live_result(text: str, **overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "status": "ok",
        "machine_error_code": "OK",
        "provider_called": True,
        "result_available": True,
        "result_text": text,
        "result_text_sha256": direct._sha256_text(text),
        "result_text_length": len(text),
        "result_text_truncated": False,
        "source": "external_models_direct",
        "route_allowed": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "runtime_context_bridge_used": False,
        "runtime_context_file_bridge_used": False,
        "bridge_or_file_bridge_used": False,
        "direct_provider_auth_proven": True,
        "direct_provider_response_observed": True,
        "provider_auth_ok": True,
        "positive_provider_proof_gate_satisfied": True,
        "dip_work_mode": "full",
        "dip_full_work_mode": True,
        "live_result_text_limit": 64000,
        "live_result_output_token_limit": 32768,
        "repo_bridge_required": False,
        "repo_bridge_available": False,
        "repo_bridge_used": False,
    }
    result.update(overrides)
    return result


def _live_result_from_kwargs(text: str, **kwargs: object) -> dict[str, object]:
    work_mode = str(kwargs.get("dip_work_mode") or "standard")
    full = work_mode == "full"
    return _live_result(
        text,
        dip_work_mode=work_mode,
        dip_full_work_mode=full,
        live_result_text_limit=64000 if full else 2400,
        live_result_output_token_limit=32768 if full else 768,
    )


class ApiAgentDirectReplyTests(unittest.TestCase):
    def test_direct_reply_calls_api_route_agent_once_and_records_final_text(self) -> None:
        calls: list[dict[str, object]] = []

        def runner(**kwargs: object) -> dict[str, object]:
            calls.append(dict(kwargs))
            return _live_result("DIP direct answer")

        prompt = "DIP: ответь коротко."
        packet = direct.build_api_agent_direct_reply_packet(
            prompt_text=prompt,
            runtime_context=_runtime_context(),
            context_file_metadata={
                "runtime_context_file_present": True,
                "runtime_context_file_read": True,
            },
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            work_mode="full",
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["api_agent_direct_reply_proven"])
        self.assertEqual(packet["selected_alias"], "DIP")
        self.assertEqual(packet["selected_alias_lane"], "api_route")
        self.assertEqual(packet["output_text"], "DIP direct answer")
        self.assertEqual(packet["direct_reply_text"], "DIP direct answer")
        self.assertTrue(packet["direct_api_reply_block"])
        self.assertEqual(packet["reply_block_kind"], "api_agent_direct_reply")
        self.assertEqual(packet["reply_author_alias"], "DIP")
        self.assertEqual(packet["reply_agent_id"], "dip")
        self.assertEqual(packet["reply_lane"], "api_route")
        self.assertEqual(packet["reply_provider_label"], "deepseek")
        self.assertEqual(packet["reply_text"], "DIP direct answer")
        self.assertEqual(
            packet["reply_text_sha256"],
            direct._sha256_text("DIP direct answer"),
        )
        self.assertFalse(packet["reply_proof_summary"]["final_answer_was_repo_tool_call"])
        self.assertFalse(packet["reply_proof_summary"]["tools_wbp_dip_invoked"])
        self.assertFalse(packet["reply_proof_summary"]["dip_run_invoked"])
        self.assertTrue(packet["api_agent_direct_reply_text_recorded"])
        self.assertTrue(packet["api_agent_provider_called"])
        self.assertTrue(packet["direct_provider_response_observed"])
        self.assertFalse(packet["gpt_orchestrator_used"])
        self.assertFalse(packet["codex_exec_invoked"])
        self.assertFalse(packet["tools_wbp_dip_invoked"])
        self.assertFalse(packet["dip_run_invoked"])
        self.assertFalse(packet["wrapper_shopping_used"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["selected_api_route_id_recorded"])
        encoded = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(ROUTE_ID, encoded)
        self.assertNotIn(prompt, encoded)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["expected_alias"], "DIP")
        self.assertEqual(calls[0]["dip_work_mode"], "full")
        self.assertEqual(calls[0]["repo_bridge_mode"], "off")
        self.assertEqual(calls[0]["repo_root"], _active_project_root_for_test())
        self.assertEqual(calls[0]["target_repo_source"], "test_selected_active_project_root")
        self.assertEqual(calls[0]["runtime_context"], _runtime_context())
        self.assertFalse(packet["active_project_root_required"])
        self.assertTrue(packet["active_project_root_available"])
        self.assertFalse(packet["active_project_root_path_recorded"])
        self.assertFalse(packet["active_project_root_is_wbp_repo"])
        self.assertFalse(packet["target_repo_required"])
        self.assertTrue(packet["target_repo_available"])
        self.assertFalse(packet["target_repo_path_recorded"])
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_direct_reply_allows_missing_active_project_root_for_plain_reply(self) -> None:
        calls: list[dict[str, object]] = []

        def runner(**kwargs: object) -> dict[str, object]:
            calls.append(dict(kwargs))
            return _live_result("plain direct answer")

        packet = direct.build_api_agent_direct_reply_packet(
            prompt_text="DIP: ответь коротко.",
            runtime_context=_runtime_context(),
            context_file_metadata={
                "runtime_context_file_present": True,
                "runtime_context_file_read": True,
            },
            profile_dir=Path("/tmp/profile"),
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["api_agent_direct_reply_proven"])
        self.assertTrue(packet["api_agent_provider_called"])
        self.assertEqual(packet["direct_reply_text"], "plain direct answer")
        self.assertFalse(packet["active_project_root_required"])
        self.assertFalse(packet["active_project_root_available"])
        self.assertFalse(packet["target_repo_available"])
        self.assertFalse(packet["target_repo_required"])
        self.assertEqual(len(calls), 1)
        self.assertIsNone(calls[0]["repo_root"])
        self.assertEqual(calls[0]["repo_bridge_mode"], "off")
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_direct_reply_blocks_without_active_project_root_when_repo_bridge_on(self) -> None:
        runner = mock.Mock(return_value=_live_result("must not run"))

        packet = direct.build_api_agent_direct_reply_packet(
            prompt_text="DIP: прочитай AGENTS.md.",
            runtime_context=_runtime_context(),
            context_file_metadata={
                "runtime_context_file_present": True,
                "runtime_context_file_read": True,
            },
            profile_dir=Path("/tmp/profile"),
            repo_bridge_mode="on",
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "active_project_root_missing")
        self.assertFalse(packet["api_agent_direct_reply_proven"])
        self.assertFalse(packet["api_agent_provider_called"])
        self.assertTrue(packet["active_project_root_required"])
        self.assertFalse(packet["active_project_root_available"])
        self.assertFalse(packet["target_repo_available"])
        runner.assert_not_called()
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_direct_reply_accepts_custom_api_alias_from_runtime_context(self) -> None:
        seen_aliases: list[str] = []

        def runner(**kwargs: object) -> dict[str, object]:
            seen_aliases.append(str(kwargs["expected_alias"]))
            return _live_result("custom alias answered")

        packet = direct.build_api_agent_direct_reply_packet(
            prompt_text="Кодер: проверь контракт.",
            runtime_context=_runtime_context(custom_alias="Кодер"),
            context_file_metadata={
                "runtime_context_file_present": True,
                "runtime_context_file_read": True,
            },
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["selected_alias"], "Кодер")
        self.assertEqual(packet["selected_slot"], "dip")
        self.assertEqual(packet["direct_reply_text"], "custom alias answered")
        self.assertEqual(packet["reply_author_alias"], "Кодер")
        self.assertEqual(packet["reply_agent_id"], "dip")
        self.assertEqual(packet["reply_text"], "custom alias answered")
        self.assertEqual(seen_aliases, ["Кодер"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_primary_chatgpt_alias_blocks_without_provider_call(self) -> None:
        runner = mock.Mock(return_value=_live_result("must not be called"))

        packet = direct.build_api_agent_direct_reply_packet(
            prompt_text="Codex: ответь.",
            runtime_context=_runtime_context(),
            context_file_metadata={
                "runtime_context_file_present": True,
                "runtime_context_file_read": True,
            },
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "FAIL_ALIAS_NOT_API_LANE")
        self.assertFalse(packet["api_agent_direct_reply_proven"])
        self.assertFalse(packet["api_agent_provider_called"])
        runner.assert_not_called()
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_final_repo_tool_call_is_not_accepted_as_direct_reply(self) -> None:
        packet = direct.build_api_agent_direct_reply_packet(
            prompt_text="DIP: прочитай файл.",
            runtime_context=_runtime_context(),
            context_file_metadata={
                "runtime_context_file_present": True,
                "runtime_context_file_read": True,
            },
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            live_result_runner=lambda **_kwargs: _live_result(
                '{"wbp_repo_tool_call":{"tool":"read_file","path":"AGENTS.md"}}'
            ),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            direct.API_AGENT_DIRECT_REPLY_FINAL_TOOL_CALL,
        )
        self.assertTrue(packet["final_answer_was_repo_tool_call"])
        self.assertTrue(packet["final_tool_call_blocked"])
        self.assertFalse(packet["api_agent_direct_reply_text_available"])
        self.assertEqual(packet["direct_reply_text"], "")
        self.assertEqual(packet["reply_text"], "")
        self.assertTrue(packet["reply_proof_summary"]["final_answer_was_repo_tool_call"])
        self.assertIn("final_answer_was_repo_tool_call", packet["blocking_reasons"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_repo_bridge_mode_marks_mutating_effect_and_propagates_changed_files(self) -> None:
        packet = direct.build_api_agent_direct_reply_packet(
            prompt_text="DIP: почини баг и запусти тест.",
            runtime_context=_runtime_context(),
            context_file_metadata={
                "runtime_context_file_present": True,
                "runtime_context_file_read": True,
            },
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            repo_bridge_mode="on",
            live_result_runner=lambda **_kwargs: _live_result(
                "fixed and verified",
                repo_bridge_required=True,
                repo_bridge_available=True,
                repo_bridge_used=True,
                dip_action_bridge_required=True,
                dip_action_bridge_used=True,
                dip_action_mutation_applied=True,
                dip_code_mutation_required=True,
                dip_code_written=True,
                dip_code_verified=True,
                dip_action_mutated_files=["src/app.py"],
            ),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["effect"], "mutate")
        self.assertTrue(packet["file_mutation_attempted"])
        self.assertEqual(packet["changed_files"], ["src/app.py"])
        self.assertEqual(packet["dip_action_mutated_files"], ["src/app.py"])
        self.assertTrue(packet["dip_code_written"])
        self.assertTrue(packet["dip_code_verified"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_repo_bridge_flags_accept_live_result_bridge_alias_fields(self) -> None:
        packet = direct.build_api_agent_direct_reply_packet(
            prompt_text="DIP: прочитай AGENTS.md.",
            runtime_context=_runtime_context(),
            context_file_metadata={
                "runtime_context_file_present": True,
                "runtime_context_file_read": True,
            },
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            repo_bridge_mode="on",
            work_mode="full",
            live_result_runner=lambda **_kwargs: _live_result(
                "AGENTS read",
                dip_repo_tool_bridge_required=True,
                dip_repo_tool_bridge_available=True,
                dip_repo_tool_bridge_used=True,
                dip_repo_direct_access=False,
                repo_bridge_context_pack_used=True,
                repo_bridge_context_pack_recorded=False,
                repo_bridge_readonly=True,
                repo_bridge_mutation_allowed=False,
                repo_bridge_mutation_controlled=False,
                repo_bridge_bootstrap_used=True,
                repo_bridge_bootstrap_tool_call_count=1,
                repo_bridge_tool_call_count=2,
                repo_bridge_successful_tool_call_count=2,
                repo_bridge_raw_tool_results_recorded=False,
            ),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["repo_bridge_required"])
        self.assertTrue(packet["repo_bridge_available"])
        self.assertTrue(packet["repo_bridge_used"])
        self.assertTrue(packet["dip_repo_tool_bridge_required"])
        self.assertTrue(packet["dip_repo_tool_bridge_available"])
        self.assertTrue(packet["dip_repo_tool_bridge_used"])
        self.assertFalse(packet["dip_repo_direct_access"])
        self.assertTrue(packet["repo_bridge_context_pack_used"])
        self.assertFalse(packet["repo_bridge_context_pack_recorded"])
        self.assertTrue(packet["repo_bridge_readonly"])
        self.assertFalse(packet["repo_bridge_mutation_allowed"])
        self.assertFalse(packet["repo_bridge_mutation_controlled"])
        self.assertTrue(packet["repo_bridge_bootstrap_used"])
        self.assertEqual(packet["repo_bridge_bootstrap_tool_call_count"], 1)
        self.assertEqual(packet["repo_bridge_tool_call_count"], 2)
        self.assertEqual(packet["repo_bridge_successful_tool_call_count"], 2)
        self.assertFalse(packet["repo_bridge_raw_tool_results_recorded"])
        self.assertTrue(packet["repo_bridge_final_answer_required"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_absolute_mutated_file_path_is_blocked_and_not_recorded(self) -> None:
        packet = direct.build_api_agent_direct_reply_packet(
            prompt_text="DIP: почини баг.",
            runtime_context=_runtime_context(),
            context_file_metadata={
                "runtime_context_file_present": True,
                "runtime_context_file_read": True,
            },
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            repo_bridge_mode="on",
            live_result_runner=lambda **_kwargs: _live_result(
                "fixed",
                dip_action_mutation_applied=True,
                dip_action_mutated_files=["/tmp/private/project/src/app.py"],
            ),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], direct.API_AGENT_DIRECT_REPLY_UNSAFE)
        self.assertIn(
            direct.API_AGENT_DIRECT_REPLY_UNSAFE_CHANGED_FILE_PATH,
            packet["blocking_reasons"],
        )
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(packet["dip_action_mutated_files"], [])
        encoded = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("/tmp/private/project/src/app.py", encoded)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_direct_reply_uses_runtime_context_file_and_standard_mode_default(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            managed = root / "managed"
            project = root / "project"
            profile.mkdir()
            managed.mkdir()
            project.mkdir()
            context_file = profile / "wbp-agent-runtime-context.json"
            context_file.write_text(
                json.dumps(_runtime_context(), ensure_ascii=False),
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {
                    "WBP_PROFILE_DIR": str(profile),
                    "WBP_MANAGED_DIR": str(managed),
                    "WBP_ACTIVE_PROJECT_ROOT": str(project),
                },
                clear=False,
            ), mock.patch(
                "wild_boar_proxy.api_agent_direct_reply.request_live_result",
                side_effect=lambda **kwargs: _live_result_from_kwargs(
                    "cli direct answer",
                    **kwargs,
                ),
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "direct-reply",
                            "--prompt",
                            "DIP: ответь.",
                            "--runtime-context-file",
                            str(context_file),
                            "--json",
                        ]
                    )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["packet_kind"], direct.API_AGENT_DIRECT_REPLY_PACKET_KIND)
        self.assertEqual(payload["direct_reply_text"], "cli direct answer")
        self.assertEqual(payload["dip_work_mode"], "standard")
        self.assertFalse(payload["dip_full_work_mode"])
        self.assertEqual(payload["active_project_root_source"], "server_runtime_env")
        self.assertTrue(payload["active_project_root_available"])
        self.assertTrue(payload["api_agent_direct_reply_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])

    def test_cli_direct_reply_routes_agent_2_alias(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            managed = root / "managed"
            project = root / "project"
            profile.mkdir()
            managed.mkdir()
            project.mkdir()
            context_file = profile / "wbp-agent-runtime-context.json"
            context_file.write_text(
                json.dumps(_runtime_context(), ensure_ascii=False),
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {
                    "WBP_PROFILE_DIR": str(profile),
                    "WBP_MANAGED_DIR": str(managed),
                    "WBP_ACTIVE_PROJECT_ROOT": str(project),
                },
                clear=False,
            ), mock.patch(
                "wild_boar_proxy.api_agent_direct_reply.request_live_result",
                side_effect=lambda **_kwargs: _live_result("agent 2 direct answer"),
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "direct-reply",
                            "--prompt",
                            "Agent 2: ответь.",
                            "--runtime-context-file",
                            str(context_file),
                            "--json",
                        ]
                    )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["selected_alias"], "Agent 2")
        self.assertEqual(payload["direct_reply_text"], "agent 2 direct answer")
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])

    def test_cli_direct_reply_proof_dir_writes_own_packet_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            managed = root / "managed"
            project = root / "project"
            proof_dir = root / "proof"
            profile.mkdir()
            managed.mkdir()
            project.mkdir()
            context_file = profile / "wbp-agent-runtime-context.json"
            context_file.write_text(
                json.dumps(_runtime_context(), ensure_ascii=False),
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {
                    "WBP_PROFILE_DIR": str(profile),
                    "WBP_MANAGED_DIR": str(managed),
                    "WBP_ACTIVE_PROJECT_ROOT": str(project),
                },
                clear=False,
            ), mock.patch(
                "wild_boar_proxy.api_agent_direct_reply.request_live_result",
                side_effect=lambda **_kwargs: _live_result("proof direct answer"),
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "direct-reply",
                            "--prompt",
                            "DIP: ответь.",
                            "--runtime-context-file",
                            str(context_file),
                            "--proof-dir",
                            str(proof_dir),
                            "--json",
                        ]
                    )
                output = stdout.getvalue()
                proof_file = proof_dir / direct.API_AGENT_DIRECT_REPLY_FILE_NAME
                persisted = json.loads(proof_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(output.splitlines()), 1)
        payload = json.loads(output)
        self.assertEqual(payload, persisted)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["direct_reply_text"], "proof direct answer")
        self.assertEqual(payload["effect"], "probe")
        self.assertFalse(payload["file_mutation_attempted"])
        self.assertTrue(payload["evidence_written"])
        self.assertFalse(payload["state_written"])
        self.assertTrue(payload["proof_file_written"])
        self.assertEqual(
            payload["changed_files"],
            [direct.API_AGENT_DIRECT_REPLY_FILE_NAME],
        )
        self.assertFalse(payload["proof_file_path_recorded"])
        self.assertFalse(payload["proof_dir_path_recorded"])
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])

    def test_cli_direct_reply_proof_dir_write_failure_returns_json_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            managed = root / "managed"
            project = root / "project"
            proof_file_path = root / "proof-file"
            profile.mkdir()
            managed.mkdir()
            project.mkdir()
            proof_file_path.write_text("not a directory", encoding="utf-8")
            context_file = profile / "wbp-agent-runtime-context.json"
            context_file.write_text(
                json.dumps(_runtime_context(), ensure_ascii=False),
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {
                    "WBP_PROFILE_DIR": str(profile),
                    "WBP_MANAGED_DIR": str(managed),
                    "WBP_ACTIVE_PROJECT_ROOT": str(project),
                },
                clear=False,
            ), mock.patch(
                "wild_boar_proxy.api_agent_direct_reply.request_live_result",
                side_effect=lambda **_kwargs: _live_result("proof direct answer"),
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "direct-reply",
                            "--prompt",
                            "DIP: ответь.",
                            "--runtime-context-file",
                            str(context_file),
                            "--proof-dir",
                            str(proof_file_path),
                            "--json",
                        ]
                    )

        self.assertEqual(exit_code, 1)
        output = stdout.getvalue()
        self.assertEqual(len(output.splitlines()), 1)
        payload = json.loads(output)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["machine_error_code"],
            "WBP_API_AGENT_DIRECT_REPLY_PROOF_WRITE_FAILED",
        )
        self.assertEqual(payload["effect"], "mutate")
        self.assertEqual(payload["changed_files"], [])


class ApiAgentDirectReplyCommandTests(unittest.TestCase):
    def test_run_command_uses_active_project_root_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile = root / "profile"
            managed = root / "managed"
            project = root / "project"
            profile.mkdir()
            managed.mkdir()
            project.mkdir()
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(_runtime_context(), ensure_ascii=False),
                encoding="utf-8",
            )
            seen: list[dict[str, object]] = []

            def runner(**kwargs: object) -> dict[str, object]:
                seen.append(dict(kwargs))
                return _live_result(
                    "env root answer",
                    active_project_root_required=False,
                    active_project_root_available=True,
                    active_project_root_source="server_runtime_env",
                    active_project_root_status="ok",
                    active_project_root_path_recorded=False,
                    active_project_root_sha256="abc",
                    active_project_root_is_wbp_repo=False,
                    active_project_root_git_available=False,
                    active_project_root_fallback_used=False,
                    active_project_root_legacy_target_repo_alias_used=False,
                )

            with mock.patch.dict(
                os.environ,
                {
                    "WBP_PROFILE_DIR": str(profile),
                    "WBP_MANAGED_DIR": str(managed),
                    "WBP_ACTIVE_PROJECT_ROOT": str(project),
                },
                clear=False,
            ):
                packet = direct.run_api_agent_direct_reply_command(
                    paths=RuntimePaths.from_env(),
                    prompt_text="DIP: ответь.",
                    live_result_runner=runner,
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(seen[0]["repo_root"], project.resolve(strict=False))
        self.assertEqual(seen[0]["target_repo_source"], "server_runtime_env")
        self.assertEqual(packet["active_project_root_source"], "server_runtime_env")
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_command_effect_is_probe_without_repo_bridge_and_mutate_with_repo_bridge(self) -> None:
        parser = cli.build_parser()
        probe_args = parser.parse_args(
            [
                "router-hook",
                "direct-reply",
                "--prompt",
                "DIP: ответь.",
                "--json",
            ]
        )
        mutate_args = parser.parse_args(
            [
                "router-hook",
                "direct-reply",
                "--prompt",
                "DIP: проверь репо.",
                "--repo-bridge",
                "on",
                "--json",
            ]
        )

        self.assertEqual(cli.command_effect_from_args(probe_args), "probe")
        self.assertEqual(cli.command_effect_from_args(mutate_args), "mutate")
        proof_args = parser.parse_args(
            [
                "router-hook",
                "direct-reply",
                "--prompt",
                "DIP: ответь.",
                "--proof-dir",
                "/tmp/wbp-proof",
                "--json",
            ]
        )
        self.assertEqual(cli.command_effect_from_args(proof_args), "mutate")


if __name__ == "__main__":
    unittest.main()
