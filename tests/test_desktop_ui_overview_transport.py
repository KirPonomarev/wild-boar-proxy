from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Any, Mapping

from wild_boar_proxy.desktop_ui.overview_transport import (
    BRIDGE_ROUTE,
    LOCAL_BIND_HOST,
    SOURCE_ID,
    create_transport_server,
)


@contextmanager
def running_transport(bridge_runner):
    server = create_transport_server(bridge_runner=bridge_runner)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request_json(
    base_url: str,
    path: str,
    body: Any | bytes | None,
    *,
    method: str = "POST",
    origin: str | None = None,
) -> tuple[int, Mapping[str, Any]]:
    data = None
    if isinstance(body, bytes):
        data = body
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if origin:
        headers["Origin"] = origin
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=3) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def request_options(base_url: str, path: str, *, origin: str | None = None) -> tuple[int, Mapping[str, str] | Mapping[str, Any]]:
    headers = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    if origin:
        headers["Origin"] = origin
    request = urllib.request.Request(f"{base_url}{path}", headers=headers, method="OPTIONS")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=3) as response:
            return response.status, dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class DesktopUiOverviewTransportTests(unittest.TestCase):
    def test_valid_refresh_request_delegates_to_bridge_runner(self) -> None:
        calls: list[Mapping[str, Any]] = []

        def bridge_runner(request: Mapping[str, Any]) -> Mapping[str, Any]:
            calls.append(dict(request))
            return {
                "source": "test_bridge",
                "operation_id": "refresh_overview",
                "status": "ok",
                "machine_error_code": "OK",
                "human_message": "refreshed",
            }

        with running_transport(bridge_runner) as base_url:
            status, packet = request_json(base_url, BRIDGE_ROUTE, {"operation_id": "refresh_overview"})

        self.assertEqual(status, 200)
        self.assertEqual(packet["source"], "test_bridge")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(calls, [{"operation_id": "refresh_overview"}])

    def test_valid_action_request_delegates_as_bridge_request(self) -> None:
        calls: list[Mapping[str, Any]] = []

        def bridge_runner(request: Mapping[str, Any]) -> Mapping[str, Any]:
            calls.append(dict(request))
            return {
                "source": "test_bridge",
                "operation_id": "run_overview_action",
                "status": "ok",
                "machine_error_code": "OK",
                "human_message": "action ok",
            }

        request = {"operation_id": "run_overview_action", "action_id": "run_smoke", "confirmed": True}
        with running_transport(bridge_runner) as base_url:
            status, packet = request_json(base_url, BRIDGE_ROUTE, request)

        self.assertEqual(status, 200)
        self.assertEqual(packet["operation_id"], "run_overview_action")
        self.assertEqual(calls, [request])

    def test_invalid_json_is_transport_error_and_does_not_call_bridge(self) -> None:
        calls: list[Mapping[str, Any]] = []

        with running_transport(lambda request: calls.append(request) or {}) as base_url:
            status, packet = request_json(base_url, BRIDGE_ROUTE, b"{not json")

        self.assertEqual(status, 400)
        self.assertEqual(packet["source"], SOURCE_ID)
        self.assertEqual(packet["machine_error_code"], "TRANSPORT_INVALID_JSON")
        self.assertEqual(calls, [])

    def test_forbidden_fields_are_rejected_before_bridge_runner(self) -> None:
        calls: list[Mapping[str, Any]] = []

        with running_transport(lambda request: calls.append(request) or {}) as base_url:
            status, packet = request_json(
                base_url,
                BRIDGE_ROUTE,
                {"operation_id": "refresh_overview", "command": "status --json"},
            )

        self.assertEqual(status, 400)
        self.assertEqual(packet["source"], SOURCE_ID)
        self.assertEqual(packet["machine_error_code"], "TRANSPORT_REQUEST_FORBIDDEN_FIELD")
        self.assertEqual(calls, [])

    def test_unknown_operation_stays_structured_json_error(self) -> None:
        def bridge_runner(request: Mapping[str, Any]) -> Mapping[str, Any]:
            return {
                "source": "test_bridge",
                "operation_id": request.get("operation_id", ""),
                "status": "error",
                "machine_error_code": "BRIDGE_OPERATION_FORBIDDEN",
                "human_message": "blocked",
            }

        with running_transport(bridge_runner) as base_url:
            status, packet = request_json(base_url, BRIDGE_ROUTE, {"operation_id": "delete_everything"})

        self.assertEqual(status, 400)
        self.assertEqual(packet["machine_error_code"], "BRIDGE_OPERATION_FORBIDDEN")
        self.assertEqual(packet["status"], "error")

    def test_get_method_is_rejected(self) -> None:
        with running_transport(lambda request: {}) as base_url:
            status, packet = request_json(base_url, BRIDGE_ROUTE, None, method="GET")

        self.assertEqual(status, 405)
        self.assertEqual(packet["machine_error_code"], "TRANSPORT_METHOD_FORBIDDEN")

    def test_non_admitted_route_is_rejected(self) -> None:
        with running_transport(lambda request: {}) as base_url:
            status, packet = request_json(base_url, "/anything-else", {"operation_id": "refresh_overview"})

        self.assertEqual(status, 404)
        self.assertEqual(packet["machine_error_code"], "TRANSPORT_ROUTE_FORBIDDEN")

    def test_localhost_origin_is_admitted_for_browser_transport(self) -> None:
        with running_transport(lambda request: {"status": "ok"}) as base_url:
            status, headers = request_options(base_url, BRIDGE_ROUTE, origin="http://127.0.0.1:8123")

        self.assertEqual(status, 204)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://127.0.0.1:8123")
        self.assertEqual(headers["Access-Control-Allow-Methods"], "POST")

    def test_non_localhost_origin_is_rejected(self) -> None:
        with running_transport(lambda request: {}) as base_url:
            status, packet = request_options(base_url, BRIDGE_ROUTE, origin="http://localhost:8123")

        self.assertEqual(status, 403)
        self.assertEqual(packet["machine_error_code"], "TRANSPORT_ORIGIN_FORBIDDEN")

    def test_post_from_non_localhost_origin_is_rejected_before_bridge(self) -> None:
        calls: list[Mapping[str, Any]] = []

        with running_transport(lambda request: calls.append(request) or {}) as base_url:
            status, packet = request_json(
                base_url,
                BRIDGE_ROUTE,
                {"operation_id": "refresh_overview"},
                origin="http://localhost:8123",
            )

        self.assertEqual(status, 403)
        self.assertEqual(packet["machine_error_code"], "TRANSPORT_ORIGIN_FORBIDDEN")
        self.assertEqual(calls, [])

    def test_transport_binds_only_to_localhost(self) -> None:
        server = create_transport_server()
        try:
            self.assertEqual(server.server_address[0], LOCAL_BIND_HOST)
        finally:
            server.server_close()

        with self.assertRaises(ValueError):
            create_transport_server(host="0.0.0.0")


if __name__ == "__main__":
    unittest.main()
