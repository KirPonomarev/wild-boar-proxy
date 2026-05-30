# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from wild_boar_proxy.codex_account_selection import build_model_selection_truth_packet
from wild_boar_proxy.codex_custom_sessions import CodexCustomSessionManager
from wild_boar_proxy.codex_model_registry import (
    build_custom_model_dry_run_packet,
    build_custom_model_registry_packet,
    build_wbp_model_catalog_contract_packet,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DESIGN_UI = REPO_ROOT / "wild_boar_proxy" / "web_design_ui"


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
                "claim_gate": {"status": "passed"},
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
        "status": {
            "status": "ok",
            "machine_error_code": "OK",
            "configured_model": "gpt-5.3-codex",
        },
        "claim_gate": {"status": "passed"},
        "models": {
            "ok": True,
            "server_issued": True,
            "model_ids": ["gpt-5.3-codex", "gpt-5.4"],
        },
    }


def api_snapshot() -> dict[str, object]:
    return {
        "status": "ok",
        "source": "api_connections_readonly",
        "primary_truth_ok": True,
        "routes": [
            {
                "route_id": "wbp-enabled-openrouter",
                "provider": "openrouter",
                "upstream_model": "openai/gpt-5",
                "enabled": True,
                "secret_ref": "OPENROUTER_API_KEY",
            },
            {
                "route_id": "wbp-disabled-openrouter",
                "provider": "openrouter",
                "upstream_model": "openai/gpt-5",
                "enabled": False,
                "secret_ref": "OPENROUTER_API_KEY",
            },
            {
                "route_id": "wbp-missing-secret",
                "provider": "openrouter",
                "upstream_model": "openai/gpt-5-mini",
                "enabled": True,
            },
        ],
    }


class CustomCodexModelGridBoundAuthorityR1Tests(unittest.TestCase):
    def test_registry_keeps_disabled_routes_visible_without_making_them_selectable(self) -> None:
        packet = build_custom_model_registry_packet(operator_status(), api_snapshot=api_snapshot())

        rows = {entry["model_id"]: entry for entry in packet["available_models"]}
        self.assertEqual(packet["selectable_model_count"], 3)
        self.assertEqual(packet["disabled_model_count"], 2)
        self.assertFalse(rows["wbp-disabled-openrouter"]["selection_enabled"])
        self.assertEqual(rows["wbp-disabled-openrouter"]["selection_state"], "disabled")
        self.assertEqual(
            rows["wbp-disabled-openrouter"]["selection_disabled_reason_code"],
            "ROUTE_DISABLED",
        )
        self.assertFalse(rows["wbp-missing-secret"]["selection_enabled"])
        self.assertEqual(
            rows["wbp-missing-secret"]["selection_disabled_reason_code"],
            "SECRET_REF_MISSING",
        )
        self.assertEqual(rows["wbp-enabled-openrouter"]["provider_label"], "openrouter via WBP")

    def test_catalog_contract_keeps_browser_authority_blocked_and_disabled_rows_honest(self) -> None:
        packet = build_wbp_model_catalog_contract_packet(operator_status(), api_snapshot=api_snapshot())

        self.assertEqual(packet["allowed_browser_fields"], ["model_id"])
        self.assertTrue(all(value is False for value in packet["browser_authority"].values()))
        self.assertEqual(packet["selectable_model_count"], 3)
        self.assertEqual(packet["disabled_model_count"], 2)
        rows = {entry["model_id"]: entry for entry in packet["models"]}
        self.assertEqual(rows["wbp-disabled-openrouter"]["selection_state"], "disabled")
        self.assertEqual(rows["wbp-missing-secret"]["selection_state"], "disabled")
        self.assertEqual(
            rows["wbp-missing-secret"]["selection_disabled_reasons"],
            ["secret_ref_missing"],
        )

    def test_model_dry_run_rejects_disabled_visible_route(self) -> None:
        packet = build_custom_model_dry_run_packet(
            {"model_id": "wbp-disabled-openrouter"},
            operator_status(),
            api_snapshot=api_snapshot(),
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "MODEL_NOT_SELECTABLE")
        self.assertTrue(packet["model_server_issued"])
        self.assertFalse(packet["selected_model_selectable"])
        self.assertEqual(packet["selection_state"], "disabled")
        self.assertFalse(packet["network_call_summary"]["network_calls_made"])

    def test_browser_cannot_supply_provider_wire_api_base_url_or_auth_path(self) -> None:
        packet = build_custom_model_dry_run_packet(
            {
                "model_id": "gpt-5.3-codex",
                "provider": "openai",
                "wire_api": "chat_completions",
                "model_provider": "browser-owned",
                "openai_base_url": "http://127.0.0.1:9999/v1",
                "auth_path": "/tmp/secret.txt",
            },
            operator_status(),
            api_snapshot=api_snapshot(),
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(
            packet["forbidden_fields"],
            ["provider", "wire_api", "model_provider", "openai_base_url", "auth_path"],
        )

    def test_session_creation_rejects_disabled_route_without_selection_proof(self) -> None:
        selection = build_model_selection_truth_packet(
            {"model_id": "wbp-disabled-openrouter"},
            commands(),
            operator_status(),
            api_snapshot=api_snapshot(),
        )

        manager = CodexCustomSessionManager(REPO_ROOT / "audit_results" / "_tmp_model_grid_probe_sessions")
        packet = manager.create_packet(
            {"primary_model_id": "wbp-disabled-openrouter"},
            commands(),
            operator_status(),
            selection=selection,
            api_snapshot=api_snapshot(),
        )
        self.addCleanup(lambda: manager.root.exists() and shutil.rmtree(manager.root))

        self.assertEqual(selection["status"], "degraded")
        self.assertFalse(selection["selection_policy_proven"])
        self.assertEqual(packet["status"], "rejected")
        self.assertFalse(packet["session_created"])
        self.assertEqual(packet["next_action"], "choose_selectable_slot_model")

    def test_ui_projects_provider_labels_and_disabled_state_without_extra_authority(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text(encoding="utf-8")
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text(encoding="utf-8")

        self.assertIn('id="codexCustomModelCatalog"', html)
        self.assertIn("entry?.provider_label || entry?.provider_class || \"unknown\"", js)
        self.assertIn("entry?.selection_enabled === true", js)
        self.assertIn("selection_disabled_reason_code", js)
        self.assertIn("body: JSON.stringify({ model_id: modelId })", js)
        self.assertNotIn("body: JSON.stringify({ model_id: modelId, route_id", js)
        self.assertNotIn("body: JSON.stringify({ model_id: modelId, provider", js)


if __name__ == "__main__":
    unittest.main()
