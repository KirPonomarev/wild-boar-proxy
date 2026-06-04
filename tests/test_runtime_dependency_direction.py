# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from wild_boar_proxy import accounts_lifecycle
from wild_boar_proxy import installer
from wild_boar_proxy import packaging
from wild_boar_proxy import rollout
from wild_boar_proxy import runtime as runtime_mod
from wild_boar_proxy import runtime_health
from wild_boar_proxy import runtime_modes
from wild_boar_proxy import runtime_repair
from wild_boar_proxy import runtime_status


REPO_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_IMPORT_PREFIXES_BY_MODULE = {
    "wild_boar_proxy.accounts_lifecycle": (
        "tools",
        "wild_boar_proxy.cli",
        "wild_boar_proxy.operator_surface",
        "wild_boar_proxy.runtime",
        "wild_boar_proxy.runtime_health",
        "wild_boar_proxy.runtime_modes",
        "wild_boar_proxy.runtime_repair",
        "wild_boar_proxy.runtime_status",
        "wild_boar_proxy.web",
        "wild_boar_proxy.web_design_command_adapter",
        "wild_boar_proxy.web_design_live_server",
        "wild_boar_proxy.web_design_ui",
        "wild_boar_proxy.web_ui",
    ),
    "wild_boar_proxy.rollout": (
        "tools",
        "wild_boar_proxy.accounts_lifecycle",
        "wild_boar_proxy.cli",
        "wild_boar_proxy.operator_surface",
        "wild_boar_proxy.runtime",
        "wild_boar_proxy.runtime_health",
        "wild_boar_proxy.runtime_modes",
        "wild_boar_proxy.runtime_repair",
        "wild_boar_proxy.runtime_status",
        "wild_boar_proxy.web",
        "wild_boar_proxy.web_design_command_adapter",
        "wild_boar_proxy.web_design_live_server",
        "wild_boar_proxy.web_design_ui",
        "wild_boar_proxy.web_ui",
    ),
    "wild_boar_proxy.installer": (
        "tools",
        "wild_boar_proxy.accounts_lifecycle",
        "wild_boar_proxy.cli",
        "wild_boar_proxy.operator_surface",
        "wild_boar_proxy.runtime",
        "wild_boar_proxy.runtime_health",
        "wild_boar_proxy.runtime_modes",
        "wild_boar_proxy.runtime_repair",
        "wild_boar_proxy.runtime_status",
        "wild_boar_proxy.web",
        "wild_boar_proxy.web_design_command_adapter",
        "wild_boar_proxy.web_design_live_server",
        "wild_boar_proxy.web_design_ui",
        "wild_boar_proxy.web_ui",
    ),
    "wild_boar_proxy.packaging": (
        "tools",
        "wild_boar_proxy.accounts_lifecycle",
        "wild_boar_proxy.cli",
        "wild_boar_proxy.installer",
        "wild_boar_proxy.operator_surface",
        "wild_boar_proxy.runtime",
        "wild_boar_proxy.runtime_health",
        "wild_boar_proxy.runtime_modes",
        "wild_boar_proxy.runtime_repair",
        "wild_boar_proxy.runtime_status",
        "wild_boar_proxy.web",
        "wild_boar_proxy.web_design_command_adapter",
        "wild_boar_proxy.web_design_live_server",
        "wild_boar_proxy.web_design_ui",
        "wild_boar_proxy.web_ui",
    ),
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
    "wild_boar_proxy.runtime_health": (
        "tools",
        "wild_boar_proxy.accounts_lifecycle",
        "wild_boar_proxy.cli",
        "wild_boar_proxy.mutation_ledger",
        "wild_boar_proxy.operator_surface",
        "wild_boar_proxy.process_runner",
        "wild_boar_proxy.runtime",
        "wild_boar_proxy.runtime_repair",
        "wild_boar_proxy.state_startup_contract",
        "wild_boar_proxy.state_startup_lock",
        "wild_boar_proxy.state_startup_recovery",
        "wild_boar_proxy.state_startup_schema",
        "wild_boar_proxy.state_startup_truth",
        "wild_boar_proxy.state_transaction",
        "wild_boar_proxy.web",
        "wild_boar_proxy.web_design_command_adapter",
        "wild_boar_proxy.web_design_live_server",
        "wild_boar_proxy.web_design_ui",
        "wild_boar_proxy.web_ui",
    ),
    "wild_boar_proxy.runtime_repair": (
        "tools",
        "wild_boar_proxy.accounts_lifecycle",
        "wild_boar_proxy.cli",
        "wild_boar_proxy.mutation_ledger",
        "wild_boar_proxy.operator_surface",
        "wild_boar_proxy.process_runner",
        "wild_boar_proxy.runtime",
        "wild_boar_proxy.runtime_health",
        "wild_boar_proxy.runtime_status",
        "wild_boar_proxy.state_startup_contract",
        "wild_boar_proxy.state_startup_lock",
        "wild_boar_proxy.state_startup_recovery",
        "wild_boar_proxy.state_startup_schema",
        "wild_boar_proxy.state_startup_truth",
        "wild_boar_proxy.state_transaction",
        "wild_boar_proxy.web",
        "wild_boar_proxy.web_design_command_adapter",
        "wild_boar_proxy.web_design_live_server",
        "wild_boar_proxy.web_design_ui",
        "wild_boar_proxy.web_ui",
    ),
    "wild_boar_proxy.runtime_status": (
        "tools",
        "wild_boar_proxy.accounts_lifecycle",
        "wild_boar_proxy.cli",
        "wild_boar_proxy.mutation_ledger",
        "wild_boar_proxy.operator_surface",
        "wild_boar_proxy.process_runner",
        "wild_boar_proxy.runtime",
        "wild_boar_proxy.runtime_health",
        "wild_boar_proxy.runtime_repair",
        "wild_boar_proxy.state_startup_contract",
        "wild_boar_proxy.state_startup_lock",
        "wild_boar_proxy.state_startup_recovery",
        "wild_boar_proxy.state_startup_schema",
        "wild_boar_proxy.state_startup_truth",
        "wild_boar_proxy.state_transaction",
        "wild_boar_proxy.web",
        "wild_boar_proxy.web_design_command_adapter",
        "wild_boar_proxy.web_design_live_server",
        "wild_boar_proxy.web_design_ui",
        "wild_boar_proxy.web_ui",
    ),
}

RUNTIME_MODULE_PATHS = {
    "wild_boar_proxy.accounts_lifecycle": REPO_ROOT
    / "wild_boar_proxy"
    / "accounts_lifecycle.py",
    "wild_boar_proxy.installer": REPO_ROOT / "wild_boar_proxy" / "installer.py",
    "wild_boar_proxy.packaging": REPO_ROOT / "wild_boar_proxy" / "packaging.py",
    "wild_boar_proxy.rollout": REPO_ROOT / "wild_boar_proxy" / "rollout.py",
    "wild_boar_proxy.runtime_errors": REPO_ROOT / "wild_boar_proxy" / "runtime_errors.py",
    "wild_boar_proxy.runtime": REPO_ROOT / "wild_boar_proxy" / "runtime.py",
    "wild_boar_proxy.runtime_health": REPO_ROOT / "wild_boar_proxy" / "runtime_health.py",
    "wild_boar_proxy.runtime_modes": REPO_ROOT / "wild_boar_proxy" / "runtime_modes.py",
    "wild_boar_proxy.runtime_repair": REPO_ROOT / "wild_boar_proxy" / "runtime_repair.py",
    "wild_boar_proxy.runtime_status": REPO_ROOT / "wild_boar_proxy" / "runtime_status.py",
}
CLI_MODULE_PATH = REPO_ROOT / "wild_boar_proxy" / "cli.py"


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


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Call):
        return _dotted_name(node.func)
    return ""


def _call_names(source: str) -> set[str]:
    tree = ast.parse(source)
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            dotted = _dotted_name(node.func)
            if dotted:
                calls.add(dotted)
                calls.add(dotted.rsplit(".", 1)[-1])
    return calls


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


def _status_runtime_paths(root: Path) -> runtime_mod.RuntimePaths:
    paths = _runtime_paths(root)
    auth_dir = root / "auth"
    auth_dir.mkdir()
    backend_auth = auth_dir / "backend-a.json"
    backend_auth.write_text("{}\n", encoding="utf-8")
    paths.config_toml.write_text(
        'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:1/v1"\n',
        encoding="utf-8",
    )
    paths.registry_file.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "version": 2,
                "updated_at": "2026-06-01T00:00:00+00:00",
                "stable_default_backend_id": "default-backend",
                "pool_policy": {
                    "active_min": 1,
                    "active_target": 2,
                    "reserve_target": 0,
                },
                "backends": [
                    {
                        "id": "backend-a",
                        "label": "Backend A",
                        "pool": "active",
                        "status": "healthy",
                        "manual_hold": False,
                        "auth_ref": str(backend_auth),
                        "fail_count": 0,
                        "success_count": 1,
                    }
                ],
            },
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths.state_file.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "version": 2,
                "status": "healthy",
                "effective_mode": "stable",
                "selected_backend_ids": ["backend-a"],
                "managed_port": 9999,
                "last_error": "",
            },
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths.runtime_effective_mode_file.write_text("stable\n", encoding="utf-8")
    paths.managed_config_file.write_text("host: 127.0.0.1\nport: 9999\n", encoding="utf-8")
    return paths


def _snapshot_files(paths: list[Path]) -> dict[Path, tuple[bool, bytes]]:
    return {
        path: (path.exists(), path.read_bytes() if path.exists() else b"")
        for path in paths
    }


def _normalize_observed_times(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "<OBSERVED_AT>"
                if key == "observed_at_utc" and isinstance(item, str) and item
                else _normalize_observed_times(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_observed_times(item) for item in value]
    return value


def _assert_status_snapshot_contract(
    testcase: unittest.TestCase, payload: dict[str, object]
) -> None:
    testcase.assertEqual(payload["status"], "ok")
    testcase.assertEqual(payload["exit_code"], 0)
    testcase.assertEqual(payload["human_message"], "Runtime status snapshot is available.")
    testcase.assertEqual(payload["machine_error_code"], "OK")
    testcase.assertEqual(payload["changed_files"], [])
    testcase.assertEqual(payload["next_action"], "none")
    testcase.assertEqual(payload["liveness"], "unknown")
    testcase.assertEqual(payload["severity"], "recoverable")
    testcase.assertEqual(payload["operator_action"], "none")
    testcase.assertEqual(payload["effect"], "read")
    testcase.assertEqual(payload["desired_mode"], "stable")
    testcase.assertEqual(payload["effective_mode"], "stable")
    testcase.assertEqual(payload["configured_model"], "gpt-5.4")
    testcase.assertEqual(payload["requested_model"], "gpt-5.4")
    testcase.assertEqual(
        payload["pool_summary"],
        {
            "active": 1,
            "reserve": 0,
            "retired": 0,
            "healthy": 0,
            "degraded": 0,
            "down": 0,
            "selected_backend_ids": ["backend-a"],
            "backend_count": 1,
        },
    )
    auth_pool_hygiene = payload["auth_pool_hygiene"]
    testcase.assertEqual(auth_pool_hygiene["status"], "launch_capable_available")
    testcase.assertEqual(auth_pool_hygiene["machine_error_code"], "OK")
    testcase.assertEqual(auth_pool_hygiene["blocking_reason"], "")
    testcase.assertEqual(auth_pool_hygiene["launch_capable_backend_count"], 1)
    testcase.assertEqual(
        auth_pool_hygiene["selected_backend_ids_observed"], ["backend-a"]
    )
    testcase.assertIs(auth_pool_hygiene["delegated_from_status"], False)
    testcase.assertEqual(
        payload["launch_readiness"]["machine_error_code"],
        "LIVE_ATTESTATION_NOT_RUN_BY_STATUS",
    )
    testcase.assertEqual(payload["launch_readiness"]["status"], "not_evaluated")
    testcase.assertEqual(payload["launch_readiness"]["owner_command_surface"], "status --json")
    testcase.assertIs(payload["launch_readiness"]["delegated_from_status"], False)
    testcase.assertIs(payload["launch_readiness"]["gate_passed"], False)
    testcase.assertEqual(
        payload["runtime_guardrails"]["owner_command_surface"], "status --json"
    )
    testcase.assertIs(payload["runtime_guardrails"]["delegated_from_status"], False)
    testcase.assertEqual(payload["attestation_summary"]["status"], "not_run")
    testcase.assertEqual(
        payload["attestation_summary"]["machine_error_code"],
        "LIVE_ATTESTATION_NOT_RUN_BY_STATUS",
    )
    testcase.assertEqual(
        payload["attestation_summary"]["attestation_source"], "status --json"
    )
    testcase.assertEqual(payload["attestation_summary"]["observed_at_utc"], "")


def _assert_health_probe_contract(
    testcase: unittest.TestCase, payload: dict[str, object]
) -> None:
    testcase.assertEqual(payload["status"], "error")
    testcase.assertEqual(payload["exit_code"], 1)
    testcase.assertEqual(payload["machine_error_code"], "LISTENER_DOWN")
    testcase.assertEqual(payload["changed_files"], [])
    testcase.assertEqual(payload["effect"], "probe")
    testcase.assertEqual(payload["liveness"], "down")
    testcase.assertEqual(payload["severity"], "recoverable")
    testcase.assertEqual(payload["operator_action"], "retry")
    testcase.assertEqual(payload["attestation"]["attestation_source"], "healthcheck --json")
    testcase.assertEqual(
        payload["launch_readiness"]["owner_command_surface"],
        "healthcheck --json",
    )
    testcase.assertEqual(
        payload["runtime_guardrails"]["owner_command_surface"],
        "healthcheck --json",
    )
    testcase.assertNotIn("mutation_id", payload)
    testcase.assertNotIn("mutation_ledger", payload)
    testcase.assertNotIn("deterministic_stable_recovery_result", payload)
    testcase.assertNotIn("proxy_reprobe_adoption_result", payload)


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

    def test_detector_flags_status_repair_import(self) -> None:
        source = "from . import runtime_repair\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.runtime_status"),
            ["wild_boar_proxy.runtime_repair"],
        )

    def test_detector_flags_status_web_import(self) -> None:
        source = "import wild_boar_proxy.web_design_live_server\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.runtime_status"),
            ["wild_boar_proxy.web_design_live_server"],
        )

    def test_detector_flags_status_mutation_layer_import(self) -> None:
        source = "from . import state_transaction\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.runtime_status"),
            ["wild_boar_proxy.state_transaction"],
        )

    def test_detector_flags_health_runtime_import(self) -> None:
        source = "from . import runtime\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.runtime_health"),
            ["wild_boar_proxy.runtime"],
        )

    def test_detector_flags_health_repair_import(self) -> None:
        source = "from . import runtime_repair\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.runtime_health"),
            ["wild_boar_proxy.runtime_repair"],
        )

    def test_detector_flags_health_mutation_layer_import(self) -> None:
        source = "from . import mutation_ledger\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.runtime_health"),
            ["wild_boar_proxy.mutation_ledger"],
        )

    def test_detector_flags_repair_runtime_import(self) -> None:
        source = "from . import runtime\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.runtime_repair"),
            ["wild_boar_proxy.runtime"],
        )

    def test_detector_flags_repair_health_import(self) -> None:
        source = "from . import runtime_health\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.runtime_repair"),
            ["wild_boar_proxy.runtime_health"],
        )

    def test_detector_flags_repair_mutation_layer_import(self) -> None:
        source = "from . import mutation_ledger\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.runtime_repair"),
            ["wild_boar_proxy.mutation_ledger"],
        )

    def test_detector_flags_repair_startup_state_imports(self) -> None:
        source = (
            "from . import state_startup_contract\n"
            "from . import state_startup_lock\n"
            "from . import state_startup_recovery\n"
            "from . import state_startup_schema\n"
            "from . import state_startup_truth\n"
            "from . import state_transaction\n"
        )

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.runtime_repair"),
            [
                "wild_boar_proxy.state_startup_contract",
                "wild_boar_proxy.state_startup_lock",
                "wild_boar_proxy.state_startup_recovery",
                "wild_boar_proxy.state_startup_schema",
                "wild_boar_proxy.state_startup_truth",
                "wild_boar_proxy.state_transaction",
            ],
        )

    def test_detector_flags_accounts_lifecycle_runtime_import(self) -> None:
        source = "from . import runtime\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.accounts_lifecycle"),
            ["wild_boar_proxy.runtime"],
        )

    def test_detector_flags_rollout_runtime_import(self) -> None:
        source = "from . import runtime\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.rollout"),
            ["wild_boar_proxy.runtime"],
        )

    def test_detector_flags_installer_runtime_import(self) -> None:
        source = "from . import runtime\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.installer"),
            ["wild_boar_proxy.runtime"],
        )

    def test_detector_flags_packaging_runtime_import(self) -> None:
        source = "from . import runtime\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.packaging"),
            ["wild_boar_proxy.runtime"],
        )

    def test_runtime_split_modules_do_not_import_forbidden_layers(self) -> None:
        for module_name, path in RUNTIME_MODULE_PATHS.items():
            with self.subTest(module=module_name):
                source = path.read_text(encoding="utf-8")
                self.assertEqual(_forbidden_imports(source, module_name), [])

    def test_runtime_repair_module_does_not_import_startup_state_modules(
        self,
    ) -> None:
        source = RUNTIME_MODULE_PATHS["wild_boar_proxy.runtime_repair"].read_text(
            encoding="utf-8"
        )
        imported_modules = set(
            _iter_imported_modules(source, "wild_boar_proxy.runtime_repair")
        )
        forbidden_modules = {
            "wild_boar_proxy.state_startup_contract",
            "wild_boar_proxy.state_startup_lock",
            "wild_boar_proxy.state_startup_recovery",
            "wild_boar_proxy.state_startup_schema",
            "wild_boar_proxy.state_startup_truth",
            "wild_boar_proxy.state_transaction",
        }

        self.assertEqual(imported_modules & forbidden_modules, set())

    def test_cli_healthcheck_dispatch_imports_split_owner_surfaces(self) -> None:
        source = CLI_MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = _iter_imported_modules(source, "wild_boar_proxy.cli")
        runtime_imported_names: set[str] = set()
        split_imported_names: dict[str, set[str]] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            absolute_modules = _absolute_import_name("wild_boar_proxy.cli", node)
            if absolute_modules == ["wild_boar_proxy.runtime"]:
                runtime_imported_names.update(alias.name for alias in node.names)
            if absolute_modules in (
                ["wild_boar_proxy.runtime_health"],
                ["wild_boar_proxy.runtime_repair"],
            ):
                split_imported_names.setdefault(absolute_modules[0], set()).update(
                    alias.name for alias in node.names
                )

        self.assertIn("wild_boar_proxy.runtime_health", imported_modules)
        self.assertIn("wild_boar_proxy.runtime_repair", imported_modules)
        self.assertIn(
            "run_healthcheck_probe",
            split_imported_names.get("wild_boar_proxy.runtime_health", set()),
        )
        self.assertIn(
            "run_healthcheck_repair",
            split_imported_names.get("wild_boar_proxy.runtime_repair", set()),
        )
        self.assertNotIn("run_healthcheck_probe", runtime_imported_names)
        self.assertNotIn("run_healthcheck_repair", runtime_imported_names)

    def test_runtime_status_snapshot_does_not_call_health_or_repair_owner_surfaces(self) -> None:
        source = RUNTIME_MODULE_PATHS["wild_boar_proxy.runtime_status"].read_text(
            encoding="utf-8"
        )
        calls = _call_names(source)
        forbidden = {
            "run_current_proxy_owner_path_activation",
            "run_healthcheck",
            "run_healthcheck_probe",
            "run_healthcheck_repair",
            "run_stable_repair_apply",
            "run_stable_repair_dry_run",
            "run_stable_runtime_launcher_attempt",
        }

        self.assertEqual(calls & forbidden, set())

    def test_runtime_health_probe_does_not_call_repair_owner_surfaces(self) -> None:
        source = RUNTIME_MODULE_PATHS["wild_boar_proxy.runtime_health"].read_text(
            encoding="utf-8"
        )
        calls = _call_names(source)
        forbidden = {
            "clear_stale_managed_pid_if_needed",
            "reconcile_stable_fallback",
            "refresh_last_known_good_proxy_from_healthcheck",
            "run_current_proxy_owner_path_activation",
            "run_healthcheck_repair",
            "run_stable_runtime_launcher_attempt",
            "run_startup_contract_repair_owner_path",
            "write_stable_runtime_consumer_snapshot",
        }

        self.assertEqual(calls & forbidden, set())

    def test_runtime_repair_wrapper_does_not_call_repair_primitives_directly(self) -> None:
        source = RUNTIME_MODULE_PATHS["wild_boar_proxy.runtime_repair"].read_text(
            encoding="utf-8"
        )
        calls = _call_names(source)
        forbidden = {
            "clear_stale_managed_pid_if_needed",
            "reconcile_stable_fallback",
            "refresh_last_known_good_proxy_from_healthcheck",
            "run_current_proxy_owner_path_activation",
            "run_stable_runtime_launcher_attempt",
            "run_startup_contract_repair_owner_path",
            "write_stable_runtime_consumer_snapshot",
        }

        self.assertEqual(calls & forbidden, set())

    def test_accounts_lifecycle_wrapper_does_not_call_owner_primitives_directly(
        self,
    ) -> None:
        source = RUNTIME_MODULE_PATHS["wild_boar_proxy.accounts_lifecycle"].read_text(
            encoding="utf-8"
        )
        calls = _call_names(source)
        forbidden = {
            "build_command_payload",
            "dual_lock",
            "materialize_selected_backend_snapshot_for_sync",
            "read_json",
            "run_healthcheck_probe",
            "serialized_lock",
            "run_bounded_process",
            "run_sync_for_owner_path_under_lock",
            "observe_status_proof_for_owner_path_under_lock",
        }

        self.assertEqual(calls & forbidden, set())
        self.assertNotIn("EFFECT_READ", source)

    def test_rollout_wrapper_does_not_call_owner_primitives_directly(self) -> None:
        source = RUNTIME_MODULE_PATHS["wild_boar_proxy.rollout"].read_text(
            encoding="utf-8"
        )
        calls = _call_names(source)
        forbidden = {
            "build_command_payload",
            "coerce_nonnegative_int",
            "detect_changed_files",
            "detect_changed_files_by_state",
            "dual_lock",
            "export_scale_evidence_bundle",
            "get_stable_policy_drift",
            "list_accounts",
            "materialize_rollout_stage_advance_stable_auth",
            "materialize_selected_backend_snapshot_for_sync",
            "observe_current_stage_from_pool_policy",
            "observe_status_proof_for_owner_path_under_lock",
            "read_json",
            "restore_path_state",
            "restore_promotion_owner_path_runtime_surfaces",
            "restore_rollout_stage_advance_inventory_dir_state",
            "run_bounded_process",
            "run_healthcheck",
            "run_healthcheck_probe",
            "run_healthcheck_repair",
            "run_launch_smoke",
            "run_policy_stage_set",
            "run_promote",
            "run_rollout_attestation_healthcheck",
            "run_rollout_evidence_capture",
            "run_rollout_stage_advance",
            "run_rollout_stage_prove",
            "run_stable_runtime_launcher_attempt",
            "run_sync_for_owner_path_under_lock",
            "runtime_write_surface_candidates",
            "serialized_lock",
            "snapshot_known_files",
            "snapshot_path_state",
            "snapshot_path_states",
            "socket_is_listening",
            "summarize_rollout_stage_advance_postflight",
            "summarize_rollout_stage_advance_preflight",
            "summarize_registry_pool_counts",
            "summarize_status",
            "summarize_stable_10_rollback_readiness",
            "summarize_stage_pool_policy_mapping",
            "write_json_artifact",
            "write_json_atomic",
            "write_text_atomic",
        }

        self.assertEqual(calls & forbidden, set())
        self.assertNotIn("EFFECT_READ", source)

    def test_installer_wrapper_does_not_call_owner_primitives_directly(self) -> None:
        source = RUNTIME_MODULE_PATHS["wild_boar_proxy.installer"].read_text(
            encoding="utf-8"
        )
        calls = _call_names(source)
        forbidden = {
            "build_command_payload",
            "detect_changed_files_by_state",
            "ensure_installed_layout",
            "ensure_repo_owned_operator_wrapper_chain",
            "ensure_repo_owned_owner_helper_chain",
            "import_legacy_layout",
            "installer_managed_paths",
            "installer_operator_wrapper_paths",
            "installer_owner_helper_paths",
            "read_json",
            "read_text",
            "restore_path_state",
            "serialized_lock",
            "snapshot_path_states",
            "write_json_atomic",
            "write_text_atomic",
        }

        self.assertEqual(calls & forbidden, set())
        self.assertNotIn("EFFECT_READ", source)

    def test_packaging_wrapper_does_not_call_owner_primitives_directly(self) -> None:
        source = RUNTIME_MODULE_PATHS["wild_boar_proxy.packaging"].read_text(
            encoding="utf-8"
        )
        calls = _call_names(source)
        forbidden = {
            "Path",
            "build_command_payload",
            "hash_directory_files",
            "hash_file",
            "json.loads",
            "mkdir",
            "os.access",
            "open",
            "probe_runtime_tk_support",
            "read_text",
            "shutil.copy2",
            "shutil.rmtree",
            "tarfile.open",
            "write_executable_text_atomic",
            "write_json_artifact",
            "write_text_atomic",
        }

        self.assertEqual(calls & forbidden, set())
        self.assertNotIn("EFFECT_READ", source)

    def test_rollout_rotation_inspect_wrapper_passes_exact_impl_args(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_rollout_rotation_inspect_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "rollout-rotation-inspect",
                "lock_acquired": kwargs["lock_acquired"],
            }

        dependencies = rollout.RolloutDependencies(
            run_rollout_rotation_inspect_impl=fake_run_rollout_rotation_inspect_impl,
            run_rollout_posture_inspect_impl=lambda *args, **kwargs: {},
            run_rollout_evidence_capture_impl=lambda *args, **kwargs: {},
            run_rollout_stage_prove_impl=lambda *args, **kwargs: {},
            run_rollout_stage_advance_impl=lambda *args, **kwargs: {},
        )

        default_payload = rollout.run_rollout_rotation_inspect(
            "paths-sentinel",
            dependencies=dependencies,
        )
        locked_payload = rollout.run_rollout_rotation_inspect(
            "paths-sentinel",
            lock_acquired=True,
            dependencies=dependencies,
        )

        self.assertEqual(default_payload["surface"], "rollout-rotation-inspect")
        self.assertIs(default_payload["lock_acquired"], False)
        self.assertIs(locked_payload["lock_acquired"], True)
        self.assertEqual(
            calls,
            [
                (("paths-sentinel",), {"lock_acquired": False}),
                (("paths-sentinel",), {"lock_acquired": True}),
            ],
        )

    def test_rollout_posture_inspect_wrapper_passes_exact_impl_args(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_rollout_posture_inspect_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "rollout-posture-inspect",
                "stage": args[1],
            }

        dependencies = rollout.RolloutDependencies(
            run_rollout_rotation_inspect_impl=lambda *args, **kwargs: {},
            run_rollout_posture_inspect_impl=fake_run_rollout_posture_inspect_impl,
            run_rollout_evidence_capture_impl=lambda *args, **kwargs: {},
            run_rollout_stage_prove_impl=lambda *args, **kwargs: {},
            run_rollout_stage_advance_impl=lambda *args, **kwargs: {},
        )

        payload = rollout.run_rollout_posture_inspect(
            "paths-sentinel",
            "20",
            dependencies=dependencies,
        )

        self.assertEqual(payload["surface"], "rollout-posture-inspect")
        self.assertEqual(payload["stage"], "20")
        self.assertEqual(calls, [(("paths-sentinel", "20"), {})])

    def test_rollout_evidence_capture_wrapper_passes_exact_impl_args(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_rollout_evidence_capture_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "rollout-evidence-capture",
                "target": args[1],
            }

        dependencies = rollout.RolloutDependencies(
            run_rollout_rotation_inspect_impl=lambda *args, **kwargs: {},
            run_rollout_posture_inspect_impl=lambda *args, **kwargs: {},
            run_rollout_evidence_capture_impl=fake_run_rollout_evidence_capture_impl,
            run_rollout_stage_prove_impl=lambda *args, **kwargs: {},
            run_rollout_stage_advance_impl=lambda *args, **kwargs: {},
        )

        payload = rollout.run_rollout_evidence_capture(
            "paths-sentinel",
            "16",
            dependencies=dependencies,
        )

        self.assertEqual(payload["surface"], "rollout-evidence-capture")
        self.assertEqual(payload["target"], "16")
        self.assertEqual(calls, [(("paths-sentinel", "16"), {})])

    def test_rollout_stage_prove_wrapper_passes_exact_impl_args(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_rollout_stage_prove_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "rollout-stage-prove",
                "stage": args[1],
                "lock_acquired": kwargs["lock_acquired"],
            }

        dependencies = rollout.RolloutDependencies(
            run_rollout_rotation_inspect_impl=lambda *args, **kwargs: {},
            run_rollout_posture_inspect_impl=lambda *args, **kwargs: {},
            run_rollout_evidence_capture_impl=lambda *args, **kwargs: {},
            run_rollout_stage_prove_impl=fake_run_rollout_stage_prove_impl,
            run_rollout_stage_advance_impl=lambda *args, **kwargs: {},
        )

        default_payload = rollout.run_rollout_stage_prove(
            "paths-sentinel",
            "10",
            dependencies=dependencies,
        )
        locked_payload = rollout.run_rollout_stage_prove(
            "paths-sentinel",
            "15",
            lock_acquired=True,
            dependencies=dependencies,
        )

        self.assertEqual(default_payload["surface"], "rollout-stage-prove")
        self.assertEqual(default_payload["stage"], "10")
        self.assertIs(default_payload["lock_acquired"], False)
        self.assertEqual(locked_payload["stage"], "15")
        self.assertIs(locked_payload["lock_acquired"], True)
        self.assertEqual(
            calls,
            [
                (("paths-sentinel", "10"), {"lock_acquired": False}),
                (("paths-sentinel", "15"), {"lock_acquired": True}),
            ],
        )

    def test_rollout_stage_advance_wrapper_passes_exact_impl_args(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_rollout_stage_advance_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "rollout-stage-advance",
                "stage": args[1],
                "backend_id": args[2],
            }

        dependencies = rollout.RolloutDependencies(
            run_rollout_rotation_inspect_impl=lambda *args, **kwargs: {},
            run_rollout_posture_inspect_impl=lambda *args, **kwargs: {},
            run_rollout_evidence_capture_impl=lambda *args, **kwargs: {},
            run_rollout_stage_prove_impl=lambda *args, **kwargs: {},
            run_rollout_stage_advance_impl=fake_run_rollout_stage_advance_impl,
        )

        payload = rollout.run_rollout_stage_advance(
            "paths-sentinel",
            "15",
            "backend-01",
            dependencies=dependencies,
        )

        self.assertEqual(payload["surface"], "rollout-stage-advance")
        self.assertEqual(payload["stage"], "15")
        self.assertEqual(payload["backend_id"], "backend-01")
        self.assertEqual(calls, [(("paths-sentinel", "15", "backend-01"), {})])

    def test_installer_init_wrapper_passes_exact_impl_args(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_installer_init_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "installer-init",
                "paths": args[0],
            }

        dependencies = installer.InstallerDependencies(
            run_installer_init_impl=fake_run_installer_init_impl,
            run_legacy_import_impl=lambda *args, **kwargs: {},
        )

        payload = installer.run_installer_init(
            "paths-sentinel",
            dependencies=dependencies,
        )

        self.assertEqual(payload["surface"], "installer-init")
        self.assertEqual(payload["paths"], "paths-sentinel")
        self.assertEqual(calls, [(("paths-sentinel",), {})])

    def test_legacy_import_wrapper_passes_exact_impl_args(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_legacy_import_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "legacy-import",
                "paths": args[0],
                "source_dir": args[1],
            }

        dependencies = installer.InstallerDependencies(
            run_installer_init_impl=lambda *args, **kwargs: {},
            run_legacy_import_impl=fake_run_legacy_import_impl,
        )

        payload = installer.run_legacy_import(
            "paths-sentinel",
            "source-dir-sentinel",
            dependencies=dependencies,
        )

        self.assertEqual(payload["surface"], "legacy-import")
        self.assertEqual(payload["paths"], "paths-sentinel")
        self.assertEqual(payload["source_dir"], "source-dir-sentinel")
        self.assertEqual(calls, [(("paths-sentinel", "source-dir-sentinel"), {})])

    def test_package_experimental_build_wrapper_passes_exact_impl_args(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_package_experimental_build_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "package-experimental-build",
                "paths": args[0],
                "output_dir": args[1],
            }

        dependencies = packaging.PackagingDependencies(
            run_package_experimental_build_impl=fake_run_package_experimental_build_impl,
            run_package_experimental_verify_impl=lambda *args, **kwargs: {},
            run_package_launchable_build_impl=lambda *args, **kwargs: {},
            run_package_launchable_verify_impl=lambda *args, **kwargs: {},
        )

        payload = packaging.run_package_experimental_build(
            "paths-sentinel",
            "output-dir-sentinel",
            dependencies=dependencies,
        )

        self.assertEqual(payload["surface"], "package-experimental-build")
        self.assertEqual(payload["paths"], "paths-sentinel")
        self.assertEqual(payload["output_dir"], "output-dir-sentinel")
        self.assertEqual(calls, [(("paths-sentinel", "output-dir-sentinel"), {})])

    def test_package_experimental_verify_wrapper_passes_exact_impl_args(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_package_experimental_verify_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "package-experimental-verify",
                "paths": args[0],
                "manifest": args[1],
            }

        dependencies = packaging.PackagingDependencies(
            run_package_experimental_build_impl=lambda *args, **kwargs: {},
            run_package_experimental_verify_impl=fake_run_package_experimental_verify_impl,
            run_package_launchable_build_impl=lambda *args, **kwargs: {},
            run_package_launchable_verify_impl=lambda *args, **kwargs: {},
        )

        payload = packaging.run_package_experimental_verify(
            "paths-sentinel",
            "manifest-sentinel",
            dependencies=dependencies,
        )

        self.assertEqual(payload["surface"], "package-experimental-verify")
        self.assertEqual(payload["paths"], "paths-sentinel")
        self.assertEqual(payload["manifest"], "manifest-sentinel")
        self.assertEqual(calls, [(("paths-sentinel", "manifest-sentinel"), {})])

    def test_package_launchable_build_wrapper_passes_exact_impl_args(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_package_launchable_build_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "package-launchable-build",
                "paths": args[0],
                "output_dir": args[1],
                "runtime_executable": kwargs["runtime_executable_raw"],
            }

        dependencies = packaging.PackagingDependencies(
            run_package_experimental_build_impl=lambda *args, **kwargs: {},
            run_package_experimental_verify_impl=lambda *args, **kwargs: {},
            run_package_launchable_build_impl=fake_run_package_launchable_build_impl,
            run_package_launchable_verify_impl=lambda *args, **kwargs: {},
        )

        payload = packaging.run_package_launchable_build(
            "paths-sentinel",
            "output-dir-sentinel",
            runtime_executable_raw="runtime-executable-sentinel",
            dependencies=dependencies,
        )

        self.assertEqual(payload["surface"], "package-launchable-build")
        self.assertEqual(payload["paths"], "paths-sentinel")
        self.assertEqual(payload["output_dir"], "output-dir-sentinel")
        self.assertEqual(payload["runtime_executable"], "runtime-executable-sentinel")
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "output-dir-sentinel"),
                    {"runtime_executable_raw": "runtime-executable-sentinel"},
                )
            ],
        )

    def test_package_launchable_verify_wrapper_passes_exact_impl_args(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_package_launchable_verify_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "package-launchable-verify",
                "paths": args[0],
                "manifest": args[1],
            }

        dependencies = packaging.PackagingDependencies(
            run_package_experimental_build_impl=lambda *args, **kwargs: {},
            run_package_experimental_verify_impl=lambda *args, **kwargs: {},
            run_package_launchable_build_impl=lambda *args, **kwargs: {},
            run_package_launchable_verify_impl=fake_run_package_launchable_verify_impl,
        )

        payload = packaging.run_package_launchable_verify(
            "paths-sentinel",
            "manifest-sentinel",
            dependencies=dependencies,
        )

        self.assertEqual(payload["surface"], "package-launchable-verify")
        self.assertEqual(payload["paths"], "paths-sentinel")
        self.assertEqual(payload["manifest"], "manifest-sentinel")
        self.assertEqual(calls, [(("paths-sentinel", "manifest-sentinel"), {})])

    def test_rollout_rotation_inspect_facade_passes_runtime_dependency(
        self,
    ) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_rollout_rotation_inspect(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "rollout-rotation-inspect",
                "lock_acquired": kwargs["lock_acquired"],
            }

        with mock.patch.object(
            rollout,
            "run_rollout_rotation_inspect",
            side_effect=fake_rollout_rotation_inspect,
        ):
            default_payload = runtime_mod.run_rollout_rotation_inspect(
                "paths-sentinel",
            )
            locked_payload = runtime_mod.run_rollout_rotation_inspect(
                "paths-sentinel",
                lock_acquired=True,
            )

        self.assertEqual(default_payload["surface"], "rollout-rotation-inspect")
        self.assertIs(default_payload["lock_acquired"], False)
        self.assertIs(locked_payload["lock_acquired"], True)
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel",),
                    {
                        "lock_acquired": False,
                        "dependencies": runtime_mod._rollout_dependencies(),
                    },
                ),
                (
                    ("paths-sentinel",),
                    {
                        "lock_acquired": True,
                        "dependencies": runtime_mod._rollout_dependencies(),
                    },
                ),
            ],
        )

    def test_rollout_posture_inspect_facade_passes_runtime_dependency(
        self,
    ) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_rollout_posture_inspect(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "rollout-posture-inspect",
                "stage": args[1],
            }

        with mock.patch.object(
            rollout,
            "run_rollout_posture_inspect",
            side_effect=fake_rollout_posture_inspect,
        ):
            payload = runtime_mod.run_rollout_posture_inspect(
                "paths-sentinel",
                "15",
            )

        self.assertEqual(payload["surface"], "rollout-posture-inspect")
        self.assertEqual(payload["stage"], "15")
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "15"),
                    {
                        "dependencies": runtime_mod._rollout_dependencies(),
                    },
                )
            ],
        )

    def test_rollout_evidence_capture_facade_passes_runtime_dependency(
        self,
    ) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_rollout_evidence_capture(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "rollout-evidence-capture",
                "target": args[1],
            }

        with mock.patch.object(
            rollout,
            "run_rollout_evidence_capture",
            side_effect=fake_rollout_evidence_capture,
        ):
            payload = runtime_mod.run_rollout_evidence_capture(
                "paths-sentinel",
                "16",
            )

        self.assertEqual(payload["surface"], "rollout-evidence-capture")
        self.assertEqual(payload["target"], "16")
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "16"),
                    {
                        "dependencies": runtime_mod._rollout_dependencies(),
                    },
                )
            ],
        )

    def test_rollout_stage_prove_facade_passes_runtime_dependency(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_rollout_stage_prove(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "rollout-stage-prove",
                "stage": args[1],
                "lock_acquired": kwargs["lock_acquired"],
            }

        with mock.patch.object(
            rollout,
            "run_rollout_stage_prove",
            side_effect=fake_rollout_stage_prove,
        ):
            default_payload = runtime_mod.run_rollout_stage_prove(
                "paths-sentinel",
                "10",
            )
            locked_payload = runtime_mod.run_rollout_stage_prove(
                "paths-sentinel",
                "15",
                lock_acquired=True,
            )

        self.assertEqual(default_payload["surface"], "rollout-stage-prove")
        self.assertEqual(default_payload["stage"], "10")
        self.assertIs(default_payload["lock_acquired"], False)
        self.assertEqual(locked_payload["stage"], "15")
        self.assertIs(locked_payload["lock_acquired"], True)
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "10"),
                    {
                        "lock_acquired": False,
                        "dependencies": runtime_mod._rollout_dependencies(),
                    },
                ),
                (
                    ("paths-sentinel", "15"),
                    {
                        "lock_acquired": True,
                        "dependencies": runtime_mod._rollout_dependencies(),
                    },
                ),
            ],
        )

    def test_rollout_stage_advance_facade_passes_runtime_dependency(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_rollout_stage_advance(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "rollout-stage-advance",
                "stage": args[1],
                "backend_id": args[2],
            }

        with mock.patch.object(
            rollout,
            "run_rollout_stage_advance",
            side_effect=fake_rollout_stage_advance,
        ):
            payload = runtime_mod.run_rollout_stage_advance(
                "paths-sentinel",
                "15",
                "backend-01",
            )

        self.assertEqual(payload["surface"], "rollout-stage-advance")
        self.assertEqual(payload["stage"], "15")
        self.assertEqual(payload["backend_id"], "backend-01")
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "15", "backend-01"),
                    {
                        "dependencies": runtime_mod._rollout_dependencies(),
                    },
                )
            ],
        )

    def test_installer_init_facade_passes_runtime_dependency(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_installer_init(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "installer-init",
                "paths": args[0],
            }

        with mock.patch.object(
            installer,
            "run_installer_init",
            side_effect=fake_installer_init,
        ):
            payload = runtime_mod.run_installer_init("paths-sentinel")

        self.assertEqual(payload["surface"], "installer-init")
        self.assertEqual(payload["paths"], "paths-sentinel")
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel",),
                    {
                        "dependencies": runtime_mod._installer_dependencies(),
                    },
                )
            ],
        )

    def test_legacy_import_facade_passes_runtime_dependency(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_legacy_import(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "legacy-import",
                "paths": args[0],
                "source_dir": args[1],
            }

        with mock.patch.object(
            installer,
            "run_legacy_import",
            side_effect=fake_legacy_import,
        ):
            payload = runtime_mod.run_legacy_import(
                "paths-sentinel",
                "source-dir-sentinel",
            )

        self.assertEqual(payload["surface"], "legacy-import")
        self.assertEqual(payload["paths"], "paths-sentinel")
        self.assertEqual(payload["source_dir"], "source-dir-sentinel")
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "source-dir-sentinel"),
                    {
                        "dependencies": runtime_mod._installer_dependencies(),
                    },
                )
            ],
        )

    def test_package_experimental_build_facade_passes_runtime_dependency(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_package_experimental_build(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "package-experimental-build",
                "paths": args[0],
                "output_dir": args[1],
            }

        with mock.patch.object(
            packaging,
            "run_package_experimental_build",
            side_effect=fake_package_experimental_build,
        ):
            payload = runtime_mod.run_package_experimental_build(
                "paths-sentinel",
                "output-dir-sentinel",
            )

        self.assertEqual(payload["surface"], "package-experimental-build")
        self.assertEqual(payload["paths"], "paths-sentinel")
        self.assertEqual(payload["output_dir"], "output-dir-sentinel")
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "output-dir-sentinel"),
                    {
                        "dependencies": runtime_mod._packaging_dependencies(),
                    },
                )
            ],
        )

    def test_package_experimental_verify_facade_passes_runtime_dependency(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_package_experimental_verify(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "package-experimental-verify",
                "paths": args[0],
                "manifest": args[1],
            }

        with mock.patch.object(
            packaging,
            "run_package_experimental_verify",
            side_effect=fake_package_experimental_verify,
        ):
            payload = runtime_mod.run_package_experimental_verify(
                "paths-sentinel",
                "manifest-sentinel",
            )

        self.assertEqual(payload["surface"], "package-experimental-verify")
        self.assertEqual(payload["paths"], "paths-sentinel")
        self.assertEqual(payload["manifest"], "manifest-sentinel")
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "manifest-sentinel"),
                    {
                        "dependencies": runtime_mod._packaging_dependencies(),
                    },
                )
            ],
        )

    def test_package_launchable_build_facade_passes_runtime_dependency(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_package_launchable_build(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "package-launchable-build",
                "paths": args[0],
                "output_dir": args[1],
                "runtime_executable": kwargs["runtime_executable_raw"],
            }

        with mock.patch.object(
            packaging,
            "run_package_launchable_build",
            side_effect=fake_package_launchable_build,
        ):
            payload = runtime_mod.run_package_launchable_build(
                "paths-sentinel",
                "output-dir-sentinel",
                runtime_executable_raw="runtime-executable-sentinel",
            )

        self.assertEqual(payload["surface"], "package-launchable-build")
        self.assertEqual(payload["paths"], "paths-sentinel")
        self.assertEqual(payload["output_dir"], "output-dir-sentinel")
        self.assertEqual(payload["runtime_executable"], "runtime-executable-sentinel")
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "output-dir-sentinel"),
                    {
                        "runtime_executable_raw": "runtime-executable-sentinel",
                        "dependencies": runtime_mod._packaging_dependencies(),
                    },
                )
            ],
        )

    def test_package_launchable_verify_facade_passes_runtime_dependency(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_package_launchable_verify(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "surface": "package-launchable-verify",
                "paths": args[0],
                "manifest": args[1],
            }

        with mock.patch.object(
            packaging,
            "run_package_launchable_verify",
            side_effect=fake_package_launchable_verify,
        ):
            payload = runtime_mod.run_package_launchable_verify(
                "paths-sentinel",
                "manifest-sentinel",
            )

        self.assertEqual(payload["surface"], "package-launchable-verify")
        self.assertEqual(payload["paths"], "paths-sentinel")
        self.assertEqual(payload["manifest"], "manifest-sentinel")
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "manifest-sentinel"),
                    {
                        "dependencies": runtime_mod._packaging_dependencies(),
                    },
                )
            ],
        )

    def test_accounts_lifecycle_hold_wrapper_passes_exact_owner_path_args(
        self,
    ) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_protective_owner_path(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "action": kwargs["action"],
                "dry_run": kwargs["dry_run"],
            }

        dependencies = accounts_lifecycle.AccountLifecycleDependencies(
            list_accounts_impl=lambda *args, **kwargs: {},
            run_protective_lifecycle_owner_path=fake_run_protective_owner_path,
            run_demote_impl=lambda *args, **kwargs: {},
            run_onboard_impl=lambda *args, **kwargs: {},
            run_promote_impl=lambda *args, **kwargs: {},
            run_retire_impl=lambda *args, **kwargs: {},
        )

        payload = accounts_lifecycle.run_hold(
            "paths-sentinel",
            "backend-sentinel",
            "reason-sentinel",
            dry_run=True,
            dependencies=dependencies,
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["action"], "hold")
        self.assertIs(payload["dry_run"], True)
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "backend-sentinel"),
                    {
                        "action": "hold",
                        "reason": "reason-sentinel",
                        "dry_run": True,
                    },
                )
            ],
        )

    def test_accounts_lifecycle_release_wrapper_passes_exact_owner_path_args(
        self,
    ) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_protective_owner_path(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {"status": "ok", "action": kwargs["action"]}

        dependencies = accounts_lifecycle.AccountLifecycleDependencies(
            list_accounts_impl=lambda *args, **kwargs: {},
            run_protective_lifecycle_owner_path=fake_run_protective_owner_path,
            run_demote_impl=lambda *args, **kwargs: {},
            run_onboard_impl=lambda *args, **kwargs: {},
            run_promote_impl=lambda *args, **kwargs: {},
            run_retire_impl=lambda *args, **kwargs: {},
        )

        payload = accounts_lifecycle.run_release(
            "paths-sentinel",
            "backend-sentinel",
            dependencies=dependencies,
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["action"], "release")
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "backend-sentinel"),
                    {
                        "action": "release",
                    },
                )
            ],
        )

    def test_accounts_lifecycle_facade_passes_runtime_dependency(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_protective_owner_path(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {"status": "ok", "action": kwargs["action"]}

        with mock.patch.object(
            runtime_mod,
            "run_protective_lifecycle_owner_path",
            side_effect=fake_run_protective_owner_path,
        ):
            hold_payload = runtime_mod.run_hold(
                "paths-sentinel",
                "backend-hold",
                "reason-sentinel",
                dry_run=True,
            )
            release_payload = runtime_mod.run_release(
                "paths-sentinel",
                "backend-release",
            )

        self.assertEqual(hold_payload["action"], "hold")
        self.assertEqual(release_payload["action"], "release")
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "backend-hold"),
                    {
                        "action": "hold",
                        "reason": "reason-sentinel",
                        "dry_run": True,
                    },
                ),
                (
                    ("paths-sentinel", "backend-release"),
                    {
                        "action": "release",
                    },
                ),
            ],
        )

    def test_accounts_lifecycle_list_wrapper_passes_exact_impl_args(
        self,
    ) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_list_accounts_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "effect": "read",
                "changed_files": [],
            }

        dependencies = accounts_lifecycle.AccountLifecycleDependencies(
            list_accounts_impl=fake_list_accounts_impl,
            run_protective_lifecycle_owner_path=lambda *args, **kwargs: {},
            run_demote_impl=lambda *args, **kwargs: {},
            run_onboard_impl=lambda *args, **kwargs: {},
            run_promote_impl=lambda *args, **kwargs: {},
            run_retire_impl=lambda *args, **kwargs: {},
        )

        payload = accounts_lifecycle.list_accounts(
            "paths-sentinel",
            dependencies=dependencies,
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["effect"], "read")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(calls, [(("paths-sentinel",), {})])

    def test_accounts_lifecycle_list_facade_passes_runtime_dependency(
        self,
    ) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_lifecycle_list_accounts(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "effect": "read",
                "changed_files": [],
            }

        with mock.patch.object(
            accounts_lifecycle,
            "list_accounts",
            side_effect=fake_lifecycle_list_accounts,
        ):
            payload = runtime_mod.list_accounts("paths-sentinel")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["effect"], "read")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel",),
                    {"dependencies": runtime_mod._accounts_lifecycle_dependencies()},
                )
            ],
        )

    def test_accounts_lifecycle_demote_wrapper_passes_exact_impl_args(
        self,
    ) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_demote_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {"status": "ok", "transition": "demote"}

        dependencies = accounts_lifecycle.AccountLifecycleDependencies(
            list_accounts_impl=lambda *args, **kwargs: {},
            run_protective_lifecycle_owner_path=lambda *args, **kwargs: {},
            run_demote_impl=fake_run_demote_impl,
            run_onboard_impl=lambda *args, **kwargs: {},
            run_promote_impl=lambda *args, **kwargs: {},
            run_retire_impl=lambda *args, **kwargs: {},
        )

        payload = accounts_lifecycle.run_demote(
            "paths-sentinel",
            "backend-sentinel",
            dependencies=dependencies,
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["transition"], "demote")
        self.assertEqual(calls, [(("paths-sentinel", "backend-sentinel"), {})])

    def test_accounts_lifecycle_retire_wrapper_passes_exact_impl_args(
        self,
    ) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_retire_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {"status": "ok", "transition": "retire"}

        dependencies = accounts_lifecycle.AccountLifecycleDependencies(
            list_accounts_impl=lambda *args, **kwargs: {},
            run_protective_lifecycle_owner_path=lambda *args, **kwargs: {},
            run_demote_impl=lambda *args, **kwargs: {},
            run_onboard_impl=lambda *args, **kwargs: {},
            run_promote_impl=lambda *args, **kwargs: {},
            run_retire_impl=fake_run_retire_impl,
        )

        payload = accounts_lifecycle.run_retire(
            "paths-sentinel",
            "backend-sentinel",
            dependencies=dependencies,
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["transition"], "retire")
        self.assertEqual(calls, [(("paths-sentinel", "backend-sentinel"), {})])

    def test_accounts_lifecycle_demote_retire_facade_passes_runtime_dependency(
        self,
    ) -> None:
        calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

        def fake_lifecycle_run_demote(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append(("demote", args, kwargs))
            return {"status": "ok", "transition": "demote"}

        def fake_lifecycle_run_retire(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append(("retire", args, kwargs))
            return {"status": "ok", "transition": "retire"}

        with (
            mock.patch.object(
                accounts_lifecycle,
                "run_demote",
                side_effect=fake_lifecycle_run_demote,
            ),
            mock.patch.object(
                accounts_lifecycle,
                "run_retire",
                side_effect=fake_lifecycle_run_retire,
            ),
        ):
            demote_payload = runtime_mod.run_demote(
                "paths-sentinel",
                "backend-demote",
            )
            retire_payload = runtime_mod.run_retire(
                "paths-sentinel",
                "backend-retire",
            )

        self.assertEqual(demote_payload["transition"], "demote")
        self.assertEqual(retire_payload["transition"], "retire")
        self.assertEqual(
            calls,
            [
                (
                    "demote",
                    ("paths-sentinel", "backend-demote"),
                    {"dependencies": runtime_mod._accounts_lifecycle_dependencies()},
                ),
                (
                    "retire",
                    ("paths-sentinel", "backend-retire"),
                    {"dependencies": runtime_mod._accounts_lifecycle_dependencies()},
                ),
            ],
        )

    def test_accounts_lifecycle_onboard_wrapper_passes_exact_impl_args(
        self,
    ) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_onboard_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "transition": "onboard",
                "auth_ref": kwargs["auth_ref"],
                "loop": kwargs["loop"],
                "skip_login": kwargs["skip_login"],
                "no_sync": kwargs["no_sync"],
                "non_interactive": kwargs["non_interactive"],
            }

        dependencies = accounts_lifecycle.AccountLifecycleDependencies(
            list_accounts_impl=lambda *args, **kwargs: {},
            run_protective_lifecycle_owner_path=lambda *args, **kwargs: {},
            run_demote_impl=lambda *args, **kwargs: {},
            run_onboard_impl=fake_run_onboard_impl,
            run_promote_impl=lambda *args, **kwargs: {},
            run_retire_impl=lambda *args, **kwargs: {},
        )

        payload = accounts_lifecycle.run_onboard(
            "paths-sentinel",
            auth_ref="auth-sentinel",
            loop=True,
            skip_login=True,
            no_sync=True,
            non_interactive=True,
            dependencies=dependencies,
        )

        self.assertEqual(payload["transition"], "onboard")
        self.assertEqual(payload["auth_ref"], "auth-sentinel")
        self.assertIs(payload["loop"], True)
        self.assertIs(payload["skip_login"], True)
        self.assertIs(payload["no_sync"], True)
        self.assertIs(payload["non_interactive"], True)
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel",),
                    {
                        "auth_ref": "auth-sentinel",
                        "loop": True,
                        "skip_login": True,
                        "no_sync": True,
                        "non_interactive": True,
                    },
                )
            ],
        )

    def test_accounts_lifecycle_onboard_facade_passes_runtime_dependency(
        self,
    ) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_lifecycle_run_onboard(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "transition": "onboard",
                "auth_ref": kwargs["auth_ref"],
                "loop": kwargs["loop"],
                "skip_login": kwargs["skip_login"],
                "no_sync": kwargs["no_sync"],
                "non_interactive": kwargs["non_interactive"],
            }

        with mock.patch.object(
            accounts_lifecycle,
            "run_onboard",
            side_effect=fake_lifecycle_run_onboard,
        ):
            payload = runtime_mod.run_onboard(
                "paths-sentinel",
                auth_ref=None,
                loop=False,
                skip_login=False,
                no_sync=False,
                non_interactive=True,
            )

        self.assertEqual(payload["transition"], "onboard")
        self.assertIsNone(payload["auth_ref"])
        self.assertIs(payload["loop"], False)
        self.assertIs(payload["skip_login"], False)
        self.assertIs(payload["no_sync"], False)
        self.assertIs(payload["non_interactive"], True)
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel",),
                    {
                        "auth_ref": None,
                        "loop": False,
                        "skip_login": False,
                        "no_sync": False,
                        "non_interactive": True,
                        "dependencies": runtime_mod._accounts_lifecycle_dependencies(),
                    },
                )
            ],
        )

    def test_accounts_lifecycle_promote_wrapper_passes_exact_impl_args(
        self,
    ) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_promote_impl(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "transition": "promote",
                "lock_acquired": kwargs["lock_acquired"],
            }

        dependencies = accounts_lifecycle.AccountLifecycleDependencies(
            list_accounts_impl=lambda *args, **kwargs: {},
            run_protective_lifecycle_owner_path=lambda *args, **kwargs: {},
            run_demote_impl=lambda *args, **kwargs: {},
            run_onboard_impl=lambda *args, **kwargs: {},
            run_promote_impl=fake_run_promote_impl,
            run_retire_impl=lambda *args, **kwargs: {},
        )

        default_payload = accounts_lifecycle.run_promote(
            "paths-sentinel",
            "backend-default",
            dependencies=dependencies,
        )
        locked_payload = accounts_lifecycle.run_promote(
            "paths-sentinel",
            "backend-locked",
            lock_acquired=True,
            dependencies=dependencies,
        )

        self.assertEqual(default_payload["transition"], "promote")
        self.assertIs(default_payload["lock_acquired"], False)
        self.assertIs(locked_payload["lock_acquired"], True)
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "backend-default"),
                    {"lock_acquired": False},
                ),
                (
                    ("paths-sentinel", "backend-locked"),
                    {"lock_acquired": True},
                ),
            ],
        )

    def test_accounts_lifecycle_promote_facade_passes_runtime_dependency(
        self,
    ) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_lifecycle_run_promote(
            *args: object, **kwargs: object
        ) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "status": "ok",
                "transition": "promote",
                "lock_acquired": kwargs["lock_acquired"],
            }

        with mock.patch.object(
            accounts_lifecycle,
            "run_promote",
            side_effect=fake_lifecycle_run_promote,
        ):
            default_payload = runtime_mod.run_promote(
                "paths-sentinel",
                "backend-default",
            )
            locked_payload = runtime_mod.run_promote(
                "paths-sentinel",
                "backend-locked",
                lock_acquired=True,
            )

        self.assertEqual(default_payload["transition"], "promote")
        self.assertIs(default_payload["lock_acquired"], False)
        self.assertIs(locked_payload["lock_acquired"], True)
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "backend-default"),
                    {
                        "lock_acquired": False,
                        "dependencies": runtime_mod._accounts_lifecycle_dependencies(),
                    },
                ),
                (
                    ("paths-sentinel", "backend-locked"),
                    {
                        "lock_acquired": True,
                        "dependencies": runtime_mod._accounts_lifecycle_dependencies(),
                    },
                ),
            ],
        )

    def test_runtime_repair_contract_declares_admitted_repair_flags(self) -> None:
        contract = runtime_repair.HEALTHCHECK_REPAIR_CONTRACT
        expected = {
            "allow_recovery": True,
            "allow_last_known_good_proxy_write": True,
            "allow_current_proxy_auto_adoption": True,
            "allow_stable_fallback_write": True,
            "allow_stale_pid_cleanup": True,
            "effect": "repair",
        }
        self.assertTrue(contract.__dataclass_params__.frozen)
        self.assertEqual(contract.kwargs(), expected)

        mutated = contract.kwargs()
        mutated["effect"] = "tampered"
        self.assertEqual(contract.kwargs(), expected)

    def test_runtime_repair_wrapper_passes_exact_repair_flags(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_healthcheck(*args: object, **kwargs: object) -> dict[str, object]:
            calls.append((args, kwargs))
            return {"effect": "repair", "changed_files": ["state.json"]}

        dependencies = runtime_repair.HealthcheckRepairDependencies(
            run_healthcheck=fake_run_healthcheck
        )

        payload = runtime_repair.run_healthcheck_repair(
            "paths-sentinel",
            "gpt-sentinel",
            dependencies=dependencies,
        )

        self.assertEqual(payload["effect"], "repair")
        self.assertEqual(payload["changed_files"], ["state.json"])
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "gpt-sentinel"),
                    runtime_repair.HEALTHCHECK_REPAIR_CONTRACT.kwargs(),
                )
            ],
        )

    def test_runtime_health_probe_contract_forbids_repair_flags(self) -> None:
        contract = runtime_health.HEALTHCHECK_PROBE_CONTRACT
        expected = {
            "allow_recovery": False,
            "allow_last_known_good_proxy_write": False,
            "allow_current_proxy_auto_adoption": False,
            "allow_stable_fallback_write": False,
            "allow_stale_pid_cleanup": False,
            "effect": "probe",
        }
        self.assertTrue(contract.__dataclass_params__.frozen)
        self.assertEqual(contract.kwargs(), expected)

        mutated = contract.kwargs()
        mutated["effect"] = "tampered"
        self.assertEqual(contract.kwargs(), expected)

    def test_runtime_health_probe_wrapper_passes_exact_probe_flags(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_healthcheck(*args: object, **kwargs: object) -> dict[str, object]:
            calls.append((args, kwargs))
            return {"effect": "probe", "changed_files": []}

        dependencies = runtime_health.HealthProbeDependencies(
            run_healthcheck=fake_run_healthcheck
        )

        payload = runtime_health.run_healthcheck_probe(
            "paths-sentinel",
            "gpt-sentinel",
            dependencies=dependencies,
        )

        self.assertEqual(payload["effect"], "probe")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "gpt-sentinel"),
                    runtime_health.HEALTHCHECK_PROBE_CONTRACT.kwargs(),
                )
            ],
        )

    def test_runtime_launch_readiness_surface_facade_matches_health_module(self) -> None:
        kwargs = {
            "owner_command_surface": "healthcheck --json",
            "delegated_from_status": False,
            "listener_ok": True,
            "models_ok": True,
            "responses_ok": False,
            "base_url_match": True,
            "effective_mode_match": True,
            "model_match": True,
            "proxy_url_match": True,
            "machine_error_code": "AUTH_UNAVAILABLE",
            "error_detail": "responses probe failed",
            "auth_pool_hygiene": {
                "status": "launch_capable_empty",
                "launch_capable_backend_count": 0,
            },
            "identity_proof_required": True,
            "identity_proof_ok": False,
            "identity_failure_reason": "missing_runtime_identity",
        }

        facade_payload = runtime_mod.build_launch_readiness_surface(**kwargs)
        direct_payload = runtime_health.build_launch_readiness_surface(**kwargs)

        self.assertEqual(facade_payload, direct_payload)
        self.assertEqual(facade_payload["status"], "blocked")
        self.assertEqual(facade_payload["blocking_reason"], "usable_auth_pool_empty")
        self.assertIn("runtime_identity_unproven", facade_payload["failed_checks"])

    def test_runtime_launch_readiness_surface_facade_delegates_to_health_module(
        self,
    ) -> None:
        kwargs = {
            "owner_command_surface": "healthcheck --json",
            "delegated_from_status": False,
            "listener_ok": True,
            "models_ok": True,
            "responses_ok": True,
            "base_url_match": True,
            "effective_mode_match": True,
            "model_match": True,
            "proxy_url_match": True,
            "machine_error_code": "OK",
            "error_detail": "",
            "auth_pool_hygiene": {
                "status": "launch_capable_available",
                "launch_capable_backend_count": 15,
            },
            "identity_proof_required": False,
            "identity_proof_ok": True,
            "identity_failure_reason": "",
        }
        expected = {"surface": "health-readiness"}

        with mock.patch.object(
            runtime_health,
            "build_launch_readiness_surface",
            return_value=expected,
        ) as builder:
            payload = runtime_mod.build_launch_readiness_surface(**kwargs)

        self.assertIs(payload, expected)
        builder.assert_called_once_with(**kwargs)

    def test_runtime_guardrail_surface_facade_matches_health_module(self) -> None:
        launch_readiness = {
            "status": "blocked",
            "blocking_reason": "listener_unreachable",
        }
        auth_pool_hygiene = {
            "status": "launch_capable_empty",
            "blocking_reason": "usable_auth_pool_empty",
        }
        recovery_result = {
            "guardrail_status": "observation_only",
            "confirmation_basis": "live_runtime_observation_not_confirmed",
            "effectful_claim_allowed": False,
        }
        expected_keys = {
            "status",
            "owner_command_surface",
            "lock_status",
            "launch_readiness_status",
            "launch_blocking_reason",
            "auth_pool_hygiene_status",
            "auth_pool_blocking_reason",
            "recovery_guardrail_status",
            "recovery_confirmation_basis",
            "recovery_effectful_claim_allowed",
            "failed_checks",
            "blocking_reason",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))
            lock_preflight = runtime_mod.get_lock_preflight(paths)

            facade_payload = runtime_mod.build_runtime_guardrail_surface(
                paths,
                launch_readiness=launch_readiness,
                auth_pool_hygiene=auth_pool_hygiene,
                recovery_result=recovery_result,
            )
            direct_payload = (
                runtime_health.build_runtime_guardrail_surface_from_preflight(
                    lock_preflight=lock_preflight,
                    launch_readiness=launch_readiness,
                    auth_pool_hygiene=auth_pool_hygiene,
                    recovery_result=recovery_result,
                )
            )

        self.assertEqual(facade_payload, direct_payload)
        self.assertEqual(set(facade_payload), expected_keys)
        self.assertEqual(facade_payload["status"], "blocked")
        self.assertEqual(facade_payload["blocking_reason"], "listener_unreachable")
        self.assertIn("usable_auth_pool_empty", facade_payload["failed_checks"])

    def test_runtime_guardrail_surface_facade_delegates_to_health_module(self) -> None:
        launch_readiness = {"status": "ready", "blocking_reason": ""}
        auth_pool_hygiene = {
            "status": "launch_capable_available",
            "blocking_reason": "",
        }
        recovery_result = {"guardrail_status": "confirmed"}
        lock_preflight = {"status": "held", "machine_error_code": "LOCK_HELD"}
        expected = {"surface": "runtime-guardrail"}

        with (
            mock.patch.object(
                runtime_mod,
                "get_lock_preflight",
                return_value=lock_preflight,
            ) as lock_reader,
            mock.patch.object(
                runtime_health,
                "build_runtime_guardrail_surface_from_preflight",
                return_value=expected,
            ) as builder,
        ):
            payload = runtime_mod.build_runtime_guardrail_surface(
                "paths-sentinel",
                launch_readiness=launch_readiness,
                auth_pool_hygiene=auth_pool_hygiene,
                recovery_result=recovery_result,
            )

        self.assertIs(payload, expected)
        lock_reader.assert_called_once_with("paths-sentinel")
        builder.assert_called_once_with(
            lock_preflight=lock_preflight,
            launch_readiness=launch_readiness,
            auth_pool_hygiene=auth_pool_hygiene,
            recovery_result=recovery_result,
        )

    def test_runtime_guardrail_surface_from_preflight_reports_lock_states(
        self,
    ) -> None:
        cases = (
            ("held", "blocked", "mutation_lock_held"),
            ("stale", "blocked", "mutation_lock_stale"),
            ("invalid", "blocked", "mutation_lock_invalid"),
            ("clear", "clear", ""),
        )

        for lock_status, expected_status, expected_blocking_reason in cases:
            with self.subTest(lock_status=lock_status):
                payload = runtime_health.build_runtime_guardrail_surface_from_preflight(
                    lock_preflight={"status": lock_status},
                    launch_readiness=None,
                    auth_pool_hygiene=None,
                    recovery_result=None,
                )

                self.assertEqual(payload["lock_status"], lock_status)
                self.assertEqual(payload["status"], expected_status)
                self.assertEqual(
                    payload["blocking_reason"], expected_blocking_reason
                )
                if expected_blocking_reason:
                    self.assertEqual(
                        payload["failed_checks"], [expected_blocking_reason]
                    )
                else:
                    self.assertEqual(payload["failed_checks"], [])

    def test_runtime_guardrail_surface_from_preflight_reports_observation_only(
        self,
    ) -> None:
        payload = runtime_health.build_runtime_guardrail_surface_from_preflight(
            lock_preflight={"status": "clear"},
            launch_readiness={"status": "ready", "blocking_reason": ""},
            auth_pool_hygiene={
                "status": "launch_capable_available",
                "blocking_reason": "",
            },
            recovery_result={
                "guardrail_status": "observation_only",
                "confirmation_basis": "live_runtime_observation_not_confirmed",
                "effectful_claim_allowed": False,
            },
        )

        self.assertEqual(payload["status"], "caution")
        self.assertEqual(payload["failed_checks"], [])
        self.assertEqual(payload["blocking_reason"], "")
        self.assertEqual(payload["recovery_guardrail_status"], "observation_only")
        self.assertEqual(
            payload["recovery_confirmation_basis"],
            "live_runtime_observation_not_confirmed",
        )
        self.assertFalse(payload["recovery_effectful_claim_allowed"])

    def test_runtime_deterministic_recovery_result_facade_matches_repair_module(
        self,
    ) -> None:
        kwargs = {
            "owner_command_surface": "healthcheck --repair --json",
            "delegated_from_status": False,
            "attempted": True,
            "entry_lane": "stable_service_disabled",
            "outcome": "recovery_failed_before_stable_healthy",
            "re_enable_method": "bounded_healthcheck_owner_retry",
            "selected_source_kind": "approved_repair_target",
            "selected_source_path": "/tmp/wbp-target",
            "generated_config_regenerated": True,
            "snapshot_refreshed": False,
            "fallback_reason": "stable_listener_unreachable_after_recovery",
            "live_runtime_observation_confirmed": False,
            "confirmation_basis": "live_runtime_observation_not_confirmed",
            "effectful_claim_allowed": False,
            "process_result": {
                "exit_code": 1,
                "stdout": "",
                "stderr": "launcher failed",
            },
        }

        facade_payload = runtime_mod.build_deterministic_stable_recovery_result(
            **kwargs
        )
        direct_payload = runtime_repair.build_deterministic_stable_recovery_result(
            **kwargs
        )

        self.assertEqual(facade_payload, direct_payload)
        self.assertEqual(facade_payload["status"], "failed")
        self.assertEqual(facade_payload["guardrail_status"], "blocked")
        self.assertEqual(facade_payload["process_result"], kwargs["process_result"])

    def test_runtime_deterministic_recovery_result_facade_delegates_to_repair_module(
        self,
    ) -> None:
        kwargs = {
            "owner_command_surface": "healthcheck --repair --json",
            "delegated_from_status": False,
            "attempted": False,
            "entry_lane": "not_invoked",
            "outcome": "not_invoked",
            "re_enable_method": "",
            "selected_source_kind": "",
            "selected_source_path": "",
            "generated_config_regenerated": False,
            "snapshot_refreshed": False,
            "fallback_reason": "",
            "live_runtime_observation_confirmed": False,
            "confirmation_basis": "",
            "effectful_claim_allowed": False,
            "process_result": None,
        }
        expected = {"surface": "repair-recovery-result"}

        with mock.patch.object(
            runtime_repair,
            "build_deterministic_stable_recovery_result",
            return_value=expected,
        ) as builder:
            payload = runtime_mod.build_deterministic_stable_recovery_result(
                **kwargs
            )

        self.assertIs(payload, expected)
        builder.assert_called_once_with(**kwargs)

    def test_runtime_deterministic_stable_recovery_contract_facade_matches_repair_module(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))

            facade_payload = runtime_mod.build_deterministic_stable_recovery_contract(
                paths
            )
            direct_payload = (
                runtime_repair.build_deterministic_stable_recovery_contract(paths)
            )

        self.assertEqual(facade_payload, direct_payload)
        self.assertEqual(facade_payload["status"], "contract_ready")
        self.assertEqual(
            facade_payload["owner_command_surface"],
            "healthcheck --repair --json",
        )
        self.assertEqual(
            runtime_repair.STABLE_RUNTIME_LAUNCHER_HANDOFF_ENV,
            runtime_mod.STABLE_RUNTIME_LAUNCHER_HANDOFF_ENV,
        )
        self.assertEqual(
            runtime_repair.STABLE_RUNTIME_CONSUMER_SNAPSHOT_TOPIC,
            runtime_mod.STABLE_RUNTIME_CONSUMER_SNAPSHOT_TOPIC,
        )
        self.assertEqual(
            facade_payload["shared_activation_mechanics"]["handoff_env_var"],
            runtime_mod.STABLE_RUNTIME_LAUNCHER_HANDOFF_ENV,
        )
        self.assertEqual(
            facade_payload["shared_activation_mechanics"]["snapshot_topic"],
            runtime_mod.STABLE_RUNTIME_CONSUMER_SNAPSHOT_TOPIC,
        )

    def test_runtime_deterministic_stable_recovery_contract_facade_delegates_to_repair_module(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))
            expected = {"surface": "repair-contract"}

            with mock.patch.object(
                runtime_repair,
                "build_deterministic_stable_recovery_contract",
                return_value=expected,
            ) as builder:
                payload = runtime_mod.build_deterministic_stable_recovery_contract(
                    paths
                )

        self.assertIs(payload, expected)
        builder.assert_called_once_with(paths)

    def test_runtime_stable_runtime_launcher_handoff_contract_facade_matches_repair_module(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))

            facade_payload = runtime_mod.build_stable_runtime_launcher_handoff_contract(
                paths
            )
            direct_payload = (
                runtime_repair.build_stable_runtime_launcher_handoff_contract(paths)
            )

        self.assertEqual(facade_payload, direct_payload)
        self.assertEqual(facade_payload["status"], "contract_ready")
        self.assertEqual(
            facade_payload["handoff_method"], "process_local_env_override"
        )
        self.assertEqual(
            runtime_repair.STABLE_RUNTIME_LAUNCHER_HANDOFF_ENV,
            runtime_mod.STABLE_RUNTIME_LAUNCHER_HANDOFF_ENV,
        )
        self.assertEqual(
            facade_payload["env_var"],
            runtime_mod.STABLE_RUNTIME_LAUNCHER_HANDOFF_ENV,
        )
        self.assertTrue(facade_payload["baseline_config_rewrite_forbidden"])
        self.assertTrue(facade_payload["generic_config_routing_forbidden"])

    def test_runtime_stable_runtime_launcher_handoff_contract_facade_delegates_to_repair_module(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))
            expected = {"surface": "stable-runtime-launcher-handoff"}

            with mock.patch.object(
                runtime_repair,
                "build_stable_runtime_launcher_handoff_contract",
                return_value=expected,
            ) as builder:
                payload = runtime_mod.build_stable_runtime_launcher_handoff_contract(
                    paths
                )

        self.assertIs(payload, expected)
        builder.assert_called_once_with(paths)

    def test_runtime_stable_runtime_effective_truth_contract_facade_matches_repair_module(
        self,
    ) -> None:
        facade_payload = runtime_mod.build_stable_runtime_effective_truth_contract()
        direct_payload = runtime_repair.build_stable_runtime_effective_truth_contract()

        self.assertEqual(facade_payload, direct_payload)
        self.assertEqual(facade_payload["status"], "contract_ready")
        self.assertEqual(
            facade_payload["truth_source"],
            "live_runtime_observation_plus_snapshot_evidence",
        )
        self.assertFalse(facade_payload["desired_source_alone_sufficient"])
        self.assertFalse(facade_payload["generated_config_existence_alone_sufficient"])
        self.assertFalse(
            facade_payload["activation_evidence_snapshot_alone_sufficient"]
        )
        self.assertTrue(facade_payload["live_runtime_observation_required"])

    def test_runtime_stable_runtime_effective_truth_contract_facade_delegates_to_repair_module(
        self,
    ) -> None:
        expected = {"surface": "stable-runtime-effective-truth"}

        with mock.patch.object(
            runtime_repair,
            "build_stable_runtime_effective_truth_contract",
            return_value=expected,
        ) as builder:
            payload = runtime_mod.build_stable_runtime_effective_truth_contract()

        self.assertIs(payload, expected)
        builder.assert_called_once_with()

    def test_runtime_stable_runtime_consumer_contract_uses_repair_contract_facades(
        self,
    ) -> None:
        launcher_handoff = {"surface": "launcher-handoff"}
        effective_truth = {"surface": "effective-truth"}

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            mock.patch.object(
                runtime_repair,
                "build_stable_runtime_launcher_handoff_contract",
                return_value=launcher_handoff,
            ) as launcher_builder,
            mock.patch.object(
                runtime_repair,
                "build_stable_runtime_effective_truth_contract",
                return_value=effective_truth,
            ) as truth_builder,
        ):
            paths = _runtime_paths(Path(temp_dir))
            registry = {
                "backends": [],
                "pool_policy": {},
                "stable_default_backend_id": "",
            }
            policy_drift = {"status": "aligned"}
            state = {}

            payload = runtime_mod.build_stable_runtime_consumer_contract(
                paths, registry, policy_drift, state
            )

        self.assertIs(payload["launcher_handoff_contract"], launcher_handoff)
        self.assertIs(payload["effective_truth_contract"], effective_truth)
        launcher_builder.assert_called_once_with(paths)
        truth_builder.assert_called_once_with()

    def test_runtime_startup_contract_repair_contract_facade_matches_repair_module(
        self,
    ) -> None:
        facade_payload = runtime_mod.build_startup_contract_repair_contract()
        direct_payload = runtime_repair.build_startup_contract_repair_contract()

        self.assertEqual(facade_payload, direct_payload)
        self.assertEqual(facade_payload["status"], "contract_ready")
        self.assertEqual(
            facade_payload["entry_owner"],
            "healthcheck_startup_contract_repair_path",
        )
        self.assertEqual(
            facade_payload["owner_command_surface"],
            "healthcheck --repair --json",
        )
        self.assertTrue(facade_payload["same_source_lock_invariant_required"])
        self.assertTrue(facade_payload["schema_auto_migrate_forbidden"])
        self.assertTrue(facade_payload["truth_file_rewrite_forbidden"])

    def test_runtime_startup_contract_repair_contract_facade_delegates_to_repair_module(
        self,
    ) -> None:
        expected = {"surface": "startup-contract-repair"}

        with mock.patch.object(
            runtime_repair,
            "build_startup_contract_repair_contract",
            return_value=expected,
        ) as builder:
            payload = runtime_mod.build_startup_contract_repair_contract()

        self.assertIs(payload, expected)
        builder.assert_called_once_with()

    def test_runtime_last_known_good_proxy_contract_facade_matches_repair_module(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))
            paths.sync_script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

            facade_payload = runtime_mod.build_last_known_good_proxy_contract(paths)
            direct_payload = runtime_repair.build_last_known_good_proxy_contract(paths)

        self.assertEqual(facade_payload, direct_payload)
        self.assertEqual(facade_payload["status"], "contract_ready")
        self.assertEqual(
            facade_payload["owner_command_surface"],
            "healthcheck --repair --json",
        )
        self.assertEqual(
            runtime_repair.LAST_KNOWN_GOOD_PROXY_URL_FIELD,
            runtime_mod.LAST_KNOWN_GOOD_PROXY_URL_FIELD,
        )
        self.assertEqual(
            runtime_repair.LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD,
            runtime_mod.LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD,
        )
        self.assertEqual(
            facade_payload["state_fields"],
            [
                runtime_mod.LAST_KNOWN_GOOD_PROXY_URL_FIELD,
                runtime_mod.LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD,
            ],
        )

    def test_runtime_last_known_good_proxy_contract_facade_delegates_to_repair_module(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))
            expected = {"surface": "last-known-good-proxy-contract"}

            with mock.patch.object(
                runtime_repair,
                "build_last_known_good_proxy_contract",
                return_value=expected,
            ) as builder:
                payload = runtime_mod.build_last_known_good_proxy_contract(paths)

        self.assertIs(payload, expected)
        builder.assert_called_once_with(paths)

    def test_runtime_last_known_good_proxy_contract_reports_sync_script_availability(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))

            missing_payload = runtime_repair.build_last_known_good_proxy_contract(
                paths
            )
            paths.sync_script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            available_payload = runtime_repair.build_last_known_good_proxy_contract(
                paths
            )

        self.assertEqual(
            missing_payload["launcher_lane_ineligible_sync_owner_recovery_surface"][
                "status"
            ],
            "unavailable",
        )
        self.assertEqual(
            available_payload["launcher_lane_ineligible_sync_owner_recovery_surface"][
                "status"
            ],
            "available",
        )
        self.assertEqual(
            available_payload["launcher_lane_ineligible_sync_owner_recovery_surface"][
                "command_surface"
            ],
            "sync --json",
        )

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

    def test_runtime_mode_read_helper_facades_delegate_to_modes_module(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))

            with mock.patch.object(
                runtime_modes, "get_desired_mode", return_value="managed"
            ) as helper:
                self.assertEqual(runtime_mod.get_desired_mode(paths), "managed")
            helper.assert_called_once_with(paths)

            state = {"effective_mode": "stable"}
            with mock.patch.object(
                runtime_modes, "get_effective_mode", return_value="managed"
            ) as helper:
                self.assertEqual(runtime_mod.get_effective_mode(paths, state), "managed")
            helper.assert_called_once_with(paths, state)

            endpoint = ("127.0.0.1", 9999, "http://127.0.0.1:9999/v1")
            with mock.patch.object(
                runtime_modes, "get_endpoint", return_value=endpoint
            ) as helper:
                self.assertEqual(runtime_mod.get_endpoint(paths, "managed"), endpoint)
            helper.assert_called_once_with(paths, "managed")

            with mock.patch.object(
                runtime_modes,
                "reconcile_effective_mode_for_reporting",
                return_value="stable",
            ) as helper:
                self.assertEqual(
                    runtime_mod.reconcile_effective_mode_for_reporting(
                        "managed", listener_ok=False
                    ),
                    "stable",
                )
            helper.assert_called_once_with("managed", listener_ok=False)

    def test_runtime_mode_read_helper_facades_match_modes_module_edges(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))
            paths.runtime_mode_file.write_text("unknown\n", encoding="utf-8")
            paths.runtime_effective_mode_file.write_text("unknown\n", encoding="utf-8")
            state = {"effective_mode": "managed"}

            self.assertEqual(runtime_mod.get_desired_mode(paths), "stable")
            self.assertEqual(
                runtime_mod.get_desired_mode(paths),
                runtime_modes.get_desired_mode(paths),
            )
            self.assertEqual(runtime_mod.get_effective_mode(paths, state), "managed")
            self.assertEqual(
                runtime_mod.get_effective_mode(paths, state),
                runtime_modes.get_effective_mode(paths, state),
            )

            for effective_mode in ("stable", "managed"):
                with self.subTest(effective_mode=effective_mode):
                    self.assertEqual(
                        runtime_mod.get_endpoint(paths, effective_mode),
                        runtime_modes.get_endpoint(paths, effective_mode),
                    )

            self.assertEqual(
                runtime_mod.reconcile_effective_mode_for_reporting(
                    "managed", listener_ok=False
                ),
                "stable",
            )
            self.assertEqual(
                runtime_mod.reconcile_effective_mode_for_reporting(
                    "managed", listener_ok=True
                ),
                "managed",
            )
            self.assertEqual(
                runtime_mod.reconcile_effective_mode_for_reporting(
                    "stable", listener_ok=False
                ),
                runtime_modes.reconcile_effective_mode_for_reporting(
                    "stable", listener_ok=False
                ),
            )

    def test_runtime_health_probe_facade_matches_direct_health_module(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _status_runtime_paths(Path(temp_dir))

            facade_payload = runtime_mod.run_healthcheck_probe(paths)
            direct_payload = runtime_health.run_healthcheck_probe(
                paths,
                dependencies=runtime_mod._health_probe_dependencies(),
            )

        self.assertEqual(
            _normalize_observed_times(facade_payload),
            _normalize_observed_times(direct_payload),
        )
        _assert_health_probe_contract(self, facade_payload)

    def test_runtime_healthcheck_repair_facade_matches_direct_repair_module(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def fake_run_healthcheck(*args: object, **kwargs: object) -> dict[str, object]:
            calls.append((args, kwargs))
            return {
                "effect": kwargs["effect"],
                "changed_files": ["state.json"],
                "surface": "fake-healthcheck",
            }

        with mock.patch.object(
            runtime_mod,
            "run_healthcheck",
            side_effect=fake_run_healthcheck,
        ):
            facade_payload = runtime_mod.run_healthcheck_repair(
                "paths-sentinel",
                "gpt-sentinel",
            )
            direct_payload = runtime_repair.run_healthcheck_repair(
                "paths-sentinel",
                "gpt-sentinel",
                dependencies=runtime_mod._healthcheck_repair_dependencies(),
            )

        self.assertEqual(facade_payload, direct_payload)
        self.assertEqual(
            calls,
            [
                (
                    ("paths-sentinel", "gpt-sentinel"),
                    runtime_repair.HEALTHCHECK_REPAIR_CONTRACT.kwargs(),
                ),
                (
                    ("paths-sentinel", "gpt-sentinel"),
                    runtime_repair.HEALTHCHECK_REPAIR_CONTRACT.kwargs(),
                ),
            ],
        )

    def test_runtime_health_probe_does_not_write_runtime_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _status_runtime_paths(Path(temp_dir))
            tracked_paths = [
                paths.registry_file,
                paths.state_file,
                paths.config_toml,
                paths.runtime_mode_file,
                paths.runtime_effective_mode_file,
                paths.stable_config,
                paths.managed_config_file,
                paths.repair_target_reference_file,
                paths.stable_runtime_generated_config_file,
                runtime_mod.managed_pid_path(paths),
            ]
            before = _snapshot_files(tracked_paths)

            payload = runtime_mod.run_healthcheck_probe(paths)

            after = _snapshot_files(tracked_paths)

        self.assertEqual(payload["effect"], "probe")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(after, before)

    def test_runtime_status_snapshot_facade_matches_direct_status_module(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _status_runtime_paths(Path(temp_dir))

            facade_payload = runtime_mod.build_status_snapshot_payload(paths)
            summarized_payload = runtime_mod.summarize_status(paths)
            direct_payload = runtime_status.build_status_snapshot_payload(
                paths,
                dependencies=runtime_mod._status_snapshot_dependencies(),
            )

        self.assertEqual(facade_payload, direct_payload)
        self.assertEqual(summarized_payload, direct_payload)
        _assert_status_snapshot_contract(self, facade_payload)

    def test_runtime_status_snapshot_invalid_json_error_matches_facade(self) -> None:
        for target in ("registry", "state"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp_dir:
                paths = _status_runtime_paths(Path(temp_dir))
                if target == "registry":
                    paths.registry_file.write_text("{not-json", encoding="utf-8")
                else:
                    paths.state_file.write_text("{not-json", encoding="utf-8")

                with self.assertRaises(runtime_mod.RuntimeErrorInfo) as facade_raised:
                    runtime_mod.build_status_snapshot_payload(paths)
                with self.assertRaises(runtime_mod.RuntimeErrorInfo) as direct_raised:
                    runtime_status.build_status_snapshot_payload(
                        paths,
                        dependencies=runtime_mod._status_snapshot_dependencies(),
                    )

                self.assertEqual(
                    facade_raised.exception.machine_error_code,
                    direct_raised.exception.machine_error_code,
                )
                self.assertEqual(
                    facade_raised.exception.machine_error_code,
                    "INVALID_JSON_FILE",
                )
                self.assertEqual(facade_raised.exception.operator_action, "stop")
                self.assertEqual(direct_raised.exception.operator_action, "stop")

    def test_runtime_status_snapshot_does_not_write_runtime_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _status_runtime_paths(Path(temp_dir))
            tracked_paths = [
                paths.registry_file,
                paths.state_file,
                paths.config_toml,
                paths.runtime_mode_file,
                paths.runtime_effective_mode_file,
                paths.stable_config,
                paths.managed_config_file,
                paths.repair_target_reference_file,
                paths.stable_runtime_generated_config_file,
            ]
            before = _snapshot_files(tracked_paths)

            payload = runtime_mod.summarize_status(paths)

            after = _snapshot_files(tracked_paths)

        self.assertEqual(payload["effect"], "read")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(after, before)

    def test_runtime_delegated_health_status_summary_facade_delegates_to_status_module(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _status_runtime_paths(Path(temp_dir))
            health_payload = {"status": "ok"}
            expected_payload = {"status": "delegated"}

            with mock.patch.object(
                runtime_status,
                "build_delegated_health_status_summary_payload",
                return_value=expected_payload,
            ) as builder:
                payload = runtime_mod.summarize_status(
                    paths, health_payload=health_payload
                )

        self.assertEqual(payload, expected_payload)
        builder.assert_called_once()
        args = builder.call_args.args
        kwargs = builder.call_args.kwargs
        self.assertEqual(args, (paths, health_payload))
        self.assertIsInstance(
            kwargs["dependencies"], runtime_status.StatusSnapshotDependencies
        )

    def test_runtime_delegated_health_status_summary_matches_direct_status_module(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _status_runtime_paths(Path(temp_dir))
            health_payload = runtime_mod.run_healthcheck_probe(paths)

            facade_payload = runtime_mod.summarize_status(
                paths, health_payload=health_payload
            )
            direct_payload = (
                runtime_status.build_delegated_health_status_summary_payload(
                    paths,
                    health_payload,
                    dependencies=runtime_mod._status_snapshot_dependencies(),
                )
            )

        self.assertEqual(facade_payload, direct_payload)
        self.assertEqual(facade_payload["changed_files"], [])
        self.assertEqual(facade_payload["attestation_summary"]["status"], "error")
        self.assertEqual(
            facade_payload["attestation_summary"]["attestation_source"],
            "healthcheck --json",
        )
        self.assertIs(
            facade_payload["launch_readiness"]["delegated_from_status"], True
        )
        self.assertIs(
            facade_payload["runtime_guardrails"]["delegated_from_status"], True
        )
        self.assertEqual(
            facade_payload["runtime_guardrails"]["owner_command_surface"],
            "status --json",
        )

    def test_runtime_delegated_health_status_summary_does_not_write_runtime_inputs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _status_runtime_paths(Path(temp_dir))
            health_payload = runtime_mod.build_command_payload(
                ok=False,
                human_message="Synthetic health payload.",
                machine_error_code="LISTENER_DOWN",
                liveness="down",
                severity="recoverable",
                operator_action="retry",
                changed_files=[],
                exit_code=1,
                extra={
                    "effective_mode": "stable",
                    "endpoint": "http://127.0.0.1:1/v1",
                    "attestation": {
                        "attestation_source": "healthcheck --json",
                        "observed_at_utc": "2026-06-01T00:00:00+00:00",
                    },
                },
            )
            tracked_paths = [
                paths.registry_file,
                paths.state_file,
                paths.config_toml,
                paths.runtime_mode_file,
                paths.runtime_effective_mode_file,
                paths.stable_config,
                paths.managed_config_file,
                paths.repair_target_reference_file,
                paths.stable_runtime_generated_config_file,
                runtime_mod.managed_pid_path(paths),
            ]
            before = _snapshot_files(tracked_paths)

            with (
                mock.patch.object(
                    runtime_mod,
                    "run_healthcheck",
                    side_effect=AssertionError("delegated adapter must not probe"),
                ),
                mock.patch.object(
                    runtime_mod,
                    "run_healthcheck_probe",
                    side_effect=AssertionError("delegated adapter must not probe"),
                ),
                mock.patch.object(
                    runtime_mod,
                    "run_healthcheck_repair",
                    side_effect=AssertionError("delegated adapter must not repair"),
                ),
            ):
                payload = runtime_mod.summarize_status(
                    paths, health_payload=health_payload
                )

            after = _snapshot_files(tracked_paths)

        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(after, before)
