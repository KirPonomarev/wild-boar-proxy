# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import unittest

from wild_boar_proxy.codex_account_selection import (
    build_account_selection_packet,
    build_account_smoke_dry_run_packet,
    build_accounts_truth_packet,
    build_model_selection_truth_packet,
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
    auth_ref: str | None = "managed:auth-ref-fixture",
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


def commands_for_selection_truth() -> dict[str, dict[str, object]]:
    payload = commands(claim_gate="passed")
    accounts_payload = payload["accounts_list"]["packet"]
    assert isinstance(accounts_payload, dict)
    accounts_payload["accounts"] = [
        account("acct-a", priority=10, auth_ref="managed:acct-a"),
        account("acct-b", priority=20, auth_ref="managed:acct-b"),
        account("acct-reserve", pool="reserve", auth_ref="managed:reserve"),
    ]
    return payload


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
        self.assertEqual(packet["account_source"], "provided_packet_or_fake")
        self.assertEqual(packet["account_count_claim_scope"], "packet_shape_only")
        self.assertFalse(packet["live_account_truth_checked"])
        self.assertEqual(packet["expected_managed_total"], 25)
        self.assertEqual(packet["launch_capable_count"], 2)
        self.assertEqual(packet["accounts_visible"], 5)
        self.assertEqual(packet["launch_capable_backend_ids"], [])
        self.assertEqual(len(packet["launch_capable_backend_refs"]), 2)
        self.assertEqual(packet["pool_classes"]["active"], 3)
        self.assertEqual(packet["pool_counts"]["active"], 3)
        self.assertEqual(packet["pool_classes"]["reserve"], 1)
        self.assertEqual(packet["pool_classes"]["hold"], 1)
        self.assertEqual(packet["pool_classes"]["problem"], 1)
        self.assertEqual(packet["quota_classes"]["quota_exhausted"], 1)
        self.assertEqual(packet["auth_ref_static_classification"]["classification_scope"], "static_dry_run_only")
        self.assertFalse(packet["auth_ref_static_classification"]["live_validation_performed"])
        self.assertFalse(packet["auth_ref_static_classification"]["token_validity_proven"])
        self.assertFalse(packet["auth_ref_static_classification"]["quota_proven"])
        self.assertFalse(packet["auth_ref_static_classification"]["raw_auth_refs_exposed"])
        self.assertFalse(packet["account_mutation_performed"])
        self.assertTrue(packet["account_ids_redacted"])
        self.assertFalse(packet["raw_backend_ids_exposed"])
        self.assertFalse(packet["raw_auth_refs_exposed"])
        self.assertFalse(packet["raw_auth_visible"])
        self.assertEqual(packet["token_burn"], 0)
        self.assertEqual(packet["selected_backend_ids_observed"], [])
        self.assertEqual(len(packet["selected_backend_refs_observed"]), 1)
        self.assertNotIn("acct-a", json.dumps(packet))
        self.assertNotIn("acct-b", json.dumps(packet))
        self.assertNotIn(".cli-proxy-api", json.dumps(packet["accounts"]))
        self.assertNotIn("auth.json", json.dumps(packet["accounts"]))

    def test_selection_packet_uses_server_side_ranking_without_inference_claim(self) -> None:
        packet = build_account_selection_packet(commands(), operator_status())

        self.assertEqual(packet["status"], "degraded")
        self.assertEqual(packet["machine_error_code"], "CLAIM_GATE_BLOCKED")
        self.assertTrue(packet["selection_dry_run_proven"])
        self.assertFalse(packet["live_selection_proven"])
        self.assertTrue(packet["selection_proven"])
        self.assertFalse(packet["inference_proven"])
        self.assertEqual(packet["selected_backend_id"], "")
        self.assertTrue(packet["selected_backend_ref"])
        self.assertTrue(packet["selected_backend_id_redacted"])
        self.assertTrue(packet["selected_backend_server_issued"])
        self.assertEqual(packet["selected_backend_source"], "server")
        self.assertEqual(packet["selected_route_ref"], "")
        self.assertFalse(packet["selected_route_server_issued"])
        self.assertFalse(packet["route_provenance_required"])
        self.assertFalse(packet["route_provenance_proven"])
        self.assertEqual(packet["source_provenance_status"], "backend_proven")
        self.assertFalse(packet["browser_selected_backend"])
        self.assertEqual(packet["selected_source_class"], "gpt_account")
        self.assertFalse(packet["runtime_meter_attached"])
        self.assertFalse(packet["smoke_admitted"])
        self.assertFalse(packet["responses_called"])
        self.assertFalse(packet["chat_completions_called"])
        self.assertFalse(packet["provider_called"])
        self.assertFalse(packet["network_calls_made"])
        self.assertFalse(packet["raw_backend_id_exposed"])
        self.assertEqual(packet["token_burn"], 0)
        self.assertTrue(packet["selection_not_inference"])
        self.assertNotIn("acct-a", json.dumps(packet))

    def test_account_smoke_dry_run_rejects_backend_route_account_provider_fields(self) -> None:
        packet = build_account_smoke_dry_run_packet(
            {
                "model_id": "gpt-5.3-codex",
                "account_id": "acct-a",
                "backend_id": "acct-a",
                "route_id": "route",
                "provider": "openai",
                "openai_base_url": "http://127.0.0.1:8318/v1",
                "wire_api": "responses",
                "nested": {"auth": "secret"},
            },
            commands(),
            operator_status(),
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(
            packet["forbidden_fields"],
            [
                "account_id",
                "backend_id",
                "route_id",
                "provider",
                "openai_base_url",
                "wire_api",
                "nested",
                "nested.auth",
            ],
        )
        self.assertFalse(packet["selection_dry_run_proven"])
        self.assertFalse(packet["live_selection_proven"])
        self.assertFalse(packet["inference_proven"])
        self.assertFalse(packet["network_calls_made"])
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
        self.assertTrue(packet["selection_dry_run_proven"])
        self.assertFalse(packet["live_selection_proven"])
        self.assertTrue(packet["selection_proven"])
        self.assertFalse(packet["inference_proven"])
        self.assertFalse(packet["smoke_admitted"])
        self.assertFalse(packet["runtime_meter_attached"])
        self.assertFalse(packet["responses_called"])
        self.assertFalse(packet["chat_completions_called"])
        self.assertFalse(packet["provider_called"])
        self.assertFalse(packet["network_calls_made"])
        self.assertFalse(packet["account_mutation_performed"])
        self.assertTrue(packet["selected_backend_id_redacted"])
        self.assertEqual(packet["selected_backend_id"], "")
        self.assertTrue(packet["selected_backend_ref"])
        self.assertFalse(packet["selected_route_server_issued"])
        self.assertFalse(packet["route_provenance_required"])
        self.assertFalse(packet["route_provenance_proven"])
        self.assertEqual(packet["source_provenance_status"], "backend_proven")
        self.assertEqual(packet["token_burn"], 0)
        self.assertEqual(
            packet["negative_claim_basis"],
            "account_smoke_dry_run_static_path_no_inference_adapter",
        )

    def test_model_selection_requires_server_issued_model_id(self) -> None:
        packet = build_model_selection_truth_packet(
            {"model_id": "invented-model"},
            commands_for_selection_truth(),
            operator_status(),
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "MODEL_NOT_SERVER_ISSUED")
        self.assertFalse(packet["model_server_issued"])
        self.assertFalse(packet["selection_policy_proven"])
        self.assertFalse(packet["network_calls_made"])
        self.assertFalse(packet["account_mutation_performed"])

    def test_model_selection_rejects_browser_route_backend_provider_authority(self) -> None:
        packet = build_model_selection_truth_packet(
            {
                "model_id": "gpt-5.3-codex",
                "route_id": "browser-route",
                "backend_id": "browser-backend",
                "provider": "openai",
                "base_url": "https://example.invalid/v1",
                "token": "browser-token",
            },
            commands_for_selection_truth(),
            operator_status(),
        )

        self.assertEqual(packet["status"], "rejected")
        self.assertEqual(packet["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(
            packet["forbidden_fields"],
            ["route_id", "backend_id", "provider", "base_url", "token"],
        )
        self.assertTrue(all(value is False for value in packet["browser_authority"].values()))
        self.assertFalse(packet["browser_selected_backend"])
        self.assertFalse(packet["browser_selected_route"])

    def test_model_selection_classifies_active_reserve_degraded_pool(self) -> None:
        packet = build_model_selection_truth_packet(
            {"model_id": "gpt-5.3-codex"},
            commands_for_selection_truth(),
            operator_status(),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["account_pool_truth"]["pool_classes"]["active"], 2)
        self.assertEqual(packet["account_pool_truth"]["pool_classes"]["reserve"], 1)
        self.assertEqual(packet["account_pool_truth"]["eligibility_classes"]["live_capable"], 2)
        self.assertEqual(packet["selection_policy_state"], "gpt_account_policy_classified")
        self.assertEqual(packet["selected_source_class"], "gpt_account")
        self.assertTrue(packet["selected_backend_server_issued"])
        self.assertTrue(packet["selected_backend_ref"])
        self.assertEqual(packet["selected_backend_source"], "server")
        self.assertNotIn("acct-a", json.dumps(packet))

    def test_model_selection_does_not_promote_reserve_without_authorization(self) -> None:
        packet = build_model_selection_truth_packet(
            {"model_id": "gpt-5.3-codex"},
            commands_for_selection_truth(),
            operator_status(),
        )

        self.assertFalse(packet["reserve_promotion_performed"])
        self.assertFalse(packet["account_mutation_performed"])
        self.assertEqual(packet["account_pool_truth"]["pool_classes"]["reserve"], 1)

    def test_model_selection_does_not_claim_live_availability_or_account_health(self) -> None:
        packet = build_model_selection_truth_packet(
            {"model_id": "gpt-5.3-codex"},
            commands_for_selection_truth(),
            operator_status(),
        )

        self.assertFalse(packet["live_model_availability_proven"])
        self.assertFalse(packet["live_account_truth_checked"])
        self.assertFalse(packet["account_token_validity_proven"])
        self.assertFalse(packet["account_quota_proven"])
        self.assertFalse(packet["upstream_credentials_accepted"])
        self.assertIn("selected_model_usable_live", packet["forbidden_claims"])
        self.assertFalse(packet["claim_limits"]["model_listed_means_usable"])
        self.assertFalse(packet["claim_limits"]["account_exists_means_healthy"])

    def test_model_selection_redacts_auth_refs_and_tokens(self) -> None:
        packet = build_model_selection_truth_packet(
            {"model_id": "gpt-5.3-codex"},
            commands_for_selection_truth(),
            operator_status(),
        )
        serialized = json.dumps(packet)

        self.assertFalse(packet["raw_auth_refs_exposed"])
        self.assertFalse(packet["raw_secret_exposed"])
        self.assertNotIn(".cli-proxy-api", serialized)
        self.assertNotIn("acct-a.json", serialized)

    def test_model_selection_missing_auth_ref_is_not_green(self) -> None:
        payload = commands_for_selection_truth()
        accounts_payload = payload["accounts_list"]["packet"]
        assert isinstance(accounts_payload, dict)
        accounts_payload["accounts"] = [
            account("acct-a", auth_ref=None),
            account("acct-b", auth_ref="managed:acct-b"),
        ]

        packet = build_model_selection_truth_packet({"model_id": "gpt-5.3-codex"}, payload, operator_status())

        self.assertEqual(packet["status"], "degraded")
        self.assertEqual(packet["machine_error_code"], "MODEL_SELECTION_STATIC_CLASSIFICATION_DEGRADED")
        self.assertEqual(packet["auth_ref_static_classification"]["auth_ref_missing_count"], 1)
        self.assertFalse(packet["auth_ref_static_classification"]["missing_auth_ref_is_green"])
        self.assertIn("auth_ref_missing_static", packet["static_not_green_reasons"])

    def test_model_selection_duplicate_auth_ref_is_not_green(self) -> None:
        payload = commands_for_selection_truth()
        accounts_payload = payload["accounts_list"]["packet"]
        assert isinstance(accounts_payload, dict)
        accounts_payload["accounts"] = [
            account("acct-a", auth_ref="managed:shared"),
            account("acct-b", auth_ref="managed:shared"),
        ]

        packet = build_model_selection_truth_packet({"model_id": "gpt-5.3-codex"}, payload, operator_status())

        self.assertEqual(packet["status"], "degraded")
        self.assertEqual(packet["machine_error_code"], "MODEL_SELECTION_STATIC_CLASSIFICATION_DEGRADED")
        self.assertEqual(packet["auth_ref_static_classification"]["duplicate_auth_ref_count"], 1)
        self.assertFalse(packet["auth_ref_static_classification"]["duplicate_auth_ref_is_green"])
        self.assertIn("duplicate_auth_ref_static", packet["static_not_green_reasons"])
        self.assertNotIn("shared.json", json.dumps(packet))

    def test_model_selection_active_routing_unchanged_by_dry_run(self) -> None:
        packet = build_model_selection_truth_packet(
            {"model_id": "gpt-5.3-codex"},
            commands_for_selection_truth(),
            operator_status(),
        )

        self.assertEqual(packet["active_routing_before_refs"], packet["active_routing_after_refs"])
        self.assertFalse(packet["active_routing_changed"])
        self.assertFalse(packet["account_mutation_performed"])

    def test_model_selection_classifies_external_route_without_raw_route_or_secret(self) -> None:
        route_operator_status = {
            "status": {"status": "ok", "machine_error_code": "OK"},
            "claim_gate": {"status": "passed"},
            "models": {"ok": True, "server_issued": True, "model_ids": []},
        }
        api_snapshot = {
            "routes": [
                {
                    "route_id": "wbp-web-primary-openrouter",
                    "enabled": True,
                    "secret_ref": "ROUTE_SECRET_REF_FIXTURE",
                    "upstream_model": "openrouter/upstream",
                }
            ]
        }

        packet = build_model_selection_truth_packet(
            {"model_id": "wbp-web-primary-openrouter"},
            commands_for_selection_truth(),
            route_operator_status,
            api_snapshot=api_snapshot,
        )
        serialized = json.dumps(packet)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["selected_source_class"], "route_backed")
        self.assertTrue(packet["selected_route_server_issued"])
        self.assertEqual(packet["selection_policy_state"], "route_ready_static")
        self.assertFalse(packet["route_selection_static"]["raw_route_id_exposed"])
        self.assertFalse(packet["route_selection_static"]["raw_secret_ref_exposed"])
        self.assertNotIn("ROUTE_SECRET_REF_FIXTURE", serialized)
        self.assertNotIn("wbp-web-primary-openrouter", packet["selected_route_ref"])

    def test_forbidden_account_smoke_fields_allows_only_top_level_model_id(self) -> None:
        self.assertEqual(forbidden_account_smoke_fields({"model_id": "gpt-5.3-codex"}), [])
        self.assertEqual(forbidden_account_smoke_fields({"account_id": "acct-a"}), ["account_id"])
        self.assertEqual(
            forbidden_account_smoke_fields({"model_id": "gpt-5.3-codex", "items": [{"path": "/x"}]}),
            ["items", "items[0].path"],
        )


if __name__ == "__main__":
    unittest.main()
