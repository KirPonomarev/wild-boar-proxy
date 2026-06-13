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
