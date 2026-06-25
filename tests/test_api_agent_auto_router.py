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
        self.assertEqual(packet["direct_reply_text"], "DIP direct block")
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
        self.assertTrue(packet["active_project_root_required"])
        self.assertTrue(packet["active_project_root_available"])
        self.assertFalse(packet["active_project_root_path_recorded"])
        self.assertTrue(packet["target_repo_required"])
        self.assertTrue(packet["target_repo_available"])
        self.assertFalse(packet["target_repo_path_recorded"])
        self.assertEqual(packet["target_repo_source"], "test_selected_active_project_root")
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_api_alias_blocks_without_active_project_root_before_provider_call(self) -> None:
        runner = mock.Mock(return_value=_live_result("must not run"))

        packet = auto.build_api_agent_auto_router_packet(
            prompt_text="DIP: ответь коротко.",
            runtime_context=_runtime_context(),
            context_file_metadata=_metadata(),
            profile_dir=Path("/tmp/profile"),
            live_result_runner=runner,
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "active_project_root_missing")
        self.assertTrue(packet["auto_router_fail_closed"])
        self.assertTrue(packet["direct_reply_selected"])
        self.assertFalse(packet["direct_reply_proven"])
        self.assertFalse(packet["api_lane_called"])
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
        self.assertEqual(seen_aliases, ["Кодер"])
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

    def test_cli_auto_route_uses_runtime_context_file_and_full_mode_default(self) -> None:
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
                side_effect=lambda **_kwargs: _live_result("cli auto answer"),
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
        self.assertEqual(payload["repo_bridge_mode"], "off")
        self.assertEqual(payload["active_project_root_source"], "server_runtime_env")
        self.assertTrue(payload["target_repo_available"])
        self.assertEqual(payload["effect"], "probe")
        self.assertTrue(payload["direct_reply_proven"])
        self.assertFalse(payload["tools_wbp_dip_invoked"])
        self.assertFalse(payload["dip_run_invoked"])
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])

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


if __name__ == "__main__":
    unittest.main()
