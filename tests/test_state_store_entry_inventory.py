from __future__ import annotations

import ast
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "wild_boar_proxy" / "runtime.py"
SANDBOX_OWNER_HELPERS = ROOT / "wild_boar_proxy" / "sandbox_owner_helpers.py"

MUTATE = "MUTATE"
REPAIR = "REPAIR"
SUBPROCESS_ADJACENT = "SUBPROCESS_ADJACENT"
AMBIENT_FIX_REQUIRED = "AMBIENT_FIX_REQUIRED"

P0_TRUTH_FILES = frozenset(
    {
        "supervisor-state.json",
        "backend-registry.json",
        "runtime-mode.txt",
        "runtime-effective-mode.txt",
    }
)

TRUTH_PATH_ATTRS = {
    "state_file": "supervisor-state.json",
    "registry_file": "backend-registry.json",
    "runtime_mode_file": "runtime-mode.txt",
    "runtime_effective_mode_file": "runtime-effective-mode.txt",
}

WRITE_HELPERS = {
    "write_json_atomic",
    "write_text_atomic",
    "write_toml_string_atomic",
}


@dataclass(frozen=True)
class InventoryRow:
    module: Path
    current_owner: str
    truth_file: str
    write_helper: str
    current_effect_class: str
    state_store_candidate: bool = True


STATE_STORE_ENTRY_INVENTORY = frozenset(
    {
        InventoryRow(
            RUNTIME,
            "materialize_selected_backend_snapshot_for_sync",
            "supervisor-state.json",
            "write_json_atomic",
            SUBPROCESS_ADJACENT,
        ),
        InventoryRow(
            RUNTIME,
            "refresh_last_known_good_proxy_from_healthcheck",
            "supervisor-state.json",
            "write_json_atomic",
            REPAIR,
        ),
        InventoryRow(
            RUNTIME,
            "write_stable_runtime_consumer_snapshot",
            "supervisor-state.json",
            "write_json_atomic",
            REPAIR,
        ),
        InventoryRow(
            RUNTIME,
            "reconcile_stable_fallback",
            "supervisor-state.json",
            "write_json_atomic",
            REPAIR,
        ),
        InventoryRow(
            RUNTIME,
            "reconcile_stable_fallback",
            "runtime-effective-mode.txt",
            "write_text_atomic",
            REPAIR,
        ),
        InventoryRow(
            RUNTIME,
            "reconcile_stable_recovery_success",
            "supervisor-state.json",
            "write_json_atomic",
            REPAIR,
        ),
        InventoryRow(
            RUNTIME,
            "reconcile_stable_recovery_success",
            "runtime-effective-mode.txt",
            "write_text_atomic",
            REPAIR,
        ),
        InventoryRow(
            RUNTIME,
            "mode_set",
            "runtime-mode.txt",
            "write_text_atomic",
            MUTATE,
        ),
        InventoryRow(
            RUNTIME,
            "run_sync",
            "supervisor-state.json",
            "write_json_atomic",
            SUBPROCESS_ADJACENT,
        ),
        InventoryRow(
            RUNTIME,
            "run_sync",
            "runtime-effective-mode.txt",
            "write_text_atomic",
            SUBPROCESS_ADJACENT,
        ),
        InventoryRow(
            RUNTIME,
            "run_policy_stage_set",
            "backend-registry.json",
            "write_json_atomic",
            MUTATE,
        ),
        InventoryRow(
            RUNTIME,
            "_run_installer_init_impl",
            "runtime-mode.txt",
            "write_text_atomic",
            AMBIENT_FIX_REQUIRED,
        ),
        InventoryRow(
            RUNTIME,
            "_run_installer_init_impl",
            "runtime-effective-mode.txt",
            "write_text_atomic",
            AMBIENT_FIX_REQUIRED,
        ),
        InventoryRow(
            RUNTIME,
            "_run_installer_init_impl",
            "backend-registry.json",
            "write_json_atomic",
            AMBIENT_FIX_REQUIRED,
        ),
        InventoryRow(
            RUNTIME,
            "_run_installer_init_impl",
            "supervisor-state.json",
            "write_json_atomic",
            AMBIENT_FIX_REQUIRED,
        ),
        InventoryRow(
            RUNTIME,
            "run_legacy_import",
            "backend-registry.json",
            "write_json_atomic",
            MUTATE,
        ),
        InventoryRow(
            RUNTIME,
            "run_legacy_import",
            "supervisor-state.json",
            "write_json_atomic",
            MUTATE,
        ),
        InventoryRow(
            RUNTIME,
            "run_legacy_import",
            "runtime-mode.txt",
            "write_text_atomic",
            MUTATE,
        ),
        InventoryRow(
            RUNTIME,
            "run_legacy_import",
            "runtime-effective-mode.txt",
            "write_text_atomic",
            MUTATE,
        ),
        InventoryRow(
            SANDBOX_OWNER_HELPERS,
            "save_registry",
            "backend-registry.json",
            "write_json_atomic",
            MUTATE,
        ),
        InventoryRow(
            SANDBOX_OWNER_HELPERS,
            "save_state",
            "supervisor-state.json",
            "write_json_atomic",
            MUTATE,
        ),
        InventoryRow(
            SANDBOX_OWNER_HELPERS,
            "cmd_sync",
            "runtime-effective-mode.txt",
            "write_text_atomic",
            SUBPROCESS_ADJACENT,
        ),
    }
)


def _module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _enclosing_function(
    parents: dict[ast.AST, ast.AST], node: ast.AST
) -> ast.FunctionDef:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, ast.FunctionDef):
            return current
    raise AssertionError("P0 write call is not inside a function")


def _truth_file_for_arg(node: ast.AST) -> str:
    dotted = _dotted_name(node)
    attr = dotted.rsplit(".", 1)[-1]
    return TRUTH_PATH_ATTRS.get(attr, "")


def _direct_p0_write_rows(path: Path) -> set[tuple[Path, str, str, str]]:
    tree = _module(path)
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    rows: set[tuple[Path, str, str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        helper = _dotted_name(node.func).rsplit(".", 1)[-1]
        if helper not in WRITE_HELPERS or not node.args:
            continue
        truth_file = _truth_file_for_arg(node.args[0])
        if not truth_file:
            continue
        owner = _enclosing_function(parents, node).name
        rows.add((path, owner, truth_file, helper))
    return rows


class StateStoreEntryInventoryTests(unittest.TestCase):
    def test_p0_truth_files_are_explicit(self) -> None:
        self.assertEqual(
            {
                "supervisor-state.json",
                "backend-registry.json",
                "runtime-mode.txt",
                "runtime-effective-mode.txt",
            },
            set(P0_TRUTH_FILES),
        )

    def test_inventory_rows_have_current_classification_not_execution_order(
        self,
    ) -> None:
        expected_classes = {
            MUTATE,
            REPAIR,
            SUBPROCESS_ADJACENT,
            AMBIENT_FIX_REQUIRED,
        }
        for row in STATE_STORE_ENTRY_INVENTORY:
            with self.subTest(owner=row.current_owner, truth_file=row.truth_file):
                self.assertIn(row.truth_file, P0_TRUTH_FILES)
                self.assertIn(row.current_effect_class, expected_classes)
                self.assertIs(row.state_store_candidate, True)
                self.assertIn(row.write_helper, WRITE_HELPERS)

    def test_inventory_matches_current_direct_p0_write_surfaces(self) -> None:
        discovered = set()
        for module_path in (RUNTIME, SANDBOX_OWNER_HELPERS):
            discovered |= _direct_p0_write_rows(module_path)

        expected = {
            (row.module, row.current_owner, row.truth_file, row.write_helper)
            for row in STATE_STORE_ENTRY_INVENTORY
        }
        self.assertEqual(expected, discovered)

    def test_each_p0_truth_file_has_declared_current_owner(self) -> None:
        files_with_owners = {row.truth_file for row in STATE_STORE_ENTRY_INVENTORY}
        self.assertEqual(P0_TRUTH_FILES, files_with_owners)

    def test_read_and_probe_surfaces_are_not_p0_write_owners(self) -> None:
        forbidden_owners = {
            "summarize_status",
            "build_status_snapshot_payload",
            "run_healthcheck_probe",
            "mode_get",
            "list_accounts",
        }
        inventory_owners = {row.current_owner for row in STATE_STORE_ENTRY_INVENTORY}
        self.assertEqual(set(), inventory_owners & forbidden_owners)

    def test_repair_writers_are_explicitly_classified(self) -> None:
        repair_owners = {
            row.current_owner
            for row in STATE_STORE_ENTRY_INVENTORY
            if row.current_effect_class == REPAIR
        }
        self.assertTrue(
            {
                "refresh_last_known_good_proxy_from_healthcheck",
                "write_stable_runtime_consumer_snapshot",
                "reconcile_stable_fallback",
                "reconcile_stable_recovery_success",
            }
            <= repair_owners
        )


if __name__ == "__main__":
    unittest.main()
