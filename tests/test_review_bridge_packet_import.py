# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import socket
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from wild_boar_proxy.review_bridge_command_bus import execute_review_command
from wild_boar_proxy.review_bridge_packet_import import (
    ReviewImportContext,
    adapt_review_packet,
)
from wild_boar_proxy.review_bridge_session_store import ReviewQueryBridge, ReviewSessionStore
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
        "project_id": IMPORT_CONTEXT.project_id,
        "baseline_hash": IMPORT_CONTEXT.baseline_hash,
        "review_items": [
            {
                "id": "change-1",
                "kind": "exact_text",
                "scene_id": "scene-001",
                "before": "old",
                "after": "new",
            },
            {
                "id": "struct-1",
                "kind": "structural",
                "scene_id": "scene-002",
                "summary": "Move heading manually",
            },
        ],
        "orphan_comments": [{"id": "orphan-1", "message": "Detached note"}],
        "diagnostics": [{"code": "manual-only-structural", "severity": "info"}],
    }
    payload.update(overrides)
    return payload


class ReviewBridgePacketImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReviewSessionStore()
        self.query = ReviewQueryBridge(self.store)

    def test_adapt_review_packet_normalizes_surface_and_hash(self) -> None:
        adapted = adapt_review_packet(review_packet(), context=IMPORT_CONTEXT)

        self.assertEqual(adapted["project_id"], IMPORT_CONTEXT.project_id)
        self.assertEqual(adapted["baseline_hash"], IMPORT_CONTEXT.baseline_hash)
        self.assertTrue(adapted["session_id"].startswith("review-import-"))
        self.assertTrue(adapted["source_packet_hash"].startswith("sha256:"))
        surface = adapted["review_surface"]
        self.assertEqual(surface["text_changes"][0]["id"], "change-1")
        self.assertEqual(surface["structural_manual_only"][0]["id"], "struct-1")
        self.assertTrue(surface["structural_manual_only"][0]["manual_only"])
        self.assertEqual(surface["orphan_comments"][0]["id"], "orphan-1")
        self.assertEqual(surface["diagnostics"][0]["code"], "manual-only-structural")
        self.assertFalse(surface["manuscript_write_performed"])
        self.assertFalse(surface["filesystem_mutation_performed"])
        self.assertTrue(surface["manual_only_structural"])

    def test_import_review_packet_from_raw_payload_stores_session_without_writes(self) -> None:
        result = execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": review_packet()},
            import_context=IMPORT_CONTEXT,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        self.assertFalse(result["data"]["manuscript_write_performed"])
        self.assertFalse(result["data"]["filesystem_mutation_performed"])
        self.assertTrue(result["data"]["session_store_memory_only"])
        surface = self.query.get_review_surface()
        self.assertEqual(surface["project_id"], IMPORT_CONTEXT.project_id)
        self.assertEqual(surface["baseline_hash"], IMPORT_CONTEXT.baseline_hash)
        self.assertEqual(surface["review_surface"]["text_changes"][0]["after"], "new")
        self.assertEqual(surface["review_surface"]["structural_manual_only"][0]["id"], "struct-1")

    def test_malformed_packet_is_rejected(self) -> None:
        result = execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": {"schema_version": 1, "project_id": IMPORT_CONTEXT.project_id}},
            import_context=IMPORT_CONTEXT,
        )
        self.assertEqual(result["status"], "command_error")
        self.assertEqual(result["machine_error_code"], "REVIEW_PACKET_MISSING_FIELD")

        wrong_list = execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": review_packet(review_items="bad")},
            import_context=IMPORT_CONTEXT,
        )
        self.assertEqual(wrong_list["status"], "command_error")
        self.assertEqual(wrong_list["machine_error_code"], "REVIEW_PACKET_INVALID_FIELD")

    def test_wrong_project_and_stale_baseline_are_rejected(self) -> None:
        wrong_project = execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": review_packet(project_id="other-project")},
            import_context=IMPORT_CONTEXT,
        )
        stale = execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": review_packet(baseline_hash="sha256:old")},
            import_context=IMPORT_CONTEXT,
        )
        self.assertEqual(wrong_project["machine_error_code"], "REVIEW_PACKET_PROJECT_MISMATCH")
        self.assertEqual(stale["machine_error_code"], "REVIEW_PACKET_BASELINE_STALE")
        self.assertEqual(self.query.get_review_surface()["status"], "empty")

    def test_http_import_surface_admits_raw_packet_and_exposes_query(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(review_import_context=IMPORT_CONTEXT),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            imported = json.loads(
                post_json(
                    f"{base}/api/review-command",
                    {
                        "command_id": "import_review_packet",
                        "payload": {"review_packet": review_packet()},
                    },
                )
            )
            surface = json.loads(fetch(f"{base}/api/review-surface"))
            self.assertEqual(imported["status"], "ok")
            self.assertEqual(imported["machine_error_code"], "OK")
            self.assertEqual(surface["status"], "ok")
            self.assertEqual(surface["review_surface"]["orphan_comments"][0]["id"], "orphan-1")
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_http_import_rejection_matrix_is_honest(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_handler(review_import_context=IMPORT_CONTEXT),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            malformed = json.loads(
                post_json(
                    f"{base}/api/review-command",
                    {
                        "command_id": "import_review_packet",
                        "payload": {"review_packet": {"schema_version": 1}},
                    },
                )
            )
            wrong_project = json.loads(
                post_json(
                    f"{base}/api/review-command",
                    {
                        "command_id": "import_review_packet",
                        "payload": {"review_packet": review_packet(project_id="other-project")},
                    },
                )
            )
            stale = json.loads(
                post_json(
                    f"{base}/api/review-command",
                    {
                        "command_id": "import_review_packet",
                        "payload": {"review_packet": review_packet(baseline_hash="sha256:old")},
                    },
                )
            )
            self.assertEqual(malformed["machine_error_code"], "REVIEW_PACKET_MISSING_FIELD")
            self.assertEqual(wrong_project["machine_error_code"], "REVIEW_PACKET_PROJECT_MISMATCH")
            self.assertEqual(stale["machine_error_code"], "REVIEW_PACKET_BASELINE_STALE")
            self.assertEqual(json.loads(fetch(f"{base}/api/review-surface"))["status"], "empty")
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
