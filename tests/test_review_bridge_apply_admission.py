# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from wild_boar_proxy.review_bridge_apply_admission import (
    REVIEW_SCENE_MAP_FILENAME,
    ReviewApplyContext,
    ReviewSceneInventoryEntry,
    default_review_apply_context,
)
from wild_boar_proxy.review_bridge_command_bus import execute_review_command
from wild_boar_proxy.review_bridge_packet_import import ReviewImportContext
from wild_boar_proxy.review_bridge_session_store import ReviewQueryBridge, ReviewSessionStore


IMPORT_CONTEXT = ReviewImportContext(
    project_id="project-alpha",
    baseline_hash="sha256:baseline-alpha",
)


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
            }
        ],
        "orphan_comments": [],
        "diagnostics": [],
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


class ReviewBridgeApplyAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReviewSessionStore()

    def test_default_review_apply_context_loads_server_owned_scene_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project-alpha"
            root.mkdir(parents=True, exist_ok=True)
            (root / "drafts").mkdir()
            (root / "drafts" / "scene-001.md").write_text("old\n", encoding="utf-8")
            write_scene_manifest(
                root,
                [{"scene_id": "scene-001", "path": "drafts/scene-001.md"}],
            )
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "init"],
                cwd=root,
                check=True,
                capture_output=True,
            )

            context = default_review_apply_context(root)

            self.assertEqual(context.project_id, "project-alpha")
            self.assertEqual(context.project_root, root.resolve())
            self.assertEqual(context.source_status, "ok")
            self.assertEqual(context.scene_inventory[0].scene_id, "scene-001")
            self.assertEqual(context.scene_inventory[0].path, "drafts/scene-001.md")

    def test_query_surface_reports_admitted_zero_write_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "drafts" / "scene-001.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("old\n", encoding="utf-8")
            scene_map_path = write_scene_manifest(
                root,
                [{"scene_id": "scene-001", "path": "drafts/scene-001.md"}],
            )
            context = ReviewApplyContext(
                project_id=IMPORT_CONTEXT.project_id,
                baseline_hash=IMPORT_CONTEXT.baseline_hash,
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

            result = execute_review_command(
                self.store,
                "import_review_packet",
                payload={"review_packet": review_packet()},
                import_context=IMPORT_CONTEXT,
            )
            self.assertEqual(result["status"], "ok")

            surface = ReviewQueryBridge(
                self.store,
                review_apply_context=context,
            ).get_review_surface()
            preflight = surface["apply_preflight"]
            self.assertEqual(preflight["status"], "ok")
            self.assertEqual(
                preflight["machine_error_code"],
                "REVIEW_APPLY_TARGET_RESOLVED_ADMITTED",
            )
            self.assertTrue(preflight["data"]["preflight_only"])
            self.assertTrue(preflight["data"]["future_apply_admissible"])
            self.assertFalse(preflight["data"]["write_permitted_now"])
            self.assertEqual(preflight["data"]["scene_path_ref"], "drafts/scene-001.md")

    def test_query_surface_blocks_unknown_scene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scene_map_path = write_scene_manifest(root, [])
            context = ReviewApplyContext(
                project_id=IMPORT_CONTEXT.project_id,
                baseline_hash=IMPORT_CONTEXT.baseline_hash,
                project_root=root.resolve(),
                scene_map_path=scene_map_path,
                scene_inventory=(),
                source_status="ok",
            )
            execute_review_command(
                self.store,
                "import_review_packet",
                payload={"review_packet": review_packet()},
                import_context=IMPORT_CONTEXT,
            )

            preflight = ReviewQueryBridge(
                self.store,
                review_apply_context=context,
            ).get_review_surface()["apply_preflight"]
            self.assertEqual(preflight["status"], "blocked")
            self.assertEqual(preflight["machine_error_code"], "REVIEW_APPLY_TARGET_SCENE_UNKNOWN")

    def test_query_surface_blocks_ambiguous_scene_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.md").write_text("old\n", encoding="utf-8")
            (root / "b.md").write_text("old\n", encoding="utf-8")
            scene_map_path = write_scene_manifest(
                root,
                [
                    {"scene_id": "scene-001", "path": "a.md"},
                    {"scene_id": "scene-001", "path": "b.md"},
                ],
            )
            context = ReviewApplyContext(
                project_id=IMPORT_CONTEXT.project_id,
                baseline_hash=IMPORT_CONTEXT.baseline_hash,
                project_root=root.resolve(),
                scene_map_path=scene_map_path,
                scene_inventory=(
                    ReviewSceneInventoryEntry(scene_id="scene-001", path="a.md"),
                    ReviewSceneInventoryEntry(scene_id="scene-001", path="b.md"),
                ),
                source_status="ok",
            )
            execute_review_command(
                self.store,
                "import_review_packet",
                payload={"review_packet": review_packet()},
                import_context=IMPORT_CONTEXT,
            )

            preflight = ReviewQueryBridge(
                self.store,
                review_apply_context=context,
            ).get_review_surface()["apply_preflight"]
            self.assertEqual(preflight["status"], "blocked")
            self.assertEqual(preflight["machine_error_code"], "REVIEW_APPLY_TARGET_AMBIGUOUS")

    def test_query_surface_blocks_missing_exact_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scene_map_path = write_scene_manifest(
                root,
                [{"scene_id": "scene-001", "path": "drafts/scene-001.md"}],
            )
            context = ReviewApplyContext(
                project_id=IMPORT_CONTEXT.project_id,
                baseline_hash=IMPORT_CONTEXT.baseline_hash,
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
            execute_review_command(
                self.store,
                "import_review_packet",
                payload={"review_packet": review_packet(review_items=[{"id": "change-1", "kind": "exact_text"}])},
                import_context=IMPORT_CONTEXT,
            )

            preflight = ReviewQueryBridge(
                self.store,
                review_apply_context=context,
            ).get_review_surface()["apply_preflight"]
            self.assertEqual(preflight["status"], "blocked")
            self.assertEqual(preflight["machine_error_code"], "REVIEW_APPLY_EXACT_FIELDS_MISSING")

    def test_query_surface_blocks_stale_baseline_and_closed_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scene_map_path = write_scene_manifest(root, [])
            stale_context = ReviewApplyContext(
                project_id=IMPORT_CONTEXT.project_id,
                baseline_hash="sha256:other",
                project_root=root.resolve(),
                scene_map_path=scene_map_path,
                scene_inventory=(),
                source_status="ok",
            )
            execute_review_command(
                self.store,
                "import_review_packet",
                payload={"review_packet": review_packet()},
                import_context=IMPORT_CONTEXT,
            )

            stale = ReviewQueryBridge(
                self.store,
                review_apply_context=stale_context,
            ).get_review_surface()["apply_preflight"]
            self.assertEqual(stale["machine_error_code"], "REVIEW_APPLY_BASELINE_STALE")

            empty = ReviewQueryBridge(
                ReviewSessionStore(),
                review_apply_context=stale_context,
            ).get_review_surface()["apply_preflight"]
            self.assertEqual(empty["machine_error_code"], "REVIEW_APPLY_SESSION_CLOSED")

    def test_query_surface_rejects_forbidden_browser_fields_and_outside_project_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root.parent / "outside.md"
            outside.write_text("old\n", encoding="utf-8")
            scene_map_path = write_scene_manifest(
                root,
                [{"scene_id": "scene-001", "path": "../outside.md"}],
            )
            context = ReviewApplyContext(
                project_id=IMPORT_CONTEXT.project_id,
                baseline_hash=IMPORT_CONTEXT.baseline_hash,
                project_root=root.resolve(),
                scene_map_path=scene_map_path,
                scene_inventory=(
                    ReviewSceneInventoryEntry(scene_id="scene-001", path="../outside.md"),
                ),
                source_status="ok",
            )
            execute_review_command(
                self.store,
                "import_review_packet",
                payload={"review_packet": review_packet()},
                import_context=IMPORT_CONTEXT,
            )

            blocked_browser = ReviewQueryBridge(
                self.store,
                review_apply_context=context,
            ).get_review_surface({"path": ["/tmp/injected"]})["apply_preflight"]
            self.assertEqual(
                blocked_browser["machine_error_code"],
                "REVIEW_APPLY_BROWSER_FIELD_REJECTED",
            )

            blocked_path = ReviewQueryBridge(
                self.store,
                review_apply_context=context,
            ).get_review_surface()["apply_preflight"]
            self.assertEqual(
                blocked_path["machine_error_code"],
                "REVIEW_APPLY_TARGET_PATH_OUTSIDE_PROJECT",
            )


if __name__ == "__main__":
    unittest.main()
