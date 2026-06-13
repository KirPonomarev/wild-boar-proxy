# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy.custom_agent_bindings import (
    agent_bindings_state_path,
    default_agent_bindings,
    dry_run_agent_bindings_packet,
    project_agent_bindings_for_runtime_context,
    read_agent_bindings_packet,
    resolve_alias_binding,
    write_agent_bindings_packet,
)


def route_records(route_id: str = "wbp-deepseek-chat") -> list[dict[str, object]]:
    return [
        {
            "route_id": route_id,
            "provider": "deepseek",
            "enabled": True,
            "auth": {"secret_ref": "DEEPSEEK_API_KEY"},
        }
    ]


class CustomAgentBindingTests(unittest.TestCase):
    def test_valid_bindings_project_aliases_and_routes_for_runtime_context(self) -> None:
        bindings = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )

        packet = dry_run_agent_bindings_packet(
            {"agent_bindings": bindings},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
        )
        projection = project_agent_bindings_for_runtime_context(
            packet["agent_bindings"],
            route_records=route_records(),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["alias_to_agent_id"]["DIP"], "dip")
        self.assertEqual(projection["agent_id_to_route"]["dip"], "wbp-deepseek-chat")
        self.assertEqual(projection["allowed_api_route_ids"], ["wbp-deepseek-chat"])
        self.assertEqual(projection["forbidden_stale_route_ids"], ["wbp-deepseek-v3"])
        self.assertFalse(packet["browser_can_supply_route_authority"])
        self.assertFalse(packet["browser_secret_intake"])

    def test_alias_resolution_accepts_manual_case_space_and_nfkc_variants(self) -> None:
        bindings = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )

        for alias in ("DIP", "dip", " DIP ", "Agent 2", "agent   2", "2", "\uff24\uff29\uff30"):
            with self.subTest(alias=alias):
                binding = resolve_alias_binding(bindings, alias)
                self.assertEqual(binding["agent_id"], "dip")
                self.assertEqual(binding["route_id"], "wbp-deepseek-chat")

        for alias in ("Codex", " codex ", "Agent   1", "\uff23\uff4f\uff44\uff45\uff58"):
            with self.subTest(alias=alias):
                binding = resolve_alias_binding(bindings, alias)
                self.assertEqual(binding["agent_id"], "codex")
                self.assertEqual(binding["model_id"], "gpt-5.5")

    def test_duplicate_alias_is_rejected(self) -> None:
        bindings = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )
        bindings[1]["aliases"] = ["DIP", "Codex"]

        packet = dry_run_agent_bindings_packet(
            {"agent_bindings": bindings},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_AGENT_BINDINGS_INVALID")
        self.assertIn("alias_duplicate:Codex", packet["blocking_reasons"])

    def test_nfkc_duplicate_alias_is_rejected(self) -> None:
        bindings = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )
        bindings[1]["aliases"] = ["DIP", "\uff24\uff29\uff30"]

        packet = dry_run_agent_bindings_packet(
            {"agent_bindings": bindings},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertIn("alias_duplicate:DIP", packet["blocking_reasons"])

    def test_hidden_alias_unknown_fields_and_non_string_values_are_rejected(self) -> None:
        hidden_alias = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )
        hidden_alias[1]["aliases"] = ["DIP\u200b"]
        unknown_field = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )
        unknown_field[1]["metadata"] = {"secret": "DEEPSEEK_API_KEY"}
        object_alias = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )
        object_alias[1]["aliases"] = [{"text": "DIP"}]
        string_enabled = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )
        string_enabled[1]["enabled"] = "false"

        hidden_packet = dry_run_agent_bindings_packet(
            {"agent_bindings": hidden_alias},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
        )
        unknown_packet = dry_run_agent_bindings_packet(
            {"agent_bindings": unknown_field},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
        )
        object_packet = dry_run_agent_bindings_packet(
            {"agent_bindings": object_alias},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
        )
        enabled_packet = dry_run_agent_bindings_packet(
            {"agent_bindings": string_enabled},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
        )

        self.assertIn("binding_1_alias_0_forbidden_codepoint", hidden_packet["blocking_reasons"])
        self.assertIn("binding_1_unknown_fields", unknown_packet["blocking_reasons"])
        self.assertIn("binding_1_alias_0_not_string", object_packet["blocking_reasons"])
        self.assertIn("binding_1_enabled_not_bool", enabled_packet["blocking_reasons"])
        self.assertEqual(hidden_packet["alias_to_agent_id"], {})
        self.assertEqual(unknown_packet["agent_id_to_route"], {})
        self.assertEqual(object_packet["allowed_api_route_ids"], [])

    def test_mixed_script_confusable_alias_is_rejected(self) -> None:
        mixed_cyrillic = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )
        mixed_cyrillic[0]["aliases"] = ["Agent 1", "\u0410gent 1"]
        all_cyrillic = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )
        all_cyrillic[0]["aliases"] = ["\u041a\u043e\u0434\u0435\u043a\u0441", "1"]

        mixed_packet = dry_run_agent_bindings_packet(
            {"agent_bindings": mixed_cyrillic},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
        )
        cyrillic_packet = dry_run_agent_bindings_packet(
            {"agent_bindings": all_cyrillic},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
        )

        self.assertEqual(mixed_packet["status"], "rejected")
        self.assertIn("alias_confusable_mixed_script:\u0410gent 1", mixed_packet["blocking_reasons"])
        self.assertEqual(cyrillic_packet["status"], "ok")

    def test_stale_and_unknown_routes_are_rejected(self) -> None:
        stale = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-v3",
        )
        unknown = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-unknown-route",
        )

        stale_packet = dry_run_agent_bindings_packet(
            {"agent_bindings": stale},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
        )
        unknown_packet = dry_run_agent_bindings_packet(
            {"agent_bindings": unknown},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
        )

        self.assertIn("binding_1_route_id_stale", stale_packet["blocking_reasons"])
        self.assertIn(
            "binding_1_route_id_not_server_issued",
            unknown_packet["blocking_reasons"],
        )

    def test_api_route_bindings_require_server_route_registry(self) -> None:
        bindings = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )

        packet = dry_run_agent_bindings_packet(
            {"agent_bindings": bindings},
            primary_model_ids=["gpt-5.5"],
            route_records=[],
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_AGENT_BINDINGS_INVALID")
        self.assertIn(
            "binding_1_route_registry_unavailable",
            packet["blocking_reasons"],
        )

    def test_api_route_bindings_require_enabled_server_route(self) -> None:
        bindings = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )

        packet = dry_run_agent_bindings_packet(
            {"agent_bindings": bindings},
            primary_model_ids=["gpt-5.5"],
            route_records=[
                {
                    "route_id": "wbp-deepseek-chat",
                    "provider": "deepseek",
                    "enabled": False,
                    "auth": {"secret_ref": "DEEPSEEK_API_KEY"},
                }
            ],
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertIn("binding_1_route_id_disabled", packet["blocking_reasons"])
        self.assertEqual(packet["allowed_api_route_ids"], [])

    def test_chatgpt_plus_api_bindings_require_enabled_api_agent(self) -> None:
        disabled_api = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )
        disabled_api[1]["enabled"] = False
        primary_only = [disabled_api[0]]

        disabled_packet = dry_run_agent_bindings_packet(
            {"agent_bindings": disabled_api},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
            require_api_route_binding=True,
        )
        primary_only_packet = dry_run_agent_bindings_packet(
            {"agent_bindings": primary_only},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
            require_api_route_binding=True,
        )
        projection = project_agent_bindings_for_runtime_context(
            disabled_packet["agent_bindings"],
            route_records=route_records(),
        )

        self.assertEqual(disabled_packet["status"], "rejected")
        self.assertIn("api_route_enabled_binding_missing", disabled_packet["blocking_reasons"])
        self.assertIn("api_route_enabled_binding_missing", primary_only_packet["blocking_reasons"])
        self.assertNotIn("DIP", projection["alias_to_agent_id"])
        self.assertNotIn("dip", projection["agent_id_to_route"])
        self.assertEqual(projection["allowed_api_route_ids"], [])

    def test_lane_specific_model_and_route_fields_are_rejected(self) -> None:
        bindings = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )
        bindings[0]["route_id"] = "wbp-deepseek-chat"
        bindings[1]["model_id"] = "gpt-5.5"

        packet = dry_run_agent_bindings_packet(
            {"agent_bindings": bindings},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertIn("binding_0_route_id_wrong_lane", packet["blocking_reasons"])
        self.assertIn("binding_1_model_id_wrong_lane", packet["blocking_reasons"])

    def test_forbidden_backend_and_secret_fields_are_rejected(self) -> None:
        bindings = default_agent_bindings(
            primary_model_id="gpt-5.5",
            api_route_id="wbp-deepseek-chat",
        )
        bindings[1]["base_url"] = "https://example.invalid/v1"
        bindings[1]["secret_ref"] = "DEEPSEEK_API_KEY"

        packet = dry_run_agent_bindings_packet(
            {"agent_bindings": bindings},
            primary_model_ids=["gpt-5.5"],
            route_records=route_records(),
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertIn("binding_1_forbidden_fields", packet["blocking_reasons"])
        self.assertFalse(packet["browser_backend_intake"])
        self.assertFalse(packet["browser_secret_intake"])

    def test_write_and_read_bindings_use_managed_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            managed_dir = Path(temp_dir) / "managed"
            path = agent_bindings_state_path(managed_dir)
            bindings = default_agent_bindings(
                primary_model_id="gpt-5.5",
                api_route_id="wbp-deepseek-chat",
            )

            written = write_agent_bindings_packet(
                path,
                {"agent_bindings": bindings},
                primary_model_ids=["gpt-5.5"],
                route_records=route_records(),
            )
            read_back = read_agent_bindings_packet(
                path,
                default_bindings=[],
                primary_model_ids=["gpt-5.5"],
                route_records=route_records(),
            )

        self.assertEqual(written["status"], "ok")
        self.assertEqual(written["changed_files"], [str(path)])
        self.assertTrue(written["state_path_redacted"])
        self.assertEqual(read_back["source"], "persisted_state")
        self.assertEqual(read_back["alias_to_agent_id"]["DIP"], "dip")

    def test_invalid_persisted_state_blocks_instead_of_falling_back(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            managed_dir = Path(temp_dir) / "managed"
            managed_dir.mkdir(parents=True)
            path = agent_bindings_state_path(managed_dir)
            path.write_text("{not-json", encoding="utf-8")

            packet = read_agent_bindings_packet(
                path,
                default_bindings=default_agent_bindings(
                    primary_model_id="gpt-5.5",
                    api_route_id="wbp-deepseek-chat",
                ),
                primary_model_ids=["gpt-5.5"],
                route_records=route_records(),
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_AGENT_BINDINGS_STATE_INVALID")
        self.assertEqual(packet["source"], "persisted_state")
        self.assertTrue(packet["state_file_present"])
        self.assertEqual(packet["agent_bindings"], [])
