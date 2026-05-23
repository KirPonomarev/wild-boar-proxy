# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest

from wild_boar_proxy.codex_account_selection import (
    build_account_selection_packet,
    build_account_smoke_dry_run_packet,
    build_accounts_truth_packet,
    forbidden_account_smoke_fields,
)


def command(packet: dict[str, object]) -> dict[str, object]:
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "human_message": "ok",
        "packet": packet,
    }


def account(
    backend_id: str,
    *,
    pool: str = "active",
    status: str = "healthy",
    priority: int = 10,
    manual_hold: bool = False,
    auth_ref: str | None = "/Users/example/.cli-proxy-api/auth.json",
    last_error: str = "",
    last_error_class: str = "",
    cooldown_until: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": backend_id,
        "label": backend_id,
        "enabled": True,
        "priority": priority,
        "pool": pool,
        "status": status,
        "fail_count": 0,
        "success_count": 5,
        "last_success": "2026-05-23T00:00:00Z",
        "last_error": last_error,
        "last_error_class": last_error_class,
        "cooldown_until": cooldown_until,
        "manual_hold": manual_hold,
        "notes": "",
    }
    if auth_ref is not None:
        payload["auth_ref"] = auth_ref
    return payload


def commands(*, claim_gate: str = "blocked_by_policy_drift") -> dict[str, dict[str, object]]:
    accounts = [
        account("acct-b", priority=20),
        account("acct-a", priority=10),
        account("acct-reserve", pool="reserve"),
        account("acct-hold", manual_hold=True),
        account(
            "acct-quota",
            pool="retired",
            status="down",
            last_error="usage_limit_reached",
            last_error_class="quota",
        ),
    ]
    return {
        "status": command(
            {
                "status": "ok",
                "machine_error_code": "OK",
                "claim_gate": {"status": claim_gate},
                "pool_summary": {
                    "selected_backend_ids": ["acct-a"],
                },
                "auth_pool_hygiene": {
                    "status": "launch_capable_available",
                    "selection_alignment_status": "aligned",
                    "launch_capable_backend_count": 2,
                },
            }
        ),
        "accounts_list": command(
            {
                "status": "ok",
                "exit_code": 0,
                "human_message": "Account registry snapshot is available.",
                "machine_error_code": "OK",
                "changed_files": [],
                "next_action": "none",
                "accounts": accounts,
                "registry_identity": {
                    "status": "ok",
                    "machine_error_code": "OK",
                    "next_action": "none",
                },
            }
        ),
        "rollout_rotation_inspect": command(
            {
                "status": "ok",
                "machine_error_code": "OK",
                "changed_files": [],
                "next_action": "none",
            }
        ),
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


class CodexAccountSelectionTests(unittest.TestCase):
    def test_accounts_truth_packet_redacts_auth_refs_and_counts_classes(self) -> None:
        packet = build_accounts_truth_packet(commands())

        self.assertEqual(packet["status"], "degraded")
        self.assertEqual(packet["machine_error_code"], "CLAIM_GATE_BLOCKED")
        self.assertEqual(packet["managed_total"], 5)
        self.assertEqual(packet["expected_managed_total"], 25)
        self.assertEqual(packet["launch_capable_count"], 2)
        self.assertEqual(packet["pool_classes"]["active"], 3)
        self.assertEqual(packet["pool_classes"]["reserve"], 1)
        self.assertEqual(packet["pool_classes"]["hold"], 1)
        self.assertEqual(packet["pool_classes"]["problem"], 1)
        self.assertEqual(packet["quota_classes"]["quota_exhausted"], 1)
        self.assertFalse(packet["account_mutation_performed"])
        self.assertFalse(packet["raw_auth_refs_exposed"])
        self.assertNotIn(".cli-proxy-api", json.dumps(packet["accounts"]))
        self.assertNotIn("auth.json", json.dumps(packet["accounts"]))

    def test_selection_packet_uses_server_side_ranking_without_inference_claim(self) -> None:
        packet = build_account_selection_packet(commands(), operator_status())

        self.assertEqual(packet["status"], "degraded")
        self.assertEqual(packet["machine_error_code"], "CLAIM_GATE_BLOCKED")
        self.assertTrue(packet["selection_proven"])
        self.assertFalse(packet["inference_proven"])
        self.assertEqual(packet["selected_backend_id"], "acct-a")
        self.assertTrue(packet["selected_backend_server_issued"])
        self.assertFalse(packet["browser_selected_backend"])
        self.assertEqual(packet["selected_source_class"], "gpt_account")
        self.assertFalse(packet["runtime_meter_attached"])
        self.assertFalse(packet["smoke_admitted"])
        self.assertTrue(packet["selection_not_inference"])

    def test_account_smoke_dry_run_rejects_backend_route_account_provider_fields(self) -> None:
        packet = build_account_smoke_dry_run_packet(
            {
                "model_id": "gpt-5.3-codex",
                "account_id": "acct-a",
                "backend_id": "acct-a",
                "route_id": "route",
                "provider": "openai",
                "nested": {"auth": "secret"},
            },
            commands(),
            operator_status(),
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(
            packet["forbidden_fields"],
            ["account_id", "backend_id", "route_id", "provider", "nested", "nested.auth"],
        )
        self.assertFalse(packet["inference_proven"])
        self.assertFalse(packet["account_mutation_performed"])

    def test_account_smoke_dry_run_accepts_server_model_but_does_not_admit_smoke(self) -> None:
        packet = build_account_smoke_dry_run_packet(
            {"model_id": "gpt-5.3-codex"},
            commands(),
            operator_status(),
        )

        self.assertEqual(packet["status"], "degraded")
        self.assertTrue(packet["dry_run"])
        self.assertTrue(packet["model_server_issued"])
        self.assertTrue(packet["selection_proven"])
        self.assertFalse(packet["inference_proven"])
        self.assertFalse(packet["smoke_admitted"])
        self.assertFalse(packet["runtime_meter_attached"])
        self.assertFalse(packet["account_mutation_performed"])
        self.assertEqual(packet["token_burn"], 0)
        self.assertEqual(
            packet["negative_claim_basis"],
            "account_smoke_dry_run_static_path_no_inference_adapter",
        )

    def test_forbidden_account_smoke_fields_allows_only_top_level_model_id(self) -> None:
        self.assertEqual(forbidden_account_smoke_fields({"model_id": "gpt-5.3-codex"}), [])
        self.assertEqual(forbidden_account_smoke_fields({"account_id": "acct-a"}), ["account_id"])
        self.assertEqual(
            forbidden_account_smoke_fields({"model_id": "gpt-5.3-codex", "items": [{"path": "/x"}]}),
            ["items", "items[0].path"],
        )


if __name__ == "__main__":
    unittest.main()
