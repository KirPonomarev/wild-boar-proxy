# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy.codex_custom_sessions import (
    CodexCustomSessionManager,
    forbidden_prompt_dry_run_fields,
    forbidden_prompt_run_fields,
    forbidden_session_create_fields,
)


def command(packet: dict[str, object]) -> dict[str, object]:
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "human_message": "ok",
        "packet": packet,
    }


def account(backend_id: str, priority: int = 10) -> dict[str, object]:
    return {
        "id": backend_id,
        "label": backend_id,
        "enabled": True,
        "priority": priority,
        "pool": "active",
        "status": "healthy",
        "fail_count": 0,
        "success_count": 7,
        "last_success": "2026-05-23T00:00:00Z",
        "last_error": "",
        "last_error_class": "",
        "cooldown_until": None,
        "manual_hold": False,
        "auth_ref": "/tmp/wbp-redacted-auth.json",
    }


def commands() -> dict[str, dict[str, object]]:
    return {
        "status": command(
            {
                "status": "ok",
                "machine_error_code": "OK",
                "claim_gate": {"status": "blocked_by_policy_drift"},
                "pool_summary": {"selected_backend_ids": ["acct-a"]},
                "auth_pool_hygiene": {
                    "status": "launch_capable_available",
                    "selection_alignment_status": "aligned",
                },
            }
        ),
        "accounts_list": command({"accounts": [account("acct-a"), account("acct-b", 20)]}),
        "rollout_rotation_inspect": command({"status": "ok", "machine_error_code": "OK"}),
    }


def operator_status() -> dict[str, object]:
    return {
        "status": {"status": "ok", "machine_error_code": "OK"},
        "claim_gate": {"status": "blocked_by_policy_drift"},
        "models": {
            "ok": True,
            "server_issued": True,
            "model_ids": ["gpt-5.3-codex", "gpt-5.4"],
        },
    }


class CodexCustomSessionManagerTests(unittest.TestCase):
    def test_create_session_binds_server_model_and_selection_without_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            packet = manager.create_packet(
                {"model_id": "gpt-5.3-codex"},
                commands(),
                operator_status(),
            )

            self.assertEqual(packet["status"], "ok")
            self.assertTrue(packet["session_created"])
            self.assertFalse(packet["live_prompt_admitted"])
            self.assertFalse(packet["current_codex_home_used"])
            self.assertTrue(packet["selected_backend_id_redacted"])
            session = packet["session"]
            self.assertTrue(session["model_server_issued"])
            self.assertTrue(session["selection_dry_run_proven"])
            self.assertFalse(session["live_selection_proven"])
            self.assertTrue(session["selection_proven"])
            self.assertTrue(session["selected_backend_id_redacted"])
            self.assertTrue(session["selected_backend_server_issued"])
            self.assertEqual(session["selected_route_digest"], "")
            self.assertFalse(session["selected_route_server_issued"])
            self.assertFalse(session["route_provenance_required"])
            self.assertFalse(session["route_provenance_proven"])
            self.assertEqual(session["source_provenance_status"], "backend_proven")
            self.assertTrue(session["source_provenance_proven"])
            self.assertFalse(session["current_codex_home_used"])
            self.assertEqual(session["session_root_scope"], "owned_temp_session_root")
            self.assertNotIn(temp_dir, json.dumps(packet))
            self.assertNotIn("acct-a", json.dumps(packet))
            self.assertFalse(packet["inference_proven"])
            self.assertFalse(packet["runtime_meter_attached"])
            self.assertFalse(packet["network_calls_made"])
            self.assertFalse(packet["provider_called"])
            self.assertEqual(packet["token_burn"], 0)

    def test_create_session_rejects_free_form_model_and_browser_backend_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            bad_model = manager.create_packet({"model_id": "free-form"}, commands(), operator_status())
            bad_fields = manager.create_packet(
                {
                    "model_id": "gpt-5.3-codex",
                    "account_id": "acct-a",
                    "backend_id": "acct-a",
                    "route_id": "route",
                    "path": "/tmp/outside",
                },
                commands(),
                operator_status(),
            )

            self.assertEqual(bad_model["status"], "rejected")
            self.assertEqual(bad_model["machine_error_code"], "MODEL_NOT_SERVER_ISSUED")
            self.assertEqual(bad_fields["status"], "rejected")
            self.assertEqual(bad_fields["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
            self.assertIn("account_id", bad_fields["forbidden_fields"])
            self.assertIn("backend_id", bad_fields["forbidden_fields"])
            self.assertIn("route_id", bad_fields["forbidden_fields"])
            self.assertIn("path", bad_fields["forbidden_fields"])

    def test_create_session_rejects_when_account_selection_is_not_proven(self) -> None:
        weak_commands = commands()
        weak_commands["accounts_list"] = command({"accounts": []})
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            packet = manager.create_packet(
                {"model_id": "gpt-5.3-codex"},
                weak_commands,
                operator_status(),
            )

            self.assertEqual(packet["status"], "rejected")
            self.assertEqual(packet["machine_error_code"], "NO_LAUNCH_CAPABLE_GPT_ACCOUNT")
            self.assertFalse(packet["selection_proven"])
            self.assertFalse(packet["session_created"])
            self.assertEqual(packet["next_action"], "repair_account_selection_truth")
            self.assertEqual(manager.list_packet()["session_count"], 0)

    def test_prompt_dry_run_hashes_prompt_and_does_not_claim_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"model_id": "gpt-5.3-codex"}, commands(), operator_status())
            session_id = created["session"]["session_id"]
            packet = manager.prompt_dry_run_packet(session_id, {"prompt": "Reply with exactly OK."})
            transcript = manager.transcript_packet(session_id)

            self.assertEqual(packet["status"], "ok")
            self.assertTrue(packet["prompt_admitted"])
            self.assertEqual(packet["prompt_length"], len("Reply with exactly OK."))
            self.assertEqual(len(packet["prompt_sha256"]), 64)
            self.assertFalse(packet["model_response_present"])
            self.assertFalse(packet["inference_proven"])
            self.assertFalse(packet["runtime_meter_attached"])
            self.assertFalse(packet["network_calls_made"])
            self.assertFalse(packet["provider_called"])
            self.assertTrue(packet["raw_prompt_not_stored"])
            self.assertEqual(packet["token_burn"], 0)
            self.assertNotIn("Reply with exactly OK.", json.dumps(transcript))
            self.assertEqual(transcript["transcript_kind"], "service_ledger_only")
            self.assertFalse(transcript["model_response_present"])
            self.assertFalse(transcript["inference_proven"])
            self.assertTrue(transcript["raw_prompt_not_stored"])
            self.assertTrue(transcript["raw_response_not_stored"])
            self.assertFalse(transcript["raw_backend_id_exposed"])
            self.assertEqual(transcript["token_burn"], 0)

    def test_prompt_dry_run_rejects_forbidden_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"model_id": "gpt-5.3-codex"}, commands(), operator_status())
            session_id = created["session"]["session_id"]
            packet = manager.prompt_dry_run_packet(
                session_id,
                {"prompt": "OK", "backend_id": "acct-a", "nested": {"path": "/tmp/outside"}},
            )

            self.assertEqual(packet["status"], "rejected")
            self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
            self.assertEqual(packet["forbidden_fields"], ["backend_id", "nested", "nested.path"])
            self.assertFalse(packet["inference_proven"])

    def test_live_prompt_not_admitted_packet_never_calls_runner_or_claims_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"model_id": "gpt-5.3-codex"}, commands(), operator_status())
            session_id = created["session"]["session_id"]
            rejected = manager.prompt_not_admitted_packet(
                session_id,
                {"prompt": "OK", "backend_id": "acct-a", "path": "/tmp/outside"},
            )
            blocked = manager.prompt_not_admitted_packet(session_id, {"prompt": "OK"})

            self.assertEqual(rejected["status"], "rejected")
            self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
            self.assertIn("backend_id", rejected["forbidden_fields"])
            self.assertIn("path", rejected["forbidden_fields"])
            self.assertFalse(rejected["live_prompt_admitted"])
            self.assertFalse(rejected["live_prompt_executed"])
            self.assertFalse(rejected["prompt_runner_called"])
            self.assertFalse(rejected["inference_proven"])
            self.assertFalse(rejected["model_response_present"])
            self.assertFalse(rejected["network_calls_made"])
            self.assertFalse(rejected["provider_called"])
            self.assertTrue(rejected["raw_prompt_not_stored"])
            self.assertEqual(rejected["token_burn"], 0)
            self.assertEqual(blocked["status"], "blocked")
            self.assertEqual(blocked["machine_error_code"], "OWNER_AUTHORIZATION_REQUIRED")
            self.assertEqual(blocked["authorization_status"], "blocked_by_operator_authorization")
            self.assertFalse(blocked["owner_authorization_phrase_present"])
            self.assertFalse(blocked["prompt_runner_called"])

    def test_prompt_run_wraps_runner_response_without_browser_model_or_backend(self) -> None:
        calls: list[dict[str, object]] = []

        def runner(payload: dict[str, object]) -> dict[str, object]:
            calls.append(payload)
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "final_message": "SESSION_REAL_OK",
                "duration_seconds": 0.125,
                "stdin_prompt_used": True,
                "temp_root_removed": True,
                "secret_value_recorded": False,
                "configured_provider": "cliproxy",
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
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"model_id": "gpt-5.3-codex"}, commands(), operator_status())
            session_id = created["session"]["session_id"]
            packet = manager.prompt_packet(
                session_id,
                {"prompt": "Reply real OK."},
                runner,
                owner_authorized=True,
            )
            transcript = manager.transcript_packet(session_id)

            self.assertEqual(calls, [{"prompt": "Reply real OK.", "model_id": "gpt-5.3-codex"}])
            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(packet["machine_error_code"], "WBP_TRACE_PROOF_MISSING")
            self.assertTrue(packet["inference_proven"])
            self.assertTrue(packet["model_response_present"])
            self.assertTrue(packet["live_prompt_admitted"])
            self.assertTrue(packet["live_prompt_executed"])
            self.assertTrue(packet["prompt_runner_called"])
            self.assertFalse(packet["live_prompt_full_success"])
            self.assertTrue(packet["model_server_issued"])
            self.assertTrue(packet["selected_backend_server_issued"])
            self.assertFalse(packet["selected_route_server_issued"])
            self.assertFalse(packet["route_provenance_required"])
            self.assertFalse(packet["route_provenance_proven"])
            self.assertEqual(packet["source_provenance_status"], "backend_proven")
            self.assertTrue(packet["source_provenance_proven"])
            self.assertFalse(packet["browser_selected_backend"])
            self.assertTrue(packet["wbp_path_configured"])
            self.assertTrue(packet["cli_proxy_api_path_configured"])
            self.assertFalse(packet["wbp_path_observed"])
            self.assertFalse(packet["cli_proxy_api_path_observed"])
            self.assertFalse(packet["wbp_path_proven"])
            self.assertFalse(packet["cli_proxy_api_path_proven"])
            self.assertFalse(packet["independent_wbp_trace_observed"])
            self.assertEqual(packet["path_proof_status"], "configured_not_independently_observed")
            self.assertEqual(packet["next_action"], "inspect_trace_observer")
            self.assertTrue(packet["isolated_engine_home_proven"])
            self.assertEqual(packet["configured_wire_api"], "responses")
            self.assertFalse(packet["fallback_attempted"])
            self.assertEqual(packet["response_preview_bounded"], "SESSION_REAL_OK")
            self.assertEqual(len(packet["response_digest"]), 64)
            self.assertFalse(packet["token_usage_present"])
            self.assertIsNone(packet["token_burn"])
            self.assertEqual(packet["latency_ms"], 125)
            self.assertNotIn("Reply real OK.", json.dumps(packet))
            self.assertNotIn("acct-a", json.dumps(packet))
            self.assertTrue(transcript["model_response_present"])
            self.assertTrue(transcript["inference_proven"])
            self.assertNotIn("Reply real OK.", json.dumps(transcript))

    def test_prompt_run_defaults_to_owner_authorization_block(self) -> None:
        calls: list[dict[str, object]] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"model_id": "gpt-5.3-codex"}, commands(), operator_status())
            session_id = created["session"]["session_id"]
            packet = manager.prompt_packet(
                session_id,
                {"prompt": "OK"},
                lambda payload: calls.append(payload) or {"status": "ok", "final_message": "SHOULD_NOT_RUN"},
            )

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(packet["machine_error_code"], "OWNER_AUTHORIZATION_REQUIRED")
            self.assertEqual(packet["authorization_status"], "blocked_by_operator_authorization")
            self.assertFalse(packet["owner_authorization_phrase_present"])
            self.assertFalse(packet["live_prompt_executed"])
            self.assertFalse(packet["prompt_runner_called"])
            self.assertEqual(calls, [])

    def test_prompt_run_rejects_forbidden_fields_and_failed_runner_does_not_overclaim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"model_id": "gpt-5.3-codex"}, commands(), operator_status())
            session_id = created["session"]["session_id"]
            rejected = manager.prompt_packet(
                session_id,
                {"prompt": "OK", "model_id": "browser-model", "backend_id": "acct-a"},
                lambda payload: {"status": "ok", "final_message": "SHOULD_NOT_RUN"},
                owner_authorized=True,
            )
            failed = manager.prompt_packet(
                session_id,
                {"prompt": "OK"},
                lambda payload: {
                    "status": "failed",
                    "machine_error_code": "ENGINE_PROMPT_FAILED",
                    "error_class": "RuntimeError",
                    "secret_value_recorded": False,
                },
                owner_authorized=True,
            )

            self.assertEqual(rejected["status"], "rejected")
            self.assertEqual(rejected["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
            self.assertIn("model_id", rejected["forbidden_fields"])
            self.assertIn("backend_id", rejected["forbidden_fields"])
            self.assertFalse(rejected["inference_proven"])
            self.assertFalse(rejected["model_response_present"])
            self.assertEqual(failed["status"], "failed")
            self.assertFalse(failed["inference_proven"])
            self.assertFalse(failed["model_response_present"])
            self.assertFalse(failed["fallback_attempted"])

    def test_prompt_run_marks_path_proven_only_with_independent_trace(self) -> None:
        def runner(payload: dict[str, object]) -> dict[str, object]:
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "final_message": "TRACE_OK",
                "secret_value_recorded": False,
                "configured_provider": "cliproxy",
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
                    "path": "/v1/responses",
                    "upstream_status": 200,
                    "forwarded_to_wbp": True,
                    "authorization": "forbidden",
                    "raw_body": "forbidden",
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"model_id": "gpt-5.3-codex"}, commands(), operator_status())
            packet = manager.prompt_packet(
                created["session"]["session_id"],
                {"prompt": "OK"},
                runner,
                owner_authorized=True,
            )

            self.assertTrue(packet["wbp_path_configured"])
            self.assertTrue(packet["cli_proxy_api_path_configured"])
            self.assertTrue(packet["independent_wbp_trace_observed"])
            self.assertTrue(packet["wbp_path_observed"])
            self.assertTrue(packet["cli_proxy_api_path_observed"])
            self.assertEqual(packet["trace_path"], "/v1/responses")
            self.assertEqual(packet["upstream_status"], 200)
            self.assertTrue(packet["forwarded_to_wbp"])
            self.assertNotIn("authorization", packet["trace_observer_packet"])
            self.assertNotIn("raw_body", packet["trace_observer_packet"])
            self.assertTrue(packet["wbp_path_proven"])
            self.assertTrue(packet["cli_proxy_api_path_proven"])
            self.assertTrue(packet["live_prompt_full_success"])
            self.assertFalse(packet["route_provenance_required"])
            self.assertFalse(packet["route_provenance_proven"])
            self.assertEqual(packet["source_provenance_status"], "backend_proven")
            self.assertTrue(packet["source_provenance_proven"])
            self.assertEqual(packet["selected_source_provenance"], "backend_proven")
            self.assertFalse(packet["current_codex_touched"])
            self.assertEqual(packet["path_proof_status"], "independently_observed")

    def test_prompt_run_blocks_success_when_current_codex_home_is_used(self) -> None:
        def runner(payload: dict[str, object]) -> dict[str, object]:
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "final_message": "TRACE_OK",
                "secret_value_recorded": False,
                "configured_provider": "cliproxy",
                "configured_wire_api": "responses",
                "wbp_endpoint_configured": True,
                "config_endpoint_matches": True,
                "config_provider_matches": True,
                "config_wire_api_matches": True,
                "command_uses_stdin_dash": True,
                "command_json_mode": True,
                "env_codex_home_is_temp": False,
                "env_home_is_temp": True,
                "workdir_is_temp": True,
                "command_workdir_is_temp": True,
                "command_output_file_is_temp": True,
                "current_codex_home_used": True,
                "independent_wbp_trace_observed": True,
                "trace_observer_packet": {
                    "path": "/v1/responses",
                    "upstream_status": 200,
                    "forwarded_to_wbp": True,
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"model_id": "gpt-5.3-codex"}, commands(), operator_status())
            packet = manager.prompt_packet(
                created["session"]["session_id"],
                {"prompt": "OK"},
                runner,
                owner_authorized=True,
            )

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(packet["machine_error_code"], "CURRENT_CODEX_TOUCHED")
            self.assertTrue(packet["model_response_present"])
            self.assertTrue(packet["inference_proven"])
            self.assertTrue(packet["wbp_path_proven"])
            self.assertFalse(packet["isolated_engine_home_proven"])
            self.assertTrue(packet["current_codex_touched"])
            self.assertFalse(packet["live_prompt_full_success"])
            self.assertEqual(packet["next_action"], "stop_and_diagnose_current_codex_touch")

    def test_route_backed_session_requires_route_provenance_before_prompt_run(self) -> None:
        calls: list[dict[str, object]] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"model_id": "gpt-5.3-codex"}, commands(), operator_status())
            session_id = created["session"]["session_id"]
            session = manager._sessions[session_id]
            session.update(
                {
                    "selected_source_class": "route_backed",
                    "selected_backend_ref": "",
                    "selected_backend_server_issued": False,
                    "selected_route_ref": "route-digest",
                    "selected_route_server_issued": True,
                    "route_provenance_required": True,
                    "route_provenance_proven": False,
                    "source_provenance_status": "route_provenance_missing",
                }
            )

            packet = manager.prompt_packet(
                session_id,
                {"prompt": "OK"},
                lambda payload: calls.append(payload) or {"status": "ok", "final_message": "SHOULD_NOT_RUN"},
                owner_authorized=True,
            )

            self.assertEqual(packet["status"], "rejected")
            self.assertEqual(packet["machine_error_code"], "ROUTE_PROVENANCE_MISSING")
            self.assertIn("ROUTE_PROVENANCE_MISSING", packet["precondition_failures"])
            self.assertFalse(packet["model_response_present"])
            self.assertFalse(packet["fallback_attempted"])
            self.assertEqual(calls, [])

    def test_route_backed_session_with_route_provenance_can_satisfy_full_success(self) -> None:
        def runner(payload: dict[str, object]) -> dict[str, object]:
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "final_message": "ROUTE_OK",
                "secret_value_recorded": False,
                "configured_provider": "cliproxy",
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
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"model_id": "gpt-5.3-codex"}, commands(), operator_status())
            session_id = created["session"]["session_id"]
            session = manager._sessions[session_id]
            session.update(
                {
                    "selected_source_class": "route_backed",
                    "selected_backend_ref": "",
                    "selected_backend_server_issued": False,
                    "selected_route_ref": "route-digest",
                    "selected_route_server_issued": True,
                    "route_provenance_required": True,
                    "route_provenance_proven": True,
                    "source_provenance_status": "route_proven",
                }
            )

            packet = manager.prompt_packet(
                session_id,
                {"prompt": "OK"},
                runner,
                owner_authorized=True,
            )

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["machine_error_code"], "OK")
            self.assertEqual(packet["selected_source_class"], "route_backed")
            self.assertFalse(packet["selected_backend_server_issued"])
            self.assertEqual(packet["selected_route_digest"], "route-digest")
            self.assertTrue(packet["selected_route_server_issued"])
            self.assertTrue(packet["route_provenance_required"])
            self.assertTrue(packet["route_provenance_proven"])
            self.assertEqual(packet["source_provenance_status"], "route_proven")
            self.assertTrue(packet["source_provenance_proven"])
            self.assertTrue(packet["live_prompt_full_success"])

    def test_prompt_run_rejects_cleaned_session_precondition(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"model_id": "gpt-5.3-codex"}, commands(), operator_status())
            session_id = created["session"]["session_id"]
            manager.cleanup_packet(session_id)
            packet = manager.prompt_packet(
                session_id,
                {"prompt": "OK"},
                lambda payload: {"status": "ok", "final_message": "SHOULD_NOT_RUN"},
                owner_authorized=True,
            )

            self.assertEqual(packet["status"], "rejected")
            self.assertIn("SESSION_ALREADY_CLEANED", packet["precondition_failures"])
            self.assertFalse(packet["inference_proven"])
            self.assertFalse(packet["model_response_present"])

    def test_cancel_and_cleanup_are_session_owned_without_process_kill_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"model_id": "gpt-5.3-codex"}, commands(), operator_status())
            session_id = created["session"]["session_id"]
            before_cleanup = list(Path(temp_dir).iterdir())

            cancel = manager.cancel_packet(session_id)
            cleanup = manager.cleanup_packet(session_id)

            self.assertTrue(before_cleanup)
            self.assertEqual(cancel["status"], "ok")
            self.assertTrue(cancel["cancelled"])
            self.assertFalse(cancel["process_kill_claimed"])
            self.assertFalse(cancel["network_calls_made"])
            self.assertFalse(cancel["provider_called"])
            self.assertEqual(cleanup["status"], "ok")
            self.assertTrue(cleanup["cleanup_performed"])
            self.assertTrue(cleanup["owned_session_root_only"])
            self.assertTrue(cleanup["session_root_removed_or_marked_cleaned"])
            self.assertFalse(cleanup["current_codex_home_touched"])
            self.assertFalse(cleanup["session_root_exists_after"])
            self.assertFalse(cleanup["arbitrary_path_accepted"])
            self.assertFalse(cleanup["network_calls_made"])
            self.assertFalse(cleanup["provider_called"])
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    def test_forbidden_helpers_allow_only_declared_top_level_fields(self) -> None:
        self.assertEqual(forbidden_session_create_fields({"model_id": "gpt-5.3-codex"}), [])
        self.assertEqual(forbidden_prompt_dry_run_fields({"prompt": "OK"}), [])
        self.assertEqual(forbidden_prompt_run_fields({"prompt": "OK"}), [])
        self.assertEqual(
            forbidden_prompt_dry_run_fields({"prompt": "OK", "items": [{"path": "/tmp/x"}]}),
            ["items", "items[0].path"],
        )
        self.assertEqual(
            forbidden_prompt_run_fields({"prompt": "OK", "items": [{"path": "/tmp/x"}]}),
            ["items", "items[0].path"],
        )


if __name__ == "__main__":
    unittest.main()
