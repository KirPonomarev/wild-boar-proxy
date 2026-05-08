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
                flash="Ready.",
                events=(UiEvent(observed_at="12:00:00", request="GET /", outcome="ok"),),
            )
        )

        self.assertIn("Wild Boar Proxy", html)
        self.assertIn("Состояние runtime", html)
        self.assertIn("Операторские действия", html)
        self.assertIn("Пул аккаунтов", html)
        self.assertIn("Последние действия", html)
        self.assertIn("Добавить explicit auth", html)
        self.assertIn("method=\"post\" action=\"/action\"", html)

    def test_apply_action_requires_explicit_auth_ref(self) -> None:
        state = apply_action(FakeRunner(), {"action": "onboard", "auth_ref": "   "})

        self.assertEqual(state.flash, "Нужен явный путь к auth-файлу.")

    def test_http_handler_serves_dashboard_and_posts_actions(self) -> None:
        state = DashboardState(runtime=runtime_snapshot(), accounts=account_snapshot(), flash="Ready.")
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
        state = DashboardState(runtime=runtime_snapshot(), accounts=account_snapshot(), flash="Ready.")
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
