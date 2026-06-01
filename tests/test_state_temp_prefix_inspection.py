from __future__ import annotations

import ast
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from wild_boar_proxy import state_temp_prefix


class StateTempPrefixInspectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.now = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def no_follow(self, path: Path) -> str:
        return str(Path(os.path.abspath(os.path.normpath(os.fspath(path)))))

    def write_file(self, path: Path, payload: bytes = b"x") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def set_mtime(self, path: Path, when: datetime) -> None:
        timestamp = when.timestamp()
        os.utime(path, (timestamp, timestamp), follow_symlinks=False)

    def test_missing_admitted_root_is_clean_empty_and_does_not_create_dir(self) -> None:
        missing_root = self.root / "missing-root"

        with (
            mock.patch.object(Path, "mkdir") as mkdir,
            mock.patch.object(Path, "unlink") as unlink,
            mock.patch.object(Path, "rmdir") as rmdir,
            mock.patch.object(state_temp_prefix.os, "replace") as replace,
        ):
            inspection = state_temp_prefix.inspect_prefixed_temp_artifacts(
                (missing_root,),
                now=self.now,
                stale_ttl_seconds=60,
            )

        self.assertEqual(inspection.candidate_paths, ())
        self.assertEqual(inspection.fresh_paths, ())
        self.assertEqual(inspection.stale_paths, ())
        self.assertEqual(inspection.blocked_paths, ())
        self.assertEqual(inspection.invalid_roots, ())
        self.assertEqual(inspection.artifacts, ())
        self.assertFalse(missing_root.exists())
        mkdir.assert_not_called()
        unlink.assert_not_called()
        rmdir.assert_not_called()
        replace.assert_not_called()

    def test_duplicate_roots_are_deduped(self) -> None:
        candidate = self.write_file(self.root / ".wbp-tmp-state.json", b"temp")
        self.set_mtime(candidate, self.now)

        inspection = state_temp_prefix.inspect_prefixed_temp_artifacts(
            (self.root, self.root),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(inspection.invalid_roots, ())
        self.assertEqual(inspection.candidate_paths, (self.no_follow(candidate),))
        self.assertEqual(inspection.fresh_paths, (self.no_follow(candidate),))
        self.assertEqual(len(inspection.artifacts), 1)

    def test_non_absolute_root_raises_invalid_error(self) -> None:
        with self.assertRaises(state_temp_prefix.StateTempPrefixError) as raised:
            state_temp_prefix.inspect_prefixed_temp_artifacts(
                (Path("relative-root"),),
                now=self.now,
                stale_ttl_seconds=60,
            )

        self.assertEqual(
            raised.exception.machine_error_code,
            state_temp_prefix.STATE_TEMP_PREFIX_INVALID,
        )

    def test_non_directory_root_is_reported_invalid(self) -> None:
        file_root = self.write_file(self.root / "state.json", b"{}")

        inspection = state_temp_prefix.inspect_prefixed_temp_artifacts(
            (file_root,),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(inspection.invalid_roots, (self.no_follow(file_root),))
        self.assertEqual(inspection.candidate_paths, ())

    def test_broken_symlink_root_is_invalid_and_not_treated_as_missing(self) -> None:
        broken_root = self.root / "broken-root"
        missing_target = self.root / "missing-target"
        broken_root.symlink_to(missing_target, target_is_directory=True)

        inspection = state_temp_prefix.inspect_prefixed_temp_artifacts(
            (broken_root,),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(inspection.invalid_roots, (self.no_follow(broken_root),))
        self.assertEqual(inspection.candidate_paths, ())
        self.assertEqual(inspection.artifacts, ())

    def test_matching_direct_child_old_regular_file_is_stale(self) -> None:
        stale = self.write_file(self.root / ".wbp-tmp-old.state.json", b"old")
        self.set_mtime(stale, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))

        inspection = state_temp_prefix.inspect_prefixed_temp_artifacts(
            (self.root,),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(inspection.candidate_paths, (self.no_follow(stale),))
        self.assertEqual(inspection.fresh_paths, ())
        self.assertEqual(inspection.stale_paths, (self.no_follow(stale),))
        self.assertEqual(inspection.blocked_paths, ())
        self.assertEqual(
            inspection.artifacts,
            (
                state_temp_prefix.PrefixedTempArtifact(
                    path=self.no_follow(stale),
                    root=self.no_follow(self.root),
                    stale=True,
                    blocked=False,
                ),
            ),
        )

    def test_matching_direct_child_recent_regular_file_is_fresh(self) -> None:
        fresh = self.write_file(self.root / ".wbp-tmp-new.state.json", b"new")
        self.set_mtime(fresh, self.now)

        inspection = state_temp_prefix.inspect_prefixed_temp_artifacts(
            (self.root,),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(inspection.candidate_paths, (self.no_follow(fresh),))
        self.assertEqual(inspection.fresh_paths, (self.no_follow(fresh),))
        self.assertEqual(inspection.stale_paths, ())
        self.assertEqual(inspection.blocked_paths, ())

    def test_non_matching_siblings_and_nested_prefixed_children_are_ignored(self) -> None:
        self.write_file(self.root / "ordinary.txt", b"ordinary")
        nested = self.root / "nested"
        self.write_file(nested / ".wbp-tmp-nested.state.json", b"nested")

        inspection = state_temp_prefix.inspect_prefixed_temp_artifacts(
            (self.root,),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(inspection.candidate_paths, ())
        self.assertEqual(inspection.fresh_paths, ())
        self.assertEqual(inspection.stale_paths, ())
        self.assertEqual(inspection.blocked_paths, ())

    def test_matching_symlink_child_is_blocked_without_following_target(self) -> None:
        outside_target = self.write_file(self.root / "outside.txt", b"outside")
        symlink_path = self.root / ".wbp-tmp-link.state.json"
        symlink_path.symlink_to(outside_target)

        inspection = state_temp_prefix.inspect_prefixed_temp_artifacts(
            (self.root,),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(inspection.candidate_paths, ())
        self.assertEqual(inspection.fresh_paths, ())
        self.assertEqual(inspection.stale_paths, ())
        self.assertEqual(inspection.blocked_paths, (self.no_follow(symlink_path),))
        self.assertEqual(
            inspection.artifacts,
            (
                state_temp_prefix.PrefixedTempArtifact(
                    path=self.no_follow(symlink_path),
                    root=self.no_follow(self.root),
                    stale=False,
                    blocked=True,
                ),
            ),
        )

    def test_matching_directory_child_is_blocked(self) -> None:
        blocked_dir = self.root / ".wbp-tmp-dir"
        blocked_dir.mkdir()

        inspection = state_temp_prefix.inspect_prefixed_temp_artifacts(
            (self.root,),
            now=self.now,
            stale_ttl_seconds=60,
        )

        self.assertEqual(inspection.candidate_paths, ())
        self.assertEqual(inspection.blocked_paths, (self.no_follow(blocked_dir),))
        self.assertEqual(inspection.stale_paths, ())

    def test_invalid_prefix_and_ttl_raise_invalid_error(self) -> None:
        with self.assertRaises(state_temp_prefix.StateTempPrefixError) as bad_prefix:
            state_temp_prefix.inspect_prefixed_temp_artifacts(
                (self.root,),
                prefix="",
                now=self.now,
                stale_ttl_seconds=60,
            )
        self.assertEqual(
            bad_prefix.exception.machine_error_code,
            state_temp_prefix.STATE_TEMP_PREFIX_INVALID,
        )

        with self.assertRaises(state_temp_prefix.StateTempPrefixError) as bad_ttl:
            state_temp_prefix.inspect_prefixed_temp_artifacts(
                (self.root,),
                now=self.now,
                stale_ttl_seconds=-1,
            )
        self.assertEqual(
            bad_ttl.exception.machine_error_code,
            state_temp_prefix.STATE_TEMP_PREFIX_INVALID,
        )

    def test_naive_now_raises_invalid_error(self) -> None:
        with self.assertRaises(state_temp_prefix.StateTempPrefixError) as raised:
            state_temp_prefix.inspect_prefixed_temp_artifacts(
                (self.root,),
                now=datetime(2026, 6, 2, 12, 0, 0),
                stale_ttl_seconds=60,
            )

        self.assertEqual(
            raised.exception.machine_error_code,
            state_temp_prefix.STATE_TEMP_PREFIX_INVALID,
        )

    def test_dataclasses_do_not_expose_packet_startup_or_rollback_fields(self) -> None:
        inspection_fields = set(state_temp_prefix.PrefixedTempInspection.__dataclass_fields__)
        artifact_fields = set(state_temp_prefix.PrefixedTempArtifact.__dataclass_fields__)

        forbidden = {
            "auto_recovered",
            "changed_files",
            "effect",
            "exit_code",
            "human_message",
            "liveness",
            "next_action",
            "operator_action",
            "repair_required",
            "rollback_available",
            "rollback_id",
            "severity",
            "startup_clean",
            "status",
        }
        self.assertTrue(forbidden.isdisjoint(inspection_fields))
        self.assertTrue(forbidden.isdisjoint(artifact_fields))

    def test_module_does_not_import_runtime_layers(self) -> None:
        source = Path(state_temp_prefix.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        forbidden = {
            "wild_boar_proxy.runtime",
            "wild_boar_proxy.operator_surface",
            "wild_boar_proxy.cli",
            "wild_boar_proxy.web_design_live_server",
            "wild_boar_proxy.command_effects",
        }
        self.assertTrue(forbidden.isdisjoint(imported_modules))


if __name__ == "__main__":
    unittest.main()
