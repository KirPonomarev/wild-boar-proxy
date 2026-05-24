# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import socket
import threading
import unittest
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import ThreadingHTTPServer

from wild_boar_proxy.review_bridge_packet_import import ReviewImportContext
from wild_boar_proxy.web_design_live_server import build_handler


NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
IMPORT_CONTEXT = ReviewImportContext(
    project_id="project-alpha",
    baseline_hash="sha256:baseline-alpha",
)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def fetch(url: str) -> str:
    with NO_PROXY_OPENER.open(url, timeout=5) as response:
        return response.read().decode("utf-8")


def post_json(url: str, payload: dict[str, object]) -> str:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with NO_PROXY_OPENER.open(request, timeout=5) as response:
        return response.read().decode("utf-8")


def review_packet(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "project_id": "project-alpha",
        "baseline_hash": "sha256:baseline-alpha",
        "review_items": [{"id": "change-1", "kind": "exact_text"}],
        "orphan_comments": [],
        "diagnostics": [],
    }
    payload.update(overrides)
    return payload


def import_command_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "command_id": "import_review_packet",
        "payload": {
            "review_packet": review_packet(),
        },
    }
    payload.update(overrides)
    return payload


class ReviewBridgeLiveServerTests(unittest.TestCase):
    def test_review_command_and_query_surfaces_stay_split(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(review_import_context=IMPORT_CONTEXT),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            empty = json.loads(fetch(f"{base}/api/review-surface"))
            command_list = json.loads(fetch(f"{base}/api/review-commands"))
            imported = json.loads(post_json(f"{base}/api/review-command", import_command_payload()))
            surface = json.loads(fetch(f"{base}/api/review-surface"))
            cleared = json.loads(
                post_json(
                    f"{base}/api/review-command",
                    {"command_id": "clear_review_session", "payload": {}},
                )
            )
            after_clear = json.loads(fetch(f"{base}/api/review-surface"))

            self.assertEqual(empty["machine_error_code"], "REVIEW_SESSION_EMPTY")
            self.assertEqual(command_list["status"], "ok")
            self.assertEqual(
                {entry["command_id"] for entry in command_list["commands"]},
                {"import_review_packet", "clear_review_session", "apply_exact_text_change"},
            )
            self.assertEqual(imported["status"], "ok")
            self.assertEqual(imported["machine_error_code"], "OK")
            self.assertEqual(surface["status"], "ok")
            self.assertTrue(surface["session_present"])
            self.assertEqual(surface["project_id"], "project-alpha")
            self.assertEqual(cleared["status"], "ok")
            self.assertEqual(cleared["machine_error_code"], "OK")
            self.assertEqual(after_clear["machine_error_code"], "REVIEW_SESSION_EMPTY")
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_review_command_requires_command_id_and_query_surface_rejects_post(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(review_import_context=IMPORT_CONTEXT),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            missing = json.loads(post_json(f"{base}/api/review-command", {"payload": {}}))
            self.assertEqual(missing["machine_error_code"], "REVIEW_COMMAND_ID_REQUIRED")

            request = urllib.request.Request(
                f"{base}/api/review-surface",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as error:
                NO_PROXY_OPENER.open(request, timeout=5)
            self.assertEqual(error.exception.code, HTTPStatus.NOT_FOUND)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_apply_exact_text_change_stays_not_enabled_through_http(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(review_import_context=IMPORT_CONTEXT),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            result = json.loads(
                post_json(
                    f"{base}/api/review-command",
                    {"command_id": "apply_exact_text_change", "payload": {}},
                )
            )
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["machine_error_code"], "REVIEW_APPLY_NOT_ENABLED")
            self.assertEqual(json.loads(fetch(f"{base}/api/review-surface"))["status"], "empty")
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
