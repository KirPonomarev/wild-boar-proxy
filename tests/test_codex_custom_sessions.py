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
            session = packet["session"]
            self.assertTrue(session["model_server_issued"])
            self.assertTrue(session["selection_proven"])
            self.assertTrue(session["selected_backend_server_issued"])
            self.assertEqual(session["session_root_scope"], "owned_temp_session_root")
            self.assertNotIn(temp_dir, json.dumps(packet))
            self.assertNotIn("acct-a", json.dumps(packet))
            self.assertFalse(packet["inference_proven"])
            self.assertFalse(packet["runtime_meter_attached"])
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
            self.assertEqual(packet["token_burn"], 0)
            self.assertNotIn("Reply with exactly OK.", json.dumps(transcript))
            self.assertEqual(transcript["transcript_kind"], "service_ledger_only")
            self.assertFalse(transcript["model_response_present"])

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
            self.assertEqual(cleanup["status"], "ok")
            self.assertTrue(cleanup["cleanup_performed"])
            self.assertFalse(cleanup["session_root_exists_after"])
            self.assertFalse(cleanup["arbitrary_path_accepted"])
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    def test_forbidden_helpers_allow_only_declared_top_level_fields(self) -> None:
        self.assertEqual(forbidden_session_create_fields({"model_id": "gpt-5.3-codex"}), [])
        self.assertEqual(forbidden_prompt_dry_run_fields({"prompt": "OK"}), [])
        self.assertEqual(
            forbidden_prompt_dry_run_fields({"prompt": "OK", "items": [{"path": "/tmp/x"}]}),
            ["items", "items[0].path"],
        )


if __name__ == "__main__":
    unittest.main()
