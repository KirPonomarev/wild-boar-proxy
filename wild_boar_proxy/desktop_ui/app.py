"""Terminal launcher for the local desktop Overview UI."""

from __future__ import annotations

import argparse
import importlib.util
import json
import mimetypes
import posixpath
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote, unquote, urlencode, urlsplit

from wild_boar_proxy.desktop_ui.live_overview import write_live_overview_payload
from wild_boar_proxy.desktop_ui.overview_actions import DEFAULT_SNAPSHOT_PATH
from wild_boar_proxy.desktop_ui.overview_transport import BRIDGE_ROUTE, LOCAL_BIND_HOST, create_transport_server


SOURCE_ID = "ui_desktop_html_app_launcher"
DESKTOP_UI_ROOT = Path(__file__).resolve().parent
DEFAULT_RENDERER_WIDTH = 1600
DEFAULT_RENDERER_HEIGHT = 1000

SnapshotWriter = Callable[[Path], Mapping[str, Any]]
UrlOpener = Callable[[str], bool]


@dataclass(frozen=True)
class RendererAvailability:
    embedded_renderer: str
    renderer_status: str
    available: bool


@dataclass
class LauncherServices:
    static_server: ThreadingHTTPServer
    transport_server: ThreadingHTTPServer
    static_thread: threading.Thread
    transport_thread: threading.Thread

    def shutdown(self) -> None:
        for server in (self.static_server, self.transport_server):
            server.shutdown()
            server.server_close()
        for thread in (self.static_thread, self.transport_thread):
            thread.join(timeout=2)


class BoundedStaticServer(ThreadingHTTPServer):
    static_root: Path


class BoundedStaticHandler(BaseHTTPRequestHandler):
    server: BoundedStaticServer

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        self._serve_static(send_body=True)

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib handler API
        self._serve_static(send_body=False)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        self._method_forbidden()

    def do_PUT(self) -> None:  # noqa: N802 - stdlib handler API
        self._method_forbidden()

    def do_PATCH(self) -> None:  # noqa: N802 - stdlib handler API
        self._method_forbidden()

    def do_DELETE(self) -> None:  # noqa: N802 - stdlib handler API
        self._method_forbidden()

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _serve_static(self, *, send_body: bool) -> None:
        resolved = self._resolve_request_path()
        if resolved is None:
            self._send_text(403, "Forbidden")
            return
        if not resolved.exists() or not resolved.is_file():
            self._send_text(404, "Not found")
            return

        body = resolved.read_bytes()
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def _resolve_request_path(self) -> Path | None:
        split = urlsplit(self.path)
        raw_path = unquote(split.path)
        if raw_path in ("", "/"):
            raw_path = "/index.html"
        normalized = posixpath.normpath(raw_path)
        if normalized.startswith("../") or normalized == "..":
            return None
        relative = normalized.lstrip("/")
        candidate = (self.server.static_root / relative).resolve()
        root = self.server.static_root.resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return None
        if candidate.is_dir():
            return None
        return candidate

    def _method_forbidden(self) -> None:
        self._send_text(405, "Method not allowed")

    def _send_text(self, status_code: int, message: str) -> None:
        body = (message + "\n").encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def detect_renderer_availability() -> RendererAvailability:
    if importlib.util.find_spec("webview"):
        return RendererAvailability("pywebview", "embedded_available", True)
    return RendererAvailability("", "embedded_unavailable_dev_preview", False)


def create_static_server(*, host: str = LOCAL_BIND_HOST, port: int = 0, static_root: Path = DESKTOP_UI_ROOT) -> BoundedStaticServer:
    if host != LOCAL_BIND_HOST:
        raise ValueError("Desktop UI static renderer may bind only to 127.0.0.1.")
    server = BoundedStaticServer((host, port), BoundedStaticHandler)
    server.static_root = static_root.resolve()
    return server


def start_server(server: ThreadingHTTPServer, *, name: str) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, name=name, daemon=True)
    thread.start()
    return thread


def build_overview_url(*, static_port: int, transport_port: int) -> str:
    transport_url = f"http://{LOCAL_BIND_HOST}:{transport_port}{BRIDGE_ROUTE}"
    query = urlencode({
        "mode": "live",
        "bridge": "transport",
        "transport": transport_url,
    })
    return f"http://{LOCAL_BIND_HOST}:{static_port}/index.html?{query}"


def startup_packet(
    *,
    static_port: int,
    transport_port: int,
    renderer: RendererAvailability,
    opened_dev_preview: bool,
) -> dict[str, Any]:
    transport_url = f"http://{LOCAL_BIND_HOST}:{transport_port}{BRIDGE_ROUTE}"
    renderer_url = build_overview_url(static_port=static_port, transport_port=transport_port)
    return {
        "source": SOURCE_ID,
        "status": "ok",
        "renderer_status": renderer.renderer_status,
        "transport_url": transport_url,
        "renderer_url": renderer_url,
        "static_host": LOCAL_BIND_HOST,
        "static_port": static_port,
        "transport_host": LOCAL_BIND_HOST,
        "transport_port": transport_port,
        "embedded_renderer": renderer.embedded_renderer,
        "dev_preview_url": renderer_url if not renderer.available else "",
        "opened_dev_preview": opened_dev_preview,
        "human_message": _human_message(renderer, opened_dev_preview),
        "next_action": "open_dev_preview_url" if not renderer.available and not opened_dev_preview else "none",
    }


def launch_app(
    *,
    smoke: bool = False,
    open_dev_preview: bool = False,
    hold_open: bool = True,
    renderer: RendererAvailability | None = None,
    snapshot_writer: SnapshotWriter | None = None,
    url_opener: UrlOpener | None = None,
) -> dict[str, Any]:
    snapshot_writer = snapshot_writer or write_live_overview_payload
    renderer = renderer or detect_renderer_availability()
    snapshot_writer(DEFAULT_SNAPSHOT_PATH)

    transport_server = create_transport_server()
    static_server = create_static_server()
    transport_thread = start_server(transport_server, name="desktop-ui-transport")
    static_thread = start_server(static_server, name="desktop-ui-static")
    services = LauncherServices(
        static_server=static_server,
        transport_server=transport_server,
        static_thread=static_thread,
        transport_thread=transport_thread,
    )

    static_port = int(static_server.server_address[1])
    transport_port = int(transport_server.server_address[1])
    renderer_url = build_overview_url(static_port=static_port, transport_port=transport_port)
    opened_dev_preview = False

    try:
        if renderer.available and not smoke:
            _open_embedded_renderer(renderer_url)
        elif open_dev_preview and not smoke:
            opened_dev_preview = bool((url_opener or webbrowser.open)(renderer_url))
        packet = startup_packet(
            static_port=static_port,
            transport_port=transport_port,
            renderer=renderer,
            opened_dev_preview=opened_dev_preview,
        )
        if smoke or not hold_open:
            return packet
        if not renderer.available:
            print(json.dumps(packet, ensure_ascii=False, indent=2), flush=True)
            _wait_forever()
        return packet
    finally:
        services.shutdown()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch the local desktop Overview companion UI.")
    parser.add_argument("--smoke", action="store_true", help="Start launcher services, print packet, and exit.")
    parser.add_argument(
        "--open-dev-preview",
        action="store_true",
        help="Explicitly open the fallback dev-preview URL when no embedded renderer is available.",
    )
    args = parser.parse_args(argv)

    packet = launch_app(smoke=args.smoke, open_dev_preview=args.open_dev_preview)
    if args.smoke or packet.get("renderer_status") != "embedded_unavailable_dev_preview":
        print(json.dumps(packet, ensure_ascii=False, indent=2), flush=True)
    return 0 if packet.get("status") == "ok" else 1


def _open_embedded_renderer(url: str) -> None:
    import webview  # type: ignore[import-not-found]

    webview.create_window("Wild Boar Proxy", url, width=DEFAULT_RENDERER_WIDTH, height=DEFAULT_RENDERER_HEIGHT)
    webview.start()


def _wait_forever() -> None:
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        return


def _human_message(renderer: RendererAvailability, opened_dev_preview: bool) -> str:
    if renderer.available:
        return "Embedded renderer opened for the first Overview screen."
    if opened_dev_preview:
        return "Embedded renderer unavailable; explicit dev-preview fallback opened."
    return "Embedded renderer unavailable; use the printed dev-preview URL while this command is running."


if __name__ == "__main__":
    raise SystemExit(main())
