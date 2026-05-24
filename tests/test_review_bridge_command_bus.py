# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from wild_boar_proxy.review_bridge_apply_admission import (
    REVIEW_SCENE_MAP_FILENAME,
    ReviewApplyContext,
    ReviewSceneInventoryEntry,
)
from wild_boar_proxy.review_bridge_command_bus import (
    ALLOWLIST,
    execute_review_command,
    review_allowlist_metadata,
)
from wild_boar_proxy.review_bridge_exact_text_apply import ReviewExactTextApplyResult
from wild_boar_proxy.review_bridge_packet_import import ReviewImportContext
from wild_boar_proxy.review_bridge_session_store import ReviewQueryBridge, ReviewSessionStore


IMPORT_CONTEXT = ReviewImportContext(
    project_id="project-alpha",
    baseline_hash="sha256:baseline-alpha",
)


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


def apply_review_packet(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "project_id": "project-alpha",
        "baseline_hash": "sha256:baseline-alpha",
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


class ReviewBridgeCommandBusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReviewSessionStore()
        self.query = ReviewQueryBridge(self.store)

    def test_allowlist_is_explicit_and_apply_is_reserved(self) -> None:
        self.assertEqual(
            set(ALLOWLIST),
            {"import_review_packet", "clear_review_session", "apply_exact_text_change"},
        )
        self.assertTrue(ALLOWLIST["apply_exact_text_change"].runtime_enabled)
        self.assertIn(
            {
                "command_id": "apply_exact_text_change",
                "required_args": [],
                "allowed_args": [],
                "runtime_enabled": True,
            },
            review_allowlist_metadata(),
        )

    def test_import_review_packet_is_admitted_through_command_bus(self) -> None:
        result = execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": review_packet()},
            import_context=IMPORT_CONTEXT,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        self.assertEqual(result["changed_files"], [])
        self.assertEqual(result["next_action"], "query_review_surface")

        surface = self.query.get_review_surface()
        self.assertEqual(surface["status"], "ok")
        self.assertTrue(surface["session_present"])
        self.assertEqual(surface["project_id"], "project-alpha")
        self.assertTrue(str(surface["session_id"]).startswith("review-import-"))
        self.assertEqual(surface["baseline_hash"], "sha256:baseline-alpha")
        self.assertTrue(str(surface["source_packet_hash"]).startswith("sha256:"))
        self.assertEqual(surface["review_surface"]["items"][0]["id"], "change-1")
        self.assertEqual(surface["revision_session"]["mode"], "review_only")
        self.assertIsInstance(surface["created_at"], str)

    def test_clear_review_session_runs_through_command_bus(self) -> None:
        execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": review_packet()},
            import_context=IMPORT_CONTEXT,
        )

        cleared = execute_review_command(self.store, "clear_review_session", payload={})

        self.assertEqual(cleared["status"], "ok")
        self.assertEqual(cleared["machine_error_code"], "OK")
        self.assertEqual(cleared["changed_files"], [])
        self.assertEqual(cleared["data"]["cleared"], True)
        self.assertEqual(
            self.query.get_review_surface(),
            {
                "status": "empty",
                "machine_error_code": "REVIEW_SESSION_EMPTY",
                "session_present": False,
                "review_surface": None,
                "revision_session": None,
            },
        )

    def test_apply_exact_text_change_blocks_without_apply_context(self) -> None:
        result = execute_review_command(
            self.store,
            "apply_exact_text_change",
            payload={},
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["machine_error_code"], "REVIEW_APPLY_PREFLIGHT_REQUIRED")
        self.assertEqual(result["changed_files"], [])
        self.assertFalse(self.store.has_active_session())

    def test_apply_exact_text_change_blocks_closed_session_with_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            result = execute_review_command(
                self.store,
                "apply_exact_text_change",
                payload={},
                apply_context=apply_context,
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["machine_error_code"], "REVIEW_APPLY_SESSION_CLOSED")
        self.assertEqual(result["changed_files"], [])
        self.assertFalse(result["data"]["write_performed"])

    def test_apply_exact_text_change_blocks_stale_baseline(self) -> None:
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
                baseline_hash="sha256:baseline-beta",
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
                payload={"review_packet": apply_review_packet()},
                import_context=IMPORT_CONTEXT,
            )

            result = execute_review_command(
                self.store,
                "apply_exact_text_change",
                payload={},
                apply_context=apply_context,
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["machine_error_code"], "REVIEW_APPLY_BASELINE_STALE")
        self.assertEqual(result["changed_files"], [])
        self.assertFalse(result["data"]["write_performed"])

    def test_apply_exact_text_change_updates_one_file_and_refreshes_surface(self) -> None:
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
            execute_review_command(
                self.store,
                "import_review_packet",
                payload={"review_packet": apply_review_packet()},
                import_context=IMPORT_CONTEXT,
            )

            result = execute_review_command(
                self.store,
                "apply_exact_text_change",
                payload={},
                apply_context=apply_context,
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["machine_error_code"], "OK")
            self.assertEqual(len(result["changed_files"]), 1)
            self.assertIn("scene-001.md", result["changed_files"][0])
            self.assertTrue(result["data"]["write_performed"])
            self.assertEqual(result["data"]["write_count"], 1)
            self.assertEqual(result["data"]["receipt"]["receipt_kind"], "review_exact_text_apply_receipt")
            self.assertEqual(result["data"]["receipt"]["write_count"], 1)
            self.assertEqual(result["data"]["receipt"]["scene_path_ref"], "drafts/scene-001.md")
            self.assertTrue(result["data"]["receipt"]["rollback_snapshot_captured"])
            self.assertFalse(result["data"]["receipt"]["rollback_attempted"])
            self.assertEqual(result["data"]["rollback_outcome"], "not_needed")
            self.assertTrue(result["data"]["rollback_snapshot_captured"])
            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")
            surface = self.query.get_review_surface()
            self.assertEqual(surface["review_surface"]["text_changes"], [])
            self.assertTrue(surface["review_surface"]["manuscript_write_performed"])
            self.assertEqual(
                surface["review_surface"]["diagnostics"][-1]["code"],
                "exact-text-applied",
            )

    def test_apply_exact_text_change_blocks_no_match_and_duplicate_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "drafts" / "scene-001.md"
            target.parent.mkdir(parents=True, exist_ok=True)
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

            target.write_text("different\n", encoding="utf-8")
            execute_review_command(
                self.store,
                "import_review_packet",
                payload={"review_packet": apply_review_packet()},
                import_context=IMPORT_CONTEXT,
            )
            no_match = execute_review_command(
                self.store,
                "apply_exact_text_change",
                payload={},
                apply_context=apply_context,
            )
            self.assertEqual(no_match["status"], "blocked")
            self.assertEqual(no_match["machine_error_code"], "REVIEW_APPLY_NO_MATCH")
            self.assertEqual(no_match["changed_files"], [])
            self.assertFalse(no_match["data"]["write_performed"])
            self.assertFalse(no_match["data"]["rollback_snapshot_captured"])

            target.write_text("old old\n", encoding="utf-8")
            duplicate = execute_review_command(
                self.store,
                "apply_exact_text_change",
                payload={},
                apply_context=apply_context,
            )
            self.assertEqual(duplicate["status"], "blocked")
            self.assertEqual(duplicate["machine_error_code"], "REVIEW_APPLY_DUPLICATE_MATCH")
            self.assertEqual(duplicate["changed_files"], [])
            self.assertFalse(duplicate["data"]["write_performed"])

            target.write_text("ababa", encoding="utf-8")
            self.store = ReviewSessionStore()
            self.query = ReviewQueryBridge(self.store)
            execute_review_command(
                self.store,
                "import_review_packet",
                payload={
                    "review_packet": apply_review_packet(
                        review_items=[
                            {
                                "id": "change-1",
                                "kind": "exact_text",
                                "scene_id": "scene-001",
                                "before": "aba",
                                "after": "xyz",
                            }
                        ]
                    )
                },
                import_context=IMPORT_CONTEXT,
            )
            overlap = execute_review_command(
                self.store,
                "apply_exact_text_change",
                payload={},
                apply_context=apply_context,
            )
            self.assertEqual(overlap["status"], "blocked")
            self.assertEqual(overlap["machine_error_code"], "REVIEW_APPLY_DUPLICATE_MATCH")
            self.assertEqual(overlap["changed_files"], [])
            self.assertFalse(overlap["data"]["write_performed"])

    def test_apply_exact_text_change_holds_store_lock_until_surface_update(self) -> None:
        execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": apply_review_packet()},
            import_context=IMPORT_CONTEXT,
        )
        clear_finished = threading.Event()
        clear_start = threading.Event()
        clear_threads: list[threading.Thread] = []

        def fake_apply(_record: object, *, context: ReviewApplyContext | None) -> ReviewExactTextApplyResult:
            self.assertIsNone(context)

            def clear_in_parallel() -> None:
                clear_start.set()
                self.store._clear_active_session()
                clear_finished.set()

            clear_thread = threading.Thread(target=clear_in_parallel)
            clear_threads.append(clear_thread)
            clear_thread.start()
            self.assertTrue(clear_start.wait(timeout=1))
            self.assertFalse(clear_finished.wait(timeout=0.05))
            return ReviewExactTextApplyResult(
                status="ok",
                exit_code=0,
                human_message="ok",
                machine_error_code="OK",
                next_action="query_review_surface",
                changed_files=["/tmp/example.md"],
                data={"write_performed": True},
                updated_review_surface={
                    "items": [],
                    "text_changes": [],
                    "diagnostics": [{"code": "exact-text-applied"}],
                },
            )

        with patch(
            "wild_boar_proxy.review_bridge_session_store.apply_exact_text_change",
            side_effect=fake_apply,
        ):
            result = execute_review_command(
                self.store,
                "apply_exact_text_change",
                payload={},
                apply_context=None,
            )

        self.assertEqual(result["status"], "ok")
        for clear_thread in clear_threads:
            clear_thread.join(timeout=1)
        self.assertTrue(clear_finished.is_set())

    def test_query_bridge_is_read_only_and_does_not_expose_mutation_methods(self) -> None:
        self.assertTrue(hasattr(self.query, "get_review_surface"))
        self.assertFalse(hasattr(self.query, "execute_review_command"))
        self.assertFalse(hasattr(self.query, "import_review_packet"))
        self.assertFalse(hasattr(self.query, "clear_review_session"))

    def test_import_rejects_missing_fields_and_unknown_args(self) -> None:
        missing = execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": {"schema_version": 1, "project_id": "project-alpha"}},
            import_context=IMPORT_CONTEXT,
        )
        extra = execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": review_packet(), "packet_text": "{bad-idea}"},
            import_context=IMPORT_CONTEXT,
        )

        self.assertEqual(missing["status"], "command_error")
        self.assertEqual(missing["machine_error_code"], "REVIEW_PACKET_MISSING_FIELD")
        self.assertEqual(extra["status"], "command_error")
        self.assertEqual(extra["machine_error_code"], "REVIEW_COMMAND_UNSUPPORTED_ARGS")

    def test_repeated_query_reads_do_not_mutate_store_state(self) -> None:
        execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": review_packet()},
            import_context=IMPORT_CONTEXT,
        )

        first = self.query.get_review_surface()
        second = self.query.get_review_surface()

        self.assertEqual(first, second)

    def test_unknown_command_is_blocked_as_direct_bypass(self) -> None:
        result = execute_review_command(self.store, "launch_client", payload={})
        self.assertEqual(result["status"], "command_error")
        self.assertEqual(result["machine_error_code"], "REVIEW_COMMAND_NOT_ALLOWLISTED")


if __name__ == "__main__":
    unittest.main()
