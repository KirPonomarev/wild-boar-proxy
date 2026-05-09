"""Local desktop transport for the Overview bridge.

This module is intentionally tiny: it moves strict JSON requests from the
desktop HTML renderer to ``overview_bridge`` and does not execute commands or
read runtime truth on its own.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from wild_boar_proxy.desktop_ui.overview_actions import DEFAULT_SNAPSHOT_PATH
from wild_boar_proxy.desktop_ui.overview_bridge import FORBIDDEN_REQUEST_FIELDS, run_bridge_request


SOURCE_ID = "ui_desktop_html_overview_safe_transport"
BRIDGE_ROUTE = "/overview-bridge"
LOCAL_BIND_HOST = "127.0.0.1"
MAX_REQUEST_BYTES = 64 * 1024
ALLOWED_CORS_REQUEST_HEADERS = "content-type"

BridgeRunner = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class OverviewTransportServer(ThreadingHTTPServer):
    """HTTP transport constrained to localhost and fixed Overview bridge calls."""

    bridge_runner: BridgeRunner


class OverviewTransportHandler(BaseHTTPRequestHandler):
    server: OverviewTransportServer

    def end_headers(self) -> None:
        origin = self._admitted_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path != BRIDGE_ROUTE:
            self._send_error(
                404,
                "TRANSPORT_ROUTE_FORBIDDEN",
                "Only the fixed Overview bridge route is admitted.",
            )
            return
        if self._admitted_origin() is None:
            self._send_error(403, "TRANSPORT_ORIGIN_FORBIDDEN", "Overview transport origin is not admitted.")
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "POST")
        self.send_header("Access-Control-Allow-Headers", ALLOWED_CORS_REQUEST_HEADERS)
        self.send_header("Access-Control-Max-Age", "300")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path != BRIDGE_ROUTE:
            self._send_error(
                404,
                "TRANSPORT_ROUTE_FORBIDDEN",
                "Only the fixed Overview bridge route is admitted.",
            )
            return
        if self.headers.get("Origin") and self._admitted_origin() is None:
            self._send_error(403, "TRANSPORT_ORIGIN_FORBIDDEN", "Overview transport origin is not admitted.")
            return

        raw_body = self._read_body()
        if raw_body is None:
            return

        try:
            request = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._send_error(
                400,
                "TRANSPORT_INVALID_JSON",
                f"Overview transport request is invalid JSON: {exc}",
            )
            return

        if not isinstance(request, dict):
            self._send_error(400, "TRANSPORT_INVALID_REQUEST", "Overview transport request must be a JSON object.")
            return

        forbidden = sorted(FORBIDDEN_REQUEST_FIELDS.intersection(request))
        if forbidden:
            self._send_error(
                400,
                "TRANSPORT_REQUEST_FORBIDDEN_FIELD",
                f"Overview transport request contains forbidden fields: {', '.join(forbidden)}",
            )
            return

        try:
            packet = dict(self.server.bridge_runner(request))
        except Exception as exc:  # pragma: no cover - defensive boundary.
            self._send_error(500, "TRANSPORT_BRIDGE_FAILED", str(exc))
            return

        self._send_json(200 if packet.get("status") == "ok" else 400, packet)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        self._method_forbidden()

    def do_PUT(self) -> None:  # noqa: N802 - stdlib handler API
        self._method_forbidden()

    def do_PATCH(self) -> None:  # noqa: N802 - stdlib handler API
        self._method_forbidden()

    def do_DELETE(self) -> None:  # noqa: N802 - stdlib handler API
        self._method_forbidden()

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _admitted_origin(self) -> str | None:
        origin = self.headers.get("Origin")
        if not origin:
            return None
        try:
            parsed = json_urlparse(origin)
        except ValueError:
            return None
        if parsed["protocol"] != "http" or parsed["hostname"] != LOCAL_BIND_HOST:
            return None
        if parsed["username"] or parsed["password"] or parsed["path"] not in ("", "/") or parsed["query"] or parsed["fragment"]:
            return None
        return origin

    def _method_forbidden(self) -> None:
        self._send_error(
            405,
            "TRANSPORT_METHOD_FORBIDDEN",
            "Overview transport accepts POST JSON bridge requests only.",
        )

    def _read_body(self) -> bytes | None:
        raw_length = self.headers.get("Content-Length")
        try:
            content_length = int(raw_length or "0")
        except ValueError:
            self._send_error(411, "TRANSPORT_INVALID_CONTENT_LENGTH", "Content-Length must be an integer.")
            return None

        if content_length <= 0:
            self._send_error(400, "TRANSPORT_EMPTY_BODY", "Overview transport request body is required.")
            return None
        if content_length > MAX_REQUEST_BYTES:
            self._send_error(413, "TRANSPORT_REQUEST_TOO_LARGE", "Overview transport request is too large.")
            return None
        return self.rfile.read(content_length)

    def _send_error(self, status_code: int, machine_error_code: str, human_message: str) -> None:
        self._send_json(
            status_code,
            {
                "source": SOURCE_ID,
                "status": "error",
                "machine_error_code": machine_error_code,
                "human_message": human_message,
                "next_action": "user_action",
                "operator_action": "user_action",
            },
        )

    def _send_json(self, status_code: int, packet: Mapping[str, Any]) -> None:
        rendered = json.dumps(dict(packet), ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(rendered)))
        self.end_headers()
        self.wfile.write(rendered)


def create_transport_server(
    *,
    host: str = LOCAL_BIND_HOST,
    port: int = 0,
    bridge_runner: BridgeRunner | None = None,
    snapshot_path: Path = DEFAULT_SNAPSHOT_PATH,
) -> OverviewTransportServer:
    if host != LOCAL_BIND_HOST:
        raise ValueError("Overview desktop transport may bind only to 127.0.0.1.")

    def default_runner(request: Mapping[str, Any]) -> Mapping[str, Any]:
        return run_bridge_request(request, snapshot_path=snapshot_path)

    server = OverviewTransportServer((host, port), OverviewTransportHandler)
    server.bridge_runner = bridge_runner or default_runner
    return server


def json_urlparse(value: str) -> dict[str, str]:
    from urllib.parse import urlsplit

    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("URL must be absolute.")
    return {
        "protocol": parsed.scheme,
        "hostname": parsed.hostname or "",
        "username": parsed.username or "",
        "password": parsed.password or "",
        "path": parsed.path,
        "query": parsed.query,
        "fragment": parsed.fragment,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local desktop Overview transport.")
    parser.add_argument("--host", default=LOCAL_BIND_HOST)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--snapshot-output", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    args = parser.parse_args(argv)

    server = create_transport_server(host=args.host, port=args.port, snapshot_path=args.snapshot_output)
    host, port = server.server_address
    print(json.dumps({"source": SOURCE_ID, "status": "listening", "host": host, "port": port}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
