from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy import state_migration, state_startup_schema


class StateStartupSchemaSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.state_path = self.root / "state.json"

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

    def write_text(self, path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def assess(
        self,
        *,
        path: Path | None = None,
        target_schema_version: int = 2,
        migrations: tuple[state_migration.MigrationStep, ...] | None = None,
        legacy_bootstrap: bool = False,
    ) -> state_startup_schema.StartupSchemaSliceAssessment:
        return state_startup_schema.assess_startup_schema_slice(
            self.state_path if path is None else path,
            target_schema_version=target_schema_version,
            migrations=migrations or (self.step(1, 2, migrated=True),),
            legacy_bootstrap=legacy_bootstrap,
        )

    def test_missing_file_returns_absent_slice(self) -> None:
        result = self.assess()

        self.assertEqual(
            result.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_ABSENT,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_ABSENT,
        )
        self.assertIsNone(result.from_schema_version)
        self.assertFalse(result.migration_path_available)
        self.assertFalse(result.legacy_bootstrap_required)

    def test_relative_path_blocks(self) -> None:
        result = self.assess(path=Path("state.json"))

        self.assertEqual(
            result.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_BLOCKED,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_BLOCKED,
        )

    def test_symlink_path_blocks(self) -> None:
        target = self.write_text(self.root / "target.json", '{"schema_version":2}')
        symlink = self.root / "state-link.json"
        symlink.symlink_to(target)

        result = self.assess(path=symlink)

        self.assertEqual(
            result.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_BLOCKED,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_BLOCKED,
        )

    def test_directory_path_blocks(self) -> None:
        directory = self.root / "state-dir"
        directory.mkdir()

        result = self.assess(path=directory)

        self.assertEqual(
            result.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_BLOCKED,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_BLOCKED,
        )

    def test_current_schema_returns_current_slice(self) -> None:
        self.write_text(self.state_path, '{"schema_version":2,"name":"current"}')

        result = self.assess(target_schema_version=2, migrations=())

        self.assertEqual(
            result.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_CURRENT,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_CURRENT,
        )
        self.assertEqual(result.from_schema_version, 2)
        self.assertFalse(result.migration_path_available)
        self.assertFalse(result.legacy_bootstrap_required)

    def test_legacy_bootstrap_missing_schema_is_migratable(self) -> None:
        self.write_text(self.state_path, '{"name":"legacy"}')

        result = self.assess(legacy_bootstrap=True)

        self.assertEqual(
            result.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_MIGRATABLE,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_MIGRATABLE,
        )
        self.assertEqual(result.from_schema_version, 1)
        self.assertTrue(result.migration_path_available)
        self.assertTrue(result.legacy_bootstrap_required)

    def test_lower_schema_with_complete_chain_is_migratable(self) -> None:
        self.write_text(self.state_path, '{"schema_version":1,"name":"old"}')

        result = self.assess(
            target_schema_version=3,
            migrations=(self.step(1, 2), self.step(2, 3)),
        )

        self.assertEqual(
            result.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_MIGRATABLE,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_MIGRATABLE,
        )
        self.assertEqual(result.from_schema_version, 1)
        self.assertTrue(result.migration_path_available)
        self.assertFalse(result.legacy_bootstrap_required)

    def test_higher_schema_blocks(self) -> None:
        self.write_text(self.state_path, '{"schema_version":3}')

        result = self.assess(target_schema_version=2)

        self.assertEqual(
            result.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_BLOCKED,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_BLOCKED,
        )
        self.assertEqual(result.from_schema_version, 3)

    def test_corrupt_json_blocks(self) -> None:
        self.write_text(self.state_path, "{not-json")

        result = self.assess(legacy_bootstrap=True)

        self.assertEqual(
            result.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_BLOCKED,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_BLOCKED,
        )

    def test_unsupported_schema_type_blocks(self) -> None:
        self.write_text(self.state_path, '{"schema_version":true}')

        result = self.assess()

        self.assertEqual(
            result.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_BLOCKED,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_BLOCKED,
        )

    def test_missing_schema_without_bootstrap_blocks(self) -> None:
        self.write_text(self.state_path, '{"name":"legacy"}')

        result = self.assess()

        self.assertEqual(
            result.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_BLOCKED,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_BLOCKED,
        )

    def test_missing_migration_step_blocks(self) -> None:
        self.write_text(self.state_path, '{"schema_version":1}')

        result = self.assess(target_schema_version=3, migrations=(self.step(1, 2),))

        self.assertEqual(
            result.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_BLOCKED,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_schema.STATE_STARTUP_SCHEMA_SLICE_BLOCKED,
        )

    def test_duplicate_or_non_sequential_steps_block(self) -> None:
        self.write_text(self.state_path, '{"schema_version":1}')

        duplicate = self.assess(
            target_schema_version=2,
            migrations=(self.step(1, 2), self.step(1, 2)),
        )
        non_sequential = self.assess(
            target_schema_version=3,
            migrations=(self.step(1, 3),),
        )

        self.assertEqual(
            duplicate.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_BLOCKED,
        )
        self.assertEqual(
            non_sequential.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_BLOCKED,
        )

    def test_assessment_is_zero_write_and_does_not_run_migration(self) -> None:
        self.write_text(self.state_path, '{"schema_version":1}')

        with (
            mock.patch.object(state_startup_schema.state_store, "write_json") as write_json,
            mock.patch.object(state_startup_schema.state_store, "write_text") as write_text,
            mock.patch.object(state_startup_schema.state_migration, "migrate_json_file") as migrate,
        ):
            result = self.assess()

        self.assertEqual(
            result.schema_slice_outcome,
            state_startup_schema.SCHEMA_SLICE_MIGRATABLE,
        )
        write_json.assert_not_called()
        write_text.assert_not_called()
        migrate.assert_not_called()

    def test_result_is_library_dataclass_not_packet_or_startup_verdict(self) -> None:
        result_fields = set(state_startup_schema.StartupSchemaSliceAssessment.__dataclass_fields__)

        self.assertTrue(
            {
                "schema_slice_outcome",
                "machine_error_code",
                "reason",
                "from_schema_version",
                "target_schema_version",
                "migration_path_available",
                "legacy_bootstrap_required",
            }.issubset(result_fields)
        )
        forbidden = {
            "status",
            "effect",
            "exit_code",
            "human_message",
            "next_action",
            "operator_action",
            "changed_files",
            "startup_clean",
            "auto_recovered",
            "repair_required",
            "rollback_available",
            "rollback_id",
        }
        self.assertTrue(forbidden.isdisjoint(result_fields))

    def test_module_does_not_import_runtime_layers(self) -> None:
        source = Path(state_startup_schema.__file__).read_text(encoding="utf-8")
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
