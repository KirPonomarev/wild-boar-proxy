# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import os
import json
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from wild_boar_proxy import web_design_live_server as live_server
from wild_boar_proxy.ui_shell import CommandResult


class MappingRunner:
    def __init__(self, payloads: dict[tuple[str, ...], dict[str, object]]) -> None:
        self.payloads = payloads

    def run(self, *args: str) -> CommandResult:
        return CommandResult(payload=dict(self.payloads[args]), stderr="")


class CustomNativeRuntimeContextManagedDirTests(unittest.TestCase):
    def test_explicit_managed_dir_overrides_runtime_env_for_bindings(self) -> None:
        execution_packet = {
            "execution_mode": "chatgpt_plus_api",
            "chatgpt_model_id": "gpt-5.4",
            "api_model_id": "wbp-deepseek-v4-pro-max",
            "coding_agent_model_slot": {
                "status": "bound",
                "lane": live_server.API_ROUTE_MODEL_LANE,
                "model_id": "wbp-deepseek-v4-pro-max",
                "provider": "deepseek",
                "server_issued": True,
            },
        }
        route_records = [
            {
                "route_id": "wbp-deepseek-v4-pro-max",
                "provider": "deepseek",
                "enabled": True,
                "auth": {"secret_ref": "DEEPSEEK_API_KEY"},
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            explicit_managed_dir = root / "profile-managed"
            explicit_managed_dir.mkdir(parents=True)
            env_managed_dir = root / "wrong-managed"
            env_managed_dir.mkdir(parents=True)
            invalid_bindings = live_server.default_agent_bindings(
                primary_model_id="gpt-5.4",
                api_route_id="wbp-deepseek-v4-pro-max",
            )
            invalid_bindings[1]["aliases"] = ["DIP", "Codex"]
            live_server.agent_bindings_state_path(env_managed_dir).write_text(
                live_server.json.dumps(
                    {
                        "schema_version": 1,
                        "packet_kind": "codex_custom_agent_bindings_state",
                        "agent_bindings": invalid_bindings,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ,
                {"WBP_MANAGED_DIR": str(env_managed_dir)},
                clear=False,
            ):
                context = live_server._custom_native_agent_runtime_context(
                    execution_packet=execution_packet,
                    launch_model_id="gpt-5.4",
                    route_model_id="wbp-deepseek-v4-pro-max",
                    bridge_endpoint="http://127.0.0.1:50555/v1",
                    route_records=route_records,
                    managed_dir=explicit_managed_dir,
                )

        self.assertEqual(context["agent_binding_source"], "server_default")
        self.assertFalse(context["agent_binding_state_file_present"])
        self.assertEqual(context["agent_bindings_status"], "ok")
        self.assertEqual(
            context["primary_aliases"],
            ["Codex", "Agent 1", "1"],
        )
        self.assertEqual(
            context["coding_aliases"],
            ["DIP", "Agent 2", "2"],
        )
        self.assertEqual(
            context["allowed_api_route_ids"],
            ["wbp-deepseek-v4-pro-max"],
        )

    def test_owner_runtime_paths_fallback_to_legacy_owner_root_for_wbp_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            custom_profile = (
                root
                / "Library"
                / "Application Support"
                / "WildBoarProxy"
                / "CodexProfiles"
                / "wbp-custom-main"
            )
            custom_managed = custom_profile / "managed"
            custom_managed.mkdir(parents=True)
            (custom_profile / "config.toml").write_text(
                "\n".join(
                    [
                        'model = "gpt-5.4"',
                        'model_provider = "wbp"',
                        "",
                        "[model_providers.wbp]",
                        'base_url = "http://127.0.0.1:50555/v1"',
                        'experimental_bearer_token = "sk-cliproxy-test"',
                    ]
                ),
                encoding="utf-8",
            )
            legacy_profile = root / ".codex-custom-cli"
            legacy_managed = legacy_profile / "managed"
            legacy_managed.mkdir(parents=True)
            (legacy_profile / "config.toml").write_text(
                'model = "gpt-5.5"\nbase_url = "http://127.0.0.1:8318/v1"\n',
                encoding="utf-8",
            )
            (legacy_managed / "backend-registry.json").write_text(
                '{"backends":[]}\n',
                encoding="utf-8",
            )
            (legacy_managed / "supervisor-state.json").write_text(
                '{}\n',
                encoding="utf-8",
            )
            custom_paths = live_server.RuntimePaths.from_roots(
                profile_dir=custom_profile,
                managed_dir=custom_managed,
            )

            with mock.patch.dict(os.environ, {"HOME": str(root)}, clear=False):
                owner_paths = live_server._owner_runtime_paths_for_live_server(
                    custom_paths
                )

        self.assertEqual(owner_paths.profile_dir, legacy_profile)
        self.assertEqual(owner_paths.managed_dir, legacy_managed)
        self.assertEqual(
            owner_paths.config_toml,
            legacy_profile / "config.toml",
        )
        self.assertEqual(
            owner_paths.registry_file,
            legacy_managed / "backend-registry.json",
        )

    def test_build_handler_uses_owner_runtime_env_but_preserves_custom_profile_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            custom_profile = (
                root
                / "Library"
                / "Application Support"
                / "WildBoarProxy"
                / "CodexProfiles"
                / "wbp-custom-main"
            )
            custom_managed = custom_profile / "managed"
            custom_managed.mkdir(parents=True)
            (custom_profile / "config.toml").write_text(
                "\n".join(
                    [
                        'model = "gpt-5.4"',
                        'model_provider = "wbp"',
                        "",
                        "[model_providers.wbp]",
                        'base_url = "http://127.0.0.1:50555/v1"',
                        'experimental_bearer_token = "sk-cliproxy-test"',
                    ]
                ),
                encoding="utf-8",
            )
            legacy_profile = root / ".codex-custom-cli"
            legacy_managed = legacy_profile / "managed"
            legacy_managed.mkdir(parents=True)
            (legacy_profile / "config.toml").write_text(
                'model = "gpt-5.5"\nbase_url = "http://127.0.0.1:8318/v1"\n',
                encoding="utf-8",
            )
            (legacy_managed / "backend-registry.json").write_text(
                '{"backends":[]}\n',
                encoding="utf-8",
            )
            (legacy_managed / "supervisor-state.json").write_text(
                '{}\n',
                encoding="utf-8",
            )
            captured: dict[str, object] = {}

            class FakeRunner:
                def __init__(self, cwd: str | None = None, env: dict[str, str] | None = None):
                    captured["cwd"] = cwd
                    captured["env"] = dict(env or {})

            with mock.patch.dict(
                os.environ,
                {
                    "HOME": str(root),
                    "WBP_PROFILE_DIR": str(custom_profile),
                    "WBP_MANAGED_DIR": str(custom_managed),
                },
                clear=False,
            ), mock.patch.object(
                live_server,
                "JsonCommandRunner",
                side_effect=lambda *args, **kwargs: FakeRunner(**kwargs),
            ):
                live_server.build_handler(action_phase=live_server.FULL_ACTION_PHASE)

        self.assertEqual(captured["cwd"], str(legacy_profile))
        env = captured["env"]
        self.assertEqual(env["WBP_PROFILE_DIR"], str(legacy_profile))
        self.assertEqual(env["WBP_MANAGED_DIR"], str(legacy_managed))
        self.assertEqual(
            env["WBP_CONFIG_TOML"],
            str(legacy_profile / "config.toml"),
        )
        self.assertEqual(
            env["WBP_REGISTRY_FILE"],
            str(legacy_managed / "backend-registry.json"),
        )

    def test_build_handler_materializes_custom_runtime_context_when_owner_paths_differ(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            custom_profile = (
                root
                / "Library"
                / "Application Support"
                / "WildBoarProxy"
                / "CodexProfiles"
                / "wbp-custom-main"
            )
            custom_managed = custom_profile / "managed"
            custom_managed.mkdir(parents=True)
            (custom_profile / "config.toml").write_text(
                "\n".join(
                    [
                        'model = "gpt-5.4"',
                        'model_provider = "wbp"',
                        "",
                        "[model_providers.wbp]",
                        'base_url = "http://127.0.0.1:50555/v1"',
                        'experimental_bearer_token = "sk-cliproxy-test"',
                    ]
                ),
                encoding="utf-8",
            )
            legacy_profile = root / ".codex-custom-cli"
            legacy_managed = legacy_profile / "managed"
            legacy_external_models = legacy_managed / "external-models"
            legacy_external_models.mkdir(parents=True)
            (legacy_profile / "config.toml").write_text(
                'model = "gpt-5.5"\nbase_url = "http://127.0.0.1:8318/v1"\n',
                encoding="utf-8",
            )
            (legacy_managed / "backend-registry.json").write_text(
                '{"backends":[]}\n',
                encoding="utf-8",
            )
            (legacy_managed / "supervisor-state.json").write_text(
                '{}\n',
                encoding="utf-8",
            )
            route_id = "wbp-deepseek-v4-pro-max"
            live_server.agent_bindings_state_path(legacy_managed).write_text(
                live_server.json.dumps(
                    {
                        "schema_version": 1,
                        "packet_kind": "codex_custom_agent_bindings_state",
                        "agent_bindings": live_server.default_agent_bindings(
                            primary_model_id="gpt-5.5",
                            api_route_id=route_id,
                        ),
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            runner = MappingRunner(
                {
                    ("external-models", "routes", "list", "--json"): {
                        "status": "ok",
                        "exit_code": 0,
                        "machine_error_code": "OK",
                        "human_message": "Routes listed.",
                        "changed_files": [],
                        "next_action": "none",
                        "data": {
                            "routes": [
                                {
                                    "route_id": route_id,
                                    "provider": "deepseek",
                                    "enabled": True,
                                    "display_name": "DeepSeek V4 Pro Max",
                                    "upstream_model": "deepseek-v4-pro",
                                    "compatibility": "openai_chat_completions",
                                    "base_url": "https://api.deepseek.com/v1",
                                    "endpoint_path": "/chat/completions",
                                    "cost_class": "paid_or_free_limited",
                                    "lane_role": "candidate",
                                    "fallback_eligible": False,
                                    "auth": {
                                        "type": "bearer",
                                        "secret_ref": "DEEPSEEK_API_KEY",
                                    },
                                    "thinking": {
                                        "type": "enabled",
                                        "reasoning_effort": "max",
                                    },
                                }
                            ]
                        },
                    }
                }
            )

            with mock.patch.dict(
                os.environ,
                {
                    "HOME": str(root),
                    "WBP_PROFILE_DIR": str(custom_profile),
                    "WBP_MANAGED_DIR": str(custom_managed),
                },
                clear=False,
            ):
                live_server.build_handler(runner=runner)

            owner_context_path = legacy_profile / "wbp-agent-runtime-context.json"
            custom_context_path = custom_profile / "wbp-agent-runtime-context.json"
            required_target, optional_targets = (
                live_server._runtime_context_profile_targets_for_live_server(
                    custom_profile_paths=live_server.RuntimePaths.from_roots(
                        profile_dir=custom_profile,
                        managed_dir=custom_managed,
                    ),
                    owner_paths=live_server.RuntimePaths.from_roots(
                        profile_dir=legacy_profile,
                        managed_dir=legacy_managed,
                    ),
                )
            )
            self.assertEqual(required_target, custom_profile)
            self.assertEqual(optional_targets, [legacy_profile])
            self.assertTrue(owner_context_path.exists())
            self.assertTrue(custom_context_path.exists())
            owner_context = json.loads(owner_context_path.read_text(encoding="utf-8"))
            self.assertEqual(owner_context["primary_aliases"][0], "Codex")
            self.assertEqual(owner_context["coding_aliases"][0], "DIP")
            self.assertEqual(owner_context["allowed_api_route_ids"], [route_id])
            self.assertEqual(
                owner_context["agent_binding_truth_source"],
                "server_owned_agent_bindings",
            )
            self.assertEqual(
                json.loads(custom_context_path.read_text(encoding="utf-8")),
                owner_context,
            )


if __name__ == "__main__":
    unittest.main()
