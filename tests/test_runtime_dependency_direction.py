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
    "wild_boar_proxy.runtime_errors": REPO_ROOT / "wild_boar_proxy" / "runtime_errors.py",
    "wild_boar_proxy.runtime": REPO_ROOT / "wild_boar_proxy" / "runtime.py",
    "wild_boar_proxy.runtime_health": REPO_ROOT / "wild_boar_proxy" / "runtime_health.py",
    "wild_boar_proxy.runtime_modes": REPO_ROOT / "wild_boar_proxy" / "runtime_modes.py",
    "wild_boar_proxy.runtime_repair": REPO_ROOT / "wild_boar_proxy" / "runtime_repair.py",
    "wild_boar_proxy.runtime_status": REPO_ROOT / "wild_boar_proxy" / "runtime_status.py",
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

    def test_detector_flags_accounts_lifecycle_runtime_import(self) -> None:
        source = "from . import runtime\n"

        self.assertEqual(
            _forbidden_imports(source, "wild_boar_proxy.accounts_lifecycle"),
            ["wild_boar_proxy.runtime"],
        )

    def test_runtime_split_modules_do_not_import_forbidden_layers(self) -> None:
        for module_name, path in RUNTIME_MODULE_PATHS.items():
            with self.subTest(module=module_name):
                source = path.read_text(encoding="utf-8")
                self.assertEqual(_forbidden_imports(source, module_name), [])

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
            "dual_lock",
            "serialized_lock",
            "run_bounded_process",
            "run_sync_for_owner_path_under_lock",
            "observe_status_proof_for_owner_path_under_lock",
        }

        self.assertEqual(calls & forbidden, set())

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
            run_protective_lifecycle_owner_path=fake_run_protective_owner_path,
            run_demote_impl=lambda *args, **kwargs: {},
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
            run_protective_lifecycle_owner_path=fake_run_protective_owner_path,
            run_demote_impl=lambda *args, **kwargs: {},
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
            run_protective_lifecycle_owner_path=lambda *args, **kwargs: {},
            run_demote_impl=fake_run_demote_impl,
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
            run_protective_lifecycle_owner_path=lambda *args, **kwargs: {},
            run_demote_impl=lambda *args, **kwargs: {},
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
            run_protective_lifecycle_owner_path=lambda *args, **kwargs: {},
            run_demote_impl=lambda *args, **kwargs: {},
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
                    {
                        "allow_recovery": True,
                        "allow_last_known_good_proxy_write": True,
                        "allow_current_proxy_auto_adoption": True,
                        "allow_stable_fallback_write": True,
                        "allow_stale_pid_cleanup": True,
                        "effect": "repair",
                    },
                )
            ],
        )

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
                    {
                        "allow_recovery": False,
                        "allow_last_known_good_proxy_write": False,
                        "allow_current_proxy_auto_adoption": False,
                        "allow_stable_fallback_write": False,
                        "allow_stale_pid_cleanup": False,
                        "effect": "probe",
                    },
                )
            ],
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
