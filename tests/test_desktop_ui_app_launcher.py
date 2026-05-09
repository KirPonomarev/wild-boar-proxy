from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit

from wild_boar_proxy.desktop_ui.app import (
    DESKTOP_UI_ROOT,
    SOURCE_ID,
    RendererAvailability,
    build_overview_url,
    create_static_server,
    detect_renderer_availability,
    launch_app,
    startup_packet,
)


@contextmanager
def running_static_server(root: Path):
    server = create_static_server(static_root=root)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request_url(url: str, *, method: str = "GET") -> tuple[int, bytes, Mapping[str, str]]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, method=method)
    try:
        with opener.open(request, timeout=3) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


class DesktopUiAppLauncherTests(unittest.TestCase):
    def test_renderer_detection_is_honest_for_current_environment(self) -> None:
        detected = detect_renderer_availability()

        self.assertIn(detected.renderer_status, {"embedded_available", "embedded_unavailable_dev_preview"})
        self.assertEqual(detected.available, bool(detected.embedded_renderer))

    def test_overview_url_uses_live_transport_mode_and_local_bridge(self) -> None:
        url = build_overview_url(static_port=7777, transport_port=8888)
        split = urlsplit(url)
        query = parse_qs(split.query)
        transport = urlsplit(query["transport"][0])

        self.assertEqual(split.scheme, "http")
        self.assertEqual(split.hostname, "127.0.0.1")
        self.assertEqual(split.path, "/index.html")
        self.assertEqual(query["mode"], ["live"])
        self.assertEqual(query["bridge"], ["transport"])
        self.assertEqual(transport.scheme, "http")
        self.assertEqual(transport.hostname, "127.0.0.1")
        self.assertEqual(transport.path, "/overview-bridge")

    def test_startup_packet_shape(self) -> None:
        renderer = RendererAvailability("", "embedded_unavailable_dev_preview", False)
        packet = startup_packet(static_port=7001, transport_port=7002, renderer=renderer, opened_dev_preview=False)

        self.assertEqual(packet["source"], SOURCE_ID)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["renderer_status"], "embedded_unavailable_dev_preview")
        self.assertEqual(packet["static_host"], "127.0.0.1")
        self.assertEqual(packet["transport_host"], "127.0.0.1")
        self.assertIn("/overview-bridge", packet["transport_url"])
        self.assertEqual(packet["next_action"], "open_dev_preview_url")

    def test_static_server_serves_index_from_bounded_root(self) -> None:
        with running_static_server(DESKTOP_UI_ROOT) as base_url:
            status, body, headers = request_url(f"{base_url}/index.html")

        self.assertEqual(status, 200)
        self.assertIn(b"Wild Boar Proxy", body)
        self.assertIn("text/html", headers["Content-Type"])

    def test_static_server_rejects_directory_listing_and_traversal(self) -> None:
        with running_static_server(DESKTOP_UI_ROOT) as base_url:
            root_status, root_body, _ = request_url(f"{base_url}/")
            traversal_status, _, _ = request_url(f"{base_url}/../../CANON.md")
            directory_status, directory_body, _ = request_url(f"{base_url}/styles/")

        self.assertEqual(root_status, 200)
        self.assertIn(b"Wild Boar Proxy", root_body)
        self.assertIn(traversal_status, {403, 404})
        self.assertIn(directory_status, {403, 404})
        self.assertNotIn(b"Directory listing", directory_body)

    def test_static_server_rejects_non_get_head(self) -> None:
        with running_static_server(DESKTOP_UI_ROOT) as base_url:
            status, body, _ = request_url(f"{base_url}/index.html", method="POST")

        self.assertEqual(status, 405)
        self.assertIn(b"Method not allowed", body)

    def test_static_server_binds_only_to_localhost(self) -> None:
        server = create_static_server()
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
        finally:
            server.server_close()

        with self.assertRaises(ValueError):
            create_static_server(host="0.0.0.0")

    def test_smoke_mode_starts_and_stops_services_without_opening_preview(self) -> None:
        snapshot_calls: list[Path] = []
        opened: list[str] = []

        def snapshot_writer(path: Path) -> dict[str, Any]:
            snapshot_calls.append(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"source": "test"}), encoding="utf-8")
            return {"status": "ok"}

        packet = launch_app(
            smoke=True,
            open_dev_preview=True,
            renderer=RendererAvailability("", "embedded_unavailable_dev_preview", False),
            snapshot_writer=snapshot_writer,
            url_opener=lambda url: opened.append(url) or True,
        )

        self.assertEqual(packet["source"], SOURCE_ID)
        self.assertEqual(packet["renderer_status"], "embedded_unavailable_dev_preview")
        self.assertEqual(packet["opened_dev_preview"], False)
        self.assertEqual(len(snapshot_calls), 1)
        self.assertEqual(opened, [])

    def test_explicit_open_dev_preview_is_not_default(self) -> None:
        opened: list[str] = []

        def snapshot_writer(path: Path) -> dict[str, Any]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
            return {"status": "ok"}

        default_packet = launch_app(
            hold_open=False,
            renderer=RendererAvailability("", "embedded_unavailable_dev_preview", False),
            snapshot_writer=snapshot_writer,
            url_opener=lambda url: opened.append(url) or True,
        )
        explicit_packet = launch_app(
            hold_open=False,
            open_dev_preview=True,
            renderer=RendererAvailability("", "embedded_unavailable_dev_preview", False),
            snapshot_writer=snapshot_writer,
            url_opener=lambda url: opened.append(url) or True,
        )

        self.assertFalse(default_packet["opened_dev_preview"])
        self.assertTrue(explicit_packet["opened_dev_preview"])
        self.assertEqual(len(opened), 1)


if __name__ == "__main__":
    unittest.main()
