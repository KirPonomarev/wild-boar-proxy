# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
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


def init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    (path / "README.md").write_text("safe worktree test repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.invalid", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


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


def operator_status_with_model_entries(entries: list[dict[str, object]]) -> dict[str, object]:
    return {
        "status": {"status": "ok", "machine_error_code": "OK"},
        "claim_gate": {"status": "blocked_by_policy_drift"},
        "models": {
            "ok": True,
            "server_issued": True,
            "model_entries": entries,
        },
    }


def api_snapshot(route_id: str = "wbp-web-primary-openrouter") -> dict[str, object]:
    return {
        "status": "ok",
        "source": "api_connections_readonly",
        "primary_truth_ok": True,
        "routes": [
            {
                "route_id": route_id,
                "provider": "openrouter",
                "upstream_model": "openai/gpt-5",
                "enabled": True,
                "secret_ref": "OPENROUTER_API_KEY",
            }
        ],
    }


class CodexCustomSessionManagerTests(unittest.TestCase):
    def test_create_session_binds_server_model_and_selection_without_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            packet = manager.create_packet(
                {
                    "primary_model_id": "gpt-5.3-codex",
                    "coding_agent_model_id": "wbp-web-primary-openrouter",
                },
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )

            self.assertEqual(packet["status"], "ok")
            self.assertTrue(packet["session_created"])
            self.assertFalse(packet["live_prompt_admitted"])
            self.assertFalse(packet["current_codex_home_used"])
            self.assertTrue(packet["selected_backend_id_redacted"])
            self.assertEqual(packet["current_execution_slot_id"], "primary_model_slot")
            self.assertEqual(packet["current_execution_path_model_id"], "gpt-5.3-codex")
            self.assertEqual(packet["current_execution_path_source"], "session_primary_model_slot")
            session = packet["session"]
            self.assertEqual(session["session_schema_version"], 3)
            self.assertFalse(session["legacy_single_model_migrated"])
            self.assertTrue(session["role_slot_binding_proven"])
            self.assertEqual(session["role_slot_binding_count"], 2)
            self.assertTrue(session["model_server_issued"])
            self.assertEqual(session["current_execution_slot_id"], "primary_model_slot")
            self.assertEqual(session["current_execution_path_source"], "session_primary_model_slot")
            self.assertEqual(
                session["role_slots"]["primary_model_slot"]["model_id"],
                "gpt-5.3-codex",
            )
            self.assertEqual(
                session["role_slots"]["coding_agent_model_slot"]["model_id"],
                "wbp-web-primary-openrouter",
            )
            self.assertEqual(
                session["role_slots"]["primary_model_slot"]["selected_source_class"],
                "gpt_account",
            )
            self.assertTrue(
                session["role_slots"]["primary_model_slot"]["selected_backend_server_issued"]
            )
            self.assertFalse(
                session["role_slots"]["primary_model_slot"]["selected_route_server_issued"]
            )
            self.assertEqual(
                session["role_slots"]["coding_agent_model_slot"]["selected_source_class"],
                "route_backed",
            )
            self.assertFalse(
                session["role_slots"]["coding_agent_model_slot"]["selected_backend_server_issued"]
            )
            self.assertTrue(
                session["role_slots"]["coding_agent_model_slot"]["selected_route_server_issued"]
            )
            self.assertEqual(
                session["role_slots"]["reviewer_model_slot"]["binding_status"],
                "unbound",
            )
            self.assertTrue(session["selection_dry_run_proven"])
            self.assertFalse(session["live_selection_proven"])
            self.assertTrue(session["selection_proven"])
            self.assertTrue(session["selected_backend_id_redacted"])
            self.assertTrue(session["selected_backend_server_issued"])
            self.assertEqual(session["selected_route_digest"], "")
            self.assertFalse(session["selected_route_server_issued"])
            self.assertFalse(session["route_provenance_required"])
            self.assertFalse(session["route_provenance_proven"])
            self.assertEqual(session["source_provenance_status"], "backend_candidate_classified")
            self.assertTrue(session["source_candidate_classified"])
            self.assertFalse(session["source_provenance_proven"])
            self.assertTrue(session["model_selected_by_user"])
            self.assertTrue(session["role_slot_selected_by_user"])
            self.assertEqual(session["account_candidate_source"], "server_ranked_candidate")
            self.assertFalse(session["account_selected_by_user"])
            self.assertFalse(session["browser_selected_backend"])
            self.assertFalse(session["account_execution_proven"])
            self.assertFalse(session["runtime_execution_proven"])
            self.assertFalse(session["live_compatibility_proven"])
            self.assertFalse(session["raw_backend_exposed"])
            self.assertFalse(session["raw_backend_id_exposed"])
            self.assertFalse(session["current_codex_home_used"])
            self.assertEqual(session["session_root_scope"], "owned_temp_session_root")
            self.assertNotIn(temp_dir, json.dumps(packet))
            self.assertNotIn("acct-a", json.dumps(packet))
            self.assertFalse(packet["inference_proven"])
            self.assertFalse(packet["runtime_meter_attached"])
            self.assertFalse(packet["network_calls_made"])
            self.assertFalse(packet["provider_called"])
            self.assertEqual(packet["token_burn"], 0)

    def test_manager_loads_legacy_single_model_session_and_migrates_to_role_slots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            session_root = root / "ccs-legacy1234"
            session_root.mkdir()
            (session_root / "codex-home").mkdir()
            (session_root / "workdir").mkdir()
            legacy_payload = {
                "session": {
                    "session_id": "ccs-legacy1234",
                    "created_at_utc": "2026-05-28T00:00:00Z",
                    "updated_at_utc": "2026-05-28T00:00:00Z",
                    "status": "ready",
                    "model_id": "gpt-5.3-codex",
                    "model_server_issued": True,
                    "selected_source_class": "gpt_account",
                    "selected_backend_digest": "digest-acct-a",
                    "selected_backend_id_redacted": True,
                    "selected_backend_server_issued": True,
                    "selected_route_digest": "",
                    "selected_route_server_issued": False,
                    "route_provenance_required": False,
                    "route_provenance_proven": False,
                    "source_provenance_status": "backend_proven",
                    "source_provenance_proven": True,
                    "selection_dry_run_proven": True,
                    "live_selection_proven": False,
                    "selection_proven": True,
                    "selection_machine_error_code": "OK",
                    "session_root_digest": "legacy-root",
                    "codex_home_digest": "legacy-home",
                    "session_root_scope": "owned_temp_session_root",
                    "current_codex_home_used": False,
                    "prompt_admission_count": 0,
                    "cleanup_state": "not_cleaned",
                    "cancel_state": "not_cancelled",
                    "ledger_entry_count": 0,
                    "model_response_present": False,
                    "inference_proven": False,
                    "runtime_meter_attached": False,
                    "network_calls_made": False,
                    "provider_called": False,
                    "token_burn": 0,
                },
                "ledger": [],
            }
            (session_root / "session.json").write_text(
                json.dumps(legacy_payload, indent=2) + "\n",
                encoding="utf-8",
            )
            manager = CodexCustomSessionManager(root)
            packet = manager.get_packet("ccs-legacy1234")

            self.assertEqual(packet["status"], "ok")
            session = packet["session"]
            self.assertEqual(session["session_schema_version"], 3)
            self.assertTrue(session["legacy_single_model_migrated"])
            self.assertEqual(session["migration_status"], "legacy_single_model_migrated")
            self.assertEqual(session["model_id"], "gpt-5.3-codex")
            self.assertEqual(
                session["role_slots"]["primary_model_slot"]["binding_source"],
                "legacy_single_model_migration",
            )
            self.assertEqual(
                session["role_slots"]["primary_model_slot"]["model_id"],
                "gpt-5.3-codex",
            )
            self.assertEqual(
                session["role_slots"]["coding_agent_model_slot"]["binding_status"],
                "unbound",
            )
            self.assertEqual(
                packet["role_slot_binding_packet"]["current_execution_slot_id"],
                "primary_model_slot",
            )
            self.assertFalse(session["slot_catalog_revalidated"])

    def test_create_session_rejects_free_form_model_and_browser_backend_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            bad_model = manager.create_packet(
                {"primary_model_id": "free-form"},
                commands(),
                operator_status(),
            )
            bad_fields = manager.create_packet(
                {
                    "primary_model_id": "gpt-5.3-codex",
                    "account_id": "acct-a",
                    "backend_id": "acct-a",
                    "route_id": "route",
                    "auth_path": "/tmp/auth.json",
                    "profile_path": "/tmp/profile",
                    "codex_home": "/tmp/codex-home",
                    "secret_ref": "BROWSER_SECRET",
                    "base_url": "https://example.invalid/v1",
                    "api_key": "browser-key",
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
            self.assertIn("auth_path", bad_fields["forbidden_fields"])
            self.assertIn("profile_path", bad_fields["forbidden_fields"])
            self.assertIn("codex_home", bad_fields["forbidden_fields"])
            self.assertIn("secret_ref", bad_fields["forbidden_fields"])
            self.assertIn("base_url", bad_fields["forbidden_fields"])
            self.assertIn("api_key", bad_fields["forbidden_fields"])
            self.assertIn("route_id", bad_fields["forbidden_fields"])
            self.assertIn("path", bad_fields["forbidden_fields"])

    def test_create_session_requires_manual_server_model_selection_without_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            packet = manager.create_packet({}, commands(), operator_status(), api_snapshot=api_snapshot())
            legacy_alias = manager.create_packet(
                {"model_id": "gpt-5.3-codex"},
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )

            self.assertEqual(packet["status"], "rejected")
            self.assertEqual(packet["machine_error_code"], "MANUAL_MODEL_SELECTION_REQUIRED")
            self.assertFalse(packet["session_created"])
            self.assertFalse(packet["model_auto_selected"])
            self.assertFalse(packet["fallback_used"])
            self.assertFalse(packet["external_route_selected"])
            self.assertIn("primary_model_id", packet["required_choice_fields"])
            self.assertEqual(legacy_alias["status"], "rejected")
            self.assertEqual(legacy_alias["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
            self.assertEqual(legacy_alias["forbidden_fields"], ["model_id"])
            self.assertFalse(legacy_alias["session_created"])
            self.assertFalse(legacy_alias["model_auto_selected"])
            self.assertEqual(manager.list_packet()["session_count"], 0)

    def test_create_session_accepts_server_owned_route_model_when_api_snapshot_visible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            packet = manager.create_packet(
                {"primary_model_id": "wbp-web-primary-openrouter"},
                commands(),
                operator_status(),
                selection={
                    "status": "ok",
                    "machine_error_code": "OK",
                    "selection_proven": True,
                    "selection_dry_run_proven": True,
                    "live_selection_proven": False,
                    "selected_source_class": "route_backed",
                    "selected_backend_ref": "",
                    "selected_backend_server_issued": False,
                    "selected_route_ref": "route-digest",
                    "selected_route_server_issued": True,
                    "route_provenance_required": True,
                    "route_provenance_proven": False,
                    "source_provenance_status": "route_static_candidate_classified",
                },
                api_snapshot=api_snapshot(),
            )

            self.assertEqual(packet["status"], "ok")
            self.assertTrue(packet["session_created"])
            self.assertTrue(packet["session"]["model_server_issued"])
            self.assertEqual(packet["session"]["model_lane"], "api_route_lane")
            self.assertTrue(packet["session"]["model_lane_classified"])
            self.assertEqual(
                packet["session"]["model_lane_classification_source"],
                "server_api_route_snapshot",
            )
            self.assertFalse(packet["session"]["model_lane_fallback_used"])
            self.assertFalse(packet["session"]["runtime_lane_proven"])
            self.assertEqual(packet["session"]["selected_source_class"], "route_backed")
            self.assertTrue(packet["session"]["selected_route_server_issued"])
            self.assertTrue(packet["session"]["route_static_readiness_classified"])
            self.assertFalse(packet["session"]["route_provenance_proven"])
            self.assertEqual(
                packet["session"]["source_provenance_status"],
                "route_static_candidate_classified",
            )

    def test_create_session_uses_server_lane_when_api_route_name_starts_with_gpt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            packet = manager.create_packet(
                {"primary_model_id": "gpt-external-route"},
                commands(),
                operator_status(),
                api_snapshot=api_snapshot("gpt-external-route"),
            )

            self.assertEqual(packet["status"], "ok")
            self.assertTrue(packet["session_created"])
            self.assertEqual(packet["session"]["model_lane"], "api_route_lane")
            self.assertEqual(
                packet["session"]["model_lane_classification_source"],
                "server_api_route_snapshot",
            )
            self.assertEqual(packet["session"]["selected_source_class"], "route_backed")
            self.assertFalse(packet["session"]["selected_backend_server_issued"])
            self.assertTrue(packet["session"]["selected_route_server_issued"])
            self.assertFalse(packet["session"]["runtime_lane_proven"])

    def test_create_session_uses_server_lane_for_non_gpt_native_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            packet = manager.create_packet(
                {"primary_model_id": "orion-native"},
                commands(),
                operator_status_with_model_entries(
                    [{"model_id": "orion-native", "lane": "codex_native"}]
                ),
            )

            self.assertEqual(packet["status"], "ok")
            self.assertTrue(packet["session_created"])
            self.assertEqual(packet["session"]["model_lane"], "codex_account_lane")
            self.assertEqual(
                packet["session"]["model_lane_classification_source"],
                "server_model_catalog",
            )
            self.assertFalse(packet["session"]["model_lane_fallback_used"])
            self.assertEqual(packet["session"]["selected_source_class"], "gpt_account")

    def test_create_session_rejects_heuristic_only_gpt_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            packet = manager.create_packet(
                {"primary_model_id": "gpt-unknown-local"},
                commands(),
                {
                    "status": {"status": "ok", "machine_error_code": "OK"},
                    "claim_gate": {"status": "blocked_by_policy_drift"},
                    "models": {
                        "ok": True,
                        "server_issued": True,
                        "model_ids": ["gpt-unknown-local"],
                    },
                },
            )

            self.assertEqual(packet["status"], "rejected")
            self.assertEqual(packet["machine_error_code"], "HEURISTIC_ONLY_NOT_EXECUTABLE")
            self.assertFalse(packet["session_created"])
            self.assertEqual(packet["model_id"], "gpt-unknown-local")
            self.assertEqual(packet["selection_packet"]["model_lane"], "unknown_lane")
            self.assertTrue(packet["selection_packet"]["model_lane_fallback_used"])
            self.assertTrue(packet["selection_packet"]["heuristic_only_not_executable"])

    def test_create_session_derives_session_selection_truth_from_primary_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            packet = manager.create_packet(
                {"primary_model_id": "gpt-5.3-codex"},
                commands(),
                operator_status(),
                selection={
                    "status": "ok",
                    "machine_error_code": "OK",
                    "selection_proven": True,
                    "selection_dry_run_proven": True,
                    "live_selection_proven": False,
                    "selected_source_class": "route_backed",
                    "selected_backend_ref": "",
                    "selected_backend_server_issued": False,
                    "selected_route_ref": "wrong-route-digest",
                    "selected_route_server_issued": True,
                    "route_provenance_required": True,
                    "route_provenance_proven": False,
                    "route_static_readiness_classified": True,
                    "source_provenance_status": "route_static_candidate_classified",
                },
                api_snapshot=api_snapshot(),
            )

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["session"]["selected_source_class"], "gpt_account")
            self.assertTrue(packet["session"]["selected_backend_server_issued"])
            self.assertFalse(packet["session"]["selected_route_server_issued"])
            self.assertFalse(packet["session"]["route_provenance_required"])
            self.assertEqual(packet["selection_packet"]["selected_source_class"], "gpt_account")
            self.assertFalse(packet["selection_packet"]["selected_route_server_issued"])

    def test_create_session_accepts_all_declared_role_slots_when_server_issued(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            packet = manager.create_packet(
                {
                    "primary_model_id": "gpt-5.3-codex",
                    "coding_agent_model_id": "wbp-web-primary-openrouter",
                    "reviewer_model_id": "gpt-5.4",
                    "cheap_scanner_model_id": "gpt-5.4",
                    "deep_reasoning_model_id": "gpt-5.4",
                },
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["session"]["role_slot_binding_count"], 5)
            self.assertEqual(
                packet["session"]["role_slots"]["reviewer_model_slot"]["model_id"],
                "gpt-5.4",
            )
            self.assertEqual(
                packet["session"]["role_slots"]["cheap_scanner_model_slot"]["model_id"],
                "gpt-5.4",
            )
            self.assertEqual(
                packet["session"]["role_slots"]["deep_reasoning_model_slot"]["model_id"],
                "gpt-5.4",
            )

    def test_create_session_rejects_when_account_selection_is_not_proven(self) -> None:
        weak_commands = commands()
        weak_commands["accounts_list"] = command({"accounts": []})
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            packet = manager.create_packet(
                {"primary_model_id": "gpt-5.3-codex"},
                weak_commands,
                operator_status(),
            )

            self.assertEqual(packet["status"], "rejected")
            self.assertEqual(packet["machine_error_code"], "NO_LAUNCH_CAPABLE_GPT_ACCOUNT")
            self.assertFalse(packet["selection_proven"])
            self.assertFalse(packet["session_created"])
            self.assertEqual(packet["next_action"], "repair_account_selection_truth")
            self.assertEqual(manager.list_packet()["session_count"], 0)

    def test_reloaded_multi_slot_session_requires_slot_revalidation_before_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = CodexCustomSessionManager(root)
            created = manager.create_packet(
                {
                    "primary_model_id": "gpt-5.3-codex",
                    "coding_agent_model_id": "wbp-web-primary-openrouter",
                },
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )
            session_id = created["session"]["session_id"]
            manager.prompt_dry_run_packet(session_id, {"prompt": "Reply with exactly OK."})

            reloaded = CodexCustomSessionManager(root)
            detail = reloaded.get_packet(session_id)
            blocked = reloaded.prompt_packet(
                session_id,
                {"prompt": "Reply with exactly OK."},
                lambda payload: {"status": "ok", "final_message": "OK"},
                owner_authorized=True,
            )

            self.assertEqual(detail["status"], "ok")
            self.assertFalse(detail["session"]["slot_catalog_revalidated"])
            self.assertFalse(detail["role_slot_binding_packet"]["slot_catalog_revalidated"])
            self.assertEqual(blocked["status"], "rejected")
            self.assertEqual(blocked["machine_error_code"], "SLOT_CATALOG_REVALIDATION_REQUIRED")
            self.assertIn("SLOT_CATALOG_REVALIDATION_REQUIRED", blocked["precondition_failures"])

    def test_reloaded_multi_slot_session_can_revalidate_and_run_with_exact_identity(self) -> None:
        calls: list[dict[str, object]] = []

        def runner(payload: dict[str, object]) -> dict[str, object]:
            calls.append(dict(payload))
            route_backed = payload.get("model_id") == "wbp-web-primary-openrouter"
            model_id = str(payload.get("model_id") or "")
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "requested_slot_id": payload.get("slot_id"),
                "runtime_model": model_id,
                "selected_model": model_id,
                "final_message": "ROUTE_OK" if route_backed else "PRIMARY_OK",
                "secret_value_recorded": False,
                "configured_provider": "external_route" if route_backed else "cliproxy",
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
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = CodexCustomSessionManager(root)
            created = manager.create_packet(
                {
                    "primary_model_id": "gpt-5.3-codex",
                    "coding_agent_model_id": "wbp-web-primary-openrouter",
                },
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )
            session_id = created["session"]["session_id"]
            manager.prompt_dry_run_packet(session_id, {"prompt": "Reply with exactly OK."})

            reloaded = CodexCustomSessionManager(root)
            revalidated = reloaded.revalidate_packet(
                session_id,
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )
            primary = reloaded.prompt_packet(
                session_id,
                {"prompt": "PRIMARY", "slot_id": "primary_model_slot"},
                runner,
                owner_authorized=True,
            )
            coding = reloaded.prompt_packet(
                session_id,
                {"prompt": "CODING", "slot_id": "coding_agent_model_slot"},
                runner,
                owner_authorized=True,
            )

            self.assertEqual(revalidated["status"], "ok")
            self.assertTrue(revalidated["slot_catalog_revalidated"])
            self.assertTrue(revalidated["provider_model_identity_persistence_proven"])
            self.assertTrue(
                revalidated[
                    "no_hidden_fallback_from_saved_slot_to_different_provider_model_proven"
                ]
            )
            self.assertTrue(revalidated["same_provider_account_selection_proven"])
            self.assertEqual(revalidated["revalidated_bound_slot_count"], 2)
            self.assertEqual(primary["status"], "ok")
            self.assertEqual(primary["runtime_selected_model"], "gpt-5.3-codex")
            self.assertTrue(primary["runtime_selected_model_matches_bound_model"])
            self.assertEqual(primary["selected_source_provenance"], "backend_proven")
            self.assertEqual(primary["configured_provider"], "cliproxy")
            self.assertEqual(coding["status"], "ok")
            self.assertEqual(coding["runtime_selected_model"], "wbp-web-primary-openrouter")
            self.assertTrue(coding["runtime_selected_model_matches_bound_model"])
            self.assertEqual(coding["selected_source_provenance"], "route_proven")
            self.assertEqual(coding["configured_provider"], "external_route")
            self.assertEqual(
                calls,
                [
                    {
                        "prompt": "PRIMARY",
                        "model_id": "gpt-5.3-codex",
                        "slot_id": "primary_model_slot",
                    },
                    {
                        "prompt": "CODING",
                        "model_id": "wbp-web-primary-openrouter",
                        "slot_id": "coding_agent_model_slot",
                    },
                ],
            )

    def test_revalidate_blocks_when_reloaded_slot_source_class_drops_from_saved_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = CodexCustomSessionManager(root)
            created = manager.create_packet(
                {
                    "primary_model_id": "gpt-5.3-codex",
                    "coding_agent_model_id": "wbp-web-primary-openrouter",
                },
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )
            session_id = created["session"]["session_id"]
            manager.prompt_dry_run_packet(session_id, {"prompt": "Reply with exactly OK."})

            reloaded = CodexCustomSessionManager(root)
            blocked = reloaded.revalidate_packet(
                session_id,
                commands(),
                operator_status(),
                api_snapshot={"status": "ok", "source": "api_connections_readonly", "routes": []},
            )

            self.assertEqual(blocked["status"], "blocked")
            self.assertEqual(blocked["machine_error_code"], "MODEL_NOT_SERVER_ISSUED")
            self.assertFalse(blocked["slot_catalog_revalidated"])
            self.assertFalse(blocked["provider_model_identity_persistence_proven"])
            self.assertFalse(
                blocked[
                    "no_hidden_fallback_from_saved_slot_to_different_provider_model_proven"
                ]
            )

    def test_prompt_dry_run_hashes_prompt_and_does_not_claim_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"primary_model_id": "gpt-5.3-codex"}, commands(), operator_status())
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

    def test_prompt_run_can_dispatch_primary_and_coding_slot_in_same_session(self) -> None:
        calls: list[dict[str, object]] = []

        def runner(payload: dict[str, object]) -> dict[str, object]:
            calls.append(dict(payload))
            route_backed = payload.get("model_id") == "wbp-web-primary-openrouter"
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "requested_slot_id": payload.get("slot_id"),
                "final_message": "ROUTE_OK" if route_backed else "PRIMARY_OK",
                "secret_value_recorded": False,
                "configured_provider": "external_route" if route_backed else "cliproxy",
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
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet(
                {
                    "primary_model_id": "gpt-5.3-codex",
                    "coding_agent_model_id": "wbp-web-primary-openrouter",
                },
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )
            session_id = created["session"]["session_id"]

            primary = manager.prompt_packet(
                session_id,
                {
                    "prompt": "Reply primary OK.",
                    "slot_id": "primary_model_slot",
                },
                runner,
                owner_authorized=True,
            )
            coding = manager.prompt_packet(
                session_id,
                {
                    "prompt": "Reply coding OK.",
                    "slot_id": "coding_agent_model_slot",
                },
                runner,
                owner_authorized=True,
            )

            self.assertEqual(primary["status"], "ok")
            self.assertEqual(primary["current_execution_slot_id"], "primary_model_slot")
            self.assertEqual(primary["requested_slot_id"], "primary_model_slot")
            self.assertTrue(primary["requested_slot_explicit"])
            self.assertFalse(primary["requested_slot_defaulted_to_primary"])
            self.assertEqual(primary["runner_slot_id_echo"], "primary_model_slot")
            self.assertTrue(primary["runner_slot_id_matches_requested"])
            self.assertTrue(primary["requested_slot_bound"])
            self.assertTrue(primary["slot_catalog_revalidated"])
            self.assertTrue(primary["slot_model_server_issued"])
            self.assertTrue(primary["slot_lane_revalidated"])
            self.assertTrue(primary["slot_source_revalidated"])
            self.assertTrue(primary["slot_admission_passed"])
            self.assertEqual(primary["wbp_runner_payload_slot_id"], "primary_model_slot")
            self.assertEqual(primary["wbp_runner_payload_model_id"], "gpt-5.3-codex")
            self.assertTrue(primary["wbp_runner_payload_slot_matches_requested"])
            self.assertTrue(primary["wbp_runner_payload_model_matches_slot"])
            self.assertTrue(primary["wbp_session_manager_slot_dispatch_proven"])
            self.assertEqual(
                primary["runtime_slot_dispatch_proof_scope"],
                "wbp_session_manager_payload_plus_downstream_echo",
            )
            self.assertTrue(primary["downstream_runner_slot_echo_present"])
            self.assertEqual(primary["downstream_runner_slot_echo"], "primary_model_slot")
            self.assertTrue(primary["downstream_runner_slot_echo_matches_requested"])
            self.assertEqual(primary["executed_slot_id"], "primary_model_slot")
            self.assertEqual(primary["executed_slot_model_id"], "gpt-5.3-codex")
            self.assertTrue(primary["runtime_slot_dispatch_proven"])
            self.assertTrue(primary["slot_binding_runtime_dispatch_claimed"])
            self.assertFalse(primary["parallel_slot_execution_proven"])
            self.assertFalse(primary["fanout_execution_proven"])
            self.assertEqual(primary["current_execution_path_source"], "session_bound_slot_runtime")
            self.assertEqual(primary["model_id"], "gpt-5.3-codex")
            self.assertEqual(primary["selected_source_class"], "gpt_account")
            self.assertEqual(primary["selected_source_provenance"], "backend_proven")
            self.assertTrue(primary["selected_backend_server_issued"])
            self.assertFalse(primary["selected_route_server_issued"])
            self.assertTrue(primary["live_prompt_full_success"])

            self.assertEqual(coding["status"], "ok")
            self.assertEqual(coding["session_id"], session_id)
            self.assertEqual(coding["current_execution_slot_id"], "coding_agent_model_slot")
            self.assertEqual(coding["requested_slot_id"], "coding_agent_model_slot")
            self.assertTrue(coding["requested_slot_explicit"])
            self.assertFalse(coding["requested_slot_defaulted_to_primary"])
            self.assertEqual(coding["runner_slot_id_echo"], "coding_agent_model_slot")
            self.assertTrue(coding["runner_slot_id_matches_requested"])
            self.assertTrue(coding["requested_slot_bound"])
            self.assertTrue(coding["slot_catalog_revalidated"])
            self.assertTrue(coding["slot_model_server_issued"])
            self.assertTrue(coding["slot_lane_revalidated"])
            self.assertTrue(coding["slot_source_revalidated"])
            self.assertTrue(coding["slot_admission_passed"])
            self.assertEqual(coding["wbp_runner_payload_slot_id"], "coding_agent_model_slot")
            self.assertEqual(coding["wbp_runner_payload_model_id"], "wbp-web-primary-openrouter")
            self.assertTrue(coding["wbp_runner_payload_slot_matches_requested"])
            self.assertTrue(coding["wbp_runner_payload_model_matches_slot"])
            self.assertTrue(coding["wbp_session_manager_slot_dispatch_proven"])
            self.assertEqual(
                coding["runtime_slot_dispatch_proof_scope"],
                "wbp_session_manager_payload_plus_downstream_echo",
            )
            self.assertTrue(coding["downstream_runner_slot_echo_present"])
            self.assertEqual(coding["downstream_runner_slot_echo"], "coding_agent_model_slot")
            self.assertTrue(coding["downstream_runner_slot_echo_matches_requested"])
            self.assertEqual(coding["executed_slot_id"], "coding_agent_model_slot")
            self.assertEqual(coding["executed_slot_model_id"], "wbp-web-primary-openrouter")
            self.assertTrue(coding["runtime_slot_dispatch_proven"])
            self.assertTrue(coding["slot_binding_runtime_dispatch_claimed"])
            self.assertFalse(coding["parallel_slot_execution_proven"])
            self.assertFalse(coding["fanout_execution_proven"])
            self.assertEqual(coding["current_execution_path_source"], "session_bound_slot_runtime")
            self.assertEqual(coding["model_id"], "wbp-web-primary-openrouter")
            self.assertEqual(coding["selected_source_class"], "route_backed")
            self.assertEqual(coding["selected_source_provenance"], "route_proven")
            self.assertFalse(coding["selected_backend_server_issued"])
            self.assertTrue(coding["selected_route_server_issued"])
            self.assertTrue(coding["route_provenance_required"])
            self.assertTrue(coding["route_provenance_proven"])
            self.assertTrue(coding["live_prompt_full_success"])
            self.assertEqual(
                calls,
                [
                    {
                        "prompt": "Reply primary OK.",
                        "model_id": "gpt-5.3-codex",
                        "slot_id": "primary_model_slot",
                    },
                    {
                        "prompt": "Reply coding OK.",
                        "model_id": "wbp-web-primary-openrouter",
                        "slot_id": "coding_agent_model_slot",
                    },
                ],
            )
            detail = manager.get_packet(session_id)
            self.assertEqual(
                detail["session"]["current_execution_slot_id"],
                "coding_agent_model_slot",
            )
            self.assertEqual(
                detail["role_slot_binding_packet"]["current_execution_slot_id"],
                "coding_agent_model_slot",
            )

    def test_prompt_run_can_dispatch_bound_reviewer_slot_without_primary_swap(self) -> None:
        calls: list[dict[str, object]] = []

        def runner(payload: dict[str, object]) -> dict[str, object]:
            calls.append(dict(payload))
            model_id = str(payload.get("model_id") or "")
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "requested_slot_id": payload.get("slot_id"),
                "selected_model": model_id,
                "runtime_model": model_id,
                "final_message": "REVIEWER_OK",
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
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet(
                {
                    "primary_model_id": "gpt-5.3-codex",
                    "reviewer_model_id": "gpt-5.4",
                },
                commands(),
                operator_status(),
            )
            packet = manager.prompt_packet(
                created["session"]["session_id"],
                {"prompt": "Review this.", "slot_id": "reviewer_model_slot"},
                runner,
                owner_authorized=True,
            )

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["current_execution_slot_id"], "reviewer_model_slot")
            self.assertEqual(packet["requested_slot_id"], "reviewer_model_slot")
            self.assertEqual(packet["model_id"], "gpt-5.4")
            self.assertEqual(packet["executed_slot_id"], "reviewer_model_slot")
            self.assertEqual(packet["executed_slot_model_id"], "gpt-5.4")
            self.assertEqual(packet["wbp_runner_payload_slot_id"], "reviewer_model_slot")
            self.assertEqual(packet["wbp_runner_payload_model_id"], "gpt-5.4")
            self.assertTrue(packet["wbp_runner_payload_slot_matches_requested"])
            self.assertTrue(packet["wbp_runner_payload_model_matches_slot"])
            self.assertTrue(packet["wbp_session_manager_slot_dispatch_proven"])
            self.assertTrue(packet["runtime_slot_dispatch_proven"])
            self.assertTrue(packet["slot_binding_runtime_dispatch_claimed"])
            self.assertFalse(packet["parallel_slot_execution_proven"])
            self.assertFalse(packet["fanout_execution_proven"])
            self.assertEqual(
                calls,
                [
                    {
                        "prompt": "Review this.",
                        "model_id": "gpt-5.4",
                        "slot_id": "reviewer_model_slot",
                    }
                ],
            )

    def test_prompt_run_blocks_unbound_reviewer_slot_without_primary_fallback(self) -> None:
        calls: list[dict[str, object]] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet(
                {
                    "primary_model_id": "gpt-5.3-codex",
                    "coding_agent_model_id": "wbp-web-primary-openrouter",
                },
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )
            packet = manager.prompt_packet(
                created["session"]["session_id"],
                {"prompt": "Review this.", "slot_id": "reviewer_model_slot"},
                lambda payload: calls.append(dict(payload)) or {"status": "ok", "final_message": "SHOULD_NOT_RUN"},
                owner_authorized=True,
            )

            self.assertEqual(packet["status"], "rejected")
            self.assertEqual(packet["machine_error_code"], "SLOT_NOT_BOUND")
            self.assertEqual(packet["requested_slot_id"], "reviewer_model_slot")
            self.assertEqual(packet["current_execution_slot_id"], "primary_model_slot")
            self.assertIn("SLOT_NOT_BOUND", packet["precondition_failures"])
            self.assertFalse(packet["requested_slot_bound"])
            self.assertTrue(packet["slot_catalog_revalidated"])
            self.assertFalse(packet["slot_model_server_issued"])
            self.assertFalse(packet["slot_lane_revalidated"])
            self.assertFalse(packet["slot_source_revalidated"])
            self.assertFalse(packet["slot_admission_passed"])
            self.assertEqual(packet["runtime_slot_dispatch_proof_scope"], "not_attempted_precondition_failed")
            self.assertFalse(packet["runtime_slot_dispatch_proven"])
            self.assertFalse(packet["slot_binding_runtime_dispatch_claimed"])
            self.assertFalse(packet["parallel_slot_execution_proven"])
            self.assertFalse(packet["fanout_execution_proven"])
            self.assertFalse(packet["model_response_present"])
            self.assertFalse(packet["fallback_attempted"])
            self.assertEqual(calls, [])

    def test_prompt_run_rejects_invalid_slot_id_without_primary_fallback(self) -> None:
        calls: list[dict[str, object]] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet(
                {"primary_model_id": "gpt-5.3-codex"},
                commands(),
                operator_status(),
            )
            packet = manager.prompt_packet(
                created["session"]["session_id"],
                {"prompt": "OK", "slot_id": "made_up_slot"},
                lambda payload: calls.append(payload) or {"status": "ok", "final_message": "SHOULD_NOT_RUN"},
                owner_authorized=True,
            )

            self.assertEqual(packet["status"], "rejected")
            self.assertEqual(packet["machine_error_code"], "SLOT_ID_NOT_SERVER_ISSUED")
            self.assertFalse(packet["model_response_present"])
            self.assertFalse(packet["fallback_attempted"])
            self.assertEqual(calls, [])

    def test_prompt_dry_run_rejects_forbidden_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"primary_model_id": "gpt-5.3-codex"}, commands(), operator_status())
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
            created = manager.create_packet({"primary_model_id": "gpt-5.3-codex"}, commands(), operator_status())
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
            created = manager.create_packet({"primary_model_id": "gpt-5.3-codex"}, commands(), operator_status())
            session_id = created["session"]["session_id"]
            packet = manager.prompt_packet(
                session_id,
                {"prompt": "Reply real OK."},
                runner,
                owner_authorized=True,
            )
            detail = manager.get_packet(session_id)
            transcript = manager.transcript_packet(session_id)

            self.assertEqual(
                calls,
                [
                    {
                        "prompt": "Reply real OK.",
                        "model_id": "gpt-5.3-codex",
                        "slot_id": "primary_model_slot",
                        "slot_id_explicit": False,
                    }
                ],
            )
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
            self.assertEqual(packet["source_provenance_status"], "backend_candidate_classified")
            self.assertTrue(packet["source_candidate_classified"])
            self.assertFalse(packet["source_provenance_proven"])
            self.assertFalse(packet["browser_selected_backend"])
            self.assertEqual(packet["account_candidate_source"], "server_ranked_candidate")
            self.assertFalse(packet["account_selected_by_user"])
            self.assertFalse(packet["account_execution_proven"])
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
            self.assertTrue(packet["requested_slot_defaulted_to_primary"])
            self.assertEqual(packet["wbp_runner_payload_slot_id"], "primary_model_slot")
            self.assertEqual(packet["wbp_runner_payload_model_id"], "gpt-5.3-codex")
            self.assertTrue(packet["wbp_runner_payload_slot_matches_requested"])
            self.assertTrue(packet["wbp_runner_payload_model_matches_slot"])
            self.assertTrue(packet["wbp_session_manager_slot_dispatch_proven"])
            self.assertEqual(
                packet["runtime_slot_dispatch_proof_scope"],
                "wbp_session_manager_payload_plus_downstream_echo",
            )
            self.assertFalse(packet["downstream_runner_slot_echo_present"])
            self.assertEqual(packet["downstream_runner_slot_echo"], "")
            self.assertFalse(packet["downstream_runner_slot_echo_matches_requested"])
            self.assertEqual(packet["executed_slot_id"], "primary_model_slot")
            self.assertEqual(packet["executed_slot_model_id"], "gpt-5.3-codex")
            self.assertFalse(packet["runtime_slot_dispatch_proven"])
            self.assertFalse(packet["slot_binding_runtime_dispatch_claimed"])
            self.assertFalse(packet["parallel_slot_execution_proven"])
            self.assertFalse(packet["fanout_execution_proven"])
            self.assertNotIn("Reply real OK.", json.dumps(packet))
            self.assertNotIn("acct-a", json.dumps(packet))
            self.assertEqual(detail["session"]["status"], "prompt_blocked_after_response_e2e")
            self.assertTrue(detail["session"]["model_response_present"])
            self.assertFalse(detail["session"]["inference_proven"])
            self.assertTrue(transcript["model_response_present"])
            self.assertFalse(transcript["inference_proven"])
            self.assertNotIn("Reply real OK.", json.dumps(transcript))

    def test_prompt_run_defaults_to_owner_authorization_block(self) -> None:
        calls: list[dict[str, object]] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"primary_model_id": "gpt-5.3-codex"}, commands(), operator_status())
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
            created = manager.create_packet({"primary_model_id": "gpt-5.3-codex"}, commands(), operator_status())
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
                "selected_model": "gpt-5.3-codex",
                "runtime_model": "gpt-5.3-codex",
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
                    "response_error_type": "invalid_request_error",
                    "response_error_message_bounded": "bounded provider message",
                    "authorization": "forbidden",
                    "raw_body": "forbidden",
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"primary_model_id": "gpt-5.3-codex"}, commands(), operator_status())
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
            self.assertEqual(
                packet["trace_observer_packet"]["response_error_type"],
                "invalid_request_error",
            )
            self.assertEqual(
                packet["trace_observer_packet"]["response_error_message_bounded"],
                "bounded provider message",
            )
            self.assertNotIn("authorization", packet["trace_observer_packet"])
            self.assertNotIn("raw_body", packet["trace_observer_packet"])
            self.assertTrue(packet["wbp_path_proven"])
            self.assertTrue(packet["cli_proxy_api_path_proven"])
            self.assertTrue(packet["live_prompt_full_success"])
            self.assertFalse(packet["route_provenance_required"])
            self.assertFalse(packet["route_provenance_proven"])
            self.assertEqual(packet["source_provenance_status"], "backend_proven")
            self.assertTrue(packet["source_candidate_classified"])
            self.assertTrue(packet["source_provenance_proven"])
            self.assertEqual(packet["selected_source_provenance"], "backend_proven")
            self.assertEqual(packet["account_candidate_source"], "server_ranked_candidate")
            self.assertFalse(packet["account_selected_by_user"])
            self.assertFalse(packet["account_execution_proven"])
            self.assertFalse(packet["current_codex_touched"])
            self.assertEqual(packet["path_proof_status"], "independently_observed")
            self.assertTrue(packet["runtime_selected_model_recorded"])
            self.assertTrue(packet["runtime_selected_model_matches_bound_model"])

    def test_api_only_temp_write_probe_requires_owner_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet(
                {"primary_model_id": "wbp-web-primary-openrouter"},
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )

            packet = manager.temp_write_probe_packet(
                created["session"]["session_id"],
                {"api_model_id": "wbp-web-primary-openrouter"},
                lambda _payload, _writable_dir: self.fail("runner must not be called"),
                owner_authorized=False,
            )

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(packet["machine_error_code"], "OWNER_AUTHORIZATION_REQUIRED")
            self.assertEqual(
                packet["final_status"],
                "KNOWN_BLOCKER_API_ONLY_DEEPSEEK_TEMP_WRITE_NOT_ADMITTED",
            )
            self.assertFalse(packet["repo_mutation_attempted"])

    def test_api_only_temp_write_probe_rejects_browser_path_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet(
                {"primary_model_id": "wbp-web-primary-openrouter"},
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )

            packet = manager.temp_write_probe_packet(
                created["session"]["session_id"],
                {"api_model_id": "wbp-web-primary-openrouter", "path": "/tmp/owned"},
                lambda _payload, _writable_dir: self.fail("runner must not be called"),
                owner_authorized=True,
            )

            self.assertEqual(packet["status"], "rejected")
            self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
            self.assertIn("path", packet["forbidden_fields"])
            self.assertFalse(packet["browser_path_intake"])
            self.assertFalse(packet["repo_mutation_attempted"])

    def test_api_only_temp_write_probe_proves_temp_file_write_and_cleanup(self) -> None:
        observed_payload: dict[str, object] = {}

        def runner(payload: dict[str, object], writable_dir: Path) -> dict[str, object]:
            observed_payload.update(payload)
            prompt = str(payload["prompt"])
            target = Path(prompt.split("> ", 1)[1].split(" &&", 1)[0]).resolve()
            self.assertEqual(target.parent, writable_dir)
            target.write_text("WBP_DEEPSEEK_TEMP_WRITE_OK", encoding="utf-8")
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "selected_model": "wbp-web-primary-openrouter",
                "runtime_model": "wbp-web-primary-openrouter",
                "final_message": "WBP_DEEPSEEK_TEMP_WRITE_OK",
                "configured_provider": "external_route",
                "configured_wire_api": "responses",
                "workspace_write_admitted": True,
                "current_codex_home_used": False,
                "secret_value_recorded": False,
                "trace_observer_packet": {
                    "path": "/v1/responses",
                    "upstream_status": 200,
                    "forwarded_to_wbp": True,
                    "request_count": 2,
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet(
                {"primary_model_id": "wbp-web-primary-openrouter"},
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )

            packet = manager.temp_write_probe_packet(
                created["session"]["session_id"],
                {"api_model_id": "wbp-web-primary-openrouter"},
                runner,
                owner_authorized=True,
            )

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(
                packet["final_status"],
                "API_ONLY_DEEPSEEK_TEMP_WRITE_PROVEN_WITH_LIMITS",
            )
            self.assertEqual(observed_payload["model_id"], "wbp-web-primary-openrouter")
            self.assertEqual(observed_payload["slot_id"], "primary_model_slot")
            self.assertTrue(packet["tool_loop_proven"])
            self.assertEqual(packet["request_count"], 2)
            self.assertTrue(packet["file_existed_after_tool"])
            self.assertTrue(packet["file_content_matches"])
            self.assertTrue(packet["file_removed_after_probe"])
            self.assertTrue(packet["file_within_probe_dir"])
            self.assertEqual(packet["write_surface"], "temp_only")
            self.assertFalse(packet["repo_mutation_attempted"])
            self.assertFalse(packet["original_codex_touched"])
            self.assertFalse(packet["wbp_patch_applier_used"])
            self.assertFalse(packet["live_product_code_edit_claimed"])

    def test_api_only_safe_worktree_edit_probe_requires_owner_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet(
                {"primary_model_id": "wbp-web-primary-openrouter"},
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )

            packet = manager.safe_worktree_edit_probe_packet(
                created["session"]["session_id"],
                {"api_model_id": "wbp-web-primary-openrouter"},
                lambda _payload, _writable_dir: self.fail("runner must not be called"),
                owner_authorized=False,
            )

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(packet["machine_error_code"], "OWNER_AUTHORIZATION_REQUIRED")
            self.assertEqual(
                packet["final_status"],
                "KNOWN_BLOCKER_SAFE_WORKTREE_WRITE_NOT_ADMISSIBLE",
            )
            self.assertFalse(packet["safe_worktree_used"])

    def test_api_only_safe_worktree_edit_probe_rejects_browser_worktree_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet(
                {"primary_model_id": "wbp-web-primary-openrouter"},
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )

            packet = manager.safe_worktree_edit_probe_packet(
                created["session"]["session_id"],
                {"api_model_id": "wbp-web-primary-openrouter", "path": "/tmp/owned"},
                lambda _payload, _writable_dir: self.fail("runner must not be called"),
                owner_authorized=True,
            )

            self.assertEqual(packet["status"], "rejected")
            self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
            self.assertIn("path", packet["forbidden_fields"])
            self.assertFalse(packet["browser_worktree_path_intake"])
            self.assertFalse(packet["main_worktree_mutated_by_probe"])

    def test_api_only_safe_worktree_edit_probe_proves_diff_and_cleanup(self) -> None:
        observed_payload: dict[str, object] = {}

        def runner(payload: dict[str, object], writable_dir: Path) -> dict[str, object]:
            observed_payload.update(payload)
            prompt = str(payload["prompt"])
            target = Path(prompt.split("> ", 1)[1].split(" &&", 1)[0]).resolve()
            self.assertEqual(target.parent, writable_dir)
            target.write_text("WBP_DEEPSEEK_SAFE_WORKTREE_EDIT_OK", encoding="utf-8")
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "selected_model": "wbp-web-primary-openrouter",
                "runtime_model": "wbp-web-primary-openrouter",
                "final_message": "WBP_DEEPSEEK_SAFE_WORKTREE_EDIT_OK",
                "configured_provider": "external_route",
                "configured_wire_api": "responses",
                "workspace_write_admitted": True,
                "current_codex_home_used": False,
                "secret_value_recorded": False,
                "trace_observer_packet": {
                    "path": "/v1/responses",
                    "upstream_status": 200,
                    "forwarded_to_wbp": True,
                    "request_count": 2,
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as repo_dir:
            init_git_repo(Path(repo_dir))
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet(
                {"primary_model_id": "wbp-web-primary-openrouter"},
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )

            packet = manager.safe_worktree_edit_probe_packet(
                created["session"]["session_id"],
                {"api_model_id": "wbp-web-primary-openrouter"},
                runner,
                owner_authorized=True,
                repo_root=Path(repo_dir),
            )

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(
                packet["final_status"],
                "API_ONLY_DEEPSEEK_SAFE_WORKTREE_EDIT_PROVEN_WITH_LIMITS",
            )
            self.assertEqual(observed_payload["model_id"], "wbp-web-primary-openrouter")
            self.assertEqual(observed_payload["slot_id"], "primary_model_slot")
            self.assertTrue(packet["tool_loop_proven"])
            self.assertTrue(packet["safe_worktree_used"])
            self.assertEqual(packet["write_surface"], "safe_worktree_only")
            self.assertTrue(packet["file_changed_by_codex_tool"])
            self.assertTrue(packet["file_content_matches"])
            self.assertTrue(packet["git_diff_observed"])
            self.assertTrue(packet["expected_diff_observed"])
            self.assertFalse(packet["main_worktree_mutated_by_probe"])
            self.assertFalse(packet["secret_in_diff"])
            self.assertFalse(packet["original_codex_touched"])
            self.assertFalse(packet["original_codex_profile_touched"])
            self.assertFalse(packet["wbp_patch_applier_used"])
            self.assertFalse(packet["commit_attempted"])
            self.assertFalse(packet["push_attempted"])
            self.assertFalse(packet["merge_attempted"])
            self.assertTrue(packet["worktree_removed_after_probe"])

    def test_api_only_product_safe_worktree_coder_keeps_active_worktree_until_cleanup(self) -> None:
        observed_payload: dict[str, object] = {}

        def runner(payload: dict[str, object], worktree_dir: Path) -> dict[str, object]:
            observed_payload.update(payload)
            self.assertTrue((worktree_dir / ".git").exists() or (worktree_dir / ".git").is_file())
            readme = worktree_dir / "README.md"
            readme.write_text("safe worktree test repo\nDeepSeek product coder touched this file.\n", encoding="utf-8")
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "selected_model": "wbp-web-primary-openrouter",
                "runtime_model": "wbp-web-primary-openrouter",
                "final_message": "changed README.md",
                "configured_provider": "external_route",
                "configured_wire_api": "responses",
                "workspace_write_admitted": True,
                "working_dir_override_admitted": True,
                "working_dir_scope": "safe_worktree_only",
                "current_codex_home_used": False,
                "secret_value_recorded": False,
                "direct_non_wbp_model_egress_absent_proven": True,
                "trace_observer_packet": {
                    "path": "/v1/responses",
                    "upstream_status": 200,
                    "forwarded_to_wbp": True,
                    "request_count": 2,
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as repo_dir:
            repo = Path(repo_dir)
            init_git_repo(repo)
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet(
                {"primary_model_id": "wbp-web-primary-openrouter"},
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )

            packet = manager.safe_worktree_coder_packet(
                created["session"]["session_id"],
                {
                    "api_model_id": "wbp-web-primary-openrouter",
                    "task": "Append a short sentence to README.md.",
                },
                runner,
                owner_authorized=True,
                repo_root=repo,
            )
            cleanup = manager.safe_worktree_cleanup_packet(packet["worktree_id"])

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(
                packet["final_status"],
                "API_ONLY_DEEPSEEK_PRODUCT_SAFE_WORKTREE_CODER_READY_WITH_LIMITS",
            )
            self.assertEqual(observed_payload["model_id"], "wbp-web-primary-openrouter")
            self.assertIn("Append a short sentence", observed_payload["prompt"])
            self.assertTrue(packet["safe_worktree_used"])
            self.assertEqual(packet["safe_worktree_status"], "active")
            self.assertTrue(packet["cleanup_required"])
            self.assertTrue(packet["diff_present"])
            self.assertEqual(packet["changed_files"], ["README.md"])
            self.assertFalse(packet["main_worktree_mutated_by_run"])
            self.assertFalse(packet["secret_in_diff"])
            self.assertFalse(packet["commit_attempted"])
            self.assertFalse(packet["push_attempted"])
            self.assertTrue(packet["push_attempt_absent_proven"])
            self.assertFalse(packet["merge_attempted"])
            self.assertFalse(packet["wbp_patch_applier_used"])
            self.assertFalse(packet["original_codex_touched"])
            self.assertFalse(packet["original_codex_profile_touched"])
            self.assertTrue(packet["working_dir_override_admitted"])
            self.assertEqual(packet["working_dir_scope"], "safe_worktree_only")
            self.assertIn("DeepSeek product coder touched this file", packet["diff_text_bounded"])
            self.assertEqual(cleanup["status"], "ok")
            self.assertTrue(cleanup["cleanup_performed"])
            self.assertEqual(cleanup["safe_worktree_status"], "cleaned")

    def test_api_only_product_safe_worktree_coder_rejects_browser_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet(
                {"primary_model_id": "wbp-web-primary-openrouter"},
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )

            packet = manager.safe_worktree_coder_packet(
                created["session"]["session_id"],
                {
                    "api_model_id": "wbp-web-primary-openrouter",
                    "task": "ok",
                    "worktree_path": "/tmp/owned",
                },
                lambda _payload, _worktree_dir: self.fail("runner must not be called"),
                owner_authorized=True,
            )

            self.assertEqual(packet["status"], "rejected")
            self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
            self.assertIn("worktree_path", packet["forbidden_fields"])
            self.assertFalse(packet["browser_worktree_path_intake"])

    def test_prompt_run_blocks_when_runtime_model_mismatches_bound_slot_model(self) -> None:
        def runner(payload: dict[str, object]) -> dict[str, object]:
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "selected_model": "gpt-5.3-codex",
                "runtime_model": "gpt-5.3-codex",
                "final_message": "MISMATCH_OK",
                "secret_value_recorded": False,
                "configured_provider": "external_route",
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
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet(
                {
                    "primary_model_id": "gpt-5.3-codex",
                    "coding_agent_model_id": "wbp-web-primary-openrouter",
                },
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )
            packet = manager.prompt_packet(
                created["session"]["session_id"],
                {"prompt": "OK", "slot_id": "coding_agent_model_slot"},
                runner,
                owner_authorized=True,
            )

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(packet["machine_error_code"], "RUNTIME_MODEL_ID_MISMATCH")
            self.assertEqual(packet["runtime_selected_model"], "gpt-5.3-codex")
            self.assertTrue(packet["runtime_selected_model_recorded"])
            self.assertFalse(packet["runtime_selected_model_matches_bound_model"])
            self.assertEqual(packet["path_proof_status"], "runtime_model_mismatch_after_observation")
            self.assertEqual(packet["next_action"], "repair_runtime_model_identity")

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
            created = manager.create_packet({"primary_model_id": "gpt-5.3-codex"}, commands(), operator_status())
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
            created = manager.create_packet({"primary_model_id": "gpt-5.3-codex"}, commands(), operator_status())
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
            session["role_slots"]["primary_model_slot"].update(
                {
                    "selected_source_class": "route_backed",
                    "selected_backend_ref": "",
                    "selected_backend_server_issued": False,
                    "selected_route_ref": "route-digest",
                    "selected_route_server_issued": True,
                    "route_provenance_required": True,
                    "route_provenance_proven": False,
                    "source_provenance_status": "route_provenance_missing",
                    "selection_proven": True,
                }
            )

            packet = manager.prompt_packet(
                session_id,
                {"prompt": "OK"},
                lambda payload: calls.append(payload) or {"status": "ok", "final_message": "SHOULD_NOT_RUN"},
                owner_authorized=True,
            )

            self.assertEqual(packet["status"], "rejected")
            self.assertEqual(packet["machine_error_code"], "ROUTE_STATIC_READINESS_MISSING")
            self.assertIn("ROUTE_STATIC_READINESS_MISSING", packet["precondition_failures"])
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
                "configured_provider": "external_route",
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
            created = manager.create_packet({"primary_model_id": "gpt-5.3-codex"}, commands(), operator_status())
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
                    "route_static_readiness_classified": True,
                    "source_provenance_status": "route_static_candidate_classified",
                }
            )
            session["role_slots"]["primary_model_slot"].update(
                {
                    "selected_source_class": "route_backed",
                    "selected_backend_ref": "",
                    "selected_backend_server_issued": False,
                    "selected_route_ref": "route-digest",
                    "selected_route_server_issued": True,
                    "route_provenance_required": True,
                    "route_provenance_proven": False,
                    "route_static_readiness_classified": True,
                    "source_provenance_status": "route_static_candidate_classified",
                    "selection_proven": True,
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
            self.assertTrue(packet["route_static_readiness_classified"])
            self.assertTrue(packet["route_execution_proven"])
            self.assertTrue(packet["provider_response_proven"])
            self.assertEqual(packet["source_provenance_status"], "route_proven")
            self.assertTrue(packet["source_provenance_proven"])
            self.assertTrue(packet["live_prompt_full_success"])

    def test_route_backed_slot_blocks_when_runtime_provider_collapses_to_cliproxy(self) -> None:
        def runner(payload: dict[str, object]) -> dict[str, object]:
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "final_message": "ROUTE_COLLAPSE",
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
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet(
                {
                    "primary_model_id": "gpt-5.3-codex",
                    "coding_agent_model_id": "wbp-web-primary-openrouter",
                },
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )
            packet = manager.prompt_packet(
                created["session"]["session_id"],
                {"prompt": "OK", "slot_id": "coding_agent_model_slot"},
                runner,
                owner_authorized=True,
            )
            detail = manager.get_packet(created["session"]["session_id"])

            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(packet["machine_error_code"], "RUNTIME_SOURCE_PROVENANCE_MISMATCH")
            self.assertEqual(packet["selected_source_provenance"], "route_static_candidate_classified")
            self.assertEqual(packet["configured_provider"], "cliproxy")
            self.assertFalse(packet["live_prompt_full_success"])
            self.assertEqual(detail["session"]["status"], "prompt_blocked_after_response_e2e")
            self.assertFalse(detail["session"]["inference_proven"])

    def test_prompt_run_rejects_cleaned_session_precondition(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CodexCustomSessionManager(Path(temp_dir))
            created = manager.create_packet({"primary_model_id": "gpt-5.3-codex"}, commands(), operator_status())
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
            created = manager.create_packet({"primary_model_id": "gpt-5.3-codex"}, commands(), operator_status())
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
        self.assertEqual(forbidden_session_create_fields({"primary_model_id": "gpt-5.3-codex"}), [])
        self.assertEqual(forbidden_session_create_fields({"model_id": "gpt-5.3-codex"}), ["model_id"])
        self.assertEqual(
            forbidden_session_create_fields(
                {"primary_model_id": "gpt-5.3-codex", "model_lane": "api_route_lane"}
            ),
            ["model_lane"],
        )
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
