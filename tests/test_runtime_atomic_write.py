# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
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
        self.assertTrue(all(name.endswith(".runtime-mode.txt.tmp") for name in temp_names))
        self.assertTrue(all(not Path(name).match("*.txt") for name in temp_names))
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

    def test_write_bytes_atomic_delegates_to_state_store(self) -> None:
        target = self.root / "runtime-secret.bin"

        with mock.patch.object(runtime_mod.state_store, "write_bytes") as write_bytes:
            runtime_mod.write_bytes_atomic(target, b"\x00secret", mode=0o600)

        write_bytes.assert_called_once_with(target, b"\x00secret", mode=0o600)

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
            all(name.endswith(".supervisor-state.json.tmp") for name in temp_names)
        )
        self.assertTrue(all(not Path(name).match("*.json") for name in temp_names))
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

    def test_write_stable_runtime_consumer_snapshot_rejects_incomplete_state(self) -> None:
        paths = runtime_mod.RuntimePaths.from_roots(
            profile_dir=self.root / "profile",
            managed_dir=self.root / "managed",
            stable_config=self.root / "stable" / "config.yaml",
        )
        paths.managed_dir.mkdir(parents=True, exist_ok=True)
        paths.state_file.write_text(json.dumps({"status": "failed"}) + "\n", encoding="utf-8")
        before = paths.state_file.read_text(encoding="utf-8")
        snapshot = runtime_mod.build_stable_runtime_consumer_snapshot_payload(
            activation_method="baseline_stable_config",
            selected_config_file=str(paths.stable_config),
            selected_source_kind="observed_stable_inventory_source",
            selected_source_path=str(paths.stable_config.parent),
            activation_outcome=runtime_mod.STABLE_RUNTIME_OBSERVED_SOURCE_SELECTED_OUTCOME,
            fallback_reason="",
        )

        with self.assertRaises(runtime_mod.RuntimeErrorInfo) as raised:
            runtime_mod.write_stable_runtime_consumer_snapshot(paths, snapshot)

        self.assertEqual(
            raised.exception.machine_error_code, state_store.STATE_SCHEMA_MISSING
        )
        self.assertEqual(paths.state_file.read_text(encoding="utf-8"), before)

    def test_write_json_atomic_validates_runtime_state_payload_before_publish(self) -> None:
        target = self.root / "supervisor-state.json"
        target.write_text(
            json.dumps(runtime_mod.build_installer_default_state_payload()) + "\n",
            encoding="utf-8",
        )
        before = target.read_text(encoding="utf-8")

        with self.assertRaises(state_store.StateStoreError) as raised:
            runtime_mod.write_json_atomic(
                target,
                {"status": "healthy"},
                expected_schema_version=runtime_mod.SUPERVISOR_STATE_SCHEMA_VERSION,
                validator=runtime_mod._validate_runtime_state_payload,
            )

        self.assertEqual(
            raised.exception.machine_error_code, state_store.STATE_SCHEMA_MISSING
        )
        self.assertEqual(target.read_text(encoding="utf-8"), before)
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])

    def test_write_json_atomic_validates_runtime_registry_payload_before_publish(self) -> None:
        target = self.root / "backend-registry.json"
        target.write_text(
            json.dumps(runtime_mod.build_installer_default_registry_payload()) + "\n",
            encoding="utf-8",
        )
        before = target.read_text(encoding="utf-8")

        with self.assertRaises(state_store.StateStoreError) as raised:
            runtime_mod.write_json_atomic(
                target,
                {"schema_version": runtime_mod.BACKEND_REGISTRY_SCHEMA_VERSION},
                expected_schema_version=runtime_mod.BACKEND_REGISTRY_SCHEMA_VERSION,
                validator=runtime_mod._validate_runtime_registry_payload,
            )

        self.assertEqual(
            raised.exception.machine_error_code, state_store.STATE_PAYLOAD_INVALID
        )
        self.assertEqual(target.read_text(encoding="utf-8"), before)
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])

    def test_legacy_import_impl_preserves_local_effective_mode_truth(self) -> None:
        paths = runtime_mod.RuntimePaths.from_roots(
            profile_dir=self.root / "profile",
            managed_dir=self.root / "managed",
            stable_config=self.root / "stable" / "config.yaml",
        )
        paths.profile_dir.mkdir(parents=True, exist_ok=True)
        paths.managed_dir.mkdir(parents=True, exist_ok=True)
        runtime_mod.write_json_atomic(
            paths.registry_file, runtime_mod.build_installer_default_registry_payload()
        )
        runtime_mod.write_json_atomic(
            paths.state_file, runtime_mod.build_installer_default_state_payload()
        )
        runtime_mod.write_text_atomic(paths.config_toml, 'model = "gpt-5.5"')
        runtime_mod.write_text_atomic(paths.runtime_mode_file, "stable")
        runtime_mod.write_text_atomic(paths.runtime_effective_mode_file, "stable")

        source_dir = self.root / "legacy-success-source"
        source_dir.mkdir(parents=True, exist_ok=True)
        source_registry = {
            "schema_version": 2,
            "version": 2,
            "updated_at": "2026-06-27T00:00:00+00:00",
            "stable_default_backend_id": "legacy-backend",
            "pool_policy": {"active_min": 1, "active_target": 1, "reserve_target": 0},
            "backends": [
                {
                    "id": "legacy-backend",
                    "label": "Legacy Backend",
                    "pool": "active",
                    "status": "healthy",
                    "manual_hold": False,
                    "auth_ref": "/tmp/legacy.json",
                    "fail_count": 0,
                    "success_count": 1,
                    "last_success": None,
                    "last_error": "",
                    "cooldown_until": None,
                    "notes": "",
                    "provider": "openai",
                }
            ],
        }
        source_state = runtime_mod.build_installer_default_state_payload()
        source_state.update(
            {
                "status": "healthy",
                "effective_mode": "managed",
                "last_sync_at": "2026-06-27T00:00:00+00:00",
                "selected_backend_ids": ["legacy-backend"],
                "managed_port": 9999,
                "current_proxy_url": "http://127.0.0.1:10899",
                "stable_default_backend_id": "legacy-backend",
                "active_count": 1,
                "healthy_count": 1,
            }
        )
        (source_dir / "backend-registry.json").write_text(
            json.dumps(source_registry) + "\n", encoding="utf-8"
        )
        (source_dir / "supervisor-state.json").write_text(
            json.dumps(source_state) + "\n", encoding="utf-8"
        )
        (source_dir / "runtime-mode.txt").write_text("managed\n", encoding="utf-8")
        (source_dir / "runtime-effective-mode.txt").write_text(
            "managed\n", encoding="utf-8"
        )
        (source_dir / "config.toml").write_text(
            'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:8320/v1"\n',
            encoding="utf-8",
        )

        with mock.patch.dict(
            os.environ,
            {
                "WBP_MANAGED_DIR": str(paths.managed_dir),
                "WBP_EXTERNAL_MODELS_DIR": str(self.root / "external-models"),
            },
            clear=False,
        ):
            payload = runtime_mod._run_legacy_import_impl(paths, str(source_dir))

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertEqual(
            payload["legacy_import_result"]["final_outcome"], "import_completed"
        )
        imported_state = json.loads(paths.state_file.read_text(encoding="utf-8"))
        self.assertEqual(imported_state["effective_mode"], "stable")
        self.assertEqual(
            paths.runtime_mode_file.read_text(encoding="utf-8").strip(), "managed"
        )
        self.assertEqual(
            paths.runtime_effective_mode_file.read_text(encoding="utf-8").strip(),
            "stable",
        )
        self.assertNotIn(str(paths.runtime_effective_mode_file), payload["changed_files"])

    def test_legacy_import_impl_rolls_back_on_state_store_switch_failure(self) -> None:
        paths = runtime_mod.RuntimePaths.from_roots(
            profile_dir=self.root / "profile",
            managed_dir=self.root / "managed",
            stable_config=self.root / "stable" / "config.yaml",
        )
        paths.profile_dir.mkdir(parents=True, exist_ok=True)
        paths.managed_dir.mkdir(parents=True, exist_ok=True)
        runtime_mod.write_json_atomic(
            paths.registry_file, runtime_mod.build_installer_default_registry_payload()
        )
        runtime_mod.write_json_atomic(
            paths.state_file, runtime_mod.build_installer_default_state_payload()
        )
        runtime_mod.write_text_atomic(paths.config_toml, 'model = "gpt-5.5"')
        runtime_mod.write_text_atomic(paths.runtime_mode_file, "stable")
        runtime_mod.write_text_atomic(paths.runtime_effective_mode_file, "stable")
        before_registry = paths.registry_file.read_text(encoding="utf-8")
        before_state = paths.state_file.read_text(encoding="utf-8")
        before_config = paths.config_toml.read_text(encoding="utf-8")
        before_mode = paths.runtime_mode_file.read_text(encoding="utf-8")
        before_effective = paths.runtime_effective_mode_file.read_text(encoding="utf-8")

        source_dir = self.root / "legacy-source"
        source_dir.mkdir(parents=True, exist_ok=True)
        source_registry = runtime_mod.build_installer_default_registry_payload()
        source_registry["updated_at"] = "2026-06-27T00:00:00+00:00"
        source_state = runtime_mod.build_installer_default_state_payload()
        source_state["status"] = "healthy"
        (source_dir / "backend-registry.json").write_text(
            json.dumps(source_registry) + "\n", encoding="utf-8"
        )
        (source_dir / "supervisor-state.json").write_text(
            json.dumps(source_state) + "\n", encoding="utf-8"
        )

        real_write_json_atomic = runtime_mod.write_json_atomic

        def failing_write_json_atomic(
            path: Path,
            payload: dict[str, object],
            *,
            expected_schema_version: int | None = None,
            validator: object | None = None,
        ) -> None:
            real_write_json_atomic(
                path,
                payload,
                expected_schema_version=expected_schema_version,
                validator=validator,
            )
            if path == paths.state_file:
                raise state_store.StateStoreError(
                    "Simulated switch-time state write failure.",
                    machine_error_code=state_store.STATE_WRITE_FAILED,
                )

        with (
            mock.patch.dict(
                os.environ,
                {
                    "WBP_MANAGED_DIR": str(paths.managed_dir),
                    "WBP_EXTERNAL_MODELS_DIR": str(self.root / "external-models"),
                },
                clear=False,
            ),
            mock.patch.object(
                runtime_mod, "write_json_atomic", side_effect=failing_write_json_atomic
            ),
        ):
            payload = runtime_mod._run_legacy_import_impl(paths, str(source_dir))

        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["machine_error_code"], state_store.STATE_WRITE_FAILED
        )
        self.assertEqual(
            payload["legacy_import_result"]["final_outcome"],
            "rollback_completed_after_failed_import",
        )
        self.assertTrue(payload["legacy_import_result"]["rollback_attempted"])
        self.assertEqual(payload["legacy_import_result"]["rollback_outcome"], "completed")
        self.assertEqual(paths.registry_file.read_text(encoding="utf-8"), before_registry)
        self.assertEqual(paths.state_file.read_text(encoding="utf-8"), before_state)
        self.assertEqual(paths.config_toml.read_text(encoding="utf-8"), before_config)
        self.assertEqual(paths.runtime_mode_file.read_text(encoding="utf-8"), before_mode)
        self.assertEqual(
            paths.runtime_effective_mode_file.read_text(encoding="utf-8"),
            before_effective,
        )

    def test_legacy_import_impl_removes_new_external_models_dirs_on_rollback(self) -> None:
        from wild_boar_proxy.external_models import integration as external_integration

        paths = runtime_mod.RuntimePaths.from_roots(
            profile_dir=self.root / "profile",
            managed_dir=self.root / "managed",
            stable_config=self.root / "stable" / "config.yaml",
        )
        paths.profile_dir.mkdir(parents=True, exist_ok=True)
        paths.managed_dir.mkdir(parents=True, exist_ok=True)
        runtime_mod.write_json_atomic(
            paths.registry_file, runtime_mod.build_installer_default_registry_payload()
        )
        runtime_mod.write_json_atomic(
            paths.state_file, runtime_mod.build_installer_default_state_payload()
        )
        runtime_mod.write_text_atomic(paths.runtime_mode_file, "stable")
        runtime_mod.write_text_atomic(paths.runtime_effective_mode_file, "stable")

        source_dir = self.root / "legacy-external-source"
        source_dir.mkdir(parents=True, exist_ok=True)
        (source_dir / "backend-registry.json").write_text(
            json.dumps(runtime_mod.build_installer_default_registry_payload()) + "\n",
            encoding="utf-8",
        )
        (source_dir / "supervisor-state.json").write_text(
            json.dumps(runtime_mod.build_installer_default_state_payload()) + "\n",
            encoding="utf-8"
        )

        external_root = self.root / "external-models"

        def failing_import(
            _source_dir: Path, destination_paths: object
        ) -> dict[str, object]:
            destination_root = destination_paths.root_dir
            destination_evidence = destination_paths.evidence_dir
            destination_root.mkdir(parents=True, exist_ok=True)
            destination_evidence.mkdir(parents=True, exist_ok=True)
            raise state_store.StateStoreError(
                "Simulated external-models import failure.",
                machine_error_code=state_store.STATE_WRITE_FAILED,
            )

        with (
            mock.patch.dict(
                os.environ,
                {
                    "WBP_MANAGED_DIR": str(paths.managed_dir),
                    "WBP_EXTERNAL_MODELS_DIR": str(external_root),
                },
                clear=False,
            ),
            mock.patch.object(
                external_integration, "import_legacy_layout", side_effect=failing_import
            ),
        ):
            payload = runtime_mod._run_legacy_import_impl(paths, str(source_dir))

        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["machine_error_code"], state_store.STATE_WRITE_FAILED
        )
        self.assertFalse(external_root.exists())

    def test_legacy_import_impl_reports_structured_rollback_failure(self) -> None:
        paths = runtime_mod.RuntimePaths.from_roots(
            profile_dir=self.root / "profile",
            managed_dir=self.root / "managed",
            stable_config=self.root / "stable" / "config.yaml",
        )
        paths.profile_dir.mkdir(parents=True, exist_ok=True)
        paths.managed_dir.mkdir(parents=True, exist_ok=True)
        runtime_mod.write_json_atomic(
            paths.registry_file, runtime_mod.build_installer_default_registry_payload()
        )
        runtime_mod.write_json_atomic(
            paths.state_file, runtime_mod.build_installer_default_state_payload()
        )
        runtime_mod.write_text_atomic(paths.runtime_mode_file, "stable")
        runtime_mod.write_text_atomic(paths.runtime_effective_mode_file, "stable")

        source_dir = self.root / "legacy-rollback-failure-source"
        source_dir.mkdir(parents=True, exist_ok=True)
        (source_dir / "backend-registry.json").write_text(
            json.dumps(runtime_mod.build_installer_default_registry_payload()) + "\n",
            encoding="utf-8",
        )
        (source_dir / "supervisor-state.json").write_text(
            json.dumps(runtime_mod.build_installer_default_state_payload()) + "\n",
            encoding="utf-8",
        )

        real_write_json_atomic = runtime_mod.write_json_atomic

        def failing_write_json_atomic(
            path: Path,
            payload: dict[str, object],
            *,
            expected_schema_version: int | None = None,
            validator: object | None = None,
        ) -> None:
            real_write_json_atomic(
                path,
                payload,
                expected_schema_version=expected_schema_version,
                validator=validator,
            )
            if path == paths.state_file:
                raise state_store.StateStoreError(
                    "Simulated switch-time state write failure.",
                    machine_error_code=state_store.STATE_WRITE_FAILED,
                )

        def failing_restore_path_state(_path: Path, _snapshot: dict[str, object]) -> None:
            raise state_store.StateStoreError(
                "Simulated rollback restore failure.",
                machine_error_code=state_store.STATE_WRITE_FAILED,
            )

        with (
            mock.patch.dict(
                os.environ,
                {
                    "WBP_MANAGED_DIR": str(paths.managed_dir),
                    "WBP_EXTERNAL_MODELS_DIR": str(self.root / "external-models"),
                },
                clear=False,
            ),
            mock.patch.object(
                runtime_mod, "write_json_atomic", side_effect=failing_write_json_atomic
            ),
            mock.patch.object(
                runtime_mod, "restore_path_state", side_effect=failing_restore_path_state
            ),
        ):
            payload = runtime_mod._run_legacy_import_impl(paths, str(source_dir))

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "LEGACY_IMPORT_ROLLBACK_FAILED")
        self.assertEqual(payload["legacy_import_result"]["rollback_outcome"], "failed")
        self.assertEqual(payload["legacy_import_result"]["final_outcome"], "rollback_failed")
        self.assertIn("rollback_error", payload["legacy_import_result"])


if __name__ == "__main__":
    unittest.main()
