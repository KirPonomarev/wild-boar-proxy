# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest
from pathlib import Path

from wild_boar_proxy.provider_auth_strategy import (
    build_provider_auth_strategy_packet,
    classify_native_config_auth_surface,
    validate_provider_auth_strategy_packet,
)


AUTH_COMMAND = Path(__file__).resolve().parents[1] / "wbp_codex_auth_command.py"


def auth_command_config() -> str:
    return (
        'model = "gpt-5.4-mini"\n'
        'model_provider = "wbp"\n\n'
        "[model_providers.wbp]\n"
        'base_url = "http://127.0.0.1:8318/v1"\n'
        'wire_api = "responses"\n'
        "requires_openai_auth = false\n\n"
        "[model_providers.wbp.auth]\n"
        f'command = "{AUTH_COMMAND}"\n'
    )


def bearer_config(token: str = "fixture-token") -> str:
    return (
        'model = "gpt-5.4-mini"\n'
        'model_provider = "wbp"\n\n'
        "[model_providers.wbp]\n"
        'base_url = "http://127.0.0.1:8318/v1"\n'
        'wire_api = "responses"\n'
        "requires_openai_auth = false\n"
        f'experimental_bearer_token = "{token}"\n'
    )


class ProviderAuthStrategyTests(unittest.TestCase):
    def test_provider_auth_strategy_precedence_required(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            native_config_text=auth_command_config(),
        )

        self.assertEqual(packet["preferred_strategy"], "auth.command")
        self.assertEqual(packet["selected_strategy"], "auth.command")
        self.assertEqual(validate_provider_auth_strategy_packet(packet), [])

    def test_auth_command_is_preferred_strategy(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)

        auth_command = packet["auth_command"]
        self.assertTrue(auth_command["server_owned_path"])
        self.assertEqual(auth_command["output_shape"], "plain_token_stdout")
        self.assertEqual(auth_command["scope"], "owner_local_listener")
        self.assertFalse(auth_command["raw_upstream_secret"])
        self.assertFalse(auth_command["browser_supplied"])

    def test_experimental_bearer_token_requires_explicit_contract(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            native_config_text=bearer_config(),
            explicit_bearer_contract=False,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn(
            "experimental_bearer_token_without_explicit_contract",
            validate_provider_auth_strategy_packet(packet),
        )

    def test_bounded_bearer_fallback_redacts_secret(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            native_config_text=bearer_config(),
            explicit_bearer_contract=True,
        )

        self.assertEqual(packet["status"], "ok")
        serialized = json.dumps(packet)
        self.assertNotIn("fixture-token", serialized)
        self.assertIn("<redacted>", packet["native_config_auth_surface"]["redacted_config"])
        self.assertTrue(packet["fallbacks"]["bounded_local_bearer"]["allowed"])
        self.assertTrue(packet["fallbacks"]["bounded_local_bearer"]["temporary"])
        self.assertFalse(packet["fallbacks"]["bounded_local_bearer"]["silent_fallback_allowed"])

    def test_file_auth_cannot_satisfy_proxy_auth_contract(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)

        file_auth = packet["fallbacks"]["file_auth_separate_contour"]
        self.assertFalse(file_auth["allowed_in_this_contour"])
        self.assertTrue(file_auth["requires_separate_contour"])
        self.assertFalse(file_auth["can_satisfy_proxy_auth_contract"])

    def test_secret_redaction_for_provider_auth_packets(self) -> None:
        surface = classify_native_config_auth_surface(
            bearer_config(),
            explicit_bearer_contract=True,
        )

        self.assertTrue(surface["raw_secret_in_input_config"])
        self.assertFalse(surface["raw_secret_after_redaction"])
        self.assertNotIn("fixture-token", json.dumps(surface))

    def test_no_browser_authority_for_auth_strategy(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            browser_payload={"token": "sk-browser-forged", "model": "gpt-5.5"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("browser_auth_authority_detected", packet["failed_checks"])
        self.assertIn("token", packet["browser_authority"]["forbidden_fields"])
        self.assertIn("model", packet["browser_authority"]["forbidden_fields"])

    def test_auth_strategy_false_green_blocks_silent_fallback(self) -> None:
        packet = build_provider_auth_strategy_packet(
            auth_command_path=AUTH_COMMAND,
            native_config_text=bearer_config(),
            explicit_bearer_contract=False,
        )

        self.assertIn("experimental_bearer_token_without_explicit_contract", packet["failed_checks"])
        self.assertNotEqual(validate_provider_auth_strategy_packet(packet), [])

    def test_native_provider_config_does_not_silently_choose_bearer(self) -> None:
        surface = classify_native_config_auth_surface(
            bearer_config(),
            explicit_bearer_contract=True,
        )

        self.assertTrue(surface["experimental_bearer_token_configured"])
        self.assertTrue(surface["bounded_bearer_contract_explicit"])
        self.assertFalse(surface["silent_bearer_fallback_allowed"])
        self.assertEqual(surface["classification_scope"], "auth_surface_only")

    def test_auth_strategy_packet_marks_native_launch_not_attempted(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)

        self.assertFalse(packet["claims"]["native_launch_attempted"])
        self.assertFalse(packet["claims"]["native_safety_proven"])
        self.assertFalse(packet["claims"]["native_routing_proven"])
        self.assertFalse(packet["claims"]["native_ux_proven"])

    def test_auth_strategy_packet_marks_model_availability_not_proven(self) -> None:
        packet = build_provider_auth_strategy_packet(auth_command_path=AUTH_COMMAND)

        self.assertFalse(packet["claims"]["model_availability_proven"])
        self.assertFalse(packet["claims"]["account_pool_validity_proven"])
        self.assertFalse(packet["claims"]["direct_egress_absence_proven"])
        self.assertFalse(packet["claims"]["final_e2e_proven"])


if __name__ == "__main__":
    unittest.main()
