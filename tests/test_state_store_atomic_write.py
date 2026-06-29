from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy import state_store


class StateStoreAtomicWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_write_json_commits_with_changed_files_and_schema_version(self) -> None:
        target = self.root / "supervisor-state.json"

        result = state_store.write_json(
            target,
            {"schema_version": 2, "status": "healthy"},
            expected_schema_version=2,
        )

        self.assertTrue(result.committed)
        self.assertEqual(result.target, str(target))
        self.assertEqual(result.changed_files, (str(target),))
        self.assertEqual(result.schema_version, 2)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["status"], "healthy")
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])

    def test_write_json_can_emit_trailing_newline(self) -> None:
        target = self.root / "supervisor-state.json"

        state_store.write_json(
            target,
            {"schema_version": 2, "status": "healthy"},
            expected_schema_version=2,
            trailing_newline=True,
        )

        self.assertTrue(target.read_text(encoding="utf-8").endswith("\n"))
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["status"], "healthy")

    def test_write_uses_unique_temp_names_without_fixed_tmp_collision(self) -> None:
        target = self.root / "backend-registry.json"
        temp_names: list[str] = []
        real_mkstemp = state_store.tempfile.mkstemp

        def recording_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
            fd, name = real_mkstemp(*args, **kwargs)
            temp_names.append(Path(name).name)
            return fd, name

        with mock.patch.object(state_store.tempfile, "mkstemp", recording_mkstemp):
            state_store.write_json(target, {"schema_version": 2}, expected_schema_version=2)
            state_store.write_json(target, {"schema_version": 2}, expected_schema_version=2)

        self.assertEqual(len(temp_names), 2)
        self.assertEqual(len(set(temp_names)), 2)
        self.assertTrue(all(name.startswith(".wbp-tmp-") for name in temp_names))
        self.assertTrue(all(name.endswith(".backend-registry.json.tmp") for name in temp_names))
        self.assertTrue(all(not Path(name).match("*.json") for name in temp_names))

    def test_successful_write_publishes_with_os_replace(self) -> None:
        target = self.root / "supervisor-state.json"
        real_replace = state_store.os.replace
        replacements: list[tuple[Path, Path]] = []

        def recording_replace(src: object, dst: object) -> None:
            replacements.append((Path(src), Path(dst)))
            real_replace(src, dst)

        with mock.patch.object(state_store.os, "replace", recording_replace):
            state_store.write_json(
                target,
                {"schema_version": 2, "status": "published"},
                expected_schema_version=2,
            )

        self.assertEqual(len(replacements), 1)
        temp_path, replaced_target = replacements[0]
        self.assertEqual(replaced_target, target)
        self.assertEqual(temp_path.parent, target.parent)
        self.assertTrue(temp_path.name.startswith(".wbp-tmp-"))
        self.assertTrue(temp_path.name.endswith(".supervisor-state.json.tmp"))
        self.assertFalse(temp_path.match("*.json"))
        self.assertFalse(temp_path.exists())
        self.assertEqual(
            json.loads(target.read_text(encoding="utf-8"))["status"],
            "published",
        )

    def test_json_payload_must_be_object(self) -> None:
        target = self.root / "supervisor-state.json"

        with self.assertRaises(state_store.StateStoreError) as raised:
            state_store.write_json(target, ["not-object"])  # type: ignore[arg-type]

        self.assertEqual(raised.exception.machine_error_code, state_store.STATE_PAYLOAD_INVALID)
        self.assertFalse(target.exists())

    def test_missing_schema_version_blocks_before_publish(self) -> None:
        target = self.root / "supervisor-state.json"
        target.write_text('{"schema_version": 2, "status": "old"}', encoding="utf-8")
        before = target.read_text(encoding="utf-8")

        with self.assertRaises(state_store.StateStoreError) as raised:
            state_store.write_json(target, {"status": "new"}, expected_schema_version=2)

        self.assertEqual(raised.exception.machine_error_code, state_store.STATE_SCHEMA_MISSING)
        self.assertEqual(target.read_text(encoding="utf-8"), before)
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])

    def test_unsupported_schema_version_blocks_before_publish(self) -> None:
        target = self.root / "backend-registry.json"
        target.write_text('{"schema_version": 2, "status": "old"}', encoding="utf-8")
        before = target.read_text(encoding="utf-8")

        with self.assertRaises(state_store.StateStoreError) as raised:
            state_store.write_json(target, {"schema_version": 3}, expected_schema_version=2)

        self.assertEqual(
            raised.exception.machine_error_code,
            state_store.STATE_SCHEMA_UNSUPPORTED,
        )
        self.assertEqual(target.read_text(encoding="utf-8"), before)
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])

    def test_write_text_supports_mode_files_and_chmod_before_publish(self) -> None:
        target = self.root / "runtime-mode.txt"

        result = state_store.write_text(target, "stable", mode=0o600)

        self.assertTrue(result.committed)
        self.assertEqual(result.changed_files, (str(target),))
        self.assertEqual(result.schema_version, None)
        self.assertEqual(target.read_text(encoding="utf-8"), "stable")
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_parent_directory_fsync_is_attempted_best_effort(self) -> None:
        target = self.root / "runtime-effective-mode.txt"
        real_open = state_store.os.open
        real_fsync = state_store.os.fsync
        fsync_paths: list[str] = []
        fsync_kinds: list[str] = []

        def recording_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
            fd = real_open(path, flags, *args, **kwargs)
            if Path(path) == self.root:
                fsync_paths.append(str(path))
            return fd

        def recording_fsync(fd: int) -> None:
            mode = os.fstat(fd).st_mode & 0o170000
            fsync_kinds.append("directory" if mode == 0o040000 else "file")
            real_fsync(fd)

        with (
            mock.patch.object(state_store.os, "open", recording_open),
            mock.patch.object(state_store.os, "fsync", recording_fsync),
        ):
            state_store.write_text(target, "managed")

        self.assertIn(str(self.root), fsync_paths)
        self.assertIn("file", fsync_kinds)
        self.assertIn("directory", fsync_kinds)

    def test_parent_directory_fsync_failure_does_not_fail_committed_write(self) -> None:
        target = self.root / "runtime-effective-mode.txt"
        real_fsync = state_store.os.fsync

        def flaky_fsync(fd: int) -> None:
            try:
                if os.fstat(fd).st_mode & 0o170000 == 0o040000:
                    raise OSError("directory fsync unsupported")
            except OSError:
                raise
            real_fsync(fd)

        with mock.patch.object(state_store.os, "fsync", flaky_fsync):
            result = state_store.write_text(target, "stable")

        self.assertTrue(result.committed)
        self.assertEqual(target.read_text(encoding="utf-8"), "stable")

    def test_failed_current_write_cleans_current_temp_and_keeps_original(self) -> None:
        target = self.root / "supervisor-state.json"
        target.write_text('{"schema_version": 2, "status": "old"}', encoding="utf-8")
        before = target.read_text(encoding="utf-8")
        real_mkstemp = state_store.tempfile.mkstemp
        created_temp: list[Path] = []

        def recording_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
            fd, name = real_mkstemp(*args, **kwargs)
            created_temp.append(Path(name))
            return fd, name

        def failing_replace(src: object, dst: object) -> None:
            raise OSError("replace failed")

        with (
            mock.patch.object(state_store.tempfile, "mkstemp", recording_mkstemp),
            mock.patch.object(state_store.os, "replace", failing_replace),
        ):
            with self.assertRaises(state_store.StateStoreError) as raised:
                state_store.write_json(
                    target,
                    {"schema_version": 2, "status": "new"},
                    expected_schema_version=2,
                )

        self.assertEqual(raised.exception.machine_error_code, state_store.STATE_WRITE_FAILED)
        self.assertEqual(target.read_text(encoding="utf-8"), before)
        self.assertTrue(created_temp)
        self.assertTrue(all(not path.exists() for path in created_temp))
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])


if __name__ == "__main__":
    unittest.main()
