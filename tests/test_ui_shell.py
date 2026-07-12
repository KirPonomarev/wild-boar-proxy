# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import io
import json
import subprocess
import unittest
from unittest import mock

from wild_boar_proxy.ui_shell import (
    CLIENT_LAUNCH_RESULT_FIELDS,
    DIAGNOSTICS_RESULT_FIELDS,
    EXTERNAL_PROFILE_FIELDS,
    ONBOARDING_RESULT_FIELDS,
    SMOKE_RESULT_FIELDS,
    AccountPoolSnapshot,
    ExternalActionResult,
    ExternalModelsSnapshot,
    JsonCommandRunner,
    MinimalCompanionShell,
    QuickStartLedgerEntry,
    UiShellError,
    build_account_pool_snapshot,
    build_external_action_result,
    build_external_models_snapshot,
    build_external_profile_field_values,
    build_quick_start_account_component,
    build_quick_start_api_component,
    build_quick_start_check_all_payload,
    build_quick_start_runtime_component,
    build_client_launch_field_values,
    build_diagnostics_field_values,
    build_smoke_field_values,
    classify_external_profile_rendered_state,
    classify_client_launch_rendered_state,
    classify_smoke_rendered_state,
    build_onboarding_field_values,
    build_runtime_snapshot,
    format_onboarding_value,
    load_account_pool_snapshot,
    load_external_models_snapshot,
    load_runtime_snapshot,
    main,
    mark_external_action_stale,
    parse_exact_json_object,
    select_primary_external_route,
    run_packaged_continuity_smoke_json,
    run_account_onboard_and_refresh,
    run_account_mutation_and_refresh,
    run_account_validate_and_refresh,
    run_stable_repair_and_refresh,
    run_external_check_and_refresh,
    run_launch_client_and_refresh,
    run_mode_control_and_refresh,
    run_external_profile_and_refresh,
    run_smoke_and_refresh,
    run_diagnostics_export_and_refresh,
    run_sync_and_refresh,
)


def command_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "ok",
        "exit_code": 0,
        "human_message": "Command completed.",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
    }
    payload.update(overrides)
    return payload


class FakeVar:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: object) -> None:
        self.value = str(value)


def status_payload(**overrides: object) -> dict[str, object]:
    payload = command_payload(
        human_message="Runtime status summary is available.",
        liveness="healthy",
        severity="info",
        operator_action="none",
        desired_mode="managed",
        effective_mode="managed",
        endpoint="127.0.0.1:9999",
        current_proxy_url="http://127.0.0.1:10808",
        pool_summary={
            "active": 1,
            "reserve": 1,
            "retired": 0,
            "healthy": 2,
            "degraded": 0,
            "down": 0,
        },
        attestation_summary={
            "status": "ok",
            "machine_error_code": "OK",
            "attestation_source": "healthcheck --json",
            "observed_at_utc": "2026-05-05T10:00:00+00:00",
        },
        last_error="",
    )
    payload.update(overrides)
    return payload


def mode_payload(**overrides: object) -> dict[str, object]:
    payload = command_payload(
        human_message="Mode values are available.",
        desired_mode="managed",
        effective_mode="managed",
    )
    payload.update(overrides)
    return payload


def launch_payload(**overrides: object) -> dict[str, object]:
    payload = command_payload(
        human_message="Client launch dispatch observed.",
        client_launch_result={
            "status": "dispatch_requested",
            "attempted": True,
            "client_path": "/Applications/Signal.app/Contents/MacOS/Signal",
            "client_path_kind": "absolute",
            "runtime_precondition_checked": True,
            "runtime_precondition_status": "passed",
            "effective_mode_observed": "managed",
            "endpoint_observed": "127.0.0.1:9999",
            "profile_context": "default",
            "env_sanitized": True,
            "dispatch_method": "subprocess_popen",
            "dispatch_attempted": True,
            "dispatch_observed": "requested",
            "dispatch_exit_code": 0,
            "launch_claim_scope": "os_dispatch_only",
            "final_outcome": "dispatch_requested",
        },
    )
    payload.update(overrides)
    return payload


def smoke_payload(**overrides: object) -> dict[str, object]:
    payload = command_payload(
        human_message="Launcher smoke completed.",
        launch_mode="smoke",
        desired_mode="managed",
        effective_mode="managed",
        endpoint="127.0.0.1:9999",
        current_proxy_url="http://127.0.0.1:10808",
        launcher_exit_code=0,
        stabilization_seconds=0.2,
        stable_runtime_consumer={"status": "observed_source_selected"},
        attestation_summary={"status": "ok", "machine_error_code": "OK"},
        last_error="",
    )
    payload.update(overrides)
    return payload


def accounts_payload(**overrides: object) -> dict[str, object]:
    payload = command_payload(
        human_message="Account registry snapshot is available.",
        accounts=[
            {
                "id": "backend-a",
                "label": "Backend A",
                "pool": "active",
                "manual_hold": False,
                "status": "healthy",
                "fail_count": 0,
                "success_count": 3,
                "last_success": "2026-05-05T10:00:00+00:00",
                "last_error": "",
                "cooldown_until": None,
                "notes": "",
            },
            {
                "id": "backend-b",
                "label": "Backend B",
                "pool": "reserve",
                "manual_hold": False,
                "status": "healthy",
                "fail_count": 0,
                "success_count": 0,
                "last_success": None,
                "last_error": "",
                "cooldown_until": None,
                "notes": "",
            },
        ],
        registry_identity={
            "status": "clear",
            "machine_error_code": "OK",
            "next_action": "none",
        },
        pool_policy={"active_min": 1, "active_target": 2, "reserve_target": 0},
        stable_default_backend_id="backend-a",
    )
    payload.update(overrides)
    return payload


def external_status_payload(**overrides: object) -> dict[str, object]:
    payload = command_payload(
        human_message="External-models synthetic lifecycle status collected without live runtime claims.",
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none",
        data={
            "foundation_phase": "C3",
            "adapter_runtime_available": False,
            "lifecycle_mode": "synthetic",
            "adapter_state": "stopped",
            "listener_proven": False,
            "runtime_claim_blocked": True,
            "profile_ready": False,
            "routes_count": 1,
            "observed_routes_count": 0,
            "adapter": {
                "state": "stopped",
                "lifecycle_mode": "synthetic",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "base_url": None,
                "host": "127.0.0.1",
                "port": None,
                "started_at_utc": None,
                "last_transition": "init",
            },
            "local_auth": {
                "token_ref": "managed_local_token",
                "token_present": False,
                "token_created_at_utc": None,
            },
        },
        timestamp_utc="2026-05-12T00:00:00Z",
    )
    payload.update(overrides)
    return payload


def external_models_payload(**overrides: object) -> dict[str, object]:
    payload = command_payload(
        human_message="External-models route models listed from local registry.",
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none",
        data={
            "count": 1,
            "source": "local_routes_registry",
            "listener_proven": False,
            "runtime_claim_blocked": True,
            "models": [
                {
                    "route_id": "wbp-deepseek-v3",
                    "display_name": "DeepSeek V3",
                    "provider": "openrouter",
                    "base_url": "http://127.0.0.1:54321/v1",
                    "endpoint_path": "/chat/completions",
                    "upstream_model": "deepseek/deepseek-chat",
                    "compatibility": "openai_chat_completions",
                    "cost_class": "paid_or_free_limited",
                    "enabled": True,
                    "lane_role": "candidate",
                    "fallback_eligible": False,
                    "synthetic_adapter_state": "stopped",
                    "profile_ready": False,
                }
            ],
        },
        timestamp_utc="2026-05-12T00:00:00Z",
    )
    payload.update(overrides)
    return payload


def external_routes_payload(**overrides: object) -> dict[str, object]:
    payload = command_payload(
        human_message="External-models routes listed from local registry.",
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none",
        data={
            "count": 1,
            "routes": [
                {
                    "schema_version": 1,
                    "route_id": "wbp-deepseek-v3",
                    "display_name": "DeepSeek V3",
                    "provider": "openrouter",
                    "base_url": "http://127.0.0.1:54321/v1",
                    "endpoint_path": "/chat/completions",
                    "upstream_model": "deepseek/deepseek-chat",
                    "compatibility": "openai_chat_completions",
                    "auth": {"type": "bearer", "secret_ref": "OPENROUTER_API_KEY"},
                    "cost_class": "paid_or_free_limited",
                    "lane_role": "candidate",
                    "fallback_eligible": False,
                    "enabled": True,
                }
            ],
        },
        timestamp_utc="2026-05-12T00:00:00Z",
    )
    payload.update(overrides)
    return payload


def external_validate_payload(**overrides: object) -> dict[str, object]:
    payload = command_payload(
        human_message="External-models route validation captured provider evidence without claiming runtime readiness.",
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none",
        changed_files=["/tmp/state.json", "/tmp/evidence-validate.json"],
        data={
            "validation_kind": "provider_route_validate",
            "network_dependent": True,
            "listener_proven": False,
            "runtime_claim_blocked": True,
            "profile_ready": False,
            "verification_scope": "route_provider_only",
            "route_state": "model_visible",
            "requested_model": "wbp-deepseek-v3",
            "effective_model": "deepseek/deepseek-chat",
            "provider": "openrouter",
            "evidence_path": "/tmp/evidence-validate.json",
            "latency_ms": 6,
        },
        timestamp_utc="2026-05-12T00:00:00Z",
    )
    payload.update(overrides)
    return payload


def external_check_payload(**overrides: object) -> dict[str, object]:
    payload = command_payload(
        human_message="External-models route check captured bounded provider evidence.",
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none",
        changed_files=["/tmp/evidence-check.json"],
        data={
            "verification_kind": "provider_request_check",
            "network_dependent": True,
            "listener_proven": False,
            "runtime_claim_blocked": True,
            "profile_ready": False,
            "verification_scope": "route_provider_only",
            "route_state": "verified",
            "route_id": "wbp-deepseek-v3",
            "effective_model": "deepseek/deepseek-chat",
            "provider": "openrouter",
            "evidence_path": "/tmp/evidence-check.json",
            "latency_ms": 8,
        },
        timestamp_utc="2026-05-12T00:00:00Z",
    )
    payload.update(overrides)
    return payload


def external_profile_payload(**overrides: object) -> dict[str, object]:
    payload = command_payload(
        human_message="Codex Desktop profile contract generated without mutating config.",
        data={
            "profile_kind": "codex_desktop_openai_compatible",
            "route_id": "wbp-deepseek-v3",
            "base_url": None,
            "model": "deepseek/deepseek-chat",
            "api_key_source": "OPENROUTER_API_KEY",
            "writes_external_config": False,
            "profile_ready": False,
            "listener_proven": False,
            "runtime_claim_blocked": True,
            "synthetic_endpoint_contract": True,
            "prerequisite": "live_listener_contour_required",
        },
    )
    payload.update(overrides)
    return payload


class FakeRunner:
    def __init__(self, responses: dict[tuple[str, ...], dict[str, object]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str):
        self.calls.append(args)
        payload = self.responses[args]
        return type("Result", (), {"payload": payload, "stderr": ""})()


class ParseExactJsonObjectTests(unittest.TestCase):
    def test_accepts_single_json_object(self) -> None:
        payload = parse_exact_json_object('{"status":"ok"}')
        self.assertEqual(payload["status"], "ok")

    def test_rejects_trailing_non_json_text(self) -> None:
        with self.assertRaisesRegex(UiShellError, "exactly one JSON object"):
            parse_exact_json_object('{"status":"ok"} trailing')

    def test_rejects_non_object_json(self) -> None:
        with self.assertRaisesRegex(UiShellError, "must be an object"):
            parse_exact_json_object('["not","an","object"]')


class JsonCommandRunnerTests(unittest.TestCase):
    @mock.patch("wild_boar_proxy.ui_shell.subprocess.run")
    def test_run_parses_and_validates_command_payload(self, run_mock: mock.Mock) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["python3", "-m", "wild_boar_proxy", "status", "--json"],
            returncode=0,
            stdout='{"status":"ok","exit_code":0,"human_message":"ready","machine_error_code":"OK","changed_files":[],"next_action":"none"}',
            stderr="",
        )
        runner = JsonCommandRunner(base_command=["python3", "-m", "wild_boar_proxy"])

        result = runner.run("status", "--json")

        self.assertEqual(result.payload["human_message"], "ready")
        self.assertEqual(run_mock.call_args.kwargs["timeout"], 300.0)

    @mock.patch("wild_boar_proxy.ui_shell.subprocess.run")
    def test_run_surfaces_bounded_command_timeout(self, run_mock: mock.Mock) -> None:
        run_mock.side_effect = subprocess.TimeoutExpired(cmd=["wbp"], timeout=3)
        runner = JsonCommandRunner(base_command=["wbp"], timeout_seconds=3)

        with self.assertRaisesRegex(UiShellError, "timed out after 3 seconds"):
            runner.run("status", "--json")

    @mock.patch("wild_boar_proxy.ui_shell.subprocess.run")
    def test_run_rejects_missing_required_command_fields(self, run_mock: mock.Mock) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["python3", "-m", "wild_boar_proxy", "status", "--json"],
            returncode=0,
            stdout='{"status":"ok","exit_code":0,"human_message":"ready","machine_error_code":"OK","changed_files":[]}',
            stderr="",
        )
        runner = JsonCommandRunner(base_command=["python3", "-m", "wild_boar_proxy"])

        with self.assertRaisesRegex(UiShellError, "next_action"):
            runner.run("status", "--json")


class RuntimeSnapshotTests(unittest.TestCase):
    def test_build_runtime_snapshot_maps_runtime_truth(self) -> None:
        snapshot = build_runtime_snapshot(
            status_payload=status_payload(),
            mode_payload=mode_payload(),
        )

        self.assertEqual(snapshot.overall_state, "ok")
        self.assertEqual(snapshot.exit_code, 0)
        self.assertEqual(snapshot.desired_mode, "managed")
        self.assertEqual(snapshot.current_proxy_url, "http://127.0.0.1:10808")
        self.assertEqual(snapshot.attestation_source, "healthcheck --json")
        self.assertEqual(snapshot.degraded_count, 0)

    def test_build_runtime_snapshot_rejects_missing_required_pool_field(self) -> None:
        broken_status = status_payload(
            pool_summary={
                "reserve": 1,
                "retired": 0,
                "healthy": 2,
                "degraded": 1,
                "down": 0,
            }
        )

        with self.assertRaisesRegex(UiShellError, "active"):
            build_runtime_snapshot(
                status_payload=broken_status,
                mode_payload=mode_payload(),
            )

    def test_build_runtime_snapshot_rejects_malformed_pool_field(self) -> None:
        broken_status = status_payload(
            pool_summary={
                "active": None,
                "reserve": 1,
                "retired": 0,
                "healthy": 2,
                "degraded": 1,
                "down": 0,
            }
        )

        with self.assertRaisesRegex(UiShellError, "pool_summary.active"):
            build_runtime_snapshot(
                status_payload=broken_status,
                mode_payload=mode_payload(),
            )

    def test_build_runtime_snapshot_rejects_missing_required_attestation_summary_field(self) -> None:
        broken_status = status_payload(
            attestation_summary={
                "status": "ok",
                "machine_error_code": "OK",
                "observed_at_utc": "2026-05-05T10:00:00+00:00",
            }
        )

        with self.assertRaisesRegex(UiShellError, "attestation_source"):
            build_runtime_snapshot(
                status_payload=broken_status,
                mode_payload=mode_payload(),
            )

    def test_load_runtime_snapshot_rejects_mode_mismatch(self) -> None:
        runner = FakeRunner(
            {
                ("status", "--json"): status_payload(effective_mode="managed"),
                ("mode", "get", "--json"): mode_payload(effective_mode="stable"),
            }
        )

        with self.assertRaisesRegex(UiShellError, "effective mode"):
            load_runtime_snapshot(runner)

    def test_load_runtime_snapshot_live_probe_uses_healthcheck_truth(self) -> None:
        runner = FakeRunner(
            {
                ("status", "--json"): status_payload(
                    liveness="unknown",
                    pool_summary={
                        "active": 0,
                        "reserve": 1,
                        "retired": 0,
                        "healthy": 1,
                        "degraded": 0,
                        "down": 0,
                    },
                    attestation_summary={
                        "status": "not_run",
                        "machine_error_code": "LIVE_ATTESTATION_NOT_RUN_BY_STATUS",
                        "attestation_source": "status --json",
                        "observed_at_utc": "",
                    },
                ),
                ("mode", "get", "--json"): mode_payload(),
                ("healthcheck", "--json"): command_payload(
                    human_message="Runtime attestation passed.",
                    liveness="healthy",
                    severity="recoverable",
                    operator_action="none",
                    desired_mode="managed",
                    effective_mode="managed",
                    endpoint="127.0.0.1:9999",
                    current_proxy_url="",
                    attestation={
                        "attestation_source": "healthcheck --json",
                        "observed_at_utc": "2026-05-05T10:00:00+00:00",
                    },
                    last_error="",
                ),
            }
        )

        snapshot = load_runtime_snapshot(runner, live_probe=True)

        self.assertEqual(snapshot.liveness, "healthy")
        self.assertEqual(snapshot.attestation_source, "healthcheck --json")
        self.assertEqual(snapshot.active_count, 0)
        self.assertEqual(snapshot.reserve_count, 1)
        self.assertEqual(
            runner.calls,
            [
                ("status", "--json"),
                ("mode", "get", "--json"),
                ("healthcheck", "--json"),
            ],
        )


class AccountPoolSnapshotTests(unittest.TestCase):
    def test_build_account_pool_snapshot_maps_account_truth(self) -> None:
        snapshot = build_account_pool_snapshot(accounts_payload())

        self.assertIsInstance(snapshot, AccountPoolSnapshot)
        self.assertEqual(snapshot.registry_identity_status, "clear")
        self.assertEqual(snapshot.active_count, 1)
        self.assertEqual(snapshot.reserve_count, 1)
        self.assertEqual(snapshot.capacity_target, 25)
        self.assertEqual(snapshot.accounts[0].backend_id, "backend-a")

    def test_build_account_pool_snapshot_rejects_missing_accounts_field(self) -> None:
        broken_payload = accounts_payload()
        del broken_payload["accounts"]

        with self.assertRaisesRegex(UiShellError, "accounts"):
            build_account_pool_snapshot(broken_payload)

    def test_build_account_pool_snapshot_rejects_missing_account_row_field(self) -> None:
        broken_payload = accounts_payload(
            accounts=[
                {
                    "id": "backend-a",
                    "label": "Backend A",
                    "pool": "active",
                    "manual_hold": False,
                    "status": "healthy",
                    "fail_count": 0,
                    "success_count": 3,
                    "last_success": "2026-05-05T10:00:00+00:00",
                    "last_error": "",
                    "cooldown_until": None,
                }
            ]
        )

        with self.assertRaisesRegex(UiShellError, "notes"):
            build_account_pool_snapshot(broken_payload)

    def test_build_account_pool_snapshot_rejects_missing_registry_identity_field(self) -> None:
        broken_payload = accounts_payload(
            registry_identity={
                "status": "clear",
                "machine_error_code": "OK",
            }
        )

        with self.assertRaisesRegex(UiShellError, "next_action"):
            build_account_pool_snapshot(broken_payload)

    def test_load_account_pool_snapshot_reads_accounts_list_only(self) -> None:
        runner = FakeRunner({("accounts", "list", "--json"): accounts_payload()})

        snapshot = load_account_pool_snapshot(runner)

        self.assertEqual(snapshot.accounts[0].label, "Backend A")
        self.assertEqual(runner.calls, [("accounts", "list", "--json")])


class ExternalModelsSnapshotTests(unittest.TestCase):
    def test_build_external_models_snapshot_maps_packet_truth(self) -> None:
        snapshot = build_external_models_snapshot(
            status_payload=external_status_payload(),
            models_payload=external_models_payload(),
            routes_payload=external_routes_payload(),
        )

        self.assertIsInstance(snapshot, ExternalModelsSnapshot)
        self.assertEqual(snapshot.foundation_phase, "C3")
        self.assertEqual(snapshot.lifecycle_mode, "synthetic")
        self.assertFalse(snapshot.listener_proven)
        self.assertTrue(snapshot.runtime_claim_blocked)
        self.assertFalse(snapshot.profile_ready)
        self.assertEqual(snapshot.models_source, "local_routes_registry")
        self.assertEqual(snapshot.models[0].route_id, "wbp-deepseek-v3")
        self.assertEqual(snapshot.routes[0].secret_ref, "OPENROUTER_API_KEY")
        self.assertEqual(snapshot.observed_routes, {})

    def test_build_external_models_snapshot_rejects_non_object_auth(self) -> None:
        broken_routes = external_routes_payload(
            data={
                "count": 1,
                "routes": [
                    {
                        "schema_version": 1,
                        "route_id": "wbp-deepseek-v3",
                        "display_name": "DeepSeek V3",
                        "provider": "openrouter",
                        "base_url": "http://127.0.0.1:54321/v1",
                        "endpoint_path": "/chat/completions",
                        "upstream_model": "deepseek/deepseek-chat",
                        "compatibility": "openai_chat_completions",
                        "auth": "broken",
                        "cost_class": "paid_or_free_limited",
                        "lane_role": "candidate",
                        "fallback_eligible": False,
                        "enabled": True,
                    }
                ],
            }
        )

        with self.assertRaisesRegex(UiShellError, "external route auth must be an object"):
            build_external_models_snapshot(
                status_payload=external_status_payload(),
                models_payload=external_models_payload(),
                routes_payload=broken_routes,
            )

    def test_load_external_models_snapshot_reads_only_external_packets(self) -> None:
        runner = FakeRunner(
            {
                ("external-models", "status", "--json"): external_status_payload(),
                ("external-models", "models", "--json"): external_models_payload(),
                ("external-models", "routes", "list", "--json"): external_routes_payload(),
            }
        )

        snapshot = load_external_models_snapshot(runner)

        self.assertEqual(snapshot.routes_count, 1)
        self.assertEqual(
            runner.calls,
            [
                ("external-models", "status", "--json"),
                ("external-models", "models", "--json"),
                ("external-models", "routes", "list", "--json"),
            ],
        )


class ExternalActionResultTests(unittest.TestCase):
    def test_build_external_action_result_preserves_provider_only_scope(self) -> None:
        result = build_external_action_result(
            action="external_validate",
            action_payload=external_validate_payload(),
        )

        self.assertIsInstance(result, ExternalActionResult)
        self.assertEqual(result.action, "external_validate")
        self.assertEqual(result.route_id, "wbp-deepseek-v3")
        self.assertEqual(result.verification_scope, "route_provider_only")
        self.assertEqual(result.route_state, "model_visible")
        self.assertFalse(result.listener_proven)
        self.assertTrue(result.runtime_claim_blocked)
        self.assertFalse(result.profile_ready)
        self.assertTrue(result.network_dependent)
        self.assertEqual(result.changed_files, ("/tmp/state.json", "/tmp/evidence-validate.json"))
        self.assertFalse(result.is_stale)
        self.assertEqual(result.stale_reason, "")

    def test_build_external_action_result_uses_network_dependent_evidence_fallback(self) -> None:
        payload = external_validate_payload(
            data={
                "route_id": "wbp-deepseek-v3",
                "network_dependent_evidence": False,
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "profile_ready": False,
                "verification_scope": "route_provider_only",
                "route_state": "verified",
                "provider": "openrouter",
                "evidence_path": "/tmp/evidence-local.json",
            }
        )

        result = build_external_action_result(
            action="external_evidence",
            action_payload=payload,
        )

        self.assertFalse(result.network_dependent)
        self.assertEqual(result.route_state, "verified")
        self.assertEqual(result.evidence_path, "/tmp/evidence-local.json")

    def test_build_external_action_result_rejects_non_list_changed_files(self) -> None:
        with self.assertRaisesRegex(UiShellError, "changed_files must be a list"):
            build_external_action_result(
                action="external_validate",
                action_payload=external_validate_payload(changed_files="/tmp/state.json"),
            )

    def test_mark_external_action_stale_sets_stale_metadata(self) -> None:
        result = build_external_action_result(
            action="external_validate",
            action_payload=external_validate_payload(),
        )

        stale_result = mark_external_action_stale(result, reason="cached_history")

        assert stale_result is not None
        self.assertTrue(stale_result.is_stale)
        self.assertEqual(stale_result.stale_reason, "cached_history")
        self.assertEqual(stale_result.route_id, result.route_id)


class ExternalProfileTests(unittest.TestCase):
    def test_run_external_profile_and_refresh_reads_packet_then_external_truth(self) -> None:
        runner = FakeRunner(
            {
                (
                    "external-models",
                    "profile",
                    "codex-desktop",
                    "--route",
                    "wbp-deepseek-v3",
                    "--json",
                ): external_profile_payload(),
                ("external-models", "status", "--json"): external_status_payload(),
                ("external-models", "models", "--json"): external_models_payload(),
                ("external-models", "routes", "list", "--json"): external_routes_payload(),
            }
        )

        action_payload, snapshot = run_external_profile_and_refresh(
            runner, "wbp-deepseek-v3"
        )

        self.assertEqual(action_payload["status"], "ok")
        self.assertEqual(snapshot.routes[0].route_id, "wbp-deepseek-v3")
        self.assertEqual(
            runner.calls,
            [
                (
                    "external-models",
                    "profile",
                    "codex-desktop",
                    "--route",
                    "wbp-deepseek-v3",
                    "--json",
                ),
                ("external-models", "status", "--json"),
                ("external-models", "models", "--json"),
                ("external-models", "routes", "list", "--json"),
            ],
        )

    def test_build_external_profile_field_values_maps_profile_packet(self) -> None:
        values = build_external_profile_field_values(external_profile_payload())

        self.assertEqual(values["profile_kind"], "codex_desktop_openai_compatible")
        self.assertEqual(values["route_id"], "wbp-deepseek-v3")
        self.assertEqual(values["writes_external_config"], "false")
        self.assertEqual(values["synthetic_endpoint_contract"], "true")

    def test_classify_external_profile_rendered_state_accepts_profile_packet_only(self) -> None:
        rendered_state = classify_external_profile_rendered_state(
            external_profile_payload(),
            build_external_profile_field_values(external_profile_payload()),
            malformed=False,
        )

        self.assertEqual(rendered_state, "profile_packet_only")


class QuickStartParityHelperTests(unittest.TestCase):
    def test_run_external_check_and_refresh_reads_packet_then_truth(self) -> None:
        runner = FakeRunner(
            {
                ("external-models", "check", "--route", "wbp-deepseek-v3", "--json"): external_check_payload(),
                ("external-models", "status", "--json"): external_status_payload(),
                ("external-models", "models", "--json"): external_models_payload(),
                ("external-models", "routes", "list", "--json"): external_routes_payload(),
            }
        )

        action_payload, snapshot = run_external_check_and_refresh(runner, "wbp-deepseek-v3")

        self.assertEqual(action_payload["status"], "ok")
        self.assertEqual(select_primary_external_route(snapshot).route_id, "wbp-deepseek-v3")
        self.assertEqual(
            runner.calls,
            [
                ("external-models", "check", "--route", "wbp-deepseek-v3", "--json"),
                ("external-models", "status", "--json"),
                ("external-models", "models", "--json"),
                ("external-models", "routes", "list", "--json"),
            ],
        )

    def test_build_quick_start_api_component_maps_missing_secret_to_partial(self) -> None:
        snapshot = build_external_models_snapshot(
            status_payload=external_status_payload(
                data={
                    **external_status_payload()["data"],
                    "local_auth": {"token_ref": "managed_local_token", "token_present": False, "token_created_at_utc": None},
                }
            ),
            models_payload=external_models_payload(),
            routes_payload=external_routes_payload(),
        )

        component = build_quick_start_api_component(snapshot)

        self.assertEqual(component["status"], "partial")
        self.assertEqual(component["machine_error_code"], "UI_CHECK_ALL_API_SECRET_REF_MISSING")

    def test_build_quick_start_check_all_payload_marks_ready_when_truths_are_green(self) -> None:
        runtime_snapshot = build_runtime_snapshot(
            status_payload=status_payload(),
            mode_payload=mode_payload(),
        )
        account_snapshot = build_account_pool_snapshot(accounts_payload())
        external_snapshot = build_external_models_snapshot(
            status_payload=external_status_payload(
                data={
                    **external_status_payload()["data"],
                    "local_auth": {"token_ref": "managed_local_token", "token_present": True, "token_created_at_utc": None},
                    "observed_routes": {
                        "wbp-deepseek-v3": {
                            "availability_state": "verified",
                            "last_check": "2026-05-21T09:45:00Z",
                        }
                    },
                    "observed_routes_count": 1,
                }
            ),
            models_payload=external_models_payload(),
            routes_payload=external_routes_payload(),
        )

        payload = build_quick_start_check_all_payload(
            runtime_snapshot=runtime_snapshot,
            account_snapshot=account_snapshot,
            external_snapshot=external_snapshot,
            api_check_payload=external_check_payload(),
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["bundle_verdict"], "ready")
        self.assertTrue(payload["data"]["hidden_mutation_absent"])


class ModeControlTests(unittest.TestCase):
    def test_run_mode_control_and_refresh_uses_command_then_truth_refresh(self) -> None:
        runner = FakeRunner(
            {
                ("mode", "set", "stable", "--json"): mode_payload(
                    human_message="Desired mode set to stable.",
                    desired_mode="stable",
                    effective_mode="managed",
                ),
                ("status", "--json"): status_payload(
                    desired_mode="stable",
                    effective_mode="managed",
                ),
                ("mode", "get", "--json"): mode_payload(
                    desired_mode="stable",
                    effective_mode="managed",
                ),
            }
        )

        action_payload, snapshot = run_mode_control_and_refresh(
            runner, ("mode", "set", "stable", "--json")
        )

        self.assertEqual(action_payload["human_message"], "Desired mode set to stable.")
        self.assertEqual(snapshot.desired_mode, "stable")
        self.assertEqual(
            runner.calls,
            [
                ("mode", "set", "stable", "--json"),
                ("status", "--json"),
                ("mode", "get", "--json"),
            ],
        )

    def test_run_sync_and_refresh_includes_accounts_refresh(self) -> None:
        runner = FakeRunner(
            {
                ("sync", "--json"): command_payload(human_message="Managed sync completed."),
                ("status", "--json"): status_payload(),
                ("accounts", "list", "--json"): accounts_payload(),
                ("mode", "get", "--json"): mode_payload(),
            }
        )

        action_payload, runtime_snapshot, account_snapshot = run_sync_and_refresh(runner)

        self.assertEqual(action_payload["human_message"], "Managed sync completed.")
        self.assertEqual(runtime_snapshot.effective_mode, "managed")
        self.assertEqual(account_snapshot.active_count, 1)
        self.assertEqual(
            runner.calls,
            [
                ("sync", "--json"),
                ("status", "--json"),
                ("accounts", "list", "--json"),
                ("mode", "get", "--json"),
            ],
        )

    def test_run_sync_and_refresh_rejects_capacity_count_mismatch(self) -> None:
        runner = FakeRunner(
            {
                ("sync", "--json"): command_payload(human_message="Managed sync completed."),
                ("status", "--json"): status_payload(
                    pool_summary={
                        "active": 2,
                        "reserve": 0,
                        "retired": 0,
                        "healthy": 2,
                        "degraded": 0,
                        "down": 0,
                    }
                ),
                ("accounts", "list", "--json"): accounts_payload(),
                ("mode", "get", "--json"): mode_payload(),
            }
        )

        with self.assertRaisesRegex(
            UiShellError, "status pool_summary and accounts list disagree"
        ):
            run_sync_and_refresh(runner)

    def test_run_diagnostics_export_and_refresh_includes_runtime_and_accounts_refresh(self) -> None:
        runner = FakeRunner(
            {
                ("diagnostics", "export", "--json"): command_payload(
                    human_message="Diagnostics bundle exported.",
                    bundle_path="/tmp/wbp-diag",
                ),
                ("status", "--json"): status_payload(),
                ("accounts", "list", "--json"): accounts_payload(),
                ("mode", "get", "--json"): mode_payload(),
            }
        )

        action_payload, runtime_snapshot, account_snapshot = run_diagnostics_export_and_refresh(
            runner
        )

        self.assertEqual(action_payload["human_message"], "Diagnostics bundle exported.")
        self.assertEqual(action_payload["bundle_path"], "/tmp/wbp-diag")
        self.assertEqual(runtime_snapshot.effective_mode, "managed")
        self.assertEqual(account_snapshot.active_count, 1)
        self.assertEqual(
            runner.calls,
            [
                ("diagnostics", "export", "--json"),
                ("status", "--json"),
                ("accounts", "list", "--json"),
                ("mode", "get", "--json"),
            ],
        )

    def test_run_stable_repair_and_refresh_includes_runtime_and_accounts_refresh(self) -> None:
        runner = FakeRunner(
            {
                ("stable", "repair", "--apply", "--json"): command_payload(
                    human_message="Stable repair applied."
                ),
                ("status", "--json"): status_payload(),
                ("accounts", "list", "--json"): accounts_payload(),
                ("mode", "get", "--json"): mode_payload(),
            }
        )

        action_payload, runtime_snapshot, account_snapshot = run_stable_repair_and_refresh(
            runner
        )

        self.assertEqual(action_payload["human_message"], "Stable repair applied.")
        self.assertEqual(runtime_snapshot.effective_mode, "managed")
        self.assertEqual(account_snapshot.active_count, 1)
        self.assertEqual(
            runner.calls,
            [
                ("stable", "repair", "--apply", "--json"),
                ("status", "--json"),
                ("accounts", "list", "--json"),
                ("mode", "get", "--json"),
            ],
        )

    def test_run_stable_repair_and_refresh_rejects_capacity_count_mismatch(self) -> None:
        runner = FakeRunner(
            {
                ("stable", "repair", "--apply", "--json"): command_payload(
                    human_message="Stable repair applied."
                ),
                ("status", "--json"): status_payload(
                    pool_summary={
                        "active": 2,
                        "reserve": 0,
                        "retired": 0,
                        "healthy": 2,
                        "degraded": 0,
                        "down": 0,
                    }
                ),
                ("accounts", "list", "--json"): accounts_payload(),
                ("mode", "get", "--json"): mode_payload(),
            }
        )

        with self.assertRaisesRegex(
            UiShellError, "status pool_summary and accounts list disagree"
        ):
            run_stable_repair_and_refresh(runner)


class LaunchClientTests(unittest.TestCase):
    def test_run_launch_client_and_refresh_uses_launch_then_status_only(self) -> None:
        runner = FakeRunner(
            {
                (
                    "launch",
                    "client",
                    "--client-path",
                    "/Applications/Signal.app/Contents/MacOS/Signal",
                    "--json",
                ): launch_payload(),
                ("status", "--json"): status_payload(),
            }
        )

        action_payload, snapshot = run_launch_client_and_refresh(
            runner,
            (
                "launch",
                "client",
                "--client-path",
                "/Applications/Signal.app/Contents/MacOS/Signal",
                "--json",
            ),
        )

        self.assertEqual(action_payload["status"], "ok")
        self.assertEqual(snapshot.overall_state, "ok")
        self.assertEqual(
            runner.calls,
            [
                (
                    "launch",
                    "client",
                    "--client-path",
                    "/Applications/Signal.app/Contents/MacOS/Signal",
                    "--json",
                ),
                ("status", "--json"),
            ],
        )

    def test_build_client_launch_field_values_rejects_non_object_nested_surface(self) -> None:
        with self.assertRaisesRegex(UiShellError, "client_launch_result must be an object"):
            build_client_launch_field_values(launch_payload(client_launch_result="broken"))

    def test_classify_client_launch_rendered_state_accepts_bounded_dispatch_only(self) -> None:
        field_values = build_client_launch_field_values(launch_payload())
        rendered_state = classify_client_launch_rendered_state(
            launch_payload(),
            field_values,
            malformed=False,
        )
        self.assertEqual(rendered_state, "bounded_dispatch_only")

    def test_classify_client_launch_rendered_state_marks_precondition_failure(self) -> None:
        payload = launch_payload(
            status="error",
            machine_error_code="CLIENT_LAUNCH_RUNTIME_PRECONDITION_FAILED",
            client_launch_result={
                "final_outcome": "runtime_precondition_failed",
                "runtime_precondition_status": "failed",
            },
        )
        field_values = build_client_launch_field_values(payload)
        rendered_state = classify_client_launch_rendered_state(
            payload,
            field_values,
            malformed=False,
        )
        self.assertEqual(rendered_state, "failure")

    def test_classify_client_launch_rendered_state_marks_malformed_surface(self) -> None:
        rendered_state = classify_client_launch_rendered_state(
            launch_payload(),
            {field: "" for field in CLIENT_LAUNCH_RESULT_FIELDS},
            malformed=True,
        )
        self.assertEqual(rendered_state, "integration_failure")

    def test_classify_client_launch_rendered_state_marks_top_level_integration_failure(self) -> None:
        rendered_state = classify_client_launch_rendered_state(
            command_payload(status="integration_failure"),
            {field: "" for field in CLIENT_LAUNCH_RESULT_FIELDS},
            malformed=False,
        )
        self.assertEqual(rendered_state, "integration_failure")

    def test_classify_client_launch_rendered_state_rejects_contradictory_dispatch_payload(self) -> None:
        payload = launch_payload(
            client_launch_result={
                "final_outcome": "dispatch_requested",
                "launch_claim_scope": "os_dispatch_only",
                "dispatch_observed": "requested",
                "attempted": True,
                "dispatch_attempted": False,
                "runtime_precondition_status": "ok",
            }
        )
        field_values = build_client_launch_field_values(payload)
        rendered_state = classify_client_launch_rendered_state(
            payload,
            field_values,
            malformed=False,
        )
        self.assertEqual(rendered_state, "unknown")

    def test_classify_client_launch_rendered_state_rejects_nonzero_dispatch_exit(self) -> None:
        payload = launch_payload(
            client_launch_result={
                "final_outcome": "dispatch_requested",
                "launch_claim_scope": "os_dispatch_only",
                "dispatch_observed": "requested",
                "attempted": True,
                "dispatch_attempted": True,
                "runtime_precondition_status": "ok",
                "dispatch_exit_code": 7,
            }
        )
        field_values = build_client_launch_field_values(payload)
        rendered_state = classify_client_launch_rendered_state(
            payload,
            field_values,
            malformed=False,
        )
        self.assertEqual(rendered_state, "unknown")


class SmokeTests(unittest.TestCase):
    def test_run_smoke_and_refresh_uses_smoke_then_status_only(self) -> None:
        runner = FakeRunner(
            {
                ("launch", "smoke", "--json"): smoke_payload(),
                ("status", "--json"): status_payload(),
            }
        )

        action_payload, snapshot = run_smoke_and_refresh(runner)

        self.assertEqual(action_payload["status"], "ok")
        self.assertEqual(snapshot.overall_state, "ok")
        self.assertEqual(
            runner.calls,
            [
                ("launch", "smoke", "--json"),
                ("status", "--json"),
            ],
        )

    def test_build_smoke_field_values_rejects_non_object_nested_surface(self) -> None:
        with self.assertRaisesRegex(UiShellError, "stable_runtime_consumer must be an object"):
            build_smoke_field_values(smoke_payload(stable_runtime_consumer="broken"))

    def test_classify_smoke_rendered_state_marks_failure(self) -> None:
        rendered_state = classify_smoke_rendered_state(
            smoke_payload(
                status="error",
                machine_error_code="MANAGED_RUNTIME_PRECONDITION_FAILED",
            ),
            malformed=False,
        )
        self.assertEqual(rendered_state, "failure")

    def test_classify_smoke_rendered_state_stays_bounded(self) -> None:
        rendered_state = classify_smoke_rendered_state(
            smoke_payload(),
            malformed=False,
        )
        self.assertEqual(rendered_state, "bounded_runtime_smoke_only")
        self.assertNotEqual(rendered_state, "success")

    def test_classify_smoke_rendered_state_marks_malformed_surface(self) -> None:
        rendered_state = classify_smoke_rendered_state(
            smoke_payload(),
            malformed=True,
        )
        self.assertEqual(rendered_state, "integration_failure")

    def test_classify_smoke_rendered_state_marks_missing_launch_mode_unknown(self) -> None:
        payload = smoke_payload()
        del payload["launch_mode"]
        rendered_state = classify_smoke_rendered_state(
            payload,
            malformed=False,
        )
        self.assertEqual(rendered_state, "unknown")


class AccountCheckTests(unittest.TestCase):
    def test_run_account_validate_and_refresh_uses_validate_then_accounts_list(self) -> None:
        runner = FakeRunner(
            {
                ("accounts", "validate", "backend-a", "--json"): command_payload(
                    human_message="Account validated."
                ),
                ("accounts", "list", "--json"): accounts_payload(),
            }
        )

        action_payload, snapshot = run_account_validate_and_refresh(runner, "backend-a")

        self.assertEqual(action_payload["human_message"], "Account validated.")
        self.assertEqual(snapshot.registry_identity_status, "clear")
        self.assertEqual(
            runner.calls,
            [
                ("accounts", "validate", "backend-a", "--json"),
                ("accounts", "list", "--json"),
            ],
        )

    def test_recheck_alias_uses_same_validate_command_shape(self) -> None:
        runner = FakeRunner(
            {
                ("accounts", "validate", "backend-a", "--json"): command_payload(
                    human_message="Account validated."
                ),
                ("accounts", "list", "--json"): accounts_payload(),
            }
        )

        _action_payload, _snapshot = run_account_validate_and_refresh(runner, "backend-a")

        self.assertNotIn(("status", "--json"), runner.calls)
        self.assertEqual(runner.calls[0], ("accounts", "validate", "backend-a", "--json"))


class AccountMutationTests(unittest.TestCase):
    def test_run_account_mutation_and_refresh_uses_accounts_list_then_status(self) -> None:
        runner = FakeRunner(
            {
                ("accounts", "promote", "backend-b", "--json"): command_payload(
                    human_message="Account promoted."
                ),
                ("accounts", "list", "--json"): accounts_payload(
                    accounts=[
                        {
                            "id": "backend-b",
                            "label": "Backend B",
                            "pool": "active",
                            "manual_hold": False,
                            "status": "healthy",
                            "fail_count": 0,
                            "success_count": 1,
                            "last_success": "2026-05-05T11:00:00+00:00",
                            "last_error": "",
                            "cooldown_until": None,
                            "notes": "",
                        }
                    ]
                ),
                ("status", "--json"): status_payload(
                    pool_summary={
                        "active": 1,
                        "reserve": 0,
                        "retired": 0,
                        "healthy": 1,
                        "degraded": 0,
                        "down": 0,
                    }
                ),
            }
        )

        action_payload, runtime_snapshot, account_snapshot = run_account_mutation_and_refresh(
            runner, ("accounts", "promote", "backend-b", "--json")
        )

        self.assertEqual(action_payload["human_message"], "Account promoted.")
        self.assertEqual(runtime_snapshot.overall_state, "ok")
        self.assertEqual(account_snapshot.active_count, 1)
        self.assertNotIn(("mode", "get", "--json"), runner.calls)
        self.assertEqual(
            runner.calls,
            [
                ("accounts", "promote", "backend-b", "--json"),
                ("accounts", "list", "--json"),
                ("status", "--json"),
            ],
        )

    def test_run_account_mutation_and_refresh_rejects_broken_accounts_refresh(self) -> None:
        runner = FakeRunner(
            {
                ("accounts", "hold", "backend-a", "--json"): command_payload(
                    human_message="Account held."
                ),
                ("accounts", "list", "--json"): command_payload(
                    human_message="Account registry snapshot is available.",
                    registry_identity={
                        "status": "clear",
                        "machine_error_code": "OK",
                        "next_action": "none",
                    },
                ),
                ("status", "--json"): status_payload(),
            }
        )

        with self.assertRaisesRegex(UiShellError, "accounts"):
            run_account_mutation_and_refresh(runner, ("accounts", "hold", "backend-a", "--json"))

    def test_run_account_mutation_and_refresh_rejects_broken_status_refresh(self) -> None:
        runner = FakeRunner(
            {
                ("accounts", "release", "backend-a", "--json"): command_payload(
                    human_message="Account released."
                ),
                ("accounts", "list", "--json"): accounts_payload(),
                ("status", "--json"): command_payload(
                    human_message="Runtime status summary is available.",
                    machine_error_code="OK",
                ),
            }
        )

        with self.assertRaisesRegex(UiShellError, "liveness"):
            run_account_mutation_and_refresh(
                runner, ("accounts", "release", "backend-a", "--json")
            )

    def test_run_account_mutation_and_refresh_rejects_capacity_count_mismatch(self) -> None:
        runner = FakeRunner(
            {
                ("accounts", "hold", "backend-a", "--json"): command_payload(
                    human_message="Account held."
                ),
                ("accounts", "list", "--json"): accounts_payload(),
                ("status", "--json"): status_payload(
                    pool_summary={
                        "active": 0,
                        "reserve": 2,
                        "retired": 0,
                        "healthy": 2,
                        "degraded": 0,
                        "down": 0,
                    }
                ),
            }
        )

        with self.assertRaisesRegex(
            UiShellError, "status pool_summary and accounts list disagree"
        ):
            run_account_mutation_and_refresh(
                runner, ("accounts", "hold", "backend-a", "--json")
            )

    def test_run_account_retire_and_refresh_uses_accounts_list_then_status(self) -> None:
        runner = FakeRunner(
            {
                ("accounts", "retire", "backend-a", "--json"): command_payload(
                    human_message="Account retired."
                ),
                ("accounts", "list", "--json"): accounts_payload(
                    accounts=[
                        {
                            "id": "backend-a",
                            "label": "Backend A",
                            "pool": "retired",
                            "manual_hold": False,
                            "status": "healthy",
                            "fail_count": 0,
                            "success_count": 3,
                            "last_success": "2026-05-05T10:00:00+00:00",
                            "last_error": "",
                            "cooldown_until": None,
                            "notes": "",
                        }
                    ]
                ),
                ("status", "--json"): status_payload(
                    pool_summary={
                        "active": 0,
                        "reserve": 0,
                        "retired": 1,
                        "healthy": 1,
                        "degraded": 0,
                        "down": 0,
                    }
                ),
            }
        )

        action_payload, runtime_snapshot, account_snapshot = run_account_mutation_and_refresh(
            runner, ("accounts", "retire", "backend-a", "--json")
        )

        self.assertEqual(action_payload["human_message"], "Account retired.")
        self.assertEqual(runtime_snapshot.overall_state, "ok")
        self.assertEqual(account_snapshot.retired_count, 1)
        self.assertEqual(account_snapshot.accounts[0].pool, "retired")
        self.assertEqual(
            runner.calls,
            [
                ("accounts", "retire", "backend-a", "--json"),
                ("accounts", "list", "--json"),
                ("status", "--json"),
            ],
        )


class OnboardingActionTests(unittest.TestCase):
    def test_run_account_onboard_and_refresh_uses_onboard_then_accounts_then_status(self) -> None:
        runner = FakeRunner(
            {
                ("accounts", "onboard", "--json", "--auth-ref", "/tmp/new-auth.json", "--non-interactive"): command_payload(
                    human_message="Onboarding completed.",
                    onboarding_result={
                        "input_mode": "explicit_auth_ref",
                        "explicit_auth_ref": "/tmp/new-auth.json",
                        "new_backend_ids": ["backend-new"],
                        "selected_backend_id": "backend-new",
                        "selection_status": "selected_unique_backend",
                        "reserve_first_enforced": True,
                        "pool_after_onboarding": "reserve",
                        "validate_attempted": True,
                        "validate_outcome": "ok",
                        "sync_attempted": False,
                        "sync_outcome": "skipped_by_flag",
                        "status_observed": {"command_status": "ok"},
                        "external_command_exit_code": 7,
                        "external_command_status": "nonzero",
                        "active_routing_changed": False,
                        "final_outcome": "explicit_auth_imported_to_reserve",
                    },
                ),
                ("accounts", "list", "--json"): accounts_payload(),
                ("status", "--json"): status_payload(),
            }
        )

        action_payload, runtime_snapshot, account_snapshot = run_account_onboard_and_refresh(
            runner,
            ("accounts", "onboard", "--json", "--auth-ref", "/tmp/new-auth.json", "--non-interactive"),
        )

        self.assertEqual(action_payload["status"], "ok")
        self.assertEqual(runtime_snapshot.overall_state, "ok")
        self.assertEqual(account_snapshot.reserve_count, 1)
        self.assertEqual(
            runner.calls,
            [
                ("accounts", "onboard", "--json", "--auth-ref", "/tmp/new-auth.json", "--non-interactive"),
                ("accounts", "list", "--json"),
                ("status", "--json"),
            ],
        )

    def test_run_account_onboard_and_refresh_rejects_capacity_count_mismatch(self) -> None:
        runner = FakeRunner(
            {
                ("accounts", "onboard", "--json", "--auth-ref", "/tmp/new-auth.json", "--non-interactive"): command_payload(
                    human_message="Onboarding completed.",
                    onboarding_result={
                        "input_mode": "explicit_auth_ref",
                        "explicit_auth_ref": "/tmp/new-auth.json",
                        "new_backend_ids": ["backend-new"],
                        "selected_backend_id": "backend-new",
                        "selection_status": "selected_unique_backend",
                        "reserve_first_enforced": True,
                        "pool_after_onboarding": "reserve",
                        "validate_attempted": True,
                        "validate_outcome": "ok",
                        "sync_attempted": False,
                        "sync_outcome": "skipped_by_flag",
                        "status_observed": {"command_status": "ok"},
                        "external_command_exit_code": 7,
                        "external_command_status": "nonzero",
                        "active_routing_changed": False,
                        "final_outcome": "explicit_auth_imported_to_reserve",
                    },
                ),
                ("accounts", "list", "--json"): accounts_payload(),
                ("status", "--json"): status_payload(
                    pool_summary={
                        "active": 2,
                        "reserve": 1,
                        "retired": 0,
                        "healthy": 3,
                        "degraded": 0,
                        "down": 0,
                    }
                ),
            }
        )

        with self.assertRaisesRegex(
            UiShellError, "status pool_summary and accounts list disagree"
        ):
            run_account_onboard_and_refresh(
                runner,
                ("accounts", "onboard", "--json", "--auth-ref", "/tmp/new-auth.json", "--non-interactive"),
            )

    def test_build_onboarding_field_values_maps_known_fields_and_missing_as_blank(self) -> None:
        values = build_onboarding_field_values(
            command_payload(
                onboarding_result={
                    "input_mode": "explicit_auth_ref",
                    "sync_outcome": "skipped_by_flag",
                    "reserve_first_enforced": True,
                    "auth_snapshot_before_login_status": "ok",
                    "auth_snapshot_before_login_count": 2,
                }
            )
        )

        self.assertEqual(set(values.keys()), set(ONBOARDING_RESULT_FIELDS))
        self.assertEqual(values["input_mode"], "explicit_auth_ref")
        self.assertEqual(values["sync_outcome"], "skipped_by_flag")
        self.assertEqual(values["reserve_first_enforced"], "true")
        self.assertEqual(values["auth_snapshot_before_login_status"], "ok")
        self.assertEqual(values["auth_snapshot_before_login_count"], "2")
        self.assertEqual(values["selected_backend_id"], "")

    def test_build_onboarding_field_values_rejects_non_object_onboarding_result(self) -> None:
        with self.assertRaisesRegex(UiShellError, "onboarding_result must be an object"):
            build_onboarding_field_values(command_payload(onboarding_result="broken"))

    def test_format_onboarding_value_serializes_lists_and_dicts(self) -> None:
        self.assertEqual(format_onboarding_value(["backend-a"]), '["backend-a"]')
        self.assertEqual(
            format_onboarding_value({"command_status": "ok"}),
            '{"command_status": "ok"}',
        )

    def test_build_diagnostics_field_values_maps_bundle_path(self) -> None:
        values = build_diagnostics_field_values(
            command_payload(bundle_path="/tmp/wbp-diag")
        )
        self.assertEqual(set(values.keys()), set(DIAGNOSTICS_RESULT_FIELDS))
        self.assertEqual(values["bundle_path"], "/tmp/wbp-diag")


class UiDispatchTests(unittest.TestCase):
    def test_run_validate_action_delegates_to_account_check_alias(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._run_account_check_action = mock.Mock()

        shell.run_validate_action()

        shell._run_account_check_action.assert_called_once_with("Validate")

    def test_run_recheck_action_delegates_to_account_check_alias(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._run_account_check_action = mock.Mock()

        shell.run_recheck_action()

        shell._run_account_check_action.assert_called_once_with("Recheck")

    def test_account_mutation_action_without_selection_shows_info(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell._selected_account_id = mock.Mock(return_value=None)
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.showinfo") as showinfo_mock:
            shell._run_account_mutation_action(
                "Promote",
                "Promote selected reserve account into active routing?",
                "promote",
            )

        showinfo_mock.assert_called_once()
        shell.set_busy.assert_not_called()

    def test_account_mutation_action_declines_without_starting_thread(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell._selected_account_id = mock.Mock(return_value="backend-a")
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=False):
            with mock.patch("wild_boar_proxy.ui_shell.threading.Thread") as thread_mock:
                shell._run_account_mutation_action(
                    "Hold",
                    "Place selected account on hold and isolate it from active routing?",
                    "hold",
                )

        thread_mock.assert_not_called()
        shell.set_busy.assert_not_called()

    def test_account_check_action_starts_without_confirmation_gate(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell._selected_account_id = mock.Mock(return_value="backend-a")
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        thread_instance = mock.Mock()
        with mock.patch("wild_boar_proxy.ui_shell.threading.Thread", return_value=thread_instance) as thread_mock:
            with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", side_effect=AssertionError("unexpected confirmation")):
                shell._run_account_check_action("Validate")

        shell.set_busy.assert_called_once_with(True)
        shell.banner_var.set.assert_called_once_with("Running validate...")
        thread_mock.assert_called_once()
        thread_instance.start.assert_called_once_with()

    def test_run_promote_action_maps_to_generic_mutation_handler(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._run_account_mutation_action = mock.Mock()

        shell.run_promote_action()

        shell._run_account_mutation_action.assert_called_once_with(
            "Promote",
            "Promote selected reserve account into active routing?",
            "promote",
        )

    def test_run_mode_action_requires_confirmation(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=False):
            with mock.patch("wild_boar_proxy.ui_shell.threading.Thread") as thread_mock:
                shell.run_mode_action(
                    "Switch desired mode to stable?",
                    ("mode", "set", "stable", "--json"),
                )

        thread_mock.assert_not_called()
        shell.set_busy.assert_not_called()

    def test_run_mode_action_starts_worker_after_confirmation(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        thread_instance = mock.Mock()
        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=True):
            with mock.patch(
                "wild_boar_proxy.ui_shell.threading.Thread",
                return_value=thread_instance,
            ) as thread_mock:
                shell.run_mode_action(
                    "Switch desired mode to managed?",
                    ("mode", "set", "managed", "--json"),
                )

        shell.set_busy.assert_called_once_with(True)
        shell.banner_var.set.assert_called_once_with("Running operator action...")
        thread_mock.assert_called_once()
        kwargs = thread_mock.call_args.kwargs
        self.assertEqual(kwargs["target"], shell._action_worker)
        self.assertEqual(kwargs["args"], (("mode", "set", "managed", "--json"),))
        thread_instance.start.assert_called_once_with()

    def test_run_demote_action_maps_to_generic_mutation_handler(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._run_account_mutation_action = mock.Mock()

        shell.run_demote_action()

        shell._run_account_mutation_action.assert_called_once_with(
            "Demote",
            "Demote selected active account back to reserve?",
            "demote",
        )

    def test_run_hold_action_maps_to_generic_mutation_handler(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._run_account_mutation_action = mock.Mock()

        shell.run_hold_action()

        shell._run_account_mutation_action.assert_called_once_with(
            "Hold",
            "Place selected account on hold and isolate it from active routing?",
            "hold",
        )

    def test_run_release_action_maps_to_generic_mutation_handler(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._run_account_mutation_action = mock.Mock()

        shell.run_release_action()

        shell._run_account_mutation_action.assert_called_once_with(
            "Release",
            "Release selected held account back to reserve semantics?",
            "release",
        )

    def test_run_retire_action_maps_to_generic_mutation_handler(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._run_account_mutation_action = mock.Mock()

        shell.run_retire_action()

        shell._run_account_mutation_action.assert_called_once_with(
            "Retire",
            "Retire selected account with terminal no-return semantics?",
            "retire",
        )

    def test_no_restore_or_reactivate_affordance_is_exposed(self) -> None:
        self.assertFalse(hasattr(MinimalCompanionShell, "run_restore_action"))
        self.assertFalse(hasattr(MinimalCompanionShell, "run_reactivate_action"))

    def test_run_onboard_action_requires_confirmation(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=False):
            with mock.patch("wild_boar_proxy.ui_shell.threading.Thread") as thread_mock:
                shell.run_onboard_action()

        thread_mock.assert_not_called()
        shell.set_busy.assert_not_called()

    def test_run_onboard_action_wires_bounded_command(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        thread_instance = mock.Mock()
        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=True):
            with mock.patch(
                "wild_boar_proxy.ui_shell.threading.Thread",
                return_value=thread_instance,
            ) as thread_mock:
                shell.run_onboard_action()

        thread_mock.assert_called_once()
        kwargs = thread_mock.call_args.kwargs
        self.assertEqual(kwargs["target"], shell._onboard_worker)
        self.assertEqual(
            kwargs["args"][0],
            ("accounts", "onboard", "--json"),
        )
        thread_instance.start.assert_called_once_with()

    def test_run_launch_client_action_requires_path(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.launch_client_path_var = mock.Mock()
        shell.launch_client_path_var.get.return_value = "   "
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.showinfo") as showinfo_mock:
            with mock.patch("wild_boar_proxy.ui_shell.threading.Thread") as thread_mock:
                shell.run_launch_client_action()

        showinfo_mock.assert_called_once()
        thread_mock.assert_not_called()
        shell.set_busy.assert_not_called()

    def test_run_launch_client_action_requires_absolute_path(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.launch_client_path_var = mock.Mock()
        shell.launch_client_path_var.get.return_value = "Signal.app"
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.showinfo") as showinfo_mock:
            with mock.patch("wild_boar_proxy.ui_shell.threading.Thread") as thread_mock:
                shell.run_launch_client_action()

        showinfo_mock.assert_called_once()
        thread_mock.assert_not_called()
        shell.set_busy.assert_not_called()

    def test_run_launch_client_action_requires_confirmation(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.launch_client_path_var = mock.Mock()
        shell.launch_client_path_var.get.return_value = "/Applications/Signal.app/Contents/MacOS/Signal"
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=False):
            with mock.patch("wild_boar_proxy.ui_shell.threading.Thread") as thread_mock:
                shell.run_launch_client_action()

        thread_mock.assert_not_called()
        shell.set_busy.assert_not_called()

    def test_run_launch_client_action_wires_command(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.launch_client_path_var = mock.Mock()
        shell.launch_client_path_var.get.return_value = "/Applications/Signal.app/Contents/MacOS/Signal"
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        thread_instance = mock.Mock()
        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=True):
            with mock.patch(
                "wild_boar_proxy.ui_shell.threading.Thread",
                return_value=thread_instance,
            ) as thread_mock:
                shell.run_launch_client_action()

        thread_mock.assert_called_once()
        kwargs = thread_mock.call_args.kwargs
        self.assertEqual(kwargs["target"], shell._launch_client_worker)
        self.assertEqual(
            kwargs["args"][0],
            (
                "launch",
                "client",
                "--client-path",
                "/Applications/Signal.app/Contents/MacOS/Signal",
                "--json",
            ),
        )
        thread_instance.start.assert_called_once_with()

    def test_run_external_profile_action_requires_route(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.external_route_var = mock.Mock()
        shell.external_route_var.get.return_value = "   "
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.showinfo") as showinfo_mock:
            with mock.patch("wild_boar_proxy.ui_shell.threading.Thread") as thread_mock:
                shell.run_external_profile_action()

        showinfo_mock.assert_called_once()
        thread_mock.assert_not_called()
        shell.set_busy.assert_not_called()

    def test_run_external_profile_action_requires_confirmation(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.external_route_var = mock.Mock()
        shell.external_route_var.get.return_value = "wbp-deepseek-v3"
        shell._external_models_snapshot = mock.Mock(routes=[mock.Mock(route_id="wbp-deepseek-v3")])
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=False):
            with mock.patch("wild_boar_proxy.ui_shell.threading.Thread") as thread_mock:
                shell.run_external_profile_action()

        thread_mock.assert_not_called()
        shell.set_busy.assert_not_called()

    def test_run_external_profile_action_wires_selected_route(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.external_route_var = mock.Mock()
        shell.external_route_var.get.return_value = "wbp-deepseek-v3"
        shell._external_models_snapshot = mock.Mock(routes=[mock.Mock(route_id="wbp-deepseek-v3")])
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        thread_instance = mock.Mock()
        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=True):
            with mock.patch(
                "wild_boar_proxy.ui_shell.threading.Thread",
                return_value=thread_instance,
            ) as thread_mock:
                shell.run_external_profile_action()

        thread_mock.assert_called_once()
        kwargs = thread_mock.call_args.kwargs
        self.assertEqual(kwargs["target"], shell._external_profile_worker)
        self.assertEqual(kwargs["args"], ("wbp-deepseek-v3",))
        thread_instance.start.assert_called_once_with()

    def test_run_external_profile_action_rejects_route_outside_snapshot(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.external_route_var = mock.Mock()
        shell.external_route_var.get.return_value = "wbp-deepseek-v3"
        shell._external_models_snapshot = mock.Mock(routes=[mock.Mock(route_id="wbp-other")])
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.showinfo") as showinfo_mock:
            with mock.patch("wild_boar_proxy.ui_shell.threading.Thread") as thread_mock:
                shell.run_external_profile_action()

        showinfo_mock.assert_called_once()
        thread_mock.assert_not_called()
        shell.set_busy.assert_not_called()

    def test_run_external_check_action_requires_secret_ready_route(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell._external_models_snapshot = build_external_models_snapshot(
            status_payload=external_status_payload(),
            models_payload=external_models_payload(),
            routes_payload=external_routes_payload(),
        )
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.showinfo") as showinfo_mock:
            with mock.patch("wild_boar_proxy.ui_shell.threading.Thread") as thread_mock:
                shell.run_external_check_action()

        showinfo_mock.assert_called_once()
        thread_mock.assert_not_called()
        shell.set_busy.assert_not_called()

    def test_run_external_check_action_wires_selected_route(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell._external_models_snapshot = build_external_models_snapshot(
            status_payload=external_status_payload(
                data={
                    **external_status_payload()["data"],
                    "local_auth": {
                        "token_ref": "managed_local_token",
                        "token_present": True,
                        "token_created_at_utc": None,
                    },
                }
            ),
            models_payload=external_models_payload(),
            routes_payload=external_routes_payload(),
        )
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        thread_instance = mock.Mock()
        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=True):
            with mock.patch(
                "wild_boar_proxy.ui_shell.threading.Thread",
                return_value=thread_instance,
            ) as thread_mock:
                shell.run_external_check_action()

        kwargs = thread_mock.call_args.kwargs
        self.assertEqual(kwargs["target"], shell._external_check_worker)
        self.assertEqual(kwargs["args"], ("wbp-deepseek-v3",))
        thread_instance.start.assert_called_once_with()

    def test_run_quick_start_check_all_action_requires_confirmation(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=False):
            with mock.patch("wild_boar_proxy.ui_shell.threading.Thread") as thread_mock:
                shell.run_quick_start_check_all_action()

        thread_mock.assert_not_called()
        shell.set_busy.assert_not_called()

    def test_apply_quick_start_summary_reflects_ready_continuity_truth(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.quick_start_source_var = mock.Mock()
        shell.quick_start_account_status_var = mock.Mock()
        shell.quick_start_account_note_var = mock.Mock()
        shell.quick_start_api_status_var = mock.Mock()
        shell.quick_start_api_note_var = mock.Mock()
        shell.quick_start_route_label_var = mock.Mock()
        shell.quick_start_route_provider_var = mock.Mock()
        shell.quick_start_route_secret_ref_var = mock.Mock()
        shell.quick_start_route_last_checked_var = mock.Mock()
        shell.quick_start_route_validation_var = mock.Mock()
        shell.quick_start_onboard_reason_var = mock.Mock()
        shell.quick_start_api_reason_var = mock.Mock()
        shell.quick_start_check_all_reason_var = mock.Mock()
        shell._last_account_snapshot = build_account_pool_snapshot(
            accounts_payload(
                accounts=[
                    {
                        "id": "backend-1",
                        "label": "backend-1",
                        "pool": "active",
                        "status": "healthy",
                        "manual_hold": False,
                        "auth_ref": "/tmp/backend-1.json",
                        "fail_count": 0,
                        "success_count": 1,
                        "last_success": "2026-05-21T00:00:00Z",
                        "last_error": "",
                        "cooldown_until": None,
                        "notes": "",
                    }
                ],
                pool_policy={"active_min": 1, "active_target": 1, "reserve_target": 0},
                stable_default_backend_id="backend-1",
            )
        )
        shell._external_models_snapshot = build_external_models_snapshot(
            status_payload=external_status_payload(
                data={
                    **external_status_payload()["data"],
                    "local_auth": {
                        "token_ref": "managed_local_token",
                        "token_present": True,
                        "token_created_at_utc": None,
                    },
                    "observed_routes": {
                        "wbp-deepseek-v3": {
                            "availability_state": "verified",
                            "last_check": "2026-05-21T00:00:00Z",
                        }
                    },
                }
            ),
            models_payload=external_models_payload(),
            routes_payload=external_routes_payload(),
        )

        shell._apply_quick_start_summary()

        shell.quick_start_source_var.set.assert_called_once_with("live_sandbox")
        shell.quick_start_account_status_var.set.assert_called_once_with("ok")
        shell.quick_start_api_status_var.set.assert_called_once_with("enabled")
        shell.quick_start_route_label_var.set.assert_called_once_with("DeepSeek V3")
        shell.quick_start_route_provider_var.set.assert_called_once_with("openrouter")
        shell.quick_start_route_secret_ref_var.set.assert_called_once_with(
            "OPENROUTER_API_KEY"
        )
        shell.quick_start_route_last_checked_var.set.assert_called_once_with(
            "2026-05-21T00:00:00Z"
        )
        shell.quick_start_route_validation_var.set.assert_called_once_with("ok")
        shell.quick_start_api_reason_var.set.assert_called_once_with("")
        shell.quick_start_check_all_reason_var.set.assert_called_once_with("")

    def test_apply_quick_start_check_all_results_records_ledger_and_bundle_surface(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.quick_start_check_all_status_var = mock.Mock()
        shell.quick_start_check_all_machine_error_var = mock.Mock()
        shell.quick_start_check_all_next_action_var = mock.Mock()
        shell.quick_start_check_all_verdict_var = mock.Mock()
        shell.quick_start_check_all_message_var = mock.Mock()
        shell._record_quick_start_ledger_entry = mock.Mock()
        shell._apply_refresh_results = mock.Mock()
        runtime_snapshot = build_runtime_snapshot(
            status_payload=status_payload(),
            mode_payload=mode_payload(),
        )
        account_snapshot = build_account_pool_snapshot(accounts_payload())
        external_snapshot = build_external_models_snapshot(
            status_payload=external_status_payload(
                data={
                    **external_status_payload()["data"],
                    "local_auth": {
                        "token_ref": "managed_local_token",
                        "token_present": True,
                        "token_created_at_utc": None,
                    },
                }
            ),
            models_payload=external_models_payload(),
            routes_payload=external_routes_payload(),
        )
        payload = build_quick_start_check_all_payload(
            runtime_snapshot=runtime_snapshot,
            account_snapshot=account_snapshot,
            external_snapshot=external_snapshot,
            api_check_payload=external_check_payload(),
        )

        shell._apply_quick_start_check_all_results(
            payload,
            runtime_snapshot,
            account_snapshot,
            external_snapshot,
            banner="Quick Start check-all completed.",
        )

        shell.quick_start_check_all_status_var.set.assert_called_once_with(
            payload["status"]
        )
        shell.quick_start_check_all_machine_error_var.set.assert_called_once_with(
            payload["machine_error_code"]
        )
        shell.quick_start_check_all_next_action_var.set.assert_called_once_with(
            payload["next_action"]
        )
        shell.quick_start_check_all_verdict_var.set.assert_called_once_with(
            payload["data"]["bundle_verdict"]
        )
        shell.quick_start_check_all_message_var.set.assert_called_once_with(
            payload["human_message"]
        )
        shell._record_quick_start_ledger_entry.assert_called_once_with(
            "quick_start_check_all",
            payload,
        )
        shell._apply_refresh_results.assert_called_once_with(
            runtime_snapshot,
            account_snapshot,
            banner="Quick Start check-all completed.",
            external_snapshot=external_snapshot,
        )

    def test_run_smoke_action_requires_confirmation(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=False):
            with mock.patch("wild_boar_proxy.ui_shell.threading.Thread") as thread_mock:
                shell.run_smoke_action()

        thread_mock.assert_not_called()
        shell.set_busy.assert_not_called()

    def test_run_smoke_action_starts_worker_after_confirmation(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        thread_instance = mock.Mock()
        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=True):
            with mock.patch(
                "wild_boar_proxy.ui_shell.threading.Thread",
                return_value=thread_instance,
            ) as thread_mock:
                shell.run_smoke_action()

        thread_mock.assert_called_once()
        kwargs = thread_mock.call_args.kwargs
        self.assertEqual(kwargs["target"], shell._smoke_worker)
        self.assertEqual(kwargs["args"] if "args" in kwargs else (), ())
        thread_instance.start.assert_called_once_with()

    def test_run_diagnostics_action_requires_confirmation(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=False):
            with mock.patch("wild_boar_proxy.ui_shell.threading.Thread") as thread_mock:
                shell.run_diagnostics_action()

        thread_mock.assert_not_called()
        shell.set_busy.assert_not_called()

    def test_run_diagnostics_action_starts_worker_after_confirmation(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        thread_instance = mock.Mock()
        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=True):
            with mock.patch(
                "wild_boar_proxy.ui_shell.threading.Thread",
                return_value=thread_instance,
            ) as thread_mock:
                shell.run_diagnostics_action()

        thread_mock.assert_called_once()
        kwargs = thread_mock.call_args.kwargs
        self.assertEqual(kwargs["target"], shell._diagnostics_worker)
        self.assertEqual(kwargs["args"] if "args" in kwargs else (), ())
        thread_instance.start.assert_called_once_with()

    def test_run_stable_repair_action_requires_confirmation(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=False):
            with mock.patch("wild_boar_proxy.ui_shell.threading.Thread") as thread_mock:
                shell.run_stable_repair_action()

        thread_mock.assert_not_called()
        shell.set_busy.assert_not_called()

    def test_run_stable_repair_action_starts_worker_after_confirmation(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell._busy = False
        shell.root = object()
        shell.set_busy = mock.Mock()
        shell.banner_var = mock.Mock()

        thread_instance = mock.Mock()
        with mock.patch("wild_boar_proxy.ui_shell.messagebox.askyesno", return_value=True):
            with mock.patch(
                "wild_boar_proxy.ui_shell.threading.Thread",
                return_value=thread_instance,
            ) as thread_mock:
                shell.run_stable_repair_action()

        shell.set_busy.assert_called_once_with(True)
        shell.banner_var.set.assert_called_once_with("Running stable repair...")
        thread_mock.assert_called_once()
        kwargs = thread_mock.call_args.kwargs
        self.assertEqual(kwargs["target"], shell._stable_repair_worker)
        self.assertEqual(kwargs["args"] if "args" in kwargs else (), ())
        thread_instance.start.assert_called_once_with()

    def test_apply_smoke_payload_blanks_fields_for_malformed_nested_surface(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.smoke_command_status_var = mock.Mock()
        shell.smoke_command_exit_code_var = mock.Mock()
        shell.smoke_command_human_message_var = mock.Mock()
        shell.smoke_command_machine_error_var = mock.Mock()
        shell.smoke_command_changed_files_var = mock.Mock()
        shell.smoke_command_next_action_var = mock.Mock()
        shell.smoke_rendered_state_var = mock.Mock()
        shell.smoke_field_vars = {
            field: mock.Mock() for field in SMOKE_RESULT_FIELDS
        }

        shell._apply_smoke_payload(smoke_payload(stable_runtime_consumer="broken"))

        shell.smoke_command_status_var.set.assert_called_once_with("ok")
        for field in SMOKE_RESULT_FIELDS:
            shell.smoke_field_vars[field].set.assert_called_once_with("")
        shell.smoke_rendered_state_var.set.assert_called_once_with("integration_failure")

    def test_apply_smoke_payload_failure_not_rendered_as_success(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.smoke_command_status_var = mock.Mock()
        shell.smoke_command_exit_code_var = mock.Mock()
        shell.smoke_command_human_message_var = mock.Mock()
        shell.smoke_command_machine_error_var = mock.Mock()
        shell.smoke_command_changed_files_var = mock.Mock()
        shell.smoke_command_next_action_var = mock.Mock()
        shell.smoke_rendered_state_var = mock.Mock()
        shell.smoke_field_vars = {
            field: mock.Mock() for field in SMOKE_RESULT_FIELDS
        }

        shell._apply_smoke_payload(
            smoke_payload(
                status="error",
                machine_error_code="MANAGED_RUNTIME_PRECONDITION_FAILED",
            )
        )

        shell.smoke_rendered_state_var.set.assert_called_once_with("failure")

    def test_apply_diagnostics_payload_maps_command_and_bundle_path(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.diagnostics_command_status_var = mock.Mock()
        shell.diagnostics_command_exit_code_var = mock.Mock()
        shell.diagnostics_command_human_message_var = mock.Mock()
        shell.diagnostics_command_machine_error_var = mock.Mock()
        shell.diagnostics_command_changed_files_var = mock.Mock()
        shell.diagnostics_command_next_action_var = mock.Mock()
        shell.diagnostics_field_vars = {
            field: mock.Mock() for field in DIAGNOSTICS_RESULT_FIELDS
        }

        shell._apply_diagnostics_payload(
            command_payload(
                human_message="Diagnostics bundle exported.",
                changed_files=["/tmp/wbp-diag"],
                bundle_path="/tmp/wbp-diag",
            )
        )

        shell.diagnostics_command_status_var.set.assert_called_once_with("ok")
        shell.diagnostics_command_exit_code_var.set.assert_called_once_with("0")
        shell.diagnostics_command_human_message_var.set.assert_called_once_with(
            "Diagnostics bundle exported."
        )
        shell.diagnostics_command_machine_error_var.set.assert_called_once_with("OK")
        shell.diagnostics_command_changed_files_var.set.assert_called_once_with(
            '["/tmp/wbp-diag"]'
        )
        shell.diagnostics_command_next_action_var.set.assert_called_once_with("none")
        shell.diagnostics_field_vars["bundle_path"].set.assert_called_once_with(
            "/tmp/wbp-diag"
        )

    def test_apply_stable_repair_payload_maps_command_fields(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.stable_repair_command_status_var = mock.Mock()
        shell.stable_repair_command_exit_code_var = mock.Mock()
        shell.stable_repair_command_human_message_var = mock.Mock()
        shell.stable_repair_command_machine_error_var = mock.Mock()
        shell.stable_repair_command_changed_files_var = mock.Mock()
        shell.stable_repair_command_next_action_var = mock.Mock()

        shell._apply_stable_repair_payload(
            command_payload(
                human_message="Stable repair applied.",
                changed_files=["/tmp/config.yaml"],
            )
        )

        shell.stable_repair_command_status_var.set.assert_called_once_with("ok")
        shell.stable_repair_command_exit_code_var.set.assert_called_once_with("0")
        shell.stable_repair_command_human_message_var.set.assert_called_once_with(
            "Stable repair applied."
        )
        shell.stable_repair_command_machine_error_var.set.assert_called_once_with("OK")
        shell.stable_repair_command_changed_files_var.set.assert_called_once_with(
            "[\"/tmp/config.yaml\"]"
        )
        shell.stable_repair_command_next_action_var.set.assert_called_once_with("none")

    def test_stable_repair_worker_keeps_action_payload_when_refresh_fails(self) -> None:
        class BrokenRefreshRunner:
            def run(self, *args: str):
                if args == ("stable", "repair", "--apply", "--json"):
                    return type(
                        "Result",
                        (),
                        {
                            "payload": command_payload(
                                human_message="Stable repair applied."
                            ),
                            "stderr": "",
                        },
                    )()
                if args == ("accounts", "list", "--json"):
                    return type(
                        "Result",
                        (),
                        {"payload": accounts_payload(), "stderr": ""},
                    )()
                if args == ("status", "--json"):
                    return type(
                        "Result",
                        (),
                        {"payload": command_payload(status="ok"), "stderr": ""},
                    )()
                if args == ("mode", "get", "--json"):
                    return type(
                        "Result",
                        (),
                        {"payload": mode_payload(), "stderr": ""},
                    )()
                raise AssertionError(f"unexpected command: {args}")

        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.runner = BrokenRefreshRunner()
        shell.root = mock.Mock()
        shell.root.after = mock.Mock(side_effect=lambda _delay, cb: cb())
        shell._apply_stable_repair_results = mock.Mock()

        shell._stable_repair_worker()

        shell._apply_stable_repair_results.assert_called_once()
        action_payload = shell._apply_stable_repair_results.call_args.args[0]
        self.assertEqual(action_payload["status"], "integration_failure")
        self.assertEqual(action_payload["machine_error_code"], "UI_INTEGRATION_FAILURE")

    def test_smoke_worker_keeps_action_payload_when_status_refresh_fails(self) -> None:
        class BrokenStatusRunner:
            def run(self, *args: str):
                if args == ("launch", "smoke", "--json"):
                    return type(
                        "Result",
                        (),
                        {"payload": smoke_payload(human_message="Smoke executed."), "stderr": ""},
                    )()
                if args == ("status", "--json"):
                    return type("Result", (), {"payload": command_payload(status="ok"), "stderr": ""})()
                raise AssertionError(f"unexpected command: {args}")

        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.runner = BrokenStatusRunner()
        shell.root = mock.Mock()
        shell.root.after = mock.Mock(side_effect=lambda _delay, cb: cb())
        shell._apply_smoke_results = mock.Mock()

        shell._smoke_worker()

        shell._apply_smoke_results.assert_called_once()
        action_payload = shell._apply_smoke_results.call_args.args[0]
        self.assertEqual(action_payload["status"], "ok")

    def test_refresh_worker_turns_capacity_count_mismatch_into_integration_failure(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.runner = FakeRunner(
            {
                ("status", "--json"): status_payload(
                    pool_summary={
                        "active": 2,
                        "reserve": 0,
                        "retired": 0,
                        "healthy": 2,
                        "degraded": 0,
                        "down": 0,
                    }
                ),
                ("mode", "get", "--json"): mode_payload(),
                ("accounts", "list", "--json"): accounts_payload(),
                ("external-models", "status", "--json"): external_status_payload(),
                ("external-models", "models", "--json"): external_models_payload(),
                ("external-models", "routes", "list", "--json"): external_routes_payload(),
            }
        )
        shell.root = mock.Mock()
        shell.root.after = mock.Mock(side_effect=lambda _delay, cb: cb())
        shell._apply_refresh_results = mock.Mock()

        shell._refresh_worker()

        shell._apply_refresh_results.assert_called_once()
        runtime_snapshot, account_snapshot = shell._apply_refresh_results.call_args.args
        self.assertEqual(runtime_snapshot.overall_state, "integration_failure")
        self.assertEqual(account_snapshot.machine_error_code, "UI_INTEGRATION_FAILURE")
        self.assertIn("status pool_summary and accounts list disagree", runtime_snapshot.integration_error)
        self.assertIn("status pool_summary and accounts list disagree", account_snapshot.integration_error)

    def test_action_worker_turns_capacity_count_mismatch_into_integration_failure(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.runner = FakeRunner(
            {
                ("mode", "set", "stable", "--json"): command_payload(
                    human_message="Desired mode set to stable.",
                    desired_mode="stable",
                    effective_mode="managed",
                ),
                ("status", "--json"): status_payload(
                    desired_mode="stable",
                    effective_mode="managed",
                    pool_summary={
                        "active": 0,
                        "reserve": 2,
                        "retired": 0,
                        "healthy": 2,
                        "degraded": 0,
                        "down": 0,
                    },
                ),
                ("mode", "get", "--json"): mode_payload(
                    desired_mode="stable",
                    effective_mode="managed",
                ),
                ("accounts", "list", "--json"): accounts_payload(),
            }
        )
        shell.root = mock.Mock()
        shell.root.after = mock.Mock(side_effect=lambda _delay, cb: cb())
        shell._apply_refresh_results = mock.Mock()

        shell._action_worker(("mode", "set", "stable", "--json"))

        shell._apply_refresh_results.assert_called_once()
        runtime_snapshot, account_snapshot = shell._apply_refresh_results.call_args.args
        self.assertEqual(runtime_snapshot.overall_state, "integration_failure")
        self.assertEqual(account_snapshot.machine_error_code, "UI_INTEGRATION_FAILURE")
        self.assertEqual(
            shell._apply_refresh_results.call_args.kwargs["banner"],
            "Operator action failed.",
        )

    def test_apply_launch_payload_blanks_fields_for_malformed_nested_surface(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.launch_command_status_var = mock.Mock()
        shell.launch_command_exit_code_var = mock.Mock()
        shell.launch_command_human_message_var = mock.Mock()
        shell.launch_command_machine_error_var = mock.Mock()
        shell.launch_command_changed_files_var = mock.Mock()
        shell.launch_command_next_action_var = mock.Mock()
        shell.launch_rendered_state_var = mock.Mock()
        shell.launch_field_vars = {
            field: mock.Mock() for field in CLIENT_LAUNCH_RESULT_FIELDS
        }

        shell._apply_launch_client_payload(launch_payload(client_launch_result="broken"))

        shell.launch_command_status_var.set.assert_called_once_with("ok")
        for field in CLIENT_LAUNCH_RESULT_FIELDS:
            shell.launch_field_vars[field].set.assert_called_once_with("")

    def test_apply_external_profile_payload_maps_command_and_profile_fields(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.external_profile_command_status_var = mock.Mock()
        shell.external_profile_command_exit_code_var = mock.Mock()
        shell.external_profile_command_human_message_var = mock.Mock()
        shell.external_profile_command_machine_error_var = mock.Mock()
        shell.external_profile_command_changed_files_var = mock.Mock()
        shell.external_profile_command_next_action_var = mock.Mock()
        shell.external_profile_rendered_state_var = mock.Mock()
        shell.external_profile_field_vars = {
            field: mock.Mock() for field in EXTERNAL_PROFILE_FIELDS
        }

        shell._apply_external_profile_payload(external_profile_payload())

        shell.external_profile_command_status_var.set.assert_called_once_with("ok")
        shell.external_profile_command_exit_code_var.set.assert_called_once_with("0")
        shell.external_profile_field_vars["profile_kind"].set.assert_called_once_with(
            "codex_desktop_openai_compatible"
        )
        shell.external_profile_field_vars["writes_external_config"].set.assert_called_once_with(
            "false"
        )
        shell.external_profile_rendered_state_var.set.assert_called_once_with(
            "profile_packet_only"
        )

    def test_apply_onboarding_payload_blanks_fields_for_malformed_surface(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.onboarding_command_status_var = mock.Mock()
        shell.onboarding_machine_error_var = mock.Mock()
        shell.onboarding_next_action_var = mock.Mock()
        shell.onboarding_field_vars = {
            field: mock.Mock() for field in ONBOARDING_RESULT_FIELDS
        }

        shell._apply_onboarding_payload(command_payload(onboarding_result="broken"))

        shell.onboarding_command_status_var.set.assert_called_once_with("ok")
        for field in ONBOARDING_RESULT_FIELDS:
            shell.onboarding_field_vars[field].set.assert_called_once_with("")

    def test_apply_launch_client_payload_marks_malformed_surface_as_integration_failure(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.launch_command_status_var = mock.Mock()
        shell.launch_command_exit_code_var = mock.Mock()
        shell.launch_command_human_message_var = mock.Mock()
        shell.launch_command_machine_error_var = mock.Mock()
        shell.launch_command_changed_files_var = mock.Mock()
        shell.launch_command_next_action_var = mock.Mock()
        shell.launch_rendered_state_var = mock.Mock()
        shell.launch_field_vars = {
            field: mock.Mock() for field in CLIENT_LAUNCH_RESULT_FIELDS
        }

        shell._apply_launch_client_payload(launch_payload(client_launch_result="broken"))

        shell.launch_rendered_state_var.set.assert_called_once_with("integration_failure")

    def test_apply_launch_client_payload_marks_precondition_failure(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.launch_command_status_var = mock.Mock()
        shell.launch_command_exit_code_var = mock.Mock()
        shell.launch_command_human_message_var = mock.Mock()
        shell.launch_command_machine_error_var = mock.Mock()
        shell.launch_command_changed_files_var = mock.Mock()
        shell.launch_command_next_action_var = mock.Mock()
        shell.launch_rendered_state_var = mock.Mock()
        shell.launch_field_vars = {
            field: mock.Mock() for field in CLIENT_LAUNCH_RESULT_FIELDS
        }

        shell._apply_launch_client_payload(
            launch_payload(
                status="error",
                machine_error_code="CLIENT_LAUNCH_RUNTIME_PRECONDITION_FAILED",
                client_launch_result={
                    "runtime_precondition_status": "failed",
                    "final_outcome": "runtime_precondition_failed",
                },
            )
        )

        shell.launch_rendered_state_var.set.assert_called_once_with("failure")

    def test_apply_launch_client_payload_marks_top_level_integration_failure(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.launch_command_status_var = mock.Mock()
        shell.launch_command_exit_code_var = mock.Mock()
        shell.launch_command_human_message_var = mock.Mock()
        shell.launch_command_machine_error_var = mock.Mock()
        shell.launch_command_changed_files_var = mock.Mock()
        shell.launch_command_next_action_var = mock.Mock()
        shell.launch_rendered_state_var = mock.Mock()
        shell.launch_field_vars = {
            field: mock.Mock() for field in CLIENT_LAUNCH_RESULT_FIELDS
        }

        shell._apply_launch_client_payload(
            command_payload(
                status="integration_failure",
                machine_error_code="UI_INTEGRATION_FAILURE",
            )
        )

        shell.launch_rendered_state_var.set.assert_called_once_with("integration_failure")

    def test_external_profile_worker_keeps_packet_and_refresh_truth(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.runner = FakeRunner(
            {
                (
                    "external-models",
                    "profile",
                    "codex-desktop",
                    "--route",
                    "wbp-deepseek-v3",
                    "--json",
                ): external_profile_payload(),
                ("external-models", "status", "--json"): external_status_payload(),
                ("external-models", "models", "--json"): external_models_payload(),
                ("external-models", "routes", "list", "--json"): external_routes_payload(),
            }
        )
        shell.root = mock.Mock()
        shell.root.after = mock.Mock(side_effect=lambda _delay, cb: cb())
        shell._apply_external_profile_results = mock.Mock()

        shell._external_profile_worker("wbp-deepseek-v3")

        shell._apply_external_profile_results.assert_called_once()
        action_payload, external_snapshot = shell._apply_external_profile_results.call_args.args
        self.assertEqual(action_payload["status"], "ok")
        self.assertEqual(external_snapshot.routes[0].route_id, "wbp-deepseek-v3")

    def test_apply_onboarding_payload_keeps_reserve_first_and_skipped_sync_visible(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.onboarding_command_status_var = mock.Mock()
        shell.onboarding_machine_error_var = mock.Mock()
        shell.onboarding_next_action_var = mock.Mock()
        shell.onboarding_field_vars = {
            field: mock.Mock() for field in ONBOARDING_RESULT_FIELDS
        }

        shell._apply_onboarding_payload(
            command_payload(
                onboarding_result={
                    "reserve_first_enforced": True,
                    "auth_snapshot_before_login_status": "ok",
                    "auth_snapshot_before_login_count": 0,
                    "auth_snapshot_before_login_digest": "digest",
                    "auth_snapshot_before_login_source": {"source": "stable_config_parent"},
                    "sync_outcome": "skipped_by_flag",
                    "status_observed": {"command_status": "ok"},
                    "active_routing_changed": False,
                    "final_outcome": "explicit_auth_imported_to_reserve",
                }
            )
        )

        shell.onboarding_field_vars["reserve_first_enforced"].set.assert_called_with("true")
        shell.onboarding_field_vars["auth_snapshot_before_login_status"].set.assert_called_with("ok")
        shell.onboarding_field_vars["auth_snapshot_before_login_count"].set.assert_called_with("0")
        shell.onboarding_field_vars["auth_snapshot_before_login_digest"].set.assert_called_with("digest")
        shell.onboarding_field_vars["auth_snapshot_before_login_source"].set.assert_called_with(
            '{"source": "stable_config_parent"}'
        )
        shell.onboarding_field_vars["sync_outcome"].set.assert_called_with("skipped_by_flag")

    def test_apply_onboarding_payload_displays_status_failure_fields(self) -> None:
        shell = MinimalCompanionShell.__new__(MinimalCompanionShell)
        shell.onboarding_command_status_var = mock.Mock()
        shell.onboarding_machine_error_var = mock.Mock()
        shell.onboarding_next_action_var = mock.Mock()
        shell.onboarding_field_vars = {
            field: mock.Mock() for field in ONBOARDING_RESULT_FIELDS
        }

        shell._apply_onboarding_payload(
            command_payload(
                status="error",
                onboarding_result={
                    "status_observed": None,
                    "active_routing_changed": False,
                    "final_outcome": "status_failed",
                },
            )
        )

        shell.onboarding_command_status_var.set.assert_called_once_with("error")
        shell.onboarding_field_vars["final_outcome"].set.assert_called_with("status_failed")
        shell.onboarding_field_vars["status_observed"].set.assert_called_with("null")


class MainTests(unittest.TestCase):
    def test_run_packaged_continuity_smoke_json_collects_summary_and_ledger(self) -> None:
        class FakeShell:
            def __init__(self) -> None:
                self.quick_start_source_var = FakeVar("")
                self.quick_start_account_status_var = FakeVar("")
                self.quick_start_account_note_var = FakeVar("")
                self.quick_start_api_status_var = FakeVar("")
                self.quick_start_api_note_var = FakeVar("")
                self.quick_start_route_label_var = FakeVar("")
                self.quick_start_route_provider_var = FakeVar("")
                self.quick_start_route_secret_ref_var = FakeVar("")
                self.quick_start_route_validation_var = FakeVar("")
                self.quick_start_route_last_checked_var = FakeVar("")
                self.quick_start_check_all_status_var = FakeVar("")
                self.quick_start_check_all_verdict_var = FakeVar("")
                self.quick_start_check_all_machine_error_var = FakeVar("")
                self.quick_start_check_all_next_action_var = FakeVar("")
                self.quick_start_check_all_message_var = FakeVar("")
                self.liveness_var = FakeVar("")
                self.quick_start_events: list[QuickStartLedgerEntry] = []
                self.quick_start_ledger_tree = object()

            def _apply_refresh_results(
                self,
                runtime_snapshot: object,
                account_snapshot: object,
                *,
                banner: str | None = None,
                external_snapshot: object | None = None,
            ) -> None:
                del banner
                self.quick_start_source_var.set("live_sandbox")
                self.liveness_var.set(getattr(runtime_snapshot, "liveness"))
                self.quick_start_account_status_var.set("ok")
                self.quick_start_account_note_var.set(
                    getattr(account_snapshot, "human_message")
                )
                self.quick_start_api_status_var.set("enabled")
                self.quick_start_api_note_var.set(
                    "Проверочный запрос маршрута зафиксирован bounded packet и refresh truth."
                )
                if external_snapshot is not None:
                    route = external_snapshot.routes[0]
                    observed = external_snapshot.observed_routes[route.route_id]
                    self.quick_start_route_label_var.set(route.display_name)
                    self.quick_start_route_provider_var.set(route.provider)
                    self.quick_start_route_secret_ref_var.set(route.secret_ref)
                    self.quick_start_route_validation_var.set("ok")
                    self.quick_start_route_last_checked_var.set(
                        str(observed.get("last_check", ""))
                    )

            def _apply_quick_start_check_all_results(
                self,
                action_payload: dict[str, object],
                runtime_snapshot: object,
                account_snapshot: object,
                external_snapshot: object,
                *,
                banner: str,
            ) -> None:
                del banner
                self._apply_refresh_results(
                    runtime_snapshot,
                    account_snapshot,
                    external_snapshot=external_snapshot,
                )
                data = action_payload["data"]
                assert isinstance(data, dict)
                self.quick_start_check_all_status_var.set(action_payload["status"])
                self.quick_start_check_all_machine_error_var.set(
                    action_payload["machine_error_code"]
                )
                self.quick_start_check_all_next_action_var.set(
                    action_payload["next_action"]
                )
                self.quick_start_check_all_verdict_var.set(data["bundle_verdict"])
                self.quick_start_check_all_message_var.set(action_payload["human_message"])
                self.quick_start_events.insert(
                    0,
                    QuickStartLedgerEntry(
                        observed_at_utc="2026-05-12T00:00:03Z",
                        action_id="quick_start_check_all",
                        status=str(action_payload["status"]),
                        machine_error_code=str(action_payload["machine_error_code"]),
                        next_action=str(action_payload["next_action"]),
                        human_message=str(action_payload["human_message"]),
                    ),
                )

        runtime_snapshot = build_runtime_snapshot(status_payload=status_payload())
        account_snapshot = build_account_pool_snapshot(accounts_payload())
        external_snapshot = build_external_models_snapshot(
            status_payload=external_status_payload(
                data={
                    "foundation_phase": "C3",
                    "adapter_runtime_available": False,
                    "lifecycle_mode": "synthetic",
                    "adapter_state": "started",
                    "listener_proven": False,
                    "runtime_claim_blocked": True,
                    "profile_ready": False,
                    "routes_count": 1,
                    "observed_routes_count": 1,
                    "observed_routes": {
                        "wbp-deepseek-v3": {
                            "availability_state": "verified",
                            "last_check": "2026-05-12T00:00:01Z",
                        }
                    },
                    "adapter": {
                        "lifecycle_mode": "synthetic",
                        "state": "started",
                        "host": "127.0.0.1",
                        "port": None,
                        "base_url": None,
                        "listener_proven": False,
                        "runtime_claim_blocked": True,
                        "started_at_utc": None,
                        "last_transition": "start",
                    },
                    "local_auth": {
                        "token_ref": "managed_local_token",
                        "token_present": True,
                        "token_created_at_utc": "2026-05-12T00:00:00Z",
                    },
                }
            ),
            models_payload=external_models_payload(),
            routes_payload=external_routes_payload(),
        )
        bundle_payload = build_quick_start_check_all_payload(
            runtime_snapshot=runtime_snapshot,
            account_snapshot=account_snapshot,
            external_snapshot=external_snapshot,
            api_check_payload=None,
        )
        fake_root = mock.Mock()
        fake_shell = FakeShell()

        with (
            mock.patch("wild_boar_proxy.ui_shell.Tk", return_value=fake_root),
            mock.patch("wild_boar_proxy.ui_shell.JsonCommandRunner"),
            mock.patch(
                "wild_boar_proxy.ui_shell.MinimalCompanionShell",
                return_value=fake_shell,
            ),
            mock.patch(
                "wild_boar_proxy.ui_shell.load_runtime_snapshot",
                return_value=runtime_snapshot,
            ),
            mock.patch(
                "wild_boar_proxy.ui_shell.load_account_pool_snapshot",
                return_value=account_snapshot,
            ),
            mock.patch(
                "wild_boar_proxy.ui_shell.load_external_models_snapshot",
                return_value=external_snapshot,
            ),
            mock.patch(
                "wild_boar_proxy.ui_shell.build_quick_start_check_all_payload",
                return_value=bundle_payload,
            ),
        ):
            payload, exit_code = run_packaged_continuity_smoke_json()

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["quick_start_summary"]["source"], "live_sandbox")
        self.assertEqual(payload["quick_start_summary"]["bundle_verdict"], "ready")
        self.assertEqual(payload["quick_start_summary"]["route_label"], "DeepSeek V3")
        self.assertEqual(
            payload["quick_start_summary"]["route_last_checked"],
            "2026-05-12T00:00:01Z",
        )
        self.assertEqual(payload["direct_packets"]["accounts"]["account_count"], 2)
        self.assertEqual(payload["ledger"][0]["action_id"], "quick_start_check_all")
        fake_root.withdraw.assert_called_once_with()
        fake_root.destroy.assert_called_once_with()

    def test_run_packaged_continuity_smoke_json_rejects_partial_bundle(self) -> None:
        class FakeShell:
            def __init__(self) -> None:
                self.quick_start_source_var = FakeVar("")
                self.quick_start_account_status_var = FakeVar("")
                self.quick_start_account_note_var = FakeVar("")
                self.quick_start_api_status_var = FakeVar("")
                self.quick_start_api_note_var = FakeVar("")
                self.quick_start_route_label_var = FakeVar("")
                self.quick_start_route_provider_var = FakeVar("")
                self.quick_start_route_secret_ref_var = FakeVar("")
                self.quick_start_route_validation_var = FakeVar("")
                self.quick_start_route_last_checked_var = FakeVar("")
                self.quick_start_check_all_status_var = FakeVar("")
                self.quick_start_check_all_verdict_var = FakeVar("")
                self.quick_start_check_all_machine_error_var = FakeVar("")
                self.quick_start_check_all_next_action_var = FakeVar("")
                self.quick_start_check_all_message_var = FakeVar("")
                self.liveness_var = FakeVar("")
                self.quick_start_events: list[QuickStartLedgerEntry] = []
                self.quick_start_ledger_tree = object()

            def _apply_refresh_results(
                self,
                runtime_snapshot: object,
                account_snapshot: object,
                *,
                banner: str | None = None,
                external_snapshot: object | None = None,
            ) -> None:
                del banner
                self.quick_start_source_var.set("live_sandbox")
                self.liveness_var.set(getattr(runtime_snapshot, "liveness"))
                self.quick_start_account_status_var.set("ok")
                self.quick_start_account_note_var.set(
                    getattr(account_snapshot, "human_message")
                )
                self.quick_start_api_status_var.set("enabled")
                self.quick_start_api_note_var.set("Needs follow-up.")
                if external_snapshot is not None:
                    route = external_snapshot.routes[0]
                    observed = external_snapshot.observed_routes[route.route_id]
                    self.quick_start_route_label_var.set(route.display_name)
                    self.quick_start_route_provider_var.set(route.provider)
                    self.quick_start_route_secret_ref_var.set(route.secret_ref)
                    self.quick_start_route_validation_var.set("check failed")
                    self.quick_start_route_last_checked_var.set(
                        str(observed.get("last_check", ""))
                    )

            def _apply_quick_start_check_all_results(
                self,
                action_payload: dict[str, object],
                runtime_snapshot: object,
                account_snapshot: object,
                external_snapshot: object,
                *,
                banner: str,
            ) -> None:
                del banner
                self._apply_refresh_results(
                    runtime_snapshot,
                    account_snapshot,
                    external_snapshot=external_snapshot,
                )
                data = action_payload["data"]
                assert isinstance(data, dict)
                self.quick_start_check_all_status_var.set(action_payload["status"])
                self.quick_start_check_all_machine_error_var.set(
                    action_payload["machine_error_code"]
                )
                self.quick_start_check_all_next_action_var.set(
                    action_payload["next_action"]
                )
                self.quick_start_check_all_verdict_var.set(data["bundle_verdict"])
                self.quick_start_check_all_message_var.set(action_payload["human_message"])
                self.quick_start_events.insert(
                    0,
                    QuickStartLedgerEntry(
                        observed_at_utc="2026-05-12T00:00:03Z",
                        action_id="quick_start_check_all",
                        status=str(action_payload["status"]),
                        machine_error_code=str(action_payload["machine_error_code"]),
                        next_action=str(action_payload["next_action"]),
                        human_message=str(action_payload["human_message"]),
                    ),
                )

        runtime_snapshot = build_runtime_snapshot(status_payload=status_payload())
        account_snapshot = build_account_pool_snapshot(accounts_payload())
        external_snapshot = build_external_models_snapshot(
            status_payload=external_status_payload(
                data={
                    "foundation_phase": "C3",
                    "adapter_runtime_available": False,
                    "lifecycle_mode": "synthetic",
                    "adapter_state": "started",
                    "listener_proven": False,
                    "runtime_claim_blocked": True,
                    "profile_ready": False,
                    "routes_count": 1,
                    "observed_routes_count": 1,
                    "observed_routes": {
                        "wbp-deepseek-v3": {
                            "availability_state": "limited",
                            "last_check": "2026-05-12T00:00:01Z",
                        }
                    },
                    "adapter": {
                        "lifecycle_mode": "synthetic",
                        "state": "started",
                        "host": "127.0.0.1",
                        "port": None,
                        "base_url": None,
                        "listener_proven": False,
                        "runtime_claim_blocked": True,
                        "started_at_utc": None,
                        "last_transition": "start",
                    },
                    "local_auth": {
                        "token_ref": "managed_local_token",
                        "token_present": True,
                        "token_created_at_utc": "2026-05-12T00:00:00Z",
                    },
                }
            ),
            models_payload=external_models_payload(),
            routes_payload=external_routes_payload(),
        )

        fake_root = mock.Mock()
        fake_shell = FakeShell()

        with (
            mock.patch("wild_boar_proxy.ui_shell.Tk", return_value=fake_root),
            mock.patch("wild_boar_proxy.ui_shell.JsonCommandRunner"),
            mock.patch(
                "wild_boar_proxy.ui_shell.MinimalCompanionShell",
                return_value=fake_shell,
            ),
            mock.patch(
                "wild_boar_proxy.ui_shell.load_runtime_snapshot",
                return_value=runtime_snapshot,
            ),
            mock.patch(
                "wild_boar_proxy.ui_shell.load_account_pool_snapshot",
                return_value=account_snapshot,
            ),
            mock.patch(
                "wild_boar_proxy.ui_shell.load_external_models_snapshot",
                return_value=external_snapshot,
            ),
        ):
            payload, exit_code = run_packaged_continuity_smoke_json()

        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "PACKAGED_CONTINUITY_INCOMPLETE")
        self.assertIn("bundle_ready", payload["failed_checks"])
        fake_root.withdraw.assert_called_once_with()
        fake_root.destroy.assert_called_once_with()

    @mock.patch("wild_boar_proxy.ui_shell.run_packaged_continuity_smoke_json")
    def test_main_emits_packaged_continuity_smoke_json(
        self,
        smoke_mock: mock.Mock,
    ) -> None:
        smoke_mock.return_value = (
            {"status": "ok", "machine_error_code": "OK", "human_message": "done"},
            0,
        )
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            result = main(["--smoke-packaged-continuity-json"])

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue()), smoke_mock.return_value[0])

    @mock.patch("wild_boar_proxy.ui_shell.MinimalCompanionShell")
    @mock.patch("wild_boar_proxy.ui_shell.Tk")
    def test_main_bootstraps_shell(self, tk_mock: mock.Mock, shell_mock: mock.Mock) -> None:
        root = tk_mock.return_value

        result = main([])

        self.assertEqual(result, 0)
        tk_mock.assert_called_once_with()
        shell_mock.assert_called_once()
        self.assertIsInstance(shell_mock.call_args.args[1], JsonCommandRunner)
        root.mainloop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
