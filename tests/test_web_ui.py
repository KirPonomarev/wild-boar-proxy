# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import http.client
import socket
import threading
import unittest

from wild_boar_proxy.ui_shell import (
    AccountPoolSnapshot,
    AccountRecord,
    CommandResult,
    ExternalActionResult,
    ExternalModelRecord,
    ExternalModelsSnapshot,
    ExternalRouteRecord,
    RuntimeSnapshot,
)
from wild_boar_proxy.web_ui import (
    DashboardState,
    UiEvent,
    WildBoarWebUi,
    apply_action,
    build_handler,
    render_dashboard,
)
from http.server import ThreadingHTTPServer


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def runtime_snapshot() -> RuntimeSnapshot:
    return RuntimeSnapshot(
        overall_state="ok",
        exit_code=0,
        human_message="Runtime status summary is available.",
        next_action="none",
        machine_error_code="OK",
        desired_mode="managed",
        effective_mode="managed",
        endpoint="http://127.0.0.1:8320/v1",
        current_proxy_url="http://127.0.0.1:10808",
        liveness="healthy",
        severity="info",
        operator_action="none",
        active_count=2,
        reserve_count=1,
        retired_count=0,
        healthy_count=2,
        degraded_count=0,
        down_count=1,
        attestation_status="ok",
        attestation_machine_error_code="OK",
        attestation_source="healthcheck --json",
        attestation_observed_at="2026-05-08T00:00:00+00:00",
        last_error="",
        integration_error="",
    )


def account_snapshot() -> AccountPoolSnapshot:
    return AccountPoolSnapshot(
        human_message="Accounts listed.",
        machine_error_code="OK",
        registry_identity_status="ok",
        registry_identity_machine_error_code="OK",
        registry_identity_next_action="none",
        active_count=2,
        reserve_count=1,
        retired_count=0,
        capacity_target=25,
        accounts=(
            AccountRecord(
                backend_id="backend-a",
                label="Backend A",
                pool="active",
                manual_hold=False,
                status="healthy",
                fail_count=0,
                success_count=3,
                last_success="2026-05-08T00:00:00+00:00",
                last_error="",
                cooldown_until="",
                notes="",
            ),
        ),
        integration_error="",
    )


def external_snapshot() -> ExternalModelsSnapshot:
    return ExternalModelsSnapshot(
        foundation_phase="C3",
        adapter_runtime_available=False,
        lifecycle_mode="synthetic",
        adapter_state="stopped",
        listener_proven=False,
        runtime_claim_blocked=True,
        profile_ready=False,
        routes_count=1,
        observed_routes_count=0,
        local_token_present=False,
        models_source="local_routes_registry",
        models=(
            ExternalModelRecord(
                route_id="wbp-deepseek-v3",
                display_name="DeepSeek V3",
                provider="openrouter",
                base_url="http://127.0.0.1:54321/v1",
                endpoint_path="/chat/completions",
                upstream_model="deepseek/deepseek-chat",
                compatibility="openai_chat_completions",
                cost_class="paid_or_free_limited",
                enabled=True,
                lane_role="candidate",
                fallback_eligible=False,
                synthetic_adapter_state="stopped",
                profile_ready=False,
            ),
        ),
        routes=(
            ExternalRouteRecord(
                route_id="wbp-deepseek-v3",
                display_name="DeepSeek V3",
                provider="openrouter",
                base_url="http://127.0.0.1:54321/v1",
                endpoint_path="/chat/completions",
                upstream_model="deepseek/deepseek-chat",
                compatibility="openai_chat_completions",
                cost_class="paid_or_free_limited",
                enabled=True,
                lane_role="candidate",
                fallback_eligible=False,
                auth_type="bearer",
                secret_ref="OPENROUTER_API_KEY",
            ),
        ),
        integration_error="",
    )


def external_action() -> ExternalActionResult:
    return ExternalActionResult(
        action="external_validate",
        status="ok",
        human_message="Provider-route validation only.",
        machine_error_code="OK",
        next_action="none",
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none",
        route_id="wbp-deepseek-v3",
        verification_scope="route_provider_only",
        route_state="model_visible",
        listener_proven=False,
        runtime_claim_blocked=True,
        profile_ready=False,
        network_dependent=True,
        evidence_path="/tmp/evidence.json",
        effective_model="deepseek/deepseek-chat",
        provider="openrouter",
        fallback_used="false",
        fallback_chain="[\"wbp-deepseek-v3\"]",
        latency_ms="5",
        request_count="1",
        writes_external_config="false",
        prerequisite="live_listener_contour_required",
        base_url="",
        changed_files=("/tmp/state.json",),
    )


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> CommandResult:
        self.calls.append(args)
        if args == ("status", "--json"):
            return CommandResult(
                payload={
                    "status": "ok",
                    "exit_code": 0,
                    "human_message": "Runtime status summary is available.",
                    "machine_error_code": "OK",
                    "next_action": "none",
                    "liveness": "healthy",
                    "severity": "info",
                    "operator_action": "none",
                    "desired_mode": "managed",
                    "effective_mode": "managed",
                    "endpoint": "http://127.0.0.1:8320/v1",
                    "current_proxy_url": "http://127.0.0.1:10808",
                    "pool_summary": {
                        "active": 2,
                        "reserve": 1,
                        "retired": 0,
                        "healthy": 2,
                        "degraded": 0,
                        "down": 1,
                    },
                    "attestation_summary": {
                        "status": "ok",
                        "machine_error_code": "OK",
                        "attestation_source": "healthcheck --json",
                        "observed_at_utc": "2026-05-08T00:00:00+00:00",
                    },
                },
                stderr="",
            )
        if args == ("mode", "get", "--json"):
            return CommandResult(
                payload={"desired_mode": "managed", "effective_mode": "managed"},
                stderr="",
            )
        if args == ("accounts", "list", "--json"):
            return CommandResult(
                payload={
                    "human_message": "Accounts listed.",
                    "machine_error_code": "OK",
                    "registry_identity": {
                        "status": "ok",
                        "machine_error_code": "OK",
                        "next_action": "none",
                    },
                    "accounts": [
                        {
                            "id": "backend-a",
                            "label": "Backend A",
                            "pool": "active",
                            "manual_hold": False,
                            "status": "healthy",
                            "fail_count": 0,
                            "success_count": 3,
                            "last_success": "2026-05-08T00:00:00+00:00",
                            "last_error": "",
                            "cooldown_until": None,
                            "notes": "",
                        }
                    ],
                },
                stderr="",
            )
        if args == ("external-models", "status", "--json"):
            return CommandResult(
                payload={
                    "status": "ok",
                    "exit_code": 0,
                    "human_message": "External-models synthetic lifecycle status collected without live runtime claims.",
                    "machine_error_code": "OK",
                    "changed_files": [],
                    "next_action": "none",
                    "liveness": "not_applicable",
                    "severity": "recoverable",
                    "operator_action": "none",
                    "data": {
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
                    "timestamp_utc": "2026-05-12T00:00:00Z",
                },
                stderr="",
            )
        if args == ("external-models", "models", "--json"):
            return CommandResult(
                payload={
                    "status": "ok",
                    "exit_code": 0,
                    "human_message": "External-models route models listed from local registry.",
                    "machine_error_code": "OK",
                    "changed_files": [],
                    "next_action": "none",
                    "liveness": "not_applicable",
                    "severity": "recoverable",
                    "operator_action": "none",
                    "data": {
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
                    "timestamp_utc": "2026-05-12T00:00:00Z",
                },
                stderr="",
            )
        if args == ("external-models", "routes", "list", "--json"):
            return CommandResult(
                payload={
                    "status": "ok",
                    "exit_code": 0,
                    "human_message": "External-models routes listed from local registry.",
                    "machine_error_code": "OK",
                    "changed_files": [],
                    "next_action": "none",
                    "liveness": "not_applicable",
                    "severity": "recoverable",
                    "operator_action": "none",
                    "data": {
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
                    "timestamp_utc": "2026-05-12T00:00:00Z",
                },
                stderr="",
            )
        if args == ("external-models", "routes", "validate", "--json", "--route", "wbp-deepseek-v3"):
            return CommandResult(
                payload={
                    "status": "ok",
                    "exit_code": 0,
                    "human_message": "External-models route validation captured provider evidence without claiming runtime readiness.",
                    "machine_error_code": "OK",
                    "changed_files": ["/tmp/state.json", "/tmp/evidence-validate.json"],
                    "next_action": "none",
                    "liveness": "not_applicable",
                    "severity": "recoverable",
                    "operator_action": "none",
                    "data": {
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
                        "available_models_count": 1,
                        "latency_ms": 6,
                    },
                    "timestamp_utc": "2026-05-12T00:00:00Z",
                },
                stderr="",
            )
        if args == ("external-models", "check", "--json", "--route", "wbp-deepseek-v3"):
            return CommandResult(
                payload={
                    "status": "ok",
                    "exit_code": 0,
                    "human_message": "External-models route smoke check captured provider evidence without claiming runtime readiness.",
                    "machine_error_code": "OK",
                    "changed_files": ["/tmp/state.json", "/tmp/evidence-check.json"],
                    "next_action": "none",
                    "liveness": "not_applicable",
                    "severity": "recoverable",
                    "operator_action": "none",
                    "data": {
                        "check_kind": "provider_route_smoke",
                        "network_dependent": True,
                        "listener_proven": False,
                        "runtime_claim_blocked": True,
                        "profile_ready": False,
                        "verification_scope": "route_provider_only",
                        "route_state": "verified",
                        "requested_model": "wbp-deepseek-v3",
                        "effective_model": "deepseek/deepseek-chat",
                        "provider": "openrouter",
                        "fallback_used": False,
                        "fallback_chain": ["wbp-deepseek-v3"],
                        "evidence_path": "/tmp/evidence-check.json",
                        "latency_ms": 5,
                        "request_count": 1,
                    },
                    "timestamp_utc": "2026-05-12T00:00:00Z",
                },
                stderr="",
            )
        if args == ("external-models", "profile", "codex-desktop", "--json", "--route", "wbp-deepseek-v3"):
            return CommandResult(
                payload={
                    "status": "ok",
                    "exit_code": 0,
                    "human_message": "Codex Desktop profile contract generated without mutating config.",
                    "machine_error_code": "OK",
                    "changed_files": [],
                    "next_action": "none",
                    "liveness": "not_applicable",
                    "severity": "recoverable",
                    "operator_action": "none",
                    "data": {
                        "profile_kind": "codex_desktop_openai_compatible",
                        "route_id": "wbp-deepseek-v3",
                        "base_url": None,
                        "model": "wbp-deepseek-v3",
                        "api_key_source": "managed_local_token",
                        "writes_external_config": False,
                        "profile_ready": False,
                        "listener_proven": False,
                        "runtime_claim_blocked": True,
                        "synthetic_endpoint_contract": True,
                        "prerequisite": "live_listener_contour_required",
                    },
                    "timestamp_utc": "2026-05-12T00:00:00Z",
                },
                stderr="",
            )
        if args == ("external-models", "evidence", "capture", "--json", "--route", "wbp-deepseek-v3"):
            return CommandResult(
                payload={
                    "status": "ok",
                    "exit_code": 0,
                    "human_message": "Local external-models evidence captured from foundation contract.",
                    "machine_error_code": "OK",
                    "changed_files": ["/tmp/evidence-local.json"],
                    "next_action": "none",
                    "liveness": "not_applicable",
                    "severity": "recoverable",
                    "operator_action": "none",
                    "data": {
                        "route_id": "wbp-deepseek-v3",
                        "network_dependent_evidence": False,
                        "evidence_path": "/tmp/evidence-local.json",
                    },
                    "timestamp_utc": "2026-05-12T00:00:00Z",
                },
                stderr="",
            )
        if args == ("external-models", "routes", "disable", "--json", "--route", "wbp-deepseek-v3"):
            return CommandResult(
                payload={
                    "status": "ok",
                    "exit_code": 0,
                    "human_message": "External-models route disabled: wbp-deepseek-v3.",
                    "machine_error_code": "OK",
                    "changed_files": ["/tmp/routes.json"],
                    "next_action": "none",
                    "liveness": "not_applicable",
                    "severity": "recoverable",
                    "operator_action": "none",
                    "data": {"route_id": "wbp-deepseek-v3", "enabled": False},
                    "timestamp_utc": "2026-05-12T00:00:00Z",
                },
                stderr="",
            )
        if args == ("external-models", "routes", "enable", "--json", "--route", "wbp-deepseek-v3"):
            return CommandResult(
                payload={
                    "status": "ok",
                    "exit_code": 0,
                    "human_message": "External-models route enabled: wbp-deepseek-v3.",
                    "machine_error_code": "OK",
                    "changed_files": ["/tmp/routes.json"],
                    "next_action": "none",
                    "liveness": "not_applicable",
                    "severity": "recoverable",
                    "operator_action": "none",
                    "data": {"route_id": "wbp-deepseek-v3", "enabled": True},
                    "timestamp_utc": "2026-05-12T00:00:00Z",
                },
                stderr="",
            )
        raise AssertionError(f"unexpected command: {args}")


class FakeApp:
    def __init__(self, state: DashboardState) -> None:
        self.state = state
        self.actions: list[dict[str, str]] = []

    def get_dashboard(self, *, path: str = "/") -> DashboardState:
        return self.state

    def post_action(self, fields: dict[str, str], *, path: str = "/action") -> DashboardState:
        self.actions.append(fields)
        return self.state


class WebUiTests(unittest.TestCase):
    def test_render_dashboard_contains_core_sections(self) -> None:
        html = render_dashboard(
            DashboardState(
                runtime=runtime_snapshot(),
                accounts=account_snapshot(),
                external_models=external_snapshot(),
                flash="Ready.",
                external_action=external_action(),
                events=(UiEvent(observed_at="12:00:00", request="GET /", outcome="ok"),),
            )
        )

        self.assertIn("Wild Boar Proxy", html)
        self.assertIn("Состояние runtime", html)
        self.assertIn("Операторские действия", html)
        self.assertIn("Пул аккаунтов", html)
        self.assertIn("External Models Overview", html)
        self.assertIn("External Models Routes", html)
        self.assertIn("External Models Action Result", html)
        self.assertIn("Последние действия", html)
        self.assertIn("Добавить explicit auth", html)
        self.assertIn("provider-route evidence only", html)
        self.assertIn("method=\"post\" action=\"/action\"", html)
        self.assertIn("external_validate", html)
        self.assertIn("external_check", html)
        self.assertIn("external_profile", html)
        self.assertIn("external_evidence", html)
        self.assertIn("Disable route wbp-deepseek-v3?", html)

    def test_apply_action_requires_explicit_auth_ref(self) -> None:
        state = apply_action(FakeRunner(), {"action": "onboard", "auth_ref": "   "})

        self.assertEqual(state.flash, "Нужен явный путь к auth-файлу.")

    def test_apply_action_external_validate_uses_existing_command_surface(self) -> None:
        state = apply_action(
            FakeRunner(),
            {"action": "external_validate", "route_id": "wbp-deepseek-v3"},
        )

        self.assertEqual(state.flash, "External-models route validation captured provider evidence without claiming runtime readiness.")
        self.assertIsNotNone(state.external_action)
        assert state.external_action is not None
        self.assertEqual(state.external_action.verification_scope, "route_provider_only")
        self.assertEqual(state.external_action.route_state, "model_visible")
        self.assertFalse(state.external_action.listener_proven)
        self.assertTrue(state.external_action.runtime_claim_blocked)
        self.assertFalse(state.external_action.profile_ready)

    def test_apply_action_external_route_toggle_requires_route_id(self) -> None:
        state = apply_action(FakeRunner(), {"action": "external_route_disable", "route_id": "   "})

        self.assertEqual(state.flash, "Нужен route_id для external-models.")

    def test_apply_action_external_profile_stays_non_ready(self) -> None:
        state = apply_action(
            FakeRunner(),
            {"action": "external_profile", "route_id": "wbp-deepseek-v3"},
        )

        self.assertEqual(state.flash, "Codex Desktop profile contract generated without mutating config.")
        self.assertIsNotNone(state.external_action)
        assert state.external_action is not None
        self.assertFalse(state.external_action.profile_ready)
        self.assertEqual(state.external_action.writes_external_config, "false")
        self.assertEqual(
            state.external_action.prerequisite,
            "live_listener_contour_required",
        )

    def test_http_handler_serves_dashboard_and_posts_actions(self) -> None:
        state = DashboardState(
            runtime=runtime_snapshot(),
            accounts=account_snapshot(),
            external_models=external_snapshot(),
            flash="Ready.",
            external_action=external_action(),
        )
        app = FakeApp(state)
        server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(app))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            conn.request("GET", "/")
            response = conn.getresponse()
            body = response.read().decode("utf-8")
            conn.close()
            self.assertEqual(response.status, 200)
            self.assertIn("Wild Boar Proxy", body)

            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            conn.request(
                "POST",
                "/action",
                body="action=sync",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response = conn.getresponse()
            body = response.read().decode("utf-8")
            conn.close()
            self.assertEqual(response.status, 200)
            self.assertIn("Ready.", body)
            self.assertEqual(app.actions, [{"action": "sync"}])

            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            conn.request("GET", "/action")
            response = conn.getresponse()
            body = response.read().decode("utf-8")
            conn.close()
            self.assertEqual(response.status, 200)
            self.assertIn("Wild Boar Proxy", body)

            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            conn.request(
                "POST",
                "/",
                body="action=sync",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response = conn.getresponse()
            response.read()
            conn.close()
            self.assertEqual(response.status, 200)
            self.assertEqual(app.actions, [{"action": "sync"}, {"action": "sync"}])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_http_handler_recovers_unknown_get_route(self) -> None:
        state = DashboardState(
            runtime=runtime_snapshot(),
            accounts=account_snapshot(),
            external_models=external_snapshot(),
            flash="Ready.",
            external_action=external_action(),
        )
        app = FakeApp(state)
        server = ThreadingHTTPServer(("127.0.0.1", free_port()), build_handler(app))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            conn.request("GET", "/missing")
            response = conn.getresponse()
            body = response.read().decode("utf-8")
            conn.close()
            self.assertEqual(response.status, 200)
            self.assertIn("Wild Boar Proxy", body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
