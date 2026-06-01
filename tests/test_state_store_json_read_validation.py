from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy import state_store


class StateStoreJsonReadValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_missing_file_without_default_blocks_with_state_not_found(self) -> None:
        with self.assertRaises(state_store.StateStoreError) as raised:
            state_store.read_json(self.root / "missing-state.json")

        self.assertEqual(raised.exception.machine_error_code, state_store.STATE_NOT_FOUND)

    def test_missing_file_with_default_returns_default_without_write(self) -> None:
        target = self.root / "missing-state.json"

        payload = state_store.read_json(target, default={"schema_version": 2})

        self.assertEqual(payload, {"schema_version": 2})
        self.assertFalse(target.exists())
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])

    def test_missing_file_rejects_non_object_default(self) -> None:
        target = self.root / "missing-state.json"

        with self.assertRaises(state_store.StateStoreError) as raised:
            state_store.read_json(target, default=[])  # type: ignore[arg-type]

        self.assertEqual(
            raised.exception.machine_error_code,
            state_store.STATE_PAYLOAD_INVALID,
        )
        self.assertFalse(target.exists())
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])

    def test_missing_file_default_still_enforces_expected_schema(self) -> None:
        target = self.root / "missing-state.json"

        with self.assertRaises(state_store.StateStoreError) as raised:
            state_store.read_json(
                target,
                expected_schema_version=2,
                default={"schema_version": 3},
            )

        self.assertEqual(
            raised.exception.machine_error_code,
            state_store.STATE_SCHEMA_UNSUPPORTED,
        )
        self.assertFalse(target.exists())
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])

    def test_default_does_not_mask_corrupt_json(self) -> None:
        target = self.root / "supervisor-state.json"
        target.write_text("{not-json", encoding="utf-8")

        with self.assertRaises(state_store.StateStoreError) as raised:
            state_store.read_json(target, default={"schema_version": 2})

        self.assertEqual(raised.exception.machine_error_code, state_store.STATE_CORRUPT)

    def test_corrupt_json_blocks_with_state_corrupt(self) -> None:
        target = self.root / "supervisor-state.json"
        target.write_text("{", encoding="utf-8")

        with self.assertRaises(state_store.StateStoreError) as raised:
            state_store.read_json(target)

        self.assertEqual(raised.exception.machine_error_code, state_store.STATE_CORRUPT)

    def test_read_rejects_non_object_json(self) -> None:
        for name, value in (
            ("array.json", "[]"),
            ("string.json", '"value"'),
            ("null.json", "null"),
        ):
            target = self.root / name
            target.write_text(value, encoding="utf-8")

            with self.assertRaises(state_store.StateStoreError) as raised:
                state_store.read_json(target)

            self.assertEqual(
                raised.exception.machine_error_code,
                state_store.STATE_PAYLOAD_INVALID,
            )

    def test_read_enforces_schema_version(self) -> None:
        target = self.root / "backend-registry.json"
        target.write_text('{"schema_version": 3}', encoding="utf-8")

        with self.assertRaises(state_store.StateStoreError) as raised:
            state_store.read_json(target, expected_schema_version=2)

        self.assertEqual(
            raised.exception.machine_error_code,
            state_store.STATE_SCHEMA_UNSUPPORTED,
        )

    def test_read_blocks_missing_schema_when_expected(self) -> None:
        target = self.root / "backend-registry.json"
        target.write_text('{"backends": []}', encoding="utf-8")

        with self.assertRaises(state_store.StateStoreError) as raised:
            state_store.read_json(target, expected_schema_version=2)

        self.assertEqual(raised.exception.machine_error_code, state_store.STATE_SCHEMA_MISSING)

    def test_write_validator_runs_before_publish(self) -> None:
        target = self.root / "supervisor-state.json"
        target.write_text('{"schema_version": 2, "status": "old"}', encoding="utf-8")
        before = target.read_text(encoding="utf-8")

        def reject(payload: dict[str, object]) -> object:
            self.assertEqual(payload["schema_version"], 2)
            return False

        with mock.patch.object(state_store.tempfile, "mkstemp") as mkstemp:
            with self.assertRaises(state_store.StateStoreError) as raised:
                state_store.write_json(
                    target,
                    {"schema_version": 2, "status": "new"},
                    expected_schema_version=2,
                    validator=reject,
                )

        self.assertEqual(raised.exception.machine_error_code, state_store.STATE_VALIDATION_FAILED)
        mkstemp.assert_not_called()
        self.assertEqual(target.read_text(encoding="utf-8"), before)
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])

    def test_validator_exception_keeps_original_and_leaves_no_temp(self) -> None:
        target = self.root / "supervisor-state.json"
        target.write_text('{"schema_version": 2, "status": "old"}', encoding="utf-8")
        before = target.read_text(encoding="utf-8")

        def reject(_: dict[str, object]) -> object:
            raise ValueError("invalid state")

        with self.assertRaises(state_store.StateStoreError) as raised:
            state_store.write_json(
                target,
                {"schema_version": 2, "status": "new"},
                expected_schema_version=2,
                validator=reject,
            )

        self.assertEqual(raised.exception.machine_error_code, state_store.STATE_VALIDATION_FAILED)
        self.assertEqual(target.read_text(encoding="utf-8"), before)
        self.assertEqual(list(self.root.glob(".wbp-tmp-*")), [])

    def test_state_store_does_not_import_runtime_layers(self) -> None:
        source = Path(state_store.__file__).read_text(encoding="utf-8")
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
