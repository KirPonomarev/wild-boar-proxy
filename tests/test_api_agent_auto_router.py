import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
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
        self.assertFalse(packet["gpt_orchestrator_used"])
        self.assertTrue(packet["provider_auth_ok"])
        self.assertTrue(packet["positive_provider_proof_gate_satisfied"])
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
        self.assertFalse(packet["file_mutation_attempted"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_api_alias_address_matching_is_case_space_and_nfkc_insensitive(self) -> None:
        cases = [
            ("dip: ответь ровно OK", "DIP"),
            ("agent   2: answer exactly OK", "Agent 2"),
            ("\uff24\uff29\uff30: answer exactly OK", "DIP"),
            ("кодер: ответь ровно OK", "Кодер"),
            ("КОДЕР: answer exactly OK", "Кодер"),
        ]

        for prompt, expected_alias in cases:
            with self.subTest(prompt=prompt):
                calls: list[dict[str, object]] = []

                def runner(**kwargs: object) -> dict[str, object]:
                    calls.append(dict(kwargs))
                    return _live_result("OK")

                packet = auto.build_api_agent_auto_router_packet(
                    prompt_text=prompt,
                    runtime_context=_runtime_context(custom_alias="Кодер"),
                    context_file_metadata=_metadata(),
                    profile_dir=Path("/tmp/profile"),
                    active_project_root=_active_project_root_for_test(),
                    active_project_root_source="test_selected_active_project_root",
                    work_mode="full",
                    live_result_runner=runner,
                )

                self.assertEqual(packet["status"], "ok")
                self.assertEqual(packet["machine_error_code"], "OK")
                self.assertEqual(
                    packet["auto_router_decision"],
                    auto.AUTO_ROUTER_DECISION_API_DIRECT_REPLY,
                )
                self.assertTrue(packet["direct_reply_selected"])
                self.assertTrue(packet["direct_reply_proven"])
                self.assertEqual(packet["selected_alias"], expected_alias)
                self.assertEqual(packet["selected_alias_lane"], "api_route")
                self.assertEqual(packet["output_text"], "OK")
                self.assertTrue(packet["api_lane_called"])
                self.assertFalse(packet["chatgpt_lane_called"])
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0]["expected_alias"], expected_alias)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_primary_alias_address_matching_is_case_space_and_nfkc_insensitive(self) -> None:
        cases = [
            ("codex: ответь сам.", "Codex"),
            ("agent   1: answer yourself.", "Agent 1"),
            ("\uff23\uff4f\uff44\uff45\uff58: answer yourself.", "Codex"),
        ]

        for prompt, expected_alias in cases:
            with self.subTest(prompt=prompt):
                runner = mock.Mock(return_value=_live_result("must not run"))

                packet = auto.build_api_agent_auto_router_packet(
                    prompt_text=prompt,
                    runtime_context=_runtime_context(),
                    context_file_metadata=_metadata(),
                    profile_dir=Path("/tmp/profile"),
                    active_project_root=_active_project_root_for_test(),
                    active_project_root_source="test_selected_active_project_root",
                    live_result_runner=runner,
                )

                self.assertEqual(packet["status"], "ok")
                self.assertEqual(packet["machine_error_code"], "OK")
                self.assertEqual(packet["selected_alias"], expected_alias)
                self.assertEqual(packet["selected_alias_lane"], "primary_chatgpt")
                self.assertEqual(
                    packet["auto_router_decision"],
                    auto.AUTO_ROUTER_DECISION_GPT_LANE,
                )
                self.assertTrue(packet["gpt_lane_selected"])
                self.assertTrue(packet["gpt_passthrough_to_native_chat"])
                self.assertFalse(packet["direct_reply_selected"])
                self.assertFalse(packet["api_lane_called"])
                self.assertFalse(packet["chatgpt_lane_called"])
                runner.assert_not_called()
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_primary_alias_exact_reply_stays_native_without_local_visible_output(self) -> None:
        runner = mock.Mock(return_value=_live_result("must not run"))

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="Codex: answer exactly WBP_PRIMARY_EXACT_OK",
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["selected_alias"], "Codex")
        self.assertEqual(packet["selected_alias_lane"], "primary_chatgpt")
        self.assertEqual(packet["auto_router_decision"], auto.AUTO_ROUTER_DECISION_GPT_LANE)
        self.assertTrue(packet["gpt_lane_selected"])
        self.assertTrue(packet["gpt_passthrough_to_native_chat"])
        self.assertFalse(packet["direct_reply_selected"])
        self.assertFalse(packet["direct_reply_proven"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["chatgpt_lane_called"])
        self.assertTrue(packet["primary_exact_plain_reply_requested"])
        self.assertFalse(packet["primary_exact_plain_reply_visible_output"])
        self.assertEqual(packet["output_text"], "")
        self.assertFalse(packet["output_passthrough_required"])
        self.assertEqual(packet["output_passthrough_kind"], "")
        self.assertFalse(packet["output_passthrough_text_available"])
        self.assertFalse(packet["output_passthrough_text_recorded"])
        runner.assert_not_called()
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_runtime_context_renamed_alias_routes_and_removed_alias_fails_closed(self) -> None:
        renamed_context = _runtime_context()
        renamed_context["agent_bindings"][0]["display_name"] = "Планер"
        renamed_context["agent_bindings"][0]["aliases"] = ["Планер", "Planner"]
        renamed_context["agent_bindings"][1]["display_name"] = "Строитель"
        renamed_context["agent_bindings"][1]["aliases"] = ["Строитель", "Builder"]
        renamed_context["alias_to_agent_id"] = {
            "Планер": "codex",
            "Planner": "codex",
            "Строитель": "dip",
            "Builder": "dip",
        }

        calls: list[dict[str, object]] = []

        def runner(**kwargs: object) -> dict[str, object]:
            calls.append(dict(kwargs))
            return _live_result("renamed route ok")

        routed = auto.build_api_agent_auto_router_packet(
            prompt_text="builder: answer exactly RENAMED_OK",
            runtime_context=renamed_context,
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            work_mode="full",
            live_result_runner=runner,
        )

        self.assertEqual(routed["status"], "ok")
        self.assertEqual(routed["machine_error_code"], "OK")
        self.assertEqual(routed["selected_alias"], "Builder")
        self.assertEqual(routed["selected_alias_lane"], "api_route")
        self.assertEqual(routed["auto_router_decision"], auto.AUTO_ROUTER_DECISION_API_DIRECT_REPLY)
        self.assertEqual(routed["output_text"], "renamed route ok")
        self.assertTrue(routed["api_lane_called"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["expected_alias"], "Builder")

        removed = auto.build_api_agent_auto_router_packet(
            prompt_text="DIP: answer exactly SHOULD_NOT_ROUTE",
            runtime_context=renamed_context,
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            work_mode="full",
            live_result_runner=runner,
        )

        self.assertEqual(removed["status"], "error")
        self.assertEqual(removed["machine_error_code"], auto.API_AGENT_AUTO_ROUTER_UNKNOWN_ALIAS)
        self.assertEqual(removed["auto_router_decision"], auto.AUTO_ROUTER_DECISION_BLOCKED)
        self.assertTrue(removed["auto_router_fail_closed"])
        self.assertTrue(removed["auto_router_unknown_alias_blocked"])
        self.assertFalse(removed["api_lane_called"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(packets.inspect_command_packet_semantics(routed), [])
        self.assertEqual(packets.inspect_command_packet_semantics(removed), [])

    def test_api_alias_accepts_repo_bridge_verified_evidence_without_provider_call(
        self,
    ) -> None:
        text = (
            '{"status":"ok","changed_files":["tmp/agent2-en.txt"],'
            '"readback_ok":true}'
        )

        def runner(**kwargs: object) -> dict[str, object]:
            return _live_result(
                text,
                provider_called=False,
                source="repo_bridge_verified_evidence",
                direct_provider_auth_proven=False,
                direct_provider_response_observed=False,
                provider_auth_ok=False,
                positive_provider_proof_gate_satisfied=False,
                repo_bridge_required=True,
                repo_bridge_available=True,
                repo_bridge_used=True,
                dip_repo_tool_bridge_required=True,
                dip_repo_tool_bridge_available=True,
                dip_repo_tool_bridge_used=True,
                dip_action_bridge_required=True,
                dip_action_bridge_used=True,
                dip_action_bridge_succeeded=True,
                dip_action_tool_call_count=1,
                dip_action_successful_tool_call_count=1,
                dip_action_tool_names=["write_file"],
                dip_action_mutation_applied=True,
                dip_mutation_required=True,
                dip_mutation_written=True,
                dip_mutation_verified=True,
                dip_mutation_readback_verified=True,
                dip_action_mutated_files=["tmp/agent2-en.txt"],
                repo_bridge_final_answer_synthesized=True,
            )

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text=(
                "Agent 2: using the repo bridge, create file "
                "tmp/agent2-en.txt with text OK, read it back, and answer JSON."
            ),
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            repo_bridge_mode="auto",
            work_mode="full",
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["auto_router_proven"])
        self.assertTrue(packet["direct_reply_proven"])
        self.assertEqual(packet["output_text"], text)
        self.assertFalse(packet["api_agent_provider_called"])
        self.assertFalse(packet["api_agent_response_observed"])
        self.assertTrue(packet["repo_bridge_evidence_response_proven"])
        self.assertTrue(
            packet["reply_proof_summary"]["repo_bridge_evidence_response_proven"]
        )
        self.assertFalse(packet["api_lane_called"])
        self.assertEqual(packet["changed_files"], ["tmp/agent2-en.txt"])
        self.assertTrue(packet["repo_bridge_final_answer_synthesized"])
        self.assertTrue(packet["file_mutation_attempted"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])

    def test_api_alias_propagates_code_verification_failure_fields(self) -> None:
        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="DIP: почини баг и запусти тест.",
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            repo_bridge_mode="on",
            live_result_runner=lambda **_kwargs: _live_result(
                "",
                status="error",
                machine_error_code="WBP_DIP_TOOL_CODE_VERIFICATION_FAILED",
                result_available=False,
                result_text="",
                result_text_sha256="",
                result_text_length=0,
                dip_action_bridge_required=True,
                dip_action_bridge_used=True,
                dip_action_tests_run=True,
                dip_action_patch_applied=True,
                dip_code_mutation_required=True,
                dip_code_written=True,
                dip_code_verified=False,
                dip_code_verification_failed=True,
                dip_code_failed_verification_count=1,
                dip_action_mutated_files=["src/app.py"],
            ),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            "WBP_DIP_TOOL_CODE_VERIFICATION_FAILED",
        )
        self.assertTrue(packet["api_route_selected"])
        self.assertTrue(packet["direct_reply_selected"])
        self.assertTrue(packet["dip_code_written"])
        self.assertFalse(packet["dip_code_verified"])
        self.assertTrue(packet["dip_code_verification_failed"])
        self.assertEqual(packet["dip_code_failed_verification_count"], 1)
        self.assertEqual(packet["changed_files"], ["src/app.py"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_leading_api_alias_wins_over_alias_mentions_in_human_task_body(self) -> None:
        calls: list[dict[str, object]] = []

        def runner(**kwargs: object) -> dict[str, object]:
            calls.append(dict(kwargs))
            return _live_result("human coding task accepted")

        prompt = (
            "DIP: создай модуль, который распознает слова DIP, Agent 2, "
            "Codex и Кодер внутри пользовательского текста."
        )
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
        self.assertTrue(packet["auto_router_proven"])
        self.assertEqual(
            packet["auto_router_decision"],
            auto.AUTO_ROUTER_DECISION_API_DIRECT_REPLY,
        )
        self.assertEqual(packet["selected_alias"], "DIP")
        self.assertEqual(packet["parser_target_selection_rule"], "leading_address_alias")
        self.assertFalse(packet["auto_router_ambiguous_alias_blocked"])
        self.assertTrue(packet["api_lane_called"])
        self.assertEqual(packet["output_text"], "human coding task accepted")
        self.assertEqual(len(calls), 1)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unknown_leading_alias_ignores_known_alias_mentions_in_body(self) -> None:
        runner = mock.Mock(return_value=_live_result("must not run"))

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="DIPP: проверь, что строка DIP: внутри данных не меняет адресата.",
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            auto.API_AGENT_AUTO_ROUTER_UNKNOWN_ALIAS,
        )
        self.assertTrue(packet["auto_router_fail_closed"])
        self.assertTrue(packet["auto_router_unknown_alias_blocked"])
        self.assertFalse(packet["auto_router_ambiguous_alias_blocked"])
        self.assertFalse(packet["direct_reply_selected"])
        self.assertFalse(packet["api_lane_called"])
        runner.assert_not_called()
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
                repo_bridge_readonly=False,
                repo_bridge_mutation_allowed=True,
                repo_bridge_mutation_controlled=True,
                repo_bridge_bootstrap_used=True,
                repo_bridge_bootstrap_tool_call_count=1,
                repo_bridge_tool_call_count=2,
                repo_bridge_successful_tool_call_count=2,
                dip_evidence_trace_available=True,
                dip_evidence_trace_recorded=True,
                dip_evidence_trace_count=2,
                dip_evidence_trace=[
                    {
                        "step": 1,
                        "tool": "run_tests",
                        "origin": "wbp_bootstrap",
                        "status": "error",
                        "machine_error_code": "command_failed",
                        "command_exit_code": 1,
                        "result_text_sha256": "b" * 64,
                        "result_text": "raw output must not propagate",
                    },
                    {
                        "step": 2,
                        "tool": "read_file",
                        "origin": "model",
                        "status": "ok",
                        "machine_error_code": "OK",
                        "result_text_sha256": "c" * 64,
                    },
                ],
                dip_evidence_trace_raw_output_recorded=False,
                repo_bridge_raw_tool_results_recorded=False,
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
                dip_action_mutated_files=["calculator.py"],
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
        self.assertFalse(packet["repo_bridge_readonly"])
        self.assertTrue(packet["repo_bridge_mutation_allowed"])
        self.assertTrue(packet["repo_bridge_mutation_controlled"])
        self.assertTrue(packet["repo_bridge_bootstrap_used"])
        self.assertEqual(packet["repo_bridge_bootstrap_tool_call_count"], 1)
        self.assertEqual(packet["repo_bridge_tool_call_count"], 2)
        self.assertEqual(packet["repo_bridge_successful_tool_call_count"], 2)
        self.assertTrue(packet["dip_evidence_trace_available"])
        self.assertTrue(packet["dip_evidence_trace_recorded"])
        self.assertEqual(packet["dip_evidence_trace_count"], 2)
        self.assertEqual(packet["dip_evidence_trace"][0]["tool"], "run_tests")
        self.assertEqual(
            packet["dip_evidence_trace"][0]["machine_error_code"],
            "command_failed",
        )
        self.assertNotIn("result_text", packet["dip_evidence_trace"][0])
        self.assertFalse(packet["dip_evidence_trace_raw_output_recorded"])
        self.assertFalse(packet["repo_bridge_raw_tool_results_recorded"])
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
        self.assertEqual(packet["dip_action_mutated_files"], ["calculator.py"])
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
        prompts = [
            "Ghost: ответь.",
            "DIPP: ответь ровно SHOULD_NOT_ROUTE",
            "DIPP:ответь ровно SHOULD_NOT_ROUTE",
        ]

        for prompt in prompts:
            with self.subTest(prompt=prompt):
                runner = mock.Mock(return_value=_live_result("must not run"))

                packet = auto.build_api_agent_auto_router_packet(
                    prompt_text=prompt,
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
                self.assertNotEqual(packet["output_text"], "SHOULD_NOT_ROUTE")
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

    def test_cli_auto_route_output_reads_stdin_and_prints_passthrough_only(self) -> None:
        prompt = 'DIP: ответь ровно JSON {"status":"ok","quoted":"yes"}'
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
                "sys.stdin",
                io.StringIO(prompt + "\n"),
            ), mock.patch(
                "wild_boar_proxy.api_agent_direct_reply.request_live_result",
                side_effect=lambda **kwargs: _live_result_from_kwargs(
                    '{"status":"ok","quoted":"yes"}',
                    **kwargs,
                ),
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route-output",
                            "--runtime-context-file",
                            str(context_file),
                            "--active-project-root",
                            str(project),
                        ]
                    )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), '{"status":"ok","quoted":"yes"}\n')
        self.assertNotIn("packet_kind", stdout.getvalue())
        self.assertNotIn("DIP:", stdout.getvalue())

    def test_cli_auto_route_output_prints_proven_repo_bridge_output(self) -> None:
        prompt = "DIP: через repo bridge создай файл tmp/a.txt и ответь ровно WBP_MUTATION_OK"
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

            def live_result(**kwargs: object) -> dict[str, object]:
                work_mode = str(kwargs.get("dip_work_mode") or "standard")
                full = work_mode == "full"
                return _live_result(
                    "WBP_MUTATION_OK",
                    dip_work_mode=work_mode,
                    dip_full_work_mode=full,
                    live_result_text_limit=64000 if full else 2400,
                    live_result_output_token_limit=32768 if full else 768,
                    repo_bridge_required=True,
                    repo_bridge_available=True,
                    repo_bridge_used=True,
                    repo_bridge_final_answer_synthesized=True,
                    repo_bridge_mutation_controlled=True,
                    source="repo_bridge_verified_evidence",
                    provider_called=False,
                    direct_provider_response_observed=False,
                    provider_auth_ok=False,
                    positive_provider_proof_gate_satisfied=False,
                )

            with mock.patch.dict(
                os.environ,
                {
                    "WBP_PROFILE_DIR": str(profile),
                    "WBP_MANAGED_DIR": str(managed),
                    "WBP_ACTIVE_PROJECT_ROOT": str(project),
                },
                clear=False,
            ), mock.patch("sys.stdin", io.StringIO(prompt + "\n")), mock.patch(
                "wild_boar_proxy.api_agent_direct_reply.request_live_result",
                side_effect=live_result,
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route-output",
                            "--runtime-context-file",
                            str(context_file),
                            "--active-project-root",
                            str(project),
                        ]
                    )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "WBP_MUTATION_OK\n")
        self.assertNotIn("WBP_ROUTER_OUTPUT_NOT_AVAILABLE", stdout.getvalue())

    def test_cli_auto_route_output_can_write_proof_packet_without_polluting_stdout(self) -> None:
        expected = "WBP_ROUTER_PROOF_OK"
        prompt = f"DIP: ответь ровно {expected}"
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

            def live_result(**kwargs: object) -> dict[str, object]:
                work_mode = str(kwargs.get("dip_work_mode") or "standard")
                full = work_mode == "full"
                return _live_result(
                    expected,
                    dip_work_mode=work_mode,
                    dip_full_work_mode=full,
                    live_result_text_limit=64000 if full else 2400,
                    live_result_output_token_limit=32768 if full else 768,
                    exact_plain_reply_matched=True,
                    exact_plain_reply_expected_text_sha256=direct._sha256_text(expected),
                    exact_plain_reply_expected_text_recorded=False,
                    exact_plain_reply_observed_text_sha256=direct._sha256_text(expected),
                    exact_plain_reply_observed_text_recorded=False,
                )

            with mock.patch.dict(
                os.environ,
                {
                    "WBP_PROFILE_DIR": str(profile),
                    "WBP_MANAGED_DIR": str(managed),
                    "WBP_ACTIVE_PROJECT_ROOT": str(project),
                },
                clear=False,
            ), mock.patch("sys.stdin", io.StringIO(prompt + "\n")), mock.patch(
                "wild_boar_proxy.api_agent_direct_reply.request_live_result",
                side_effect=live_result,
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route-output",
                            "--runtime-context-file",
                            str(context_file),
                            "--active-project-root",
                            str(project),
                            "--proof-dir",
                            str(proof_dir),
                        ]
                    )
            proof_packet = json.loads(
                (proof_dir / auto.API_AGENT_AUTO_ROUTER_FILE_NAME).read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), f"{expected}\n")
        self.assertTrue(proof_packet["proof_file_written"])
        self.assertTrue(proof_packet["evidence_written"])
        self.assertTrue(proof_packet["auto_router_proven"])
        self.assertTrue(proof_packet["direct_reply_proven"])
        self.assertEqual(proof_packet["output_text"], expected)
        self.assertNotIn(auto.API_AGENT_AUTO_ROUTER_PACKET_KIND, stdout.getvalue())
        self.assertEqual(packets.inspect_command_packet_semantics(proof_packet), [])

    def test_cli_auto_route_output_prints_repo_bridge_readonly_evidence_reply(
        self,
    ) -> None:
        expected = "WBP_REPO_READ_EXACT_OK"
        prompt = (
            "DIP: через repo bridge read-only проверь CANON.md "
            f"и ответь ровно {expected}"
        )
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

            def live_result(**kwargs: object) -> dict[str, object]:
                work_mode = str(kwargs.get("dip_work_mode") or "standard")
                full = work_mode == "full"
                return _live_result(
                    expected,
                    dip_work_mode=work_mode,
                    dip_full_work_mode=full,
                    live_result_text_limit=64000 if full else 2400,
                    live_result_output_token_limit=32768 if full else 768,
                    source="repo_bridge_verified_evidence",
                    provider_called=False,
                    direct_provider_response_observed=False,
                    provider_auth_ok=False,
                    positive_provider_proof_gate_satisfied=False,
                    repo_bridge_required=True,
                    repo_bridge_available=True,
                    repo_bridge_used=True,
                    repo_bridge_readonly=True,
                    repo_bridge_mutation_allowed=False,
                    repo_bridge_mutation_controlled=False,
                    repo_bridge_bootstrap_used=True,
                    repo_bridge_bootstrap_tool_call_count=1,
                    repo_bridge_tool_call_count=1,
                    repo_bridge_successful_tool_call_count=1,
                    repo_bridge_tool_names=["read_file"],
                    repo_bridge_bootstrap_tool_names=["read_file"],
                    repo_bridge_final_answer_synthesized=True,
                )

            with mock.patch.dict(
                os.environ,
                {
                    "WBP_PROFILE_DIR": str(profile),
                    "WBP_MANAGED_DIR": str(managed),
                    "WBP_ACTIVE_PROJECT_ROOT": str(project),
                },
                clear=False,
            ), mock.patch("sys.stdin", io.StringIO(prompt + "\n")), mock.patch(
                "wild_boar_proxy.api_agent_direct_reply.request_live_result",
                side_effect=live_result,
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route-output",
                            "--runtime-context-file",
                            str(context_file),
                            "--active-project-root",
                            str(project),
                        ]
                    )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), f"{expected}\n")
        self.assertNotIn("WBP_ROUTER_OUTPUT_NOT_AVAILABLE", stdout.getvalue())

    def test_cli_auto_route_output_blocks_repo_bridge_provider_exact_without_strong_proof(
        self,
    ) -> None:
        expected = "WBP_REPO_PROVIDER_WEAK_EXACT"
        prompt = (
            "DIP: через repo bridge read-only проверь репозиторий "
            f"и ответь ровно {expected}"
        )
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

            def live_result(**kwargs: object) -> dict[str, object]:
                work_mode = str(kwargs.get("dip_work_mode") or "standard")
                full = work_mode == "full"
                return _live_result(
                    expected,
                    dip_work_mode=work_mode,
                    dip_full_work_mode=full,
                    live_result_text_limit=64000 if full else 2400,
                    live_result_output_token_limit=32768 if full else 768,
                    repo_bridge_required=True,
                    repo_bridge_available=True,
                    repo_bridge_used=True,
                    repo_bridge_readonly=True,
                    repo_bridge_mutation_allowed=False,
                    repo_bridge_mutation_controlled=False,
                    repo_bridge_bootstrap_used=True,
                    repo_bridge_bootstrap_tool_call_count=1,
                    repo_bridge_tool_call_count=1,
                    repo_bridge_successful_tool_call_count=1,
                    repo_bridge_tool_names=["list_files"],
                    repo_bridge_bootstrap_tool_names=["list_files"],
                    repo_bridge_final_answer_synthesized=False,
                    exact_plain_reply_matched=True,
                    exact_plain_reply_expected_text_sha256=auto._sha256_text(expected),
                    exact_plain_reply_expected_text_recorded=False,
                    exact_plain_reply_observed_text_sha256=auto._sha256_text(expected),
                    exact_plain_reply_observed_text_recorded=False,
                    direct_provider_response_observed=False,
                    positive_provider_proof_gate_satisfied=False,
                )

            with mock.patch.dict(
                os.environ,
                {
                    "WBP_PROFILE_DIR": str(profile),
                    "WBP_MANAGED_DIR": str(managed),
                    "WBP_ACTIVE_PROJECT_ROOT": str(project),
                },
                clear=False,
            ), mock.patch("sys.stdin", io.StringIO(prompt + "\n")), mock.patch(
                "wild_boar_proxy.api_agent_direct_reply.request_live_result",
                side_effect=live_result,
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route-output",
                            "--runtime-context-file",
                            str(context_file),
                            "--active-project-root",
                            str(project),
                        ]
                    )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "WBP_ROUTER_OUTPUT_NOT_AVAILABLE\n")
        self.assertNotIn(expected, stdout.getvalue())

    def test_cli_auto_route_output_blocks_non_exact_direct_reply_text(self) -> None:
        prompt = "Builder: через repo bridge read-only проверь CANON.md и верни короткий статус"
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
                json.dumps(_runtime_context(custom_alias="Builder"), ensure_ascii=False),
                encoding="utf-8",
            )

            def live_result(**kwargs: object) -> dict[str, object]:
                work_mode = str(kwargs.get("dip_work_mode") or "standard")
                full = work_mode == "full"
                return _live_result(
                    "WBP_DIRECT_TEXT_AVAILABLE_OK",
                    dip_work_mode=work_mode,
                    dip_full_work_mode=full,
                    live_result_text_limit=64000 if full else 2400,
                    live_result_output_token_limit=32768 if full else 768,
                    repo_bridge_required=True,
                    repo_bridge_available=True,
                    repo_bridge_used=True,
                    repo_bridge_readonly=True,
                    repo_bridge_mutation_allowed=False,
                    repo_bridge_mutation_controlled=False,
                    repo_bridge_bootstrap_used=True,
                    repo_bridge_bootstrap_tool_call_count=1,
                    repo_bridge_tool_call_count=1,
                    repo_bridge_successful_tool_call_count=1,
                    repo_bridge_tool_names=["read_file"],
                    repo_bridge_bootstrap_tool_names=["read_file"],
                    repo_bridge_final_answer_synthesized=False,
                )

            with mock.patch.dict(
                os.environ,
                {
                    "WBP_PROFILE_DIR": str(profile),
                    "WBP_MANAGED_DIR": str(managed),
                    "WBP_ACTIVE_PROJECT_ROOT": str(project),
                },
                clear=False,
            ), mock.patch("sys.stdin", io.StringIO(prompt + "\n")), mock.patch(
                "wild_boar_proxy.api_agent_direct_reply.request_live_result",
                side_effect=live_result,
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route-output",
                            "--runtime-context-file",
                            str(context_file),
                            "--active-project-root",
                            str(project),
                        ]
                    )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "WBP_ROUTER_OUTPUT_NOT_AVAILABLE\n")
        self.assertNotIn("WBP_DIRECT_TEXT_AVAILABLE_OK", stdout.getvalue())

    def test_cli_auto_route_output_prints_proven_non_exact_api_reply(self) -> None:
        prompt = "Builder: explain the selected implementation briefly"
        expected = "### Result\n\n```python\nprint('provider')\n```"
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
                json.dumps(_runtime_context(custom_alias="Builder"), ensure_ascii=False),
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
            ), mock.patch("sys.stdin", io.StringIO(prompt + "\n")), mock.patch(
                "wild_boar_proxy.api_agent_direct_reply.request_live_result",
                side_effect=lambda **kwargs: _live_result_from_kwargs(
                    expected,
                    **kwargs,
                ),
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route-output",
                            "--runtime-context-file",
                            str(context_file),
                            "--active-project-root",
                            str(project),
                        ]
                    )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), expected + "\n")

    def test_cli_auto_route_output_blocks_non_exact_reply_without_provider_proof(self) -> None:
        prompt = "DIP: explain the selected implementation briefly"
        expected = "must remain hidden"

        def unproven_live_result(**kwargs: object) -> dict[str, object]:
            result = _live_result_from_kwargs(expected, **kwargs)
            result["direct_provider_response_observed"] = False
            result["positive_provider_proof_gate_satisfied"] = False
            return result

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
            ), mock.patch("sys.stdin", io.StringIO(prompt + "\n")), mock.patch(
                "wild_boar_proxy.api_agent_direct_reply.request_live_result",
                side_effect=unproven_live_result,
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route-output",
                            "--runtime-context-file",
                            str(context_file),
                            "--active-project-root",
                            str(project),
                        ]
                    )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "WBP_ROUTER_OUTPUT_NOT_AVAILABLE\n")
        self.assertNotIn(expected, stdout.getvalue())

    def test_cli_auto_route_output_does_not_synthesize_primary_exact(self) -> None:
        prompt = "Codex: answer exactly WBP_PRIMARY_CLI_EXACT_OK"
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
            ), mock.patch("sys.stdin", io.StringIO(prompt + "\n")), mock.patch(
                "wild_boar_proxy.api_agent_direct_reply.request_live_result",
                side_effect=AssertionError("primary alias must not call API lane"),
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route-output",
                            "--runtime-context-file",
                            str(context_file),
                            "--active-project-root",
                            str(project),
                        ]
                    )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "WBP_ROUTER_OUTPUT_NOT_AVAILABLE\n")
        self.assertNotIn("Codex:", stdout.getvalue())

    def test_cli_auto_route_output_unknown_alias_prints_machine_code(self) -> None:
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
            ), mock.patch("sys.stdin", io.StringIO("DIPP: ответь ровно NOPE\n")):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route-output",
                            "--runtime-context-file",
                            str(context_file),
                            "--active-project-root",
                            str(project),
                        ]
                    )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "WBP_API_AGENT_AUTO_ROUTER_UNKNOWN_ALIAS\n")

    def test_cli_auto_route_progress_stderr_keeps_stdout_json_clean(self) -> None:
        def runner(**_kwargs: object) -> dict[str, object]:
            time.sleep(0.03)
            return {
                "exit_code": 0,
                "status": "ok",
                "machine_error_code": "OK",
            }

        with mock.patch(
            "wild_boar_proxy.cli.run_api_agent_auto_router_command",
            side_effect=runner,
        ):
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = cli.main(
                    [
                        "router-hook",
                        "auto-route",
                        "--prompt",
                        "DIP: ответь.",
                        "--progress-stderr",
                        "--progress-stderr-interval",
                        "0.01",
                        "--json",
                    ]
                )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertIn("WBP_ROUTER_PROGRESS auto-route", stderr.getvalue())
        self.assertNotIn("WBP_ROUTER_PROGRESS", stdout.getvalue())

    def test_cli_auto_route_enables_repo_bridge_for_explicit_prompt_phrase(self) -> None:
        calls: list[dict[str, object]] = []
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

            def runner(**kwargs: object) -> dict[str, object]:
                calls.append(dict(kwargs))
                return _live_result(
                    "cli repo bridge answer",
                    repo_bridge_required=True,
                    repo_bridge_available=True,
                    repo_bridge_used=True,
                    dip_repo_tool_bridge_required=True,
                    dip_repo_tool_bridge_available=True,
                    dip_repo_tool_bridge_used=True,
                    repo_bridge_context_pack_used=True,
                    repo_bridge_readonly=True,
                    repo_bridge_bootstrap_used=True,
                    repo_bridge_bootstrap_tool_call_count=1,
                    repo_bridge_tool_call_count=1,
                    repo_bridge_successful_tool_call_count=1,
                    repo_bridge_tool_names=["read_file"],
                    repo_bridge_bootstrap_tool_names=["read_file"],
                    dip_action_tool_names=[],
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
                side_effect=runner,
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route",
                            "--prompt",
                            "DIP: через repo bridge read-only проверь AGENTS.md.",
                            "--runtime-context-file",
                            str(context_file),
                            "--json",
                        ]
                    )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["auto_router_decision"], "api_direct_reply")
        self.assertEqual(payload["direct_reply_text"], "cli repo bridge answer")
        self.assertEqual(payload["requested_repo_bridge_mode"], "on")
        self.assertEqual(payload["repo_bridge_mode"], "on")
        self.assertTrue(payload["repo_bridge_required"])
        self.assertTrue(payload["repo_bridge_available"])
        self.assertTrue(payload["repo_bridge_used"])
        self.assertTrue(payload["active_project_root_required"])
        self.assertTrue(payload["target_repo_required"])
        self.assertEqual(payload["repo_bridge_tool_names"], ["read_file"])
        self.assertEqual(payload["repo_bridge_bootstrap_tool_names"], ["read_file"])
        self.assertEqual(payload["dip_action_tool_names"], [])
        self.assertEqual(payload["active_project_root_source"], "server_runtime_env")
        self.assertEqual(payload["effect"], "mutate")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["repo_bridge_mode"], "on")
        self.assertEqual(calls[0]["repo_root"], project.resolve(strict=False))
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])

    def test_cli_auto_route_promotes_explicit_repo_action_to_full_work_mode(self) -> None:
        calls: list[dict[str, object]] = []
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
                side_effect=lambda **kwargs: (
                    calls.append(dict(kwargs))
                    or _live_result_from_kwargs("cli action bridge answer", **kwargs)
                ),
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route",
                            "--prompt",
                            (
                                "DIP: через repo bridge read-only запусти "
                                "python3 -m pytest tests/test_wbp_dip_tool.py -q "
                                "и ответь JSON."
                            ),
                            "--runtime-context-file",
                            str(context_file),
                            "--json",
                        ]
                    )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["requested_repo_bridge_mode"], "on")
        self.assertEqual(payload["requested_work_mode"], "full")
        self.assertEqual(payload["repo_bridge_mode"], "on")
        self.assertEqual(payload["dip_work_mode"], "full")
        self.assertTrue(payload["dip_full_work_mode"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["repo_bridge_mode"], "on")
        self.assertEqual(calls[0]["dip_work_mode"], "full")
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])

    def test_cli_auto_route_promotes_natural_code_write_task_to_repo_full_mode(self) -> None:
        calls: list[dict[str, object]] = []
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
                json.dumps(_runtime_context(custom_alias="Кодер"), ensure_ascii=False),
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
                side_effect=lambda **kwargs: (
                    calls.append(dict(kwargs))
                    or _live_result_from_kwargs(
                        '{"status":"success","marker":"WBP_UH_ROUTER_CODE_OK"}',
                        **kwargs,
                    )
                ),
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route",
                            "--prompt",
                            (
                                "Кодер: обычным русским языком создай Python-модуль "
                                "tmp/wbp-ultrahard/router_natural/parser.py и тест "
                                "pytest, запусти pytest и верни JSON."
                            ),
                            "--runtime-context-file",
                            str(context_file),
                            "--json",
                        ]
                    )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["auto_router_decision"], "api_direct_reply")
        self.assertEqual(payload["requested_repo_bridge_mode"], "on")
        self.assertEqual(payload["requested_work_mode"], "full")
        self.assertEqual(payload["repo_bridge_mode"], "on")
        self.assertEqual(payload["dip_work_mode"], "full")
        self.assertTrue(payload["dip_full_work_mode"])
        self.assertTrue(payload["active_project_root_required"])
        self.assertEqual(payload["selected_alias"], "Кодер")
        self.assertEqual(payload["parser_target_selection_rule"], "leading_address_alias")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["repo_bridge_mode"], "on")
        self.assertEqual(calls[0]["dip_work_mode"], "full")
        self.assertEqual(calls[0]["repo_root"], project.resolve(strict=False))
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])

    def test_cli_auto_route_promotes_english_create_module_task_to_repo_full_mode(
        self,
    ) -> None:
        calls: list[dict[str, object]] = []
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
                side_effect=lambda **kwargs: (
                    calls.append(dict(kwargs))
                    or _live_result_from_kwargs(
                        '{"status":"success","marker":"WBP_UH_ROUTER_EN_CODE_OK"}',
                        **kwargs,
                    )
                ),
            ):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "router-hook",
                            "auto-route",
                            "--prompt",
                            (
                                "DIP: create a Python module in "
                                "tmp/wbp-ultrahard/router_en/parser.py and return JSON."
                            ),
                            "--runtime-context-file",
                            str(context_file),
                            "--json",
                        ]
                    )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["auto_router_decision"], "api_direct_reply")
        self.assertEqual(payload["requested_repo_bridge_mode"], "on")
        self.assertEqual(payload["requested_work_mode"], "full")
        self.assertEqual(payload["repo_bridge_mode"], "on")
        self.assertEqual(payload["dip_work_mode"], "full")
        self.assertTrue(payload["dip_full_work_mode"])
        self.assertTrue(payload["dip_action_bridge_required"])
        self.assertTrue(payload["dip_code_mutation_required"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["repo_bridge_mode"], "on")
        self.assertEqual(calls[0]["dip_work_mode"], "full")
        self.assertEqual(calls[0]["repo_root"], project.resolve(strict=False))
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])

    def test_auto_route_marks_exact_json_output_passthrough(self) -> None:
        result_text = json.dumps(
            {
                "status": "ok",
                "passed_count": 73,
                "subtests_count": 2,
                "command_used": "python3 -m pytest tests/test_wbp_dip_tool.py -q",
            },
            separators=(",", ":"),
        )

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text=(
                "DIP: через repo bridge read-only запусти python3 -m pytest "
                "tests/test_wbp_dip_tool.py -q и ответь ровно JSON с полями "
                "status, passed_count, subtests_count, command_used"
            ),
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            active_project_root=_active_project_root_for_test(),
            active_project_root_source="test_selected_active_project_root",
            live_result_runner=lambda **kwargs: _live_result_from_kwargs(
                result_text,
                **kwargs,
            ),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["output_text"], result_text)
        self.assertTrue(packet["output_passthrough_required"])
        self.assertEqual(packet["output_passthrough_kind"], "exact_json_reply")
        self.assertTrue(packet["output_passthrough_text_available"])
        self.assertFalse(packet["output_passthrough_text_recorded"])
        self.assertEqual(
            packet["output_passthrough_text_sha256"],
            auto._sha256_text(result_text),
        )
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

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
        self.assertFalse(payload["file_mutation_attempted"])
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
        natural_bridge_args = parser.parse_args(
            [
                "router-hook",
                "auto-route",
                "--prompt",
                "DIP: через repo bridge read-only проверь AGENTS.md.",
                "--json",
            ]
        )
        self.assertEqual(cli.command_effect_from_args(natural_bridge_args), "mutate")
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
