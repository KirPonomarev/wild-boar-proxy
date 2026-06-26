# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy import runtime as runtime_mod
from wild_boar_proxy import state_store


class RuntimeAtomicWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_write_text_atomic_uses_unique_state_store_temp_names(self) -> None:
        target = self.root / "runtime-mode.txt"
        temp_names: list[str] = []
        real_mkstemp = runtime_mod.state_store.tempfile.mkstemp

        def recording_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
            fd, name = real_mkstemp(*args, **kwargs)
            temp_names.append(Path(name).name)
            return fd, name

        with mock.patch.object(
            runtime_mod.state_store.tempfile, "mkstemp", recording_mkstemp
        ):
            runtime_mod.write_text_atomic(target, "managed")
            runtime_mod.write_text_atomic(target, "stable")

        self.assertEqual(target.read_text(encoding="utf-8"), "stable\n")
        self.assertEqual(len(temp_names), 2)
        self.assertEqual(len(set(temp_names)), 2)
        self.assertTrue(all(name.startswith(".wbp-tmp-") for name in temp_names))
        self.assertTrue(all(name.endswith(".runtime-mode.txt") for name in temp_names))
        self.assertNotIn(".runtime-mode.txt.tmp", temp_names)
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])

    def test_write_text_atomic_fsyncs_file_and_parent_directory(self) -> None:
        target = self.root / "runtime-effective-mode.txt"
        real_open = runtime_mod.state_store.os.open
        real_fsync = runtime_mod.state_store.os.fsync
        fsync_paths: list[str] = []
        fsync_kinds: list[str] = []

        def recording_open(
            path: object, flags: int, *args: object, **kwargs: object
        ) -> int:
            fd = real_open(path, flags, *args, **kwargs)
            if Path(path) == self.root:
                fsync_paths.append(str(path))
            return fd

        def recording_fsync(fd: int) -> None:
            mode = os.fstat(fd).st_mode & 0o170000
            fsync_kinds.append("directory" if mode == 0o040000 else "file")
            real_fsync(fd)

        with (
            mock.patch.object(runtime_mod.state_store.os, "open", recording_open),
            mock.patch.object(runtime_mod.state_store.os, "fsync", recording_fsync),
        ):
            runtime_mod.write_text_atomic(target, "stable")

        self.assertEqual(target.read_text(encoding="utf-8"), "stable\n")
        self.assertIn(str(self.root), fsync_paths)
        self.assertIn("file", fsync_kinds)
        self.assertIn("directory", fsync_kinds)

    def test_failed_write_cleans_temp_and_keeps_original_runtime_truth(self) -> None:
        target = self.root / "runtime-effective-mode.txt"
        target.write_text("managed\n", encoding="utf-8")
        created_temp: list[Path] = []
        real_mkstemp = runtime_mod.state_store.tempfile.mkstemp

        def recording_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
            fd, name = real_mkstemp(*args, **kwargs)
            created_temp.append(Path(name))
            return fd, name

        def failing_replace(src: object, dst: object) -> None:
            raise OSError("replace failed")

        with (
            mock.patch.object(
                runtime_mod.state_store.tempfile, "mkstemp", recording_mkstemp
            ),
            mock.patch.object(runtime_mod.state_store.os, "replace", failing_replace),
        ):
            with self.assertRaises(state_store.StateStoreError) as raised:
                runtime_mod.write_text_atomic(target, "stable")

        self.assertEqual(
            raised.exception.machine_error_code, state_store.STATE_WRITE_FAILED
        )
        self.assertEqual(target.read_text(encoding="utf-8"), "managed\n")
        self.assertTrue(created_temp)
        self.assertTrue(all(not path.exists() for path in created_temp))
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])

    def test_write_executable_text_atomic_sets_mode_before_publish(self) -> None:
        target = self.root / "codex-custom-launch.sh"
        real_replace = runtime_mod.state_store.os.replace
        published_modes: list[int] = []

        def recording_replace(src: object, dst: object) -> None:
            published_modes.append(Path(src).stat().st_mode & 0o777)
            real_replace(src, dst)

        with mock.patch.object(runtime_mod.state_store.os, "replace", recording_replace):
            runtime_mod.write_executable_text_atomic(target, "#!/bin/sh\nexit 0")

        self.assertEqual(target.read_text(encoding="utf-8"), "#!/bin/sh\nexit 0\n")
        self.assertEqual(published_modes, [0o755])
        self.assertEqual(target.stat().st_mode & 0o777, 0o755)

    def test_restore_path_state_uses_unique_state_store_temp_names(self) -> None:
        target = self.root / "supervisor-state.json"
        temp_names: list[str] = []
        real_mkstemp = runtime_mod.state_store.tempfile.mkstemp

        def recording_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
            fd, name = real_mkstemp(*args, **kwargs)
            temp_names.append(Path(name).name)
            return fd, name

        with mock.patch.object(
            runtime_mod.state_store.tempfile, "mkstemp", recording_mkstemp
        ):
            runtime_mod.restore_path_state(
                target,
                {"state": "file", "text": '{"status": "old"}\n', "mode": 0o640},
            )
            runtime_mod.restore_path_state(
                target,
                {"state": "file", "text": '{"status": "older"}\n', "mode": 0o640},
            )

        self.assertEqual(target.read_text(encoding="utf-8"), '{"status": "older"}\n')
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        self.assertEqual(len(temp_names), 2)
        self.assertEqual(len(set(temp_names)), 2)
        self.assertTrue(all(name.startswith(".wbp-tmp-") for name in temp_names))
        self.assertTrue(
            all(name.endswith(".supervisor-state.json") for name in temp_names)
        )
        self.assertNotIn(".supervisor-state.json.tmp", temp_names)
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])

    def test_restore_path_state_sets_mode_before_publish(self) -> None:
        target = self.root / "runtime-effective-mode.txt"
        real_replace = runtime_mod.state_store.os.replace
        published_modes: list[int] = []

        def recording_replace(src: object, dst: object) -> None:
            published_modes.append(Path(src).stat().st_mode & 0o777)
            real_replace(src, dst)

        with mock.patch.object(runtime_mod.state_store.os, "replace", recording_replace):
            runtime_mod.restore_path_state(
                target,
                {"state": "file", "text": "stable\n", "mode": 0o600},
            )

        self.assertEqual(target.read_text(encoding="utf-8"), "stable\n")
        self.assertEqual(published_modes, [0o600])
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_failed_restore_path_state_cleans_temp_and_keeps_original(self) -> None:
        target = self.root / "config.toml"
        target.write_text('base_url = "old"\n', encoding="utf-8")
        os.chmod(target, 0o600)
        created_temp: list[Path] = []
        real_mkstemp = runtime_mod.state_store.tempfile.mkstemp

        def recording_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
            fd, name = real_mkstemp(*args, **kwargs)
            created_temp.append(Path(name))
            return fd, name

        def failing_replace(src: object, dst: object) -> None:
            raise OSError("replace failed")

        with (
            mock.patch.object(
                runtime_mod.state_store.tempfile, "mkstemp", recording_mkstemp
            ),
            mock.patch.object(runtime_mod.state_store.os, "replace", failing_replace),
        ):
            with self.assertRaises(state_store.StateStoreError) as raised:
                runtime_mod.restore_path_state(
                    target,
                    {"state": "file", "text": 'base_url = "new"\n', "mode": 0o600},
                )

        self.assertEqual(
            raised.exception.machine_error_code, state_store.STATE_WRITE_FAILED
        )
        self.assertEqual(target.read_text(encoding="utf-8"), 'base_url = "old"\n')
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertTrue(created_temp)
        self.assertTrue(all(not path.exists() for path in created_temp))
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])


if __name__ == "__main__":
    unittest.main()
