# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy import cli
from wild_boar_proxy import cli_runner as cli_runner_mod
from wild_boar_proxy.cli_runner import run_codex_cli_runner_smoke
from wild_boar_proxy.cli_runner_via_wbp import (
    PRIMARY_MODEL_ID,
    build_cli_runner_claims_packet,
    build_cli_runner_layer_boundary_packet,
    build_codex_auth_command_config,
    build_false_green_audit_packet,
    build_no_ambient_authority_packet,
    build_trace_acceptance_packet,
    remove_tree,
    validate_cli_runner_contour_packets,
)
from wild_boar_proxy.process_runner import (
    PROCESS_OK,
    PROCESS_TIMEOUT,
    BoundedProcessResult,
)


def _command(packet: dict[str, object]) -> dict[str, object]:
    return {
        "exit_code": 0,
        "json": packet,
        "stdout_redacted_len": 10,
        "stderr_redacted_len": 0,
        "timestamp_utc": "2026-05-25T00:00:00Z",
    }


def _account(backend_id: str) -> dict[str, object]:
    return {
        "id": backend_id,
        "label": backend_id,
        "enabled": True,
        "priority": 10,
        "pool": "active",
        "status": "healthy",
        "fail_count": 0,
        "success_count": 3,
        "last_success": "2026-05-25T00:00:00Z",
        "last_error": "",
        "last_error_class": "",
        "cooldown_until": None,
        "manual_hold": False,
        "auth_ref": "/tmp/redacted-auth.json",
    }


class FakeOperatorSurfaceSession:
    config = mock.Mock(codex_bin=Path("/Applications/Codex.app/Contents/Resources/codex"))

    def status_payload(self) -> dict[str, object]:
        return {
            "status": {
                "status": "ok",
                "machine_error_code": "OK",
                "configured_model": "wbp-web-primary-openrouter",
            },
            "claim_gate": {"status": "blocked_by_policy_drift"},
            "models": {
                "ok": True,
                "server_issued": True,
                "model_ids": ["wbp-web-primary-openrouter", "gpt-5.5", "gpt-5.3-codex"],
            },
        }

    def run_wbp(self, args: list[str]) -> dict[str, object]:
        if args == ["status", "--json"]:
            return _command(
                {
                    "status": "ok",
                    "machine_error_code": "OK",
                    "claim_gate": {"status": "blocked_by_policy_drift"},
                    "pool_summary": {"selected_backend_ids": ["acct-a"]},
                    "auth_pool_hygiene": {
                        "status": "launch_capable_available",
                        "selection_alignment_status": "aligned",
                    },
                    "configured_model": "gpt-5.5",
                }
            )
        if args == ["accounts", "list", "--json"]:
            return _command({"accounts": [_account("acct-a")]})
        if args == ["rollout", "rotation", "inspect", "--json"]:
            return _command({"status": "ok", "machine_error_code": "OK"})
        if args == ["external-models", "routes", "list", "--json"]:
            return _command(
                {
                    "data": {
                        "routes": [
                            {
                                "route_id": "wbp-web-primary-openrouter",
                                "provider": "openrouter",
                                "upstream_model": "openai/gpt-5",
                                "enabled": True,
                                "auth": {"secret_ref": "OPENROUTER_API_KEY", "type": "bearer"},
                            }
                        ],
                        "count": 1,
                    }
                }
            )
        raise AssertionError(f"unexpected args: {args}")

    def run_prompt(self, payload: dict[str, object], *, trace_wbp: bool = False) -> dict[str, object]:
        raise AssertionError("run_prompt should not be called directly by CLI runner smoke")


class FakeTraceObserver:
    listen_endpoint = "http://127.0.0.1:8318/v1"

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __enter__(self) -> "FakeTraceObserver":
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def packet(self) -> dict[str, object]:
        return {
            "request_observed": True,
            "response_observed": True,
            "forwarded_to_wbp": True,
            "path": "/v1/responses",
            "upstream_status": 200,
            "prompt_body_recorded": False,
            "auth_header_recorded": False,
            "secret_value_recorded": False,
            "machine_error_code": "OK",
        }


def _successful_runner_result() -> dict[str, object]:
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "final_message": "CLI_RUNNER_OK",
        "duration_seconds": 0.125,
        "stdin_prompt_used": True,
        "temp_root_removed": True,
        "secret_value_recorded": False,
        "configured_provider": "wbp",
        "configured_wire_api": "responses",
        "wbp_endpoint_configured": True,
        "config_endpoint_matches": True,
        "config_provider_matches": True,
        "config_wire_api_matches": True,
        "command_uses_stdin_dash": True,
        "command_json_mode": True,
        "env_codex_home_is_temp": True,
        "env_home_is_temp": True,
        "workdir_is_temp": True,
        "command_workdir_is_temp": True,
        "command_output_file_is_temp": True,
        "current_codex_home_used": False,
        "independent_wbp_trace_observed": True,
        "trace_observer_packet": {
            "request_observed": True,
            "response_observed": True,
            "forwarded_to_wbp": True,
            "forwarded_endpoint": "http://127.0.0.1:8318/v1",
            "method": "POST",
            "path": "/v1/responses",
            "upstream_status": 200,
            "prompt_body_recorded": False,
            "auth_header_recorded": False,
            "secret_value_recorded": False,
            "raw_account_id_recorded": False,
            "raw_backend_id_recorded": False,
            "machine_error_code": "OK",
            "observer_closed": False,
        },
        "process_network_observation_packet": {
            "status": "ok",
            "machine_error_code": "INSUFFICIENT_OBSERVATION",
            "classification": "insufficient_observation",
            "direct_non_wbp_model_egress_absent_proven": False,
            "process_tree_observed": False,
            "sample_count": 0,
            "observed_process_count_max": 0,
            "allowed_local_endpoints": [],
            "peer_endpoints": [],
            "non_local_peer_endpoints_present": False,
            "raw_pid_exposed": False,
            "pid_not_exposed_to_browser": True,
            "secret_value_recorded": False,
        },
        "warning_classes": ["remote_plugin_sync_401"],
        "auth_command_invoked": True,
    }


class NoModelsOperatorSurfaceSession(FakeOperatorSurfaceSession):
    def status_payload(self) -> dict[str, object]:
        return {
            "status": {
                "status": "ok",
                "machine_error_code": "OK",
                "configured_model": "gpt-5.5",
            },
            "claim_gate": {"status": "blocked_by_policy_drift"},
            "models": {"ok": False, "server_issued": True, "model_ids": []},
        }

    def run_wbp(self, args: list[str]) -> dict[str, object]:
        if args == ["external-models", "routes", "list", "--json"]:
            return _command({"data": {"routes": [], "count": 0}})
        return super().run_wbp(args)


class LaunchRejectedOperatorSurfaceSession(FakeOperatorSurfaceSession):
    def run_wbp(self, args: list[str]) -> dict[str, object]:
        if args == ["accounts", "list", "--json"]:
            return _command({"accounts": []})
        if args == ["external-models", "routes", "list", "--json"]:
            return _command({"data": {"routes": [], "count": 0}})
        return super().run_wbp(args)


class CliRunnerTests(unittest.TestCase):
    def test_cli_runner_via_wbp_layer_boundary_does_not_claim_native_or_wire(self) -> None:
        packet = build_cli_runner_layer_boundary_packet()

        self.assertFalse(packet["native_app_claimed"])
        self.assertFalse(packet["original_codex_lane_claimed"])
        self.assertFalse(packet["model_availability_reproof_claimed"])
        self.assertFalse(packet["streaming_claimed"])
        self.assertFalse(packet["tool_loop_claimed"])
        self.assertFalse(packet["direct_egress_absence_claimed"])
        self.assertFalse(packet["final_e2e_claimed"])
        self.assertFalse(packet["cli_runner_route_proof_is_responses_wire_compatibility"])
        self.assertFalse(packet["cli_runner_route_proof_is_model_availability_expansion"])
        self.assertFalse(packet["cli_runner_response_is_native_codex_app_response"])
        self.assertIn("native_codex_app_usability", packet["does_not_prove"])
        self.assertIn("direct_egress_absence", packet["does_not_prove"])

    def test_cli_runner_via_wbp_config_requires_auth_command(self) -> None:
        config = build_codex_auth_command_config(
            base_url="http://127.0.0.1:12345/v1",
            auth_command_path="/repo/wbp_codex_auth_command.py",
            model_id=PRIMARY_MODEL_ID,
        )

        self.assertIn('model = "gpt-5.4-mini"', config)
        self.assertIn('base_url = "http://127.0.0.1:12345/v1"', config)
        self.assertIn("[model_providers.wbp.auth]", config)
        self.assertIn('command = "/repo/wbp_codex_auth_command.py"', config)
        self.assertNotIn("OPENAI_API_KEY", config)
        self.assertNotIn("auth.json", config)

    def test_cli_runner_via_wbp_no_ambient_authority_packet_requires_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            codex_home = root / "codex-home"
            auth_command = root / "wbp_codex_auth_command.py"
            home.mkdir()
            codex_home.mkdir()
            auth_command.write_text("#!/usr/bin/env python3\n")
            env = {
                "HOME": str(home),
                "CODEX_HOME": str(codex_home),
                "WBP_STABLE_CONFIG": "/server-owned/config.yaml",
            }

            packet = build_no_ambient_authority_packet(
                env=env,
                home=home,
                codex_home=codex_home,
                auth_command_path=auth_command,
            )

        self.assertEqual(packet["status"], "passed")
        self.assertTrue(packet["openai_api_key_absent_or_ignored"])
        self.assertTrue(packet["proxy_env_absent_or_ignored"])
        self.assertEqual(packet["home_strategy"], "isolated_temp_home")
        self.assertEqual(packet["codex_home_strategy"], "isolated_temp_codex_home")
        self.assertTrue(packet["home_is_isolated"])
        self.assertTrue(packet["codex_home_is_isolated"])
        self.assertFalse(packet["openai_api_key_present"])
        self.assertEqual(packet["proxy_env_present"], [])
        self.assertFalse(packet["browser_supplied_authority"])
        self.assertFalse(packet["remote_client_supplied_authority"])

    def test_cli_runner_via_wbp_no_ambient_authority_fails_on_openai_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            codex_home = root / "codex-home"
            auth_command = root / "wbp_codex_auth_command.py"
            home.mkdir()
            codex_home.mkdir()
            auth_command.write_text("#!/usr/bin/env python3\n")
            env = {
                "HOME": str(home),
                "CODEX_HOME": str(codex_home),
                "OPENAI_API_KEY": "sk-test",
                "WBP_STABLE_CONFIG": "/server-owned/config.yaml",
            }

            packet = build_no_ambient_authority_packet(
                env=env,
                home=home,
                codex_home=codex_home,
                auth_command_path=auth_command,
            )

        self.assertEqual(packet["status"], "failed")
        self.assertTrue(packet["openai_api_key_present"])

    def test_cli_runner_via_wbp_trace_acceptance_requires_hashes(self) -> None:
        packet = build_trace_acceptance_packet(
            {
                "request_observed": True,
                "response_observed": True,
                "forwarded_to_wbp": True,
                "path": "/v1/responses",
                "upstream_status": 200,
                "request_body_sha256": "a" * 64,
                "response_body_sha256": "b" * 64,
                "prompt_body_recorded": False,
                "auth_header_recorded": False,
                "secret_value_recorded": False,
                "raw_account_id_recorded": False,
                "raw_backend_id_recorded": False,
            }
        )

        self.assertEqual(packet["status"], "passed")
        self.assertEqual(packet["route_trace_state"], "route_trace_observed")
        self.assertEqual(packet["request_body_sha256"], "a" * 64)
        self.assertEqual(packet["response_body_sha256"], "b" * 64)
        self.assertFalse(packet["full_wire_claimed"])
        self.assertFalse(packet["exit_code_counted_as_route_proof"])
        self.assertFalse(packet["responses_wire_compatibility_claimed"])
        self.assertFalse(packet["codex_app_acceptance_claimed"])

    def test_cli_runner_route_trace_not_exit_code_only(self) -> None:
        packet = build_trace_acceptance_packet(
            {
                "request_observed": False,
                "response_observed": False,
                "forwarded_to_wbp": False,
                "path": "",
                "upstream_status": None,
                "request_body_sha256": "",
                "response_body_sha256": "",
                "prompt_body_recorded": False,
                "auth_header_recorded": False,
                "secret_value_recorded": False,
            }
        )

        self.assertEqual(packet["status"], "failed")
        self.assertEqual(packet["route_trace_state"], "route_trace_unavailable_with_reason")
        self.assertFalse(packet["exit_code_counted_as_route_proof"])

    def test_cli_runner_via_wbp_claims_do_not_expand_model_or_egress(self) -> None:
        trace_packet = {"status": "passed"}
        packet = build_cli_runner_claims_packet(
            probe_status="passed",
            model_id=PRIMARY_MODEL_ID,
            response_match_observed=True,
            auth_command_invoked=True,
            trace_acceptance_packet=trace_packet,
        )

        self.assertEqual(packet["status"], "passed")
        self.assertEqual(
            packet["model_claim_level"],
            "cli_runner_non_stream_wbp_200_proven",
        )
        self.assertFalse(packet["model_availability_expansion_claimed"])
        self.assertFalse(packet["model_availability_reproved_in_this_contour"])
        self.assertFalse(packet["new_model_availability_claims_allowed"])
        self.assertFalse(packet["response_accepted_by_codex_app"])
        self.assertFalse(packet["direct_egress_absence_claimed"])
        self.assertFalse(packet["native_app_claimed"])

    def test_cli_runner_via_wbp_false_green_audit_blocks_missing_cleanup(self) -> None:
        audit = build_false_green_audit_packet(
            layer_boundary_packet=build_cli_runner_layer_boundary_packet(),
            env_packet={"status": "passed"},
            trace_packet={"status": "passed"},
            claims_packet={
                "native_app_claimed": False,
                "original_codex_lane_claimed": False,
                "streaming_claimed": False,
                "tool_loop_claimed": False,
                "direct_egress_absence_claimed": False,
            },
            original_integrity_passed=True,
            cleanup_passed=False,
        )

        self.assertEqual(audit["status"], "failed")
        self.assertIn("cleanup_passed", audit["failed_checks"])

    def test_cli_runner_via_wbp_cleanup_removes_owned_root_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "owned-root"
            root.mkdir()
            (root / "file.txt").write_text("owned\n")
            packet = remove_tree(root)

            self.assertEqual(packet["status"], "passed")
            self.assertTrue(packet["cleanup_performed"])
            self.assertTrue(packet["owned_session_root_only"])
            self.assertFalse(packet["exists_after"])

    def test_run_wbp_cli_prompt_uses_bounded_runner_with_stdin_prompt(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_run_bounded_process(
            command: list[str],
            *,
            env: dict[str, str],
            stdin_text: str,
            timeout_seconds: int,
        ) -> BoundedProcessResult:
            output_path = Path(command[command.index("-o") + 1])
            output_path.write_text("CLI_RUNNER_OK\n", encoding="utf-8")
            calls.append(
                {
                    "command": command,
                    "env": env,
                    "stdin_text": stdin_text,
                    "timeout_seconds": timeout_seconds,
                }
            )
            return BoundedProcessResult(
                status="ok",
                machine_error_code=PROCESS_OK,
                exit_code=0,
                stdout="runner stdout",
                stderr="Failed to sync remote plugins",
                stdout_truncated=False,
                stderr_truncated=False,
                timed_out=False,
                duration_seconds=0.01,
            )

        with (
            mock.patch(
                "wild_boar_proxy.cli_runner._build_runner_env",
                return_value={"PATH": "/usr/bin"},
            ),
            mock.patch("wild_boar_proxy.cli_runner.WbpTraceObserver", FakeTraceObserver),
            mock.patch(
                "wild_boar_proxy.cli_runner.run_bounded_process",
                side_effect=fake_run_bounded_process,
            ),
        ):
            result = cli_runner_mod._run_wbp_cli_prompt(
                mock.Mock(),
                codex_bin=Path("/tmp/codex"),
                model_id=PRIMARY_MODEL_ID,
                prompt="Reply with exactly CLI_RUNNER_OK.",
                timeout_seconds=9,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        self.assertEqual(result["final_message"], "CLI_RUNNER_OK")
        self.assertTrue(result["stdin_prompt_used"])
        self.assertTrue(result["stdout_sha256_present"])
        self.assertEqual(result["warning_classes"], ["remote_plugin_sync_401"])
        self.assertEqual(calls[0]["stdin_text"], "Reply with exactly CLI_RUNNER_OK.")
        self.assertEqual(calls[0]["timeout_seconds"], 9)
        self.assertIn("-", calls[0]["command"])
        self.assertIn("-o", calls[0]["command"])

    def test_run_wbp_cli_prompt_maps_bounded_timeout_without_false_green(self) -> None:
        def fake_run_bounded_process(
            command: list[str],
            *,
            env: dict[str, str],
            stdin_text: str,
            timeout_seconds: int,
        ) -> BoundedProcessResult:
            return BoundedProcessResult(
                status="error",
                machine_error_code=PROCESS_TIMEOUT,
                exit_code=-9,
                stdout="",
                stderr="failed to refresh available models",
                stdout_truncated=False,
                stderr_truncated=False,
                timed_out=True,
                duration_seconds=timeout_seconds,
            )

        with (
            mock.patch(
                "wild_boar_proxy.cli_runner._build_runner_env",
                return_value={"PATH": "/usr/bin"},
            ),
            mock.patch("wild_boar_proxy.cli_runner.WbpTraceObserver", FakeTraceObserver),
            mock.patch(
                "wild_boar_proxy.cli_runner.run_bounded_process",
                side_effect=fake_run_bounded_process,
            ),
        ):
            result = cli_runner_mod._run_wbp_cli_prompt(
                mock.Mock(),
                codex_bin=Path("/tmp/codex"),
                model_id=PRIMARY_MODEL_ID,
                prompt="hello",
                timeout_seconds=3,
            )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["machine_error_code"], "ENGINE_PROMPT_TIMEOUT")
        self.assertEqual(result["final_message"], "")
        self.assertFalse(result["independent_wbp_trace_observed"])
        self.assertEqual(result["warning_classes"], ["model_refresh_warning"])
        self.assertTrue(result["temp_root_removed"])

    def test_cli_runner_smoke_returns_non_native_runner_packet(self) -> None:
        snapshot = {
            "path_label": "~/.codex/config.toml",
            "exists": True,
            "is_dir": False,
            "size": 12,
            "mtime_ns": 100,
            "sha256": "a" * 64,
        }
        with (
            mock.patch("wild_boar_proxy.cli_runner.OperatorSurfaceSession", FakeOperatorSurfaceSession),
            mock.patch(
                "wild_boar_proxy.cli_runner._run_wbp_cli_prompt",
                return_value=_successful_runner_result(),
            ),
            mock.patch(
                "wild_boar_proxy.cli_runner._targeted_current_codex_snapshot",
                side_effect=[
                    {"codex_config": snapshot, "codex_auth": snapshot},
                    {"codex_config": dict(snapshot), "codex_auth": dict(snapshot)},
                ],
            ),
        ):
            packet = run_codex_cli_runner_smoke(mock.Mock(), "Reply with exactly CLI_RUNNER_OK.")

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["consumer_kind"], "codex_cli_runner")
        self.assertFalse(packet["native_app_claimed"])
        self.assertTrue(packet["reusable_runner_launch_surface"])
        self.assertEqual(packet["runner_launch_surface"], "wild-boar-proxy codex-runner smoke --json --prompt <text>")
        self.assertEqual(packet["selected_model_id"], "gpt-5.5")
        self.assertEqual(packet["selection_packet"]["selected_source_class"], "gpt_account")
        self.assertEqual(packet["selection_packet"]["selected_route_ref"], "")
        self.assertFalse(packet["selection_packet"]["selected_route_server_issued"])
        self.assertEqual(packet["prompt_packet"]["response_preview_bounded"], "CLI_RUNNER_OK")
        self.assertTrue(packet["prompt_packet"]["wbp_path_proven"])
        self.assertEqual(packet["direct_egress_negative_status"], "not_claimed_in_cli_runner_contour")
        self.assertFalse(packet["direct_non_wbp_model_egress_absent_proven"])
        self.assertFalse(packet["process_network_observation_counts_as_egress_proof"])
        self.assertEqual(packet["transcript_packet"]["transcript_kind"], "service_ledger_only")
        self.assertTrue(packet["transcript_packet"]["raw_prompt_not_stored"])
        self.assertTrue(packet["cleanup_packet"]["cleanup_performed"])
        self.assertTrue(packet["cleanup_packet"]["owned_session_root_only"])
        self.assertFalse(packet["cleanup_packet"]["session_root_exists_after"])
        self.assertTrue(packet["current_codex_observation"]["targeted_files_unchanged"])
        self.assertEqual(packet["raw_runner_warning_classes"], ["remote_plugin_sync_401"])

    def test_cli_runner_smoke_marks_cleanup_not_applicable_when_launch_rejected(self) -> None:
        with mock.patch(
            "wild_boar_proxy.cli_runner.OperatorSurfaceSession",
            LaunchRejectedOperatorSurfaceSession,
        ):
            packet = run_codex_cli_runner_smoke(mock.Mock(), "Reply with exactly CLI_RUNNER_OK.")

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["cleanup_packet"]["machine_error_code"], "NOT_APPLICABLE")
        self.assertTrue(packet["cleanup_packet"]["cleanup_not_applicable"])
        self.assertNotIn("cleanup_packet_not_ok", packet["failed_checks"])

    def test_cli_runner_smoke_blocks_without_server_issued_model(self) -> None:
        with mock.patch(
            "wild_boar_proxy.cli_runner.OperatorSurfaceSession",
            NoModelsOperatorSurfaceSession,
        ):
            packet = run_codex_cli_runner_smoke(mock.Mock(), "Reply with exactly CLI_RUNNER_OK.")

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["consumer_kind"], "codex_cli_runner")
        self.assertFalse(packet["native_app_claimed"])
        self.assertTrue(packet["reusable_runner_launch_surface"])
        self.assertIn(
            packet["machine_error_code"],
            {
                "SERVER_ISSUED_MODEL_REQUIRED",
                "NO_SERVER_MODELS_VISIBLE",
                "CLAIM_GATE_BLOCKED",
                "CUSTOM_MODELS_NOT_VISIBLE",
            },
        )

    def test_cli_main_dispatches_codex_runner_smoke(self) -> None:
        payload = {
            "status": "ok",
            "exit_code": 0,
            "human_message": "ok",
            "machine_error_code": "OK",
            "changed_files": [],
            "next_action": "none",
            "liveness": "healthy",
            "severity": "recoverable",
            "operator_action": "none",
            "consumer_kind": "codex_cli_runner",
            "native_app_claimed": False,
        }
        stdout = io.StringIO()
        with (
            mock.patch("wild_boar_proxy.cli.run_codex_cli_runner_smoke", return_value=payload) as run_mock,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli.main(["codex-runner", "smoke", "--json", "--prompt", "hi"])

        self.assertEqual(exit_code, 0)
        run_mock.assert_called_once()
        emitted = json.loads(stdout.getvalue())
        self.assertEqual(emitted["consumer_kind"], "codex_cli_runner")
        self.assertFalse(emitted["native_app_claimed"])

    def test_cli_runner_reference_model_availability_not_reproved(self) -> None:
        packets = {
            "model_availability_reference_packet.json": {
                "reference_only": True,
                "model_availability_expansion_claimed": False,
                "model_availability_reproved_in_this_contour": True,
                "new_model_availability_claims_allowed": False,
                "native_model_availability_claimed": False,
            },
            "cli_runner_layer_boundary_packet.json": build_cli_runner_layer_boundary_packet(),
            "cli_runner_route_trace_packet.json": build_trace_acceptance_packet(
                {
                    "request_observed": True,
                    "response_observed": True,
                    "forwarded_to_wbp": True,
                    "path": "/v1/responses",
                    "upstream_status": 200,
                    "request_body_sha256": "a" * 64,
                    "response_body_sha256": "b" * 64,
                    "prompt_body_recorded": False,
                    "auth_header_recorded": False,
                    "secret_value_recorded": False,
                }
            ),
            "cli_runner_response_hash_packet.json": {
                "response_exists": True,
                "response_sha256": "c" * 64,
                "raw_prompt_recorded": False,
                "auth_header_recorded": False,
                "raw_upstream_secret_recorded": False,
            },
            "cli_runner_smoke_packet.json": build_cli_runner_claims_packet(
                probe_status="passed",
                model_id=PRIMARY_MODEL_ID,
                response_match_observed=True,
                auth_command_invoked=True,
                trace_acceptance_packet={"status": "passed"},
            ),
        }

        self.assertIn(
            "model_availability_reference.model_availability_reproved_in_this_contour",
            validate_cli_runner_contour_packets(packets),
        )

    def test_cli_runner_response_hash_required(self) -> None:
        failures = validate_cli_runner_contour_packets(
            {
                "cli_runner_response_hash_packet.json": {
                    "response_exists": True,
                    "response_sha256": "",
                    "raw_prompt_recorded": False,
                    "auth_header_recorded": False,
                    "raw_upstream_secret_recorded": False,
                }
            }
        )

        self.assertIn("cli_runner_response_hash.response_sha256", failures)

    def test_cli_runner_no_streaming_or_tool_loop_claim(self) -> None:
        smoke = build_cli_runner_claims_packet(
            probe_status="passed",
            model_id=PRIMARY_MODEL_ID,
            response_match_observed=True,
            auth_command_invoked=True,
            trace_acceptance_packet={"status": "passed"},
        )
        smoke["streaming_claimed"] = True
        failures = validate_cli_runner_contour_packets({"cli_runner_smoke_packet.json": smoke})

        self.assertIn("cli_runner_smoke.streaming_claimed", failures)

    def test_cli_runner_no_egress_or_ux_claim(self) -> None:
        smoke = build_cli_runner_claims_packet(
            probe_status="passed",
            model_id=PRIMARY_MODEL_ID,
            response_match_observed=True,
            auth_command_invoked=True,
            trace_acceptance_packet={"status": "passed"},
        )
        smoke["direct_egress_absence_claimed"] = True
        smoke["native_app_claimed"] = True
        failures = validate_cli_runner_contour_packets({"cli_runner_smoke_packet.json": smoke})

        self.assertIn("cli_runner_smoke.direct_egress_absence_claimed", failures)
        self.assertIn("cli_runner_smoke.native_app_claimed", failures)


if __name__ == "__main__":
    unittest.main()
