import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import api_agent_auto_router as auto
from wild_boar_proxy import api_agent_direct_reply as direct
from wild_boar_proxy import cli
from wild_boar_proxy import natural_intent_contract as intent
from wild_boar_proxy.core import packets


ROUTE_ID = "wbp-deepseek-v4-pro-max"


def _active_project_root_for_test() -> Path:
    return Path(tempfile.gettempdir()).resolve(strict=False)


def _runtime_context(
    *,
    custom_alias: str | None = None,
    allowed_routes: list[str] | None = None,
) -> dict[str, object]:
    allowed = [ROUTE_ID] if allowed_routes is None else allowed_routes
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
        "allowed_api_route_ids": allowed,
        "route_providers": {ROUTE_ID: "deepseek"},
        "forbidden_stale_route_ids": ["wbp-deepseek-v3"],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _metadata() -> dict[str, object]:
    return {
        "runtime_context_file_present": True,
        "runtime_context_file_read": True,
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


class ApiAgentAutoRouterTests(unittest.TestCase):
    def test_api_alias_uses_direct_reply_without_wrapper_paths(self) -> None:
        calls: list[dict[str, object]] = []

        def runner(**kwargs: object) -> dict[str, object]:
            calls.append(dict(kwargs))
            return _live_result("DIP direct block")

        prompt = "DIP: ответь коротко."
        packet = auto.build_api_agent_auto_router_packet(
            prompt_text=prompt,
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            work_mode="full",
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["packet_kind"], auto.API_AGENT_AUTO_ROUTER_PACKET_KIND)
        self.assertTrue(packet["auto_router_proven"])
        self.assertEqual(
            packet["auto_router_decision"],
            auto.AUTO_ROUTER_DECISION_API_DIRECT_REPLY,
        )
        self.assertTrue(packet["direct_reply_selected"])
        self.assertTrue(packet["direct_reply_proven"])
        self.assertEqual(packet["selected_alias"], "DIP")
        self.assertEqual(packet["selected_alias_lane"], "api_route")
        self.assertEqual(packet["output_text"], "DIP direct block")
        self.assertEqual(packet["direct_reply_text"], "DIP direct block")
        self.assertTrue(packet["direct_api_reply_block"])
        self.assertEqual(packet["reply_block_kind"], "api_agent_direct_reply")
        self.assertEqual(packet["reply_author_alias"], "DIP")
        self.assertEqual(packet["reply_agent_id"], "dip")
        self.assertEqual(packet["reply_lane"], "api_route")
        self.assertEqual(packet["reply_provider_label"], "deepseek")
        self.assertEqual(packet["reply_text"], "DIP direct block")
        self.assertFalse(packet["reply_proof_summary"]["tools_wbp_dip_invoked"])
        self.assertFalse(packet["reply_proof_summary"]["dip_run_invoked"])
        self.assertFalse(
            packet["reply_proof_summary"]["final_answer_was_repo_tool_call"]
        )
        self.assertTrue(packet["api_lane_called"])
        self.assertFalse(packet["chatgpt_lane_called"])
        self.assertFalse(packet["codex_exec_invoked"])
        self.assertFalse(packet["tools_wbp_dip_invoked"])
        self.assertFalse(packet["dip_run_invoked"])
        self.assertFalse(packet["wrapper_shopping_used"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["selected_api_route_id_recorded"])
        self.assertFalse(packet["active_project_root_legacy_target_repo_alias_used"])
        encoded = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(prompt, encoded)
        self.assertNotIn(ROUTE_ID, encoded)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["expected_alias"], "DIP")
        self.assertEqual(calls[0]["dip_work_mode"], "full")
        self.assertEqual(calls[0]["repo_bridge_mode"], "off")
        self.assertEqual(calls[0]["repo_root"], _active_project_root_for_test())
        self.assertFalse(packet["active_project_root_required"])
        self.assertTrue(packet["active_project_root_available"])
        self.assertFalse(packet["active_project_root_path_recorded"])
        self.assertFalse(packet["target_repo_required"])
        self.assertTrue(packet["target_repo_available"])
        self.assertFalse(packet["target_repo_path_recorded"])
        self.assertEqual(packet["target_repo_source"], "test_selected_active_project_root")
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_api_alias_allows_missing_active_project_root_for_plain_reply(self) -> None:
        calls: list[dict[str, object]] = []

        def runner(**kwargs: object) -> dict[str, object]:
            calls.append(dict(kwargs))
            return _live_result("plain direct block")

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="DIP: ответь коротко.",
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertFalse(packet["auto_router_fail_closed"])
        self.assertTrue(packet["direct_reply_selected"])
        self.assertTrue(packet["direct_reply_proven"])
        self.assertTrue(packet["api_lane_called"])
        self.assertEqual(packet["direct_reply_text"], "plain direct block")
        self.assertFalse(packet["active_project_root_required"])
        self.assertFalse(packet["active_project_root_available"])
        self.assertFalse(packet["target_repo_available"])
        self.assertFalse(packet["target_repo_required"])
        self.assertEqual(len(calls), 1)
        self.assertIsNone(calls[0]["repo_root"])
        self.assertEqual(calls[0]["repo_bridge_mode"], "off")
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_api_alias_blocks_without_active_project_root_when_repo_bridge_on(self) -> None:
        runner = mock.Mock(return_value=_live_result("must not run"))

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="DIP: прочитай AGENTS.md.",
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            repo_bridge_mode="on",
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "active_project_root_missing")
        self.assertTrue(packet["auto_router_fail_closed"])
        self.assertTrue(packet["direct_reply_selected"])
        self.assertFalse(packet["direct_reply_proven"])
        self.assertFalse(packet["api_lane_called"])
        self.assertTrue(packet["active_project_root_required"])
        self.assertFalse(packet["active_project_root_available"])
        self.assertFalse(packet["target_repo_available"])
        runner.assert_not_called()
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_custom_api_alias_from_runtime_context_uses_direct_reply(self) -> None:
        seen_aliases: list[str] = []

        def runner(**kwargs: object) -> dict[str, object]:
            seen_aliases.append(str(kwargs["expected_alias"]))
            return _live_result("custom direct block")

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="Кодер: проверь контракт.",
            runtime_context=_runtime_context(custom_alias="Кодер"),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["selected_alias"], "Кодер")
        self.assertEqual(packet["selected_slot"], "dip")
        self.assertEqual(packet["direct_reply_text"], "custom direct block")
        self.assertEqual(packet["reply_author_alias"], "Кодер")
        self.assertEqual(packet["reply_agent_id"], "dip")
        self.assertEqual(packet["reply_text"], "custom direct block")
        self.assertEqual(seen_aliases, ["Кодер"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_auto_router_preserves_repo_bridge_flags_from_direct_reply_packet(self) -> None:
        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="DIP: прочитай AGENTS.md.",
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
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
        self.assertEqual(packet["auto_router_decision"], "api_direct_reply")
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
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_codex_alias_selects_gpt_lane_without_api_call(self) -> None:
        runner = mock.Mock(return_value=_live_result("must not run"))

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="Codex: ответь сам.",
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["auto_router_decision"],
            auto.AUTO_ROUTER_DECISION_GPT_LANE,
        )
        self.assertTrue(packet["gpt_lane_selected"])
        self.assertTrue(packet["gpt_passthrough_to_native_chat"])
        self.assertFalse(packet["direct_reply_selected"])
        self.assertEqual(packet["dispatch_status"], "not_attempted")
        self.assertFalse(packet["dispatch_attempted"])
        self.assertFalse(packet["dispatch_proven"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["chatgpt_lane_called"])
        runner.assert_not_called()
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_codex_alias_passthrough_does_not_require_active_project_root(self) -> None:
        runner = mock.Mock(return_value=_live_result("must not run"))

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="Codex: ответь сам.",
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["auto_router_decision"],
            auto.AUTO_ROUTER_DECISION_GPT_LANE,
        )
        self.assertTrue(packet["gpt_lane_selected"])
        self.assertTrue(packet["gpt_passthrough_to_native_chat"])
        self.assertFalse(packet["direct_reply_selected"])
        self.assertFalse(packet["active_project_root_required"])
        self.assertFalse(packet["active_project_root_available"])
        self.assertEqual(packet["active_project_root_status"], "active_project_root_missing")
        self.assertFalse(packet["target_repo_required"])
        self.assertFalse(packet["target_repo_available"])
        self.assertFalse(packet["api_lane_called"])
        runner.assert_not_called()
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_plain_prompt_passes_to_gpt_without_api_call(self) -> None:
        runner = mock.Mock(return_value=_live_result("must not run"))

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="Сделай краткий план без второго агента.",
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            repo_bridge_mode="on",
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["auto_router_decision"],
            auto.AUTO_ROUTER_DECISION_GPT_PASSTHROUGH,
        )
        self.assertTrue(packet["gpt_lane_selected"])
        self.assertTrue(packet["gpt_passthrough_to_native_chat"])
        self.assertFalse(packet["direct_reply_selected"])
        self.assertEqual(packet["dispatch_status"], "not_attempted")
        self.assertFalse(packet["dispatch_attempted"])
        self.assertFalse(packet["dispatch_proven"])
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["requested_repo_bridge_mode"], "on")
        runner.assert_not_called()
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_plain_prompt_with_natural_colon_passes_to_gpt_without_api_call(self) -> None:
        runner = mock.Mock(return_value=_live_result("must not run"))

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="Скажи коротко: GPT lane sanity check.",
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["auto_router_decision"],
            auto.AUTO_ROUTER_DECISION_GPT_PASSTHROUGH,
        )
        self.assertTrue(packet["gpt_lane_selected"])
        self.assertTrue(packet["gpt_passthrough_to_native_chat"])
        self.assertFalse(packet["leading_address_label_unknown_alias_candidate"])
        self.assertFalse(packet["direct_reply_selected"])
        self.assertFalse(packet["api_lane_called"])
        runner.assert_not_called()
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unknown_leading_alias_fails_closed_without_api_call(self) -> None:
        runner = mock.Mock(return_value=_live_result("must not run"))

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="Ghost: ответь.",
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            auto.API_AGENT_AUTO_ROUTER_UNKNOWN_ALIAS,
        )
        self.assertTrue(packet["auto_router_fail_closed"])
        self.assertTrue(packet["auto_router_unknown_alias_blocked"])
        self.assertTrue(packet["leading_address_label_unknown_alias_candidate"])
        self.assertFalse(packet["direct_reply_selected"])
        self.assertFalse(packet["api_lane_called"])
        runner.assert_not_called()
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_disallowed_api_route_fails_closed_without_provider_call(self) -> None:
        runner = mock.Mock(return_value=_live_result("must not run"))

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="DIP: ответь.",
            runtime_context=_runtime_context(allowed_routes=["wbp-other-route"]),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], intent.FAIL_ROUTE_NOT_ALLOWED)
        self.assertTrue(packet["auto_router_fail_closed"])
        self.assertFalse(packet["direct_reply_selected"])
        self.assertFalse(packet["api_lane_called"])
        self.assertIn(intent.FAIL_ROUTE_NOT_ALLOWED, packet["blocking_reasons"])
        runner.assert_not_called()
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_runtime_context_reports_fail_alias_context_missing(self) -> None:
        runner = mock.Mock(return_value=_live_result("must not run"))

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="DIP: ответь.",
            runtime_context={},
            context_file_metadata={
                "runtime_context_file_present": False,
                "runtime_context_file_read": False,
            },
            profile_dir=Path("/tmp/profile"),
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], intent.FAIL_ALIAS_CONTEXT_MISSING)
        self.assertTrue(packet["auto_router_fail_closed"])
        self.assertFalse(packet["auto_router_unknown_alias_blocked"])
        self.assertFalse(packet["direct_reply_selected"])
        self.assertIn("alias_context_missing_or_invalid", packet["blocking_reasons"])
        runner.assert_not_called()
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_ambiguous_alias_fails_closed(self) -> None:
        runner = mock.Mock(return_value=_live_result("must not run"))
        ambiguous_parser_packet = {
            "status": "error",
            "packet_kind": "wbp_natural_intent_parser",
            "parser_status": intent.INTENT_AMBIGUOUS_NO_DISPATCH,
            "machine_error_code": intent.INTENT_AMBIGUOUS_NO_DISPATCH,
            "runtime_context_source": "server_launch_selection_packet",
            "runtime_context_present": True,
            "runtime_context_kind_valid": True,
            "alias_context_read": True,
            "natural_alias_command_detected": False,
            "natural_api_alias_command_detected": False,
            "alias_candidate": "",
            "lane_candidate": "",
            "slot_candidate": "",
            "parser_alias_match_count": 2,
            "forbidden_stale_route_ids_enforced": True,
            "forbidden_stale_route_ids_count": 1,
        }

        with mock.patch.object(
            auto,
            "build_natural_intent_parser_packet",
            return_value=ambiguous_parser_packet,
        ):
            packet = auto.build_api_agent_auto_router_packet(
                prompt_text="DIP Codex: ответь.",
                runtime_context=_runtime_context(),
                context_file_metadata=_metadata(),
                profile_dir=Path("/tmp/profile"),
                live_result_runner=runner,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            auto.API_AGENT_AUTO_ROUTER_AMBIGUOUS,
        )
        self.assertTrue(packet["auto_router_fail_closed"])
        self.assertTrue(packet["auto_router_ambiguous_alias_blocked"])
        self.assertFalse(packet["direct_reply_selected"])
        self.assertFalse(packet["api_lane_called"])
        self.assertIn("ambiguous_alias_intent", packet["blocking_reasons"])
        runner.assert_not_called()
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_auto_route_uses_runtime_context_file_and_standard_mode_default(self) -> None:
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
                    "cli auto answer",
                    **kwargs,
                ),
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route",
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
        self.assertEqual(payload["packet_kind"], auto.API_AGENT_AUTO_ROUTER_PACKET_KIND)
        self.assertEqual(payload["auto_router_decision"], "api_direct_reply")
        self.assertEqual(payload["direct_reply_text"], "cli auto answer")
        self.assertEqual(payload["dip_work_mode"], "standard")
        self.assertFalse(payload["dip_full_work_mode"])
        self.assertEqual(payload["repo_bridge_mode"], "off")
        self.assertEqual(payload["active_project_root_source"], "server_runtime_env")
        self.assertTrue(payload["target_repo_available"])
        self.assertEqual(payload["effect"], "probe")
        self.assertTrue(payload["direct_reply_proven"])
        self.assertFalse(payload["tools_wbp_dip_invoked"])
        self.assertFalse(payload["dip_run_invoked"])
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])

    def test_cli_auto_route_routes_agent_2_alias_to_direct_reply(self) -> None:
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
                side_effect=lambda **_kwargs: _live_result("agent 2 auto answer"),
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route",
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
        self.assertEqual(payload["auto_router_decision"], "api_direct_reply")
        self.assertEqual(payload["direct_reply_text"], "agent 2 auto answer")
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])

    def test_cli_auto_route_proof_dir_writes_auto_router_packet_only(self) -> None:
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
                side_effect=lambda **_kwargs: _live_result("proof auto answer"),
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route",
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
                proof_file = proof_dir / auto.API_AGENT_AUTO_ROUTER_FILE_NAME
                persisted = json.loads(proof_file.read_text(encoding="utf-8"))
                direct_reply_file_written = (
                    proof_dir / direct.API_AGENT_DIRECT_REPLY_FILE_NAME
                ).exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(output.splitlines()), 1)
        payload = json.loads(output)
        self.assertEqual(payload, persisted)
        self.assertFalse(direct_reply_file_written)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["auto_router_decision"], "api_direct_reply")
        self.assertEqual(payload["direct_reply_text"], "proof auto answer")
        self.assertEqual(payload["effect"], "mutate")
        self.assertTrue(payload["file_mutation_attempted"])
        self.assertTrue(payload["evidence_written"])
        self.assertFalse(payload["state_written"])
        self.assertTrue(payload["proof_file_written"])
        self.assertEqual(
            payload["changed_files"],
            [auto.API_AGENT_AUTO_ROUTER_FILE_NAME],
        )
        self.assertFalse(payload["proof_file_path_recorded"])
        self.assertFalse(payload["proof_dir_path_recorded"])
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])

    def test_cli_auto_route_proof_dir_write_failure_returns_json_error(self) -> None:
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
                side_effect=lambda **_kwargs: _live_result("proof auto answer"),
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route",
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
            "WBP_API_AGENT_AUTO_ROUTER_PROOF_WRITE_FAILED",
        )
        self.assertEqual(payload["effect"], "mutate")
        self.assertEqual(payload["changed_files"], [])

    def test_command_effect_is_probe_without_repo_bridge_and_mutate_with_repo_bridge(self) -> None:
        parser = cli.build_parser()
        probe_args = parser.parse_args(
            [
                "router-hook",
                "auto-route",
                "--prompt",
                "DIP: ответь.",
                "--json",
            ]
        )
        mutate_args = parser.parse_args(
            [
                "router-hook",
                "auto-route",
                "--prompt",
                "DIP: почини тест.",
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
                "auto-route",
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
