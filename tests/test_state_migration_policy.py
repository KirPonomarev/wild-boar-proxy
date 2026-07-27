from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy import state_migration, state_store


class StateMigrationPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.target = self.root / "state.json"
        self.backup_dir = self.root / "backups"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def step(
        self,
        from_version: int,
        to_version: int,
        **fields: object,
    ) -> state_migration.MigrationStep:
        def migrate(payload: dict[str, object]) -> dict[str, object]:
            migrated = dict(payload)
            migrated.update(fields)
            migrated["schema_version"] = to_version
            return migrated

        return state_migration.MigrationStep(
            from_version=from_version,
            to_version=to_version,
            migrate=migrate,
        )

    def migrate(
        self,
        *,
        target_schema_version: int = 2,
        migrations: tuple[state_migration.MigrationStep, ...] | None = None,
        legacy_bootstrap: bool = False,
    ) -> state_migration.MigrationResult:
        return state_migration.migrate_json_file(
            self.target,
            target_schema_version=target_schema_version,
            migrations=migrations or (self.step(1, 2, migrated=True),),
            backup_dir=self.backup_dir,
            legacy_bootstrap=legacy_bootstrap,
        )

    def test_bootstrap_migration_from_legacy_state(self) -> None:
        self.target.write_text('{"name":"legacy"}', encoding="utf-8")

        result = self.migrate(legacy_bootstrap=True)

        self.assertTrue(result.committed)
        self.assertEqual(result.from_schema_version, 1)
        self.assertEqual(result.to_schema_version, 2)
        self.assertEqual(state_store.read_json(self.target, expected_schema_version=2)["name"], "legacy")
        self.assertEqual(state_store.read_json(self.target)["migrated"], True)
        self.assertEqual(set(result.changed_files), {result.backup_path, str(self.target)})

    def test_missing_schema_without_bootstrap_blocks(self) -> None:
        self.target.write_text('{"name":"legacy"}', encoding="utf-8")

        with self.assertRaises(state_store.StateStoreError) as raised:
            self.migrate()

        self.assertEqual(raised.exception.machine_error_code, state_store.STATE_SCHEMA_MISSING)
        self.assertEqual(self.target.read_text(encoding="utf-8"), '{"name":"legacy"}')
        self.assertFalse(self.backup_dir.exists())

    def test_migrate_json_file_requires_explicit_backup_dir(self) -> None:
        self.target.write_text('{"schema_version":1}', encoding="utf-8")

        with self.assertRaises(TypeError):
            state_migration.migrate_json_file(  # type: ignore[call-arg]
                self.target,
                target_schema_version=2,
                migrations=(self.step(1, 2),),
            )

    def test_corrupt_json_is_not_legacy_and_blocks(self) -> None:
        self.target.write_text("{not-json", encoding="utf-8")

        with self.assertRaises(state_store.StateStoreError) as raised:
            self.migrate(legacy_bootstrap=True)

        self.assertEqual(raised.exception.machine_error_code, state_store.STATE_CORRUPT)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "{not-json")
        self.assertFalse(self.backup_dir.exists())

    def test_unknown_schema_version_blocks(self) -> None:
        self.target.write_text('{"schema_version":"2"}', encoding="utf-8")

        with self.assertRaises(state_store.StateStoreError) as raised:
            self.migrate()

        self.assertEqual(
            raised.exception.machine_error_code,
            state_store.STATE_SCHEMA_UNSUPPORTED,
        )

    def test_downgrade_blocks(self) -> None:
        self.target.write_text('{"schema_version":3}', encoding="utf-8")

        with mock.patch.object(state_migration.state_store, "write_text") as write_text:
            with mock.patch.object(state_migration.state_store, "write_json") as write_json:
                with self.assertRaises(state_migration.StateMigrationError) as raised:
                    self.migrate(target_schema_version=2)

        self.assertEqual(
            raised.exception.machine_error_code,
            state_migration.STATE_MIGRATION_DOWNGRADE_BLOCKED,
        )
        write_text.assert_not_called()
        write_json.assert_not_called()

    def test_missing_migration_step_blocks(self) -> None:
        self.target.write_text('{"schema_version":1}', encoding="utf-8")

        with mock.patch.object(state_migration.state_store, "write_text") as write_text:
            with mock.patch.object(state_migration.state_store, "write_json") as write_json:
                with self.assertRaises(state_migration.StateMigrationError) as raised:
                    self.migrate(target_schema_version=3, migrations=(self.step(1, 2),))

        self.assertEqual(
            raised.exception.machine_error_code,
            state_migration.STATE_MIGRATION_STEP_MISSING,
        )
        write_text.assert_not_called()
        write_json.assert_not_called()

    def test_non_sequential_step_blocks(self) -> None:
        self.target.write_text('{"schema_version":1}', encoding="utf-8")

        with self.assertRaises(state_migration.StateMigrationError) as raised:
            self.migrate(
                target_schema_version=3,
                migrations=(self.step(1, 3),),
            )

        self.assertEqual(
            raised.exception.machine_error_code,
            state_migration.STATE_MIGRATION_STEP_MISSING,
        )

    def test_duplicate_migration_step_blocks(self) -> None:
        self.target.write_text('{"schema_version":1}', encoding="utf-8")

        with self.assertRaises(state_migration.StateMigrationError) as raised:
            self.migrate(
                target_schema_version=2,
                migrations=(self.step(1, 2), self.step(1, 2)),
            )

        self.assertEqual(
            raised.exception.machine_error_code,
            state_migration.STATE_MIGRATION_STEP_MISSING,
        )

    def test_step_must_emit_expected_schema_version(self) -> None:
        self.target.write_text('{"schema_version":1,"name":"old"}', encoding="utf-8")

        def wrong_version(payload: dict[str, object]) -> dict[str, object]:
            migrated = dict(payload)
            migrated["schema_version"] = 3
            return migrated

        with self.assertRaises(state_migration.StateMigrationError) as raised:
            self.migrate(
                migrations=(
                    state_migration.MigrationStep(
                        from_version=1,
                        to_version=2,
                        migrate=wrong_version,
                    ),
                )
            )

        self.assertEqual(
            raised.exception.machine_error_code,
            state_migration.STATE_MIGRATION_FAILED,
        )
        self.assertFalse(self.backup_dir.exists())

    def test_bool_schema_version_is_unsupported(self) -> None:
        self.target.write_text('{"schema_version":true}', encoding="utf-8")

        with self.assertRaises(state_store.StateStoreError) as raised:
            self.migrate()

        self.assertEqual(
            raised.exception.machine_error_code,
            state_store.STATE_SCHEMA_UNSUPPORTED,
        )

    def test_failed_migration_keeps_original_state(self) -> None:
        self.target.write_text('{"schema_version":1,"name":"old"}', encoding="utf-8")
        before = self.target.read_text(encoding="utf-8")

        def fail(_: dict[str, object]) -> dict[str, object]:
            raise ValueError("migration failed")

        with self.assertRaises(state_migration.StateMigrationError) as raised:
            self.migrate(
                migrations=(
                    state_migration.MigrationStep(
                        from_version=1,
                        to_version=2,
                        migrate=fail,
                    ),
                )
            )

        self.assertEqual(
            raised.exception.machine_error_code,
            state_migration.STATE_MIGRATION_FAILED,
        )
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)
        self.assertFalse(self.backup_dir.exists())

    def test_backup_created_before_migrated_publish(self) -> None:
        self.target.write_text('{"schema_version":1,"name":"old"}', encoding="utf-8")
        events: list[str] = []
        real_write_text = state_migration.state_store.write_text
        real_write_json = state_migration.state_store.write_json

        def recording_write_text(*args: object, **kwargs: object) -> object:
            events.append("backup")
            return real_write_text(*args, **kwargs)

        def recording_write_json(*args: object, **kwargs: object) -> object:
            events.append("target")
            return real_write_json(*args, **kwargs)

        with (
            mock.patch.object(state_migration.state_store, "write_text", recording_write_text),
            mock.patch.object(state_migration.state_store, "write_json", recording_write_json),
        ):
            self.migrate()

        self.assertEqual(events, ["backup", "target"])

    def test_backup_contains_original_bytes(self) -> None:
        original = '{\n  "schema_version": 1,\n  "name": "old"\n}\n'
        self.target.write_text(original, encoding="utf-8")

        result = self.migrate()

        self.assertEqual(Path(result.backup_path).read_bytes(), original.encode("utf-8"))

    def test_backup_failure_blocks_and_keeps_original(self) -> None:
        self.target.write_text('{"schema_version":1,"name":"old"}', encoding="utf-8")
        before = self.target.read_text(encoding="utf-8")

        def fail_backup(*_: object, **__: object) -> object:
            raise state_store.StateStoreError(
                "backup failed",
                machine_error_code=state_store.STATE_WRITE_FAILED,
            )

        with mock.patch.object(state_migration.state_store, "write_text", fail_backup):
            with self.assertRaises(state_store.StateStoreError):
                self.migrate()

        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_target_publish_failure_keeps_original_and_does_not_commit(self) -> None:
        self.target.write_text('{"schema_version":1,"name":"old"}', encoding="utf-8")
        before = self.target.read_text(encoding="utf-8")

        def fail_publish(*_: object, **__: object) -> object:
            raise state_store.StateStoreError(
                "publish failed",
                machine_error_code=state_store.STATE_WRITE_FAILED,
            )

        with mock.patch.object(state_migration.state_store, "write_json", fail_publish):
            with self.assertRaises(state_store.StateStoreError):
                self.migrate()

        self.assertEqual(self.target.read_text(encoding="utf-8"), before)
        self.assertTrue(self.backup_dir.exists())
        self.assertEqual(len(list(self.backup_dir.iterdir())), 1)

    def test_migration_writes_via_state_store_only(self) -> None:
        self.target.write_text('{"schema_version":1,"name":"old"}', encoding="utf-8")
        calls: list[str] = []
        real_write_text = state_migration.state_store.write_text
        real_write_json = state_migration.state_store.write_json

        def recording_write_text(*args: object, **kwargs: object) -> object:
            calls.append("write_text")
            return real_write_text(*args, **kwargs)

        def recording_write_json(*args: object, **kwargs: object) -> object:
            calls.append("write_json")
            return real_write_json(*args, **kwargs)

        with (
            mock.patch.object(state_migration.state_store, "write_text", recording_write_text),
            mock.patch.object(state_migration.state_store, "write_json", recording_write_json),
        ):
            self.migrate()

        self.assertEqual(calls, ["write_text", "write_json"])

    def test_migration_result_changed_files_reports_backup_and_target(self) -> None:
        self.target.write_text('{"schema_version":1,"name":"old"}', encoding="utf-8")

        result = self.migrate()

        self.assertEqual(result.changed_files, (result.backup_path, str(self.target)))

    def test_result_is_library_dataclass_not_command_packet(self) -> None:
        result_fields = set(state_migration.MigrationResult.__dataclass_fields__)

        self.assertTrue(
            {
                "committed",
                "from_schema_version",
                "to_schema_version",
                "backup_path",
                "changed_files",
            }.issubset(result_fields)
        )
        self.assertTrue({"status", "exit_code", "next_action"}.isdisjoint(result_fields))

    def test_current_schema_noop_does_not_write(self) -> None:
        self.target.write_text('{"schema_version":2,"name":"current"}', encoding="utf-8")

        result = self.migrate(target_schema_version=2, migrations=())

        self.assertFalse(result.committed)
        self.assertEqual(result.changed_files, ())
        self.assertFalse(self.backup_dir.exists())

    def test_migration_module_does_not_import_runtime_layers(self) -> None:
        source = Path(state_migration.__file__).read_text(encoding="utf-8")
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
        }
        self.assertTrue(forbidden.isdisjoint(imported_modules))


if __name__ == "__main__":
    unittest.main()
