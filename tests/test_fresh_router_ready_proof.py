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
from wild_boar_proxy import fresh_router_ready_proof as router_ready
from wild_boar_proxy import repeatable_proof_status as status
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_custom_codex_admission import (  # noqa: E402
    EXPECTED_TEXT,
    PROMPT,
    ROOT,
    ROUTE_ID,
    _paths,
    _runtime_context,
)


PROVIDER_EXPECTED_TEXT = "WBP_REPEATABLE_PROOF_PREFLIGHT_OK"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True) + "\n", encoding="utf-8")


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
        "changed_files": [],
    }
    packet.update(overrides)
    return packet


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


def _metadata() -> dict[str, object]:
    return {
        "fresh_proof_file_present": True,
        "fresh_proof_file_read": True,
        "fresh_proof_file_valid_json": True,
        "fresh_proof_file_mapping": True,
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


def _repeatable_status_packet(
    *,
    fresh_proof_file: Path,
    fresh: dict[str, object] | None = None,
    hook: dict[str, object] | None = None,
    provider: dict[str, object] | None = None,
) -> dict[str, object]:
    return status.build_repeatable_proof_status_packet(
        runtime_context=_runtime_context(),
        runtime_context_metadata=_context_metadata(),
        route_id=ROUTE_ID,
        route_id_allowed=True,
        hook_readiness_packet=_hook_ready_packet() if hook is None else hook,
        provider_preflight=_provider_packet() if provider is None else provider,
        provider_failures=[],
        fresh_proof_packet=_fresh_packet() if fresh is None else fresh,
        fresh_proof_metadata=_metadata(),
        fresh_proof_file=fresh_proof_file,
        secret_values=[PROMPT, EXPECTED_TEXT, PROVIDER_EXPECTED_TEXT, ROUTE_ID],
    )


def _assert_no_raw_sensitive_text(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in (PROMPT, EXPECTED_TEXT, PROVIDER_EXPECTED_TEXT, ROUTE_ID):
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["secret_value_exposed"])


class FreshRouterReadyProofTests(unittest.TestCase):
    def test_build_packet_accepts_only_router_ready_status_bound_to_fresh_file(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            fresh_file = root / "fresh.packet.json"
            status_file = root / "status.packet.json"
            fresh = _fresh_packet()
            _write_json(fresh_file, fresh)
            repeatable = _repeatable_status_packet(fresh_proof_file=fresh_file)
            _write_json(status_file, repeatable)

            packet = router_ready.build_fresh_router_ready_proof_packet(
                route_id=ROUTE_ID,
                proof_root=root,
                fresh_proof_packet=fresh,
                fresh_proof_file=fresh_file,
                repeatable_status_packet=repeatable,
                repeatable_status_file=status_file,
                changed_files=[str(fresh_file), str(status_file)],
                secret_values=[PROMPT, EXPECTED_TEXT, PROVIDER_EXPECTED_TEXT, ROUTE_ID],
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["operator_status"], "router_ready")
        self.assertTrue(packet["router_ready"])
        self.assertFalse(packet["proof_only"])
        self.assertFalse(packet["blocked"])
        self.assertTrue(packet["fresh_proof_digest_bound_to_status"])
        self.assertTrue(packet["provider_lane_expected_text_exact"])
        self.assertFalse(packet["provider_lane_preflight_is_dispatch_proof"])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, EXPECTED_TEXT, PROVIDER_EXPECTED_TEXT, ROUTE_ID],
            ),
            [],
        )

    def test_proof_only_status_is_never_router_ready(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            fresh_file = root / "fresh.packet.json"
            status_file = root / "status.packet.json"
            fresh = _fresh_packet()
            _write_json(fresh_file, fresh)
            repeatable = _repeatable_status_packet(
                fresh_proof_file=fresh_file,
                hook=_hook_ready_packet(
                    hook_trusted=False,
                    blocking_reasons=["hook_untrusted"],
                ),
            )
            _write_json(status_file, repeatable)

            packet = router_ready.build_fresh_router_ready_proof_packet(
                route_id=ROUTE_ID,
                proof_root=root,
                fresh_proof_packet=fresh,
                fresh_proof_file=fresh_file,
                repeatable_status_packet=repeatable,
                repeatable_status_file=status_file,
                changed_files=[str(fresh_file), str(status_file)],
                secret_values=[PROMPT, EXPECTED_TEXT, PROVIDER_EXPECTED_TEXT, ROUTE_ID],
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            router_ready.FRESH_ROUTER_READY_PROOF_PROOF_ONLY,
        )
        self.assertFalse(packet["router_ready"])
        self.assertTrue(packet["proof_only"])
        self.assertIn("fresh_router_ready_proof_only", packet["blocking_reasons"])
        self.assertIn("user_prompt_submit_hook_not_ready", packet["blocking_reasons"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_digest_mismatch_blocks_even_when_status_claims_router_ready(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            fresh_file = root / "fresh.packet.json"
            other_fresh_file = root / "other-fresh.packet.json"
            status_file = root / "status.packet.json"
            fresh = _fresh_packet()
            _write_json(fresh_file, fresh)
            _write_json(other_fresh_file, {"packet_kind": "other"})
            repeatable = _repeatable_status_packet(fresh_proof_file=other_fresh_file)
            _write_json(status_file, repeatable)

            packet = router_ready.build_fresh_router_ready_proof_packet(
                route_id=ROUTE_ID,
                proof_root=root,
                fresh_proof_packet=fresh,
                fresh_proof_file=fresh_file,
                repeatable_status_packet=repeatable,
                repeatable_status_file=status_file,
                changed_files=[str(fresh_file), str(status_file)],
                secret_values=[PROMPT, EXPECTED_TEXT, PROVIDER_EXPECTED_TEXT, ROUTE_ID],
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            router_ready.FRESH_ROUTER_READY_PROOF_BLOCKED,
        )
        self.assertFalse(packet["router_ready"])
        self.assertTrue(packet["blocked"])
        self.assertIn(
            "repeatable_status_not_bound_to_fresh_proof_file",
            packet["blocking_reasons"],
        )

    def test_fresh_packet_must_pass_router_ready_grade_even_when_status_claims_ready(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            fresh_file = root / "fresh.packet.json"
            status_file = root / "status.packet.json"
            fresh = _fresh_packet(full_runtime_diagnostics_passed=False)
            _write_json(fresh_file, fresh)
            repeatable = _repeatable_status_packet(
                fresh_proof_file=fresh_file,
                fresh=_fresh_packet(),
            )
            _write_json(status_file, repeatable)

            packet = router_ready.build_fresh_router_ready_proof_packet(
                route_id=ROUTE_ID,
                proof_root=root,
                fresh_proof_packet=fresh,
                fresh_proof_file=fresh_file,
                repeatable_status_packet=repeatable,
                repeatable_status_file=status_file,
                changed_files=[str(fresh_file), str(status_file)],
                secret_values=[PROMPT, EXPECTED_TEXT, PROVIDER_EXPECTED_TEXT, ROUTE_ID],
            )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["router_ready"])
        self.assertTrue(packet["blocked"])
        self.assertFalse(packet["fresh_proof_router_ready_grade"])
        self.assertIn("fresh_proof_not_router_ready_grade", packet["blocking_reasons"])

    def test_runner_writes_fresh_file_then_calls_repeatable_status_gate(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            paths = _paths(root)
            proof_dir = root / "proof"
            fresh = _fresh_packet()

            def status_side_effect(**kwargs: object) -> dict[str, object]:
                fresh_file = Path(str(kwargs["fresh_proof_file"]))
                self.assertTrue(fresh_file.is_file())
                payload = json.loads(fresh_file.read_text(encoding="utf-8"))
                self.assertEqual(payload["packet_kind"], "wbp_fresh_sealed_e2e_proof")
                self.assertTrue(kwargs["run_provider_preflight"])
                return _repeatable_status_packet(
                    fresh_proof_file=fresh_file,
                    fresh=payload,
                )

            with (
                mock.patch(
                    "wild_boar_proxy.fresh_router_ready_proof.run_fresh_sealed_e2e_proof_command",
                    return_value=fresh,
                ) as run_fresh,
                mock.patch(
                    "wild_boar_proxy.fresh_router_ready_proof.run_repeatable_proof_status_command",
                    side_effect=status_side_effect,
                ) as run_status,
            ):
                packet = router_ready.run_fresh_router_ready_proof_command(
                    paths=paths,
                    route_id=ROUTE_ID,
                    prompt_text=PROMPT,
                    codex_model="gpt-5.4",
                    proof_dir=str(proof_dir),
                    codex_cwd=str(ROOT),
                    provider_expected_text=PROVIDER_EXPECTED_TEXT,
                    external_models_dir=str(root / "external-models"),
                )
            self.assertTrue(
                (
                    proof_dir / "fresh-sealed" / "fresh-sealed-e2e-proof.packet.json"
                ).is_file()
            )
            self.assertTrue((proof_dir / "repeatable-proof-status.packet.json").is_file())
            self.assertTrue((proof_dir / "fresh-router-ready-proof.packet.json").is_file())

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["router_ready"])
        run_fresh.assert_called_once()
        run_status.assert_called_once()
        _, status_kwargs = run_status.call_args
        self.assertEqual(status_kwargs["route_id"], ROUTE_ID)
        self.assertEqual(status_kwargs["provider_expected_text"], PROVIDER_EXPECTED_TEXT)
        _assert_no_raw_sensitive_text(self, packet)

    def test_cli_parses_orchestrator_as_mutate_and_dispatches(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "codex-runner",
                "fresh-router-ready-proof",
                "--route",
                ROUTE_ID,
                "--prompt",
                PROMPT,
                "--codex-model",
                "gpt-5.4",
                "--proof-dir",
                "proof",
                "--codex-cwd",
                str(ROOT),
                "--provider-expected-text",
                PROVIDER_EXPECTED_TEXT,
                "--external-models-dir",
                "external",
                "--json",
            ]
        )
        self.assertEqual(args.codex_runner_command, "fresh-router-ready-proof")
        self.assertEqual(cli_mod.command_effect_from_args(args), "mutate")

        expected = packets.build_command_packet(
            ok=True,
            human_message="fresh router ready ok",
            machine_error_code="OK",
            liveness="network_dependent",
            severity="recoverable",
            operator_action="none",
            changed_files=[],
            effect="mutate",
            extra={
                "schema_version": 1,
                "packet_kind": router_ready.FRESH_ROUTER_READY_PROOF_PACKET_KIND,
                "router_ready": True,
                "product_ready": False,
                "state_written": False,
                "runtime_effective_truth_written": False,
                "evidence_written": True,
                "file_mutation_attempted": True,
                "blocking_reasons": [],
            },
        )
        stdout = io.StringIO()
        with (
            mock.patch(
                "wild_boar_proxy.cli.run_fresh_router_ready_proof_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "codex-runner",
                    "fresh-router-ready-proof",
                    "--route",
                    ROUTE_ID,
                    "--prompt",
                    PROMPT,
                    "--codex-model",
                    "gpt-5.4",
                    "--proof-dir",
                    "proof",
                    "--codex-cwd",
                    str(ROOT),
                    "--provider-expected-text",
                    PROVIDER_EXPECTED_TEXT,
                    "--external-models-dir",
                    "external",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertTrue(payload["router_ready"])
        run_command.assert_called_once_with(
            paths=mock.ANY,
            route_id=ROUTE_ID,
            prompt_text=PROMPT,
            custom_codex_ui_visibility_proof_file=None,
            codex_bin=None,
            codex_model="gpt-5.4",
            proof_dir="proof",
            codex_cwd=str(ROOT),
            expected_text=EXPECTED_TEXT,
            sandbox="danger-full-access",
            timeout_seconds=300,
            persistent_profile_id="wbp-custom-main",
            persistent_profile_base_dir=None,
            observer_timeout_seconds=None,
            native_auto_launch_custom_codex=False,
            native_auto_launch_endpoint="http://127.0.0.1:8318/v1",
            native_auto_launch_model="gpt-5.5",
            native_auto_launch_owner_authorization_phrase=None,
            native_auto_launch_repo_root=None,
            native_auto_launch_stable_runtime_generated_config_file=None,
            provider_expected_text=PROVIDER_EXPECTED_TEXT,
            external_models_dir="external",
            codex_hook_current_hash="",
            probe_codex_app_server=False,
        )

    def test_cli_failure_path_returns_nonzero_without_raw_sensitive_text(self) -> None:
        expected = packets.build_command_packet(
            ok=False,
            human_message="fresh router ready blocked",
            machine_error_code=router_ready.FRESH_ROUTER_READY_PROOF_BLOCKED,
            liveness="network_dependent",
            severity="recoverable",
            operator_action="stop",
            changed_files=[],
            effect="mutate",
            secret_values=[PROMPT, EXPECTED_TEXT, PROVIDER_EXPECTED_TEXT, ROUTE_ID],
            extra={
                "schema_version": 1,
                "packet_kind": router_ready.FRESH_ROUTER_READY_PROOF_PACKET_KIND,
                "operator_status": "blocked",
                "router_ready": False,
                "proof_only": False,
                "blocked": True,
                "route_id_sha256": "a" * 64,
                "route_id_recorded": False,
                "raw_route_id_recorded": False,
                "provider_lane_expected_text_exact": False,
                "provider_lane_preflight_is_dispatch_proof": False,
                "provider_response_preview_recorded": False,
                "fresh_sealed_e2e_proven": False,
                "api_lane_called": False,
                "dispatch_proven": False,
                "fallback_used": False,
                "local_imitation_used": False,
                "native_codex_subagent_used_as_dip": False,
                "product_ready": False,
                "raw_prompt_recorded": False,
                "prompt_text_recorded": False,
                "raw_provider_response_recorded": False,
                "provider_response_text_recorded": False,
                "secret_value_exposed": False,
                "state_written": False,
                "runtime_effective_truth_written": False,
                "evidence_written": True,
                "file_mutation_attempted": True,
                "blocking_reasons": ["fresh_router_ready_blocked"],
            },
        )
        stdout = io.StringIO()
        with (
            mock.patch(
                "wild_boar_proxy.cli.run_fresh_router_ready_proof_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "codex-runner",
                    "fresh-router-ready-proof",
                    "--route",
                    ROUTE_ID,
                    "--prompt",
                    PROMPT,
                    "--provider-expected-text",
                    PROVIDER_EXPECTED_TEXT,
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["exit_code"], 1)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["operator_status"], "blocked")
        self.assertFalse(payload["router_ready"])
        run_command.assert_called_once()
        _assert_no_raw_sensitive_text(self, payload)


if __name__ == "__main__":
    unittest.main()
