# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import runtime as runtime_mod
from wild_boar_proxy import runtime_modes


REPO_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_IMPORT_PREFIXES_BY_MODULE = {
    "wild_boar_proxy.runtime_errors": (
        "tools",
        "wild_boar_proxy.cli",
        "wild_boar_proxy.operator_surface",
        "wild_boar_proxy.runtime",
        "wild_boar_proxy.web",
        "wild_boar_proxy.web_design_command_adapter",
        "wild_boar_proxy.web_design_live_server",
        "wild_boar_proxy.web_design_ui",
        "wild_boar_proxy.web_ui",
    ),
    "wild_boar_proxy.runtime": (
        "tools",
        "wild_boar_proxy.cli",
        "wild_boar_proxy.operator_surface",
        "wild_boar_proxy.web",
        "wild_boar_proxy.web_design_command_adapter",
        "wild_boar_proxy.web_design_live_server",
        "wild_boar_proxy.web_design_ui",
        "wild_boar_proxy.web_ui",
    ),
    "wild_boar_proxy.runtime_modes": (
        "tools",
        "wild_boar_proxy.accounts_lifecycle",
        "wild_boar_proxy.cli",
        "wild_boar_proxy.operator_surface",
        "wild_boar_proxy.runtime",
        "wild_boar_proxy.runtime_health",
        "wild_boar_proxy.runtime_repair",
        "wild_boar_proxy.web",
        "wild_boar_proxy.web_design_command_adapter",
        "wild_boar_proxy.web_design_live_server",
        "wild_boar_proxy.web_design_ui",
        "wild_boar_proxy.web_ui",
    ),
}

RUNTIME_MODULE_PATHS = {
    "wild_boar_proxy.runtime_errors": REPO_ROOT / "wild_boar_proxy" / "runtime_errors.py",
    "wild_boar_proxy.runtime": REPO_ROOT / "wild_boar_proxy" / "runtime.py",
    "wild_boar_proxy.runtime_modes": REPO_ROOT / "wild_boar_proxy" / "runtime_modes.py",
}


def _absolute_import_name(module_name: str, node: ast.ImportFrom) -> list[str]:
    if node.level == 0:
        return [node.module or ""]
    module_parts = module_name.split(".")
    base_parts = module_parts[: -node.level]
    if node.module:
        return [".".join([*base_parts, node.module])]
    return [".".join([*base_parts, alias.name]) for alias in node.names]


def _iter_imported_modules(source: str, module_name: str) -> list[str]:
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.extend(name for name in _absolute_import_name(module_name, node) if name)
    return imported


def _matches_prefix(imported_module: str, forbidden_prefix: str) -> bool:
    return imported_module == forbidden_prefix or imported_module.startswith(
        f"{forbidden_prefix}."
    )


def _forbidden_imports(source: str, module_name: str) -> list[str]:
    prefixes = FORBIDDEN_IMPORT_PREFIXES_BY_MODULE[module_name]
    return [
        imported
        for imported in _iter_imported_modules(source, module_name)
        if any(_matches_prefix(imported, prefix) for prefix in prefixes)
    ]


def _runtime_paths(root: Path) -> runtime_mod.RuntimePaths:
    profile_dir = root / "profile"
    managed_dir = profile_dir / "managed"
    stable_dir = root / "stable"
    profile_dir.mkdir(parents=True)
    managed_dir.mkdir(parents=True)
    stable_dir.mkdir(parents=True)
    (profile_dir / "runtime-mode.txt").write_text("stable\n", encoding="utf-8")
    (profile_dir / "runtime-effective-mode.txt").write_text("managed\n", encoding="utf-8")
    (managed_dir / "supervisor-state.json").write_text(
        json.dumps({"effective_mode": "managed"}) + "\n",
        encoding="utf-8",
    )
    (managed_dir / "managed-config.yaml").write_text(
        "host: 127.0.0.1\nport: 1\n",
        encoding="utf-8",
    )
    (stable_dir / "config.yaml").write_text(
        "host: 127.0.0.1\nport: 1\n",
        encoding="utf-8",
    )
    return runtime_mod.RuntimePaths(
        profile_dir=profile_dir,
        managed_dir=managed_dir,
        stable_config=stable_dir / "config.yaml",
        auth_file=profile_dir / "auth.json",
        config_toml=profile_dir / "config.toml",
        runtime_mode_file=profile_dir / "runtime-mode.txt",
        runtime_effective_mode_file=profile_dir / "runtime-effective-mode.txt",
        registry_file=managed_dir / "backend-registry.json",
        state_file=managed_dir / "supervisor-state.json",
        managed_config_file=managed_dir / "managed-config.yaml",
        launcher_script=profile_dir / "codex-custom-launch.sh",
        sync_script=managed_dir / "supervisor-sync.sh",
        accounts_bin=managed_dir / "bin" / "codex-accounts",
        onboard_bin=managed_dir / "bin" / "codex-onboard",
        lock_file=managed_dir / "wild-boar-proxy.lock",
        launcher_lock_file=managed_dir / "launcher.lock",
        repair_target_inventory_dir=managed_dir / "repair-target-inventory",
        repair_target_reference_file=managed_dir / "repair-target-reference.json",
        target_switch_transaction_file=managed_dir / "target-switch-transaction.json",
        stable_runtime_generated_config_file=managed_dir / "stable-runtime-config.yaml",
    )


class RuntimeDependencyDirectionTests(unittest.TestCase):
    def test_detector_flags_relative_forbidden_import(self) -> None:
        source = "from . import web_ui\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.runtime_modes"),
            ["wild_boar_proxy.web_ui"],
        )

    def test_detector_flags_absolute_tools_import(self) -> None:
        source = "import tools.release_bundle\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.runtime"),
            ["tools.release_bundle"],
        )

    def test_h1_runtime_modules_do_not_import_forbidden_layers(self) -> None:
        for module_name, path in RUNTIME_MODULE_PATHS.items():
            with self.subTest(module=module_name):
                source = path.read_text(encoding="utf-8")
                self.assertEqual(_forbidden_imports(source, module_name), [])

    def test_runtime_mode_get_facade_matches_direct_modes_module(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))

            facade_payload = runtime_mod.mode_get(paths)
            direct_payload = runtime_modes.mode_get(paths)

        self.assertEqual(facade_payload, direct_payload)
        self.assertEqual(facade_payload["effect"], "read")
        self.assertEqual(facade_payload["changed_files"], [])
        self.assertEqual(facade_payload["desired_mode"], "stable")
        self.assertEqual(facade_payload["effective_mode"], "stable")

    def test_runtime_mode_get_invalid_state_error_matches_facade(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))
            paths.state_file.write_text("{not-json", encoding="utf-8")

            with self.assertRaises(runtime_mod.RuntimeErrorInfo) as facade_raised:
                runtime_mod.mode_get(paths)
            with self.assertRaises(runtime_mod.RuntimeErrorInfo) as direct_raised:
                runtime_modes.mode_get(paths)

        self.assertEqual(
            facade_raised.exception.machine_error_code,
            direct_raised.exception.machine_error_code,
        )
        self.assertEqual(facade_raised.exception.machine_error_code, "INVALID_JSON_FILE")
        self.assertEqual(facade_raised.exception.operator_action, "stop")
        self.assertEqual(direct_raised.exception.operator_action, "stop")

    def test_runtime_mode_get_does_not_write_runtime_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))
            tracked_paths = [
                paths.runtime_mode_file,
                paths.runtime_effective_mode_file,
                paths.state_file,
                paths.managed_config_file,
                paths.stable_config,
            ]
            before = {path: path.read_bytes() for path in tracked_paths}

            payload = runtime_mod.mode_get(paths)

            after = {path: path.read_bytes() for path in tracked_paths}

        self.assertEqual(payload["effect"], "read")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(after, before)
