# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path
import socket
import threading
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import ThreadingHTTPServer

from wild_boar_proxy.review_bridge_apply_admission import (
    REVIEW_SCENE_MAP_FILENAME,
    ReviewApplyContext,
    ReviewSceneInventoryEntry,
)
from wild_boar_proxy.review_bridge_packet_import import (
    ReviewImportContext,
    ReviewPacketImportError,
)
from wild_boar_proxy.web_design_live_server import build_handler
from wild_boar_proxy.web_token import (
    WEB_AUTH_HEADER,
    WEB_CSRF_HEADER,
    create_in_memory_web_token,
)


NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
IMPORT_CONTEXT = ReviewImportContext(
    project_id="project-alpha",
    baseline_hash="sha256:baseline-alpha",
)
WEB_TOKEN_STATE = create_in_memory_web_token()


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
        headers=web_post_headers({"Content-Type": "application/json"}),
        method="POST",
    )
    with NO_PROXY_OPENER.open(request, timeout=5) as response:
        return response.read().decode("utf-8")


def web_post_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    merged = dict(headers or {})
    merged[WEB_AUTH_HEADER] = f"Bearer {WEB_TOKEN_STATE.token}"
    merged[WEB_CSRF_HEADER] = WEB_TOKEN_STATE.csrf_token
    return merged


def build_review_handler(**kwargs: object) -> type:
    return build_handler(web_token_state=WEB_TOKEN_STATE, **kwargs)


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


def write_scene_manifest(root: Path, entries: list[dict[str, str]]) -> Path:
    path = root / REVIEW_SCENE_MAP_FILENAME
    path.write_text(
        json.dumps({"schema_version": 1, "scene_inventory": entries}) + "\n",
        encoding="utf-8",
    )
    return path


class ReviewBridgeLiveServerTests(unittest.TestCase):
    def test_default_review_context_unavailable_returns_review_import_error_packet(
        self,
    ) -> None:
        unavailable = ReviewPacketImportError(
            "REVIEW_IMPORT_CONTEXT_UNAVAILABLE",
            "Unable to determine the current baseline for review import.",
        )
        with (
            patch(
                "wild_boar_proxy.web_design_live_server.default_review_import_context",
                side_effect=unavailable,
            ),
            patch(
                "wild_boar_proxy.web_design_live_server.default_review_apply_context",
                side_effect=unavailable,
            ),
        ):
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_review_handler(),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                imported = json.loads(
                    post_json(f"{base}/api/review-command", import_command_payload())
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        self.assertEqual(imported["status"], "command_error")
        self.assertEqual(
            imported["machine_error_code"],
            "REVIEW_IMPORT_CONTEXT_UNAVAILABLE",
        )
        self.assertEqual(imported["changed_files"], [])
        self.assertEqual(imported["next_action"], "fix_command_payload")

    def test_review_command_and_query_surfaces_stay_split(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_review_handler(review_import_context=IMPORT_CONTEXT),
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
            build_review_handler(review_import_context=IMPORT_CONTEXT),
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
                headers=web_post_headers({"Content-Type": "application/json"}),
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
            build_review_handler(review_import_context=IMPORT_CONTEXT),
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
            self.assertEqual(result["machine_error_code"], "REVIEW_APPLY_PREFLIGHT_REQUIRED")
            self.assertEqual(json.loads(fetch(f"{base}/api/review-surface"))["status"], "empty")
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_default_server_manifest_does_not_auto_enable_http_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "drafts" / "scene-001.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("old\n", encoding="utf-8")
            scene_map_path = write_scene_manifest(
                root,
                [{"scene_id": "scene-001", "path": "drafts/scene-001.md"}],
            )
            default_apply_context = ReviewApplyContext(
                project_id="project-alpha",
                baseline_hash="sha256:baseline-alpha",
                project_root=root.resolve(),
                scene_map_path=scene_map_path,
                scene_inventory=(
                    ReviewSceneInventoryEntry(
                        scene_id="scene-001",
                        path="drafts/scene-001.md",
                    ),
                ),
                source_status="ok",
            )
            with patch(
                "wild_boar_proxy.web_design_live_server.default_review_apply_context",
                return_value=default_apply_context,
            ):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", free_port()),
                    build_review_handler(review_import_context=IMPORT_CONTEXT, static_dir=root),
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                try:
                    post_json(
                        f"{base}/api/review-command",
                        import_command_payload(
                            payload={
                                "review_packet": review_packet(
                                    review_items=[
                                        {
                                            "id": "change-1",
                                            "kind": "exact_text",
                                            "scene_id": "scene-001",
                                            "before": "old",
                                            "after": "new",
                                        }
                                    ]
                                )
                            }
                        ),
                    )
                    blocked = json.loads(
                        post_json(
                            f"{base}/api/review-command",
                            {"command_id": "apply_exact_text_change", "payload": {}},
                        )
                    )
                    surface = json.loads(fetch(f"{base}/api/review-surface"))
                    self.assertEqual(blocked["status"], "blocked")
                    self.assertEqual(
                        blocked["machine_error_code"],
                        "REVIEW_APPLY_PREFLIGHT_REQUIRED",
                    )
                    self.assertEqual(target.read_text(encoding="utf-8"), "old\n")
                    self.assertEqual(
                        surface["apply_preflight"]["machine_error_code"],
                        "REVIEW_APPLY_TARGET_RESOLVED_ADMITTED",
                    )
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()

    def test_review_surface_does_not_expose_apply_preflight_without_explicit_context(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", free_port()),
            build_review_handler(review_import_context=IMPORT_CONTEXT),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            post_json(f"{base}/api/review-command", import_command_payload())
            surface = json.loads(fetch(f"{base}/api/review-surface"))
            self.assertNotIn("apply_preflight", surface)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_review_surface_exposes_zero_write_apply_preflight_when_context_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "drafts" / "scene-001.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("old\n", encoding="utf-8")
            scene_map_path = write_scene_manifest(
                root,
                [{"scene_id": "scene-001", "path": "drafts/scene-001.md"}],
            )
            apply_context = ReviewApplyContext(
                project_id="project-alpha",
                baseline_hash="sha256:baseline-alpha",
                project_root=root.resolve(),
                scene_map_path=scene_map_path,
                scene_inventory=(
                    ReviewSceneInventoryEntry(
                        scene_id="scene-001",
                        path="drafts/scene-001.md",
                    ),
                ),
                source_status="ok",
            )
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_review_handler(
                    review_import_context=IMPORT_CONTEXT,
                    review_apply_context=apply_context,
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                post_json(
                    f"{base}/api/review-command",
                    import_command_payload(
                        payload={
                            "review_packet": review_packet(
                                review_items=[
                                    {
                                        "id": "change-1",
                                        "kind": "exact_text",
                                        "scene_id": "scene-001",
                                        "before": "old",
                                        "after": "new",
                                    }
                                ]
                            )
                        }
                    ),
                )
                surface = json.loads(fetch(f"{base}/api/review-surface"))
                preflight = surface["apply_preflight"]
                self.assertEqual(preflight["status"], "ok")
                self.assertEqual(
                    preflight["machine_error_code"],
                    "REVIEW_APPLY_TARGET_RESOLVED_ADMITTED",
                )
                self.assertTrue(preflight["data"]["preflight_only"])
                self.assertFalse(preflight["data"]["write_permitted_now"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_review_surface_rejects_browser_owned_apply_target_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "drafts" / "scene-001.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("old\n", encoding="utf-8")
            scene_map_path = write_scene_manifest(
                root,
                [{"scene_id": "scene-001", "path": "drafts/scene-001.md"}],
            )
            apply_context = ReviewApplyContext(
                project_id="project-alpha",
                baseline_hash="sha256:baseline-alpha",
                project_root=root.resolve(),
                scene_map_path=scene_map_path,
                scene_inventory=(
                    ReviewSceneInventoryEntry(
                        scene_id="scene-001",
                        path="drafts/scene-001.md",
                    ),
                ),
                source_status="ok",
            )
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_review_handler(
                    review_import_context=IMPORT_CONTEXT,
                    review_apply_context=apply_context,
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                post_json(
                    f"{base}/api/review-command",
                    import_command_payload(
                        payload={
                            "review_packet": review_packet(
                                review_items=[
                                    {
                                        "id": "change-1",
                                        "kind": "exact_text",
                                        "scene_id": "scene-001",
                                        "before": "old",
                                        "after": "new",
                                    }
                                ]
                            )
                        }
                    ),
                )
                surface = json.loads(fetch(f"{base}/api/review-surface?path=/tmp/injected"))
                preflight = surface["apply_preflight"]
                self.assertEqual(preflight["status"], "blocked")
                self.assertEqual(
                    preflight["machine_error_code"],
                    "REVIEW_APPLY_BROWSER_FIELD_REJECTED",
                )
                self.assertIn("path", preflight["data"]["forbidden_browser_fields"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_apply_exact_text_change_succeeds_through_http_with_explicit_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "drafts" / "scene-001.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("old\n", encoding="utf-8")
            scene_map_path = write_scene_manifest(
                root,
                [{"scene_id": "scene-001", "path": "drafts/scene-001.md"}],
            )
            apply_context = ReviewApplyContext(
                project_id="project-alpha",
                baseline_hash="sha256:baseline-alpha",
                project_root=root.resolve(),
                scene_map_path=scene_map_path,
                scene_inventory=(
                    ReviewSceneInventoryEntry(
                        scene_id="scene-001",
                        path="drafts/scene-001.md",
                    ),
                ),
                source_status="ok",
            )
            server = ThreadingHTTPServer(
                ("127.0.0.1", free_port()),
                build_review_handler(
                    review_import_context=IMPORT_CONTEXT,
                    review_apply_context=apply_context,
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                post_json(
                    f"{base}/api/review-command",
                    import_command_payload(
                        payload={
                            "review_packet": review_packet(
                                review_items=[
                                    {
                                        "id": "change-1",
                                        "kind": "exact_text",
                                        "scene_id": "scene-001",
                                        "before": "old",
                                        "after": "new",
                                    }
                                ]
                            )
                        }
                    ),
                )
                applied = json.loads(
                    post_json(
                        f"{base}/api/review-command",
                        {"command_id": "apply_exact_text_change", "payload": {}},
                    )
                )
                surface = json.loads(fetch(f"{base}/api/review-surface"))
                self.assertEqual(applied["status"], "ok")
                self.assertEqual(applied["machine_error_code"], "OK")
                self.assertEqual(len(applied["changed_files"]), 1)
                self.assertTrue(applied["data"]["write_performed"])
                self.assertEqual(
                    applied["data"]["receipt"]["receipt_kind"],
                    "review_exact_text_apply_receipt",
                )
                self.assertTrue(applied["data"]["receipt"]["rollback_snapshot_captured"])
                self.assertEqual(applied["data"]["rollback_outcome"], "not_needed")
                self.assertEqual(target.read_text(encoding="utf-8"), "new\n")
                self.assertEqual(surface["review_surface"]["text_changes"], [])
                self.assertEqual(
                    surface["review_surface"]["diagnostics"][-1]["code"],
                    "exact-text-applied",
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
