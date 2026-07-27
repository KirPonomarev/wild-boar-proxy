# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import repeatable_proof_status as status
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_custom_codex_admission import (  # noqa: E402
    EXPECTED_TEXT,
    PROMPT,
    ROUTE_ID,
    _paths,
    _runtime_context,
    _write_profile,
)


def _hook_ready_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "status": "ok",
        "machine_error_code": "OK",
        "hook_enabled": True,
        "hook_config_present": True,
        "hook_config_digest_bound": True,
        "hook_script_executable": True,
        "hook_trusted": True,
        "product_ready": False,
        "blocking_reasons": [],
    }
    packet.update(overrides)
    return packet


def _provider_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "provider_lane_preflight_attempted": True,
        "provider_lane_available": True,
        "provider_lane_machine_error_code": "OK",
        "provider_lane_expected_text_observed": True,
        "provider_lane_expected_text_exact": True,
        "provider_lane_network_dependent": True,
        "provider_lane_runtime_context_bridge_used": False,
        "provider_lane_runtime_context_file_bridge_used": False,
        "provider_lane_fallback_used": False,
        "provider_lane_request_count": 1,
        "provider_lane_latency_ms": 12,
        "provider_lane_response_preview_recorded": False,
    }
    packet.update(overrides)
    return packet


def _fresh_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "packet_kind": "wbp_fresh_sealed_e2e_proof",
        "status": "ok",
        "machine_error_code": "OK",
        "proof_run_started_at_ns": 123,
        "fresh_sealed_e2e_proven": True,
        "user_prompt_submit_hook_ran": True,
        "api_lane_called": True,
        "dispatch_proven": True,
        "full_runtime_diagnostics_passed": True,
        "native_custom_codex_visible_flow_proven": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "product_ready": False,
        "blocking_reasons": [],
    }
    packet.update(overrides)
    return packet


def _metadata(*, present: bool = True) -> dict[str, object]:
    return {
        "fresh_proof_file_present": present,
        "fresh_proof_file_read": present,
        "fresh_proof_file_valid_json": present,
        "fresh_proof_file_mapping": present,
        "fresh_proof_file_path_recorded": False,
    }


def _context_metadata() -> dict[str, object]:
    return {
        "runtime_context_file_present": True,
        "runtime_context_file_read": True,
        "runtime_context_file_valid_json": True,
        "runtime_context_file_mapping": True,
        "runtime_context_file_path_recorded": False,
    }


def _status_packet(
    *,
    route_id: str = ROUTE_ID,
    route_allowed: bool = True,
    hook: dict[str, object] | None = None,
    provider: dict[str, object] | None = None,
    fresh: dict[str, object] | None = None,
    fresh_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    return status.build_repeatable_proof_status_packet(
        runtime_context=_runtime_context(),
        runtime_context_metadata=_context_metadata(),
        route_id=route_id,
        route_id_allowed=route_allowed,
        hook_readiness_packet=_hook_ready_packet() if hook is None else hook,
        provider_preflight=_provider_packet() if provider is None else provider,
        provider_failures=[],
        fresh_proof_packet=_fresh_packet() if fresh is None else fresh,
        fresh_proof_metadata=_metadata() if fresh_metadata is None else fresh_metadata,
        fresh_proof_file=None,
        secret_values=[EXPECTED_TEXT, ROUTE_ID, PROMPT],
    )


def _assert_no_raw_sensitive_text(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in (EXPECTED_TEXT, ROUTE_ID, PROMPT):
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["route_id_recorded"])
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["secret_value_exposed"])


class RepeatableProofStatusTests(unittest.TestCase):
    def test_router_ready_requires_hook_provider_and_fresh_proof(self) -> None:
        packet = _status_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["operator_status"], "router_ready")
        self.assertTrue(packet["router_ready"])
        self.assertFalse(packet["proof_only"])
        self.assertFalse(packet["blocked"])
        self.assertTrue(packet["user_prompt_submit_hook_ready"])
        self.assertTrue(packet["provider_health_ok"])
        self.assertTrue(packet["fresh_sealed_e2e_proven"])
        self.assertFalse(packet["provider_lane_preflight_is_dispatch_proof"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[EXPECTED_TEXT, ROUTE_ID, PROMPT],
            ),
            [],
        )

    def test_provider_health_without_fresh_proof_is_blocked(self) -> None:
        packet = _status_packet(
            fresh={},
            fresh_metadata=_metadata(present=False),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            status.REPEATABLE_PROOF_STATUS_BLOCKED,
        )
        self.assertEqual(packet["operator_status"], "blocked")
        self.assertFalse(packet["router_ready"])
        self.assertFalse(packet["fresh_sealed_e2e_proven"])
        self.assertTrue(packet["provider_health_ok"])
        self.assertTrue(packet["provider_health_ok_not_feature_ready"])
        self.assertIn("provider_health_ok_not_feature_ready", packet["blocking_reasons"])
        self.assertIn("fresh_proof_not_proven", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_fresh_proof_with_missing_current_preflight_is_proof_only(self) -> None:
        packet = _status_packet(
            provider=_provider_packet(
                provider_lane_preflight_attempted=False,
                provider_lane_available=False,
            ),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            status.REPEATABLE_PROOF_STATUS_PROOF_ONLY,
        )
        self.assertEqual(packet["operator_status"], "proof_only")
        self.assertFalse(packet["router_ready"])
        self.assertTrue(packet["proof_only"])
        self.assertTrue(packet["fresh_sealed_e2e_proven"])
        self.assertFalse(packet["provider_health_ok"])
        self.assertFalse(packet["product_ready"])

    def test_provider_marker_observed_but_not_exact_is_not_available(self) -> None:
        with mock.patch(
            "wild_boar_proxy.repeatable_proof_status.check_route_provider_once_no_write",
            return_value={
                "check_kind": "api_only_live_route_format",
                "route_state": "live_response_observed_no_write",
                "expected_text_observed": True,
                "response_text_length": len(EXPECTED_TEXT) + 1,
                "fallback_used": False,
                "network_dependent": True,
                "request_count": 1,
                "latency_ms": 7,
            },
        ):
            provider, failures = status._provider_preflight_packet(
                route_id=ROUTE_ID,
                expected_text=EXPECTED_TEXT,
                run_provider_preflight=True,
            )

        self.assertFalse(provider["provider_lane_available"])
        self.assertTrue(provider["provider_lane_expected_text_observed"])
        self.assertFalse(provider["provider_lane_expected_text_exact"])
        self.assertIn("provider_lane_preflight_failed", failures)

    def test_route_outside_runtime_context_blocks_router_ready(self) -> None:
        packet = _status_packet(route_allowed=False)

        self.assertEqual(packet["operator_status"], "proof_only")
        self.assertEqual(
            packet["machine_error_code"],
            status.REPEATABLE_PROOF_STATUS_PROOF_ONLY,
        )
        self.assertFalse(packet["router_ready"])
        self.assertFalse(packet["route_id_allowed"])
        self.assertIn(
            "route_id_not_allowed_by_runtime_context",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_fresh_proof_product_ready_overclaim_blocks(self) -> None:
        packet = _status_packet(fresh=_fresh_packet(product_ready=True))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["operator_status"], "blocked")
        self.assertFalse(packet["router_ready"])
        self.assertFalse(packet["fresh_sealed_e2e_proven"])
        self.assertIn("fresh_proof_product_ready_overclaim", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])

    def test_run_command_uses_runtime_context_allowlist_and_provider_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fresh_file = root / "fresh.packet.json"
            fresh_file.write_text(json.dumps(_fresh_packet()) + "\n", encoding="utf-8")
            with (
                mock.patch(
                    "wild_boar_proxy.repeatable_proof_status."
                    "build_user_prompt_submit_readiness_packet",
                    return_value=_hook_ready_packet(),
                ),
                mock.patch(
                    "wild_boar_proxy.repeatable_proof_status."
                    "check_route_provider_once_no_write",
                    return_value={
                        "check_kind": "api_only_live_route_format",
                        "route_state": "live_response_observed_no_write",
                        "expected_text_observed": True,
                        "response_text_length": len(EXPECTED_TEXT),
                        "fallback_used": False,
                        "network_dependent": True,
                        "request_count": 1,
                        "latency_ms": 7,
                    },
                ) as provider_check,
            ):
                packet = status.run_repeatable_proof_status_command(
                    paths=paths,
                    route_id=ROUTE_ID,
                    fresh_proof_file=str(fresh_file),
                    provider_expected_text=EXPECTED_TEXT,
                    run_provider_preflight=True,
                    external_models_dir=str(paths.managed_dir / "external-models"),
                )

        self.assertEqual(packet["operator_status"], "router_ready")
        self.assertTrue(packet["router_ready"])
        self.assertTrue(packet["route_id_allowed"])
        self.assertTrue(packet["provider_lane_preflight_attempted"])
        provider_check.assert_called_once()
        _assert_no_raw_sensitive_text(self, packet)

    def test_run_command_does_not_call_provider_for_route_outside_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(
                paths,
                runtime_context=_runtime_context(allowed_route_ids=["other-route"]),
            )
            fresh_file = root / "fresh.packet.json"
            fresh_file.write_text(json.dumps(_fresh_packet()) + "\n", encoding="utf-8")
            with (
                mock.patch(
                    "wild_boar_proxy.repeatable_proof_status."
                    "build_user_prompt_submit_readiness_packet",
                    return_value=_hook_ready_packet(),
                ),
                mock.patch(
                    "wild_boar_proxy.repeatable_proof_status."
                    "check_route_provider_once_no_write",
                ) as provider_check,
            ):
                packet = status.run_repeatable_proof_status_command(
                    paths=paths,
                    route_id=ROUTE_ID,
                    fresh_proof_file=str(fresh_file),
                    provider_expected_text=EXPECTED_TEXT,
                    run_provider_preflight=True,
                    external_models_dir=str(paths.managed_dir / "external-models"),
                )

        self.assertEqual(packet["operator_status"], "proof_only")
        self.assertEqual(
            packet["machine_error_code"],
            status.REPEATABLE_PROOF_STATUS_PROOF_ONLY,
        )
        self.assertFalse(packet["router_ready"])
        self.assertFalse(packet["route_id_allowed"])
        self.assertIn(
            "route_id_not_allowed_by_runtime_context",
            packet["blocking_reasons"],
        )
        provider_check.assert_not_called()
        _assert_no_raw_sensitive_text(self, packet)

    def test_cli_parses_status_as_probe_and_dispatches(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "codex-runner",
                "repeatable-proof-status",
                "--route",
                ROUTE_ID,
                "--fresh-proof-file",
                "fresh.json",
                "--run-provider-preflight",
                "--external-models-dir",
                "external",
                "--provider-expected-text",
                EXPECTED_TEXT,
                "--json",
            ]
        )
        self.assertEqual(args.codex_runner_command, "repeatable-proof-status")
        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")

        expected = _status_packet()
        stdout = io.StringIO()
        with (
            mock.patch(
                "wild_boar_proxy.cli.run_repeatable_proof_status_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "codex-runner",
                    "repeatable-proof-status",
                    "--route",
                    ROUTE_ID,
                    "--fresh-proof-file",
                    "fresh.json",
                    "--run-provider-preflight",
                    "--external-models-dir",
                    "external",
                    "--provider-expected-text",
                    EXPECTED_TEXT,
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        run_command.assert_called_once()
        _, kwargs = run_command.call_args
        self.assertEqual(kwargs["route_id"], ROUTE_ID)
        self.assertEqual(kwargs["fresh_proof_file"], "fresh.json")
        self.assertTrue(kwargs["run_provider_preflight"])
        self.assertEqual(kwargs["external_models_dir"], "external")
        self.assertEqual(kwargs["provider_expected_text"], EXPECTED_TEXT)


if __name__ == "__main__":
    unittest.main()
