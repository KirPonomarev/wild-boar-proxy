from __future__ import annotations

import ast
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "wild_boar_proxy" / "runtime.py"
EXTERNAL_MODELS = ROOT / "wild_boar_proxy" / "external_models" / "__init__.py"
CREDENTIALS = ROOT / "wild_boar_proxy" / "external_models" / "credentials.py"
CLI = ROOT / "wild_boar_proxy" / "cli.py"


READ = "READ"
PROBE = "PROBE"
MUTATE = "MUTATE"
REPAIR = "REPAIR"
WRITE_ADJACENT = "WRITE_ADJACENT"
SUBPROCESS_ADJACENT = "SUBPROCESS_ADJACENT"
DEFERRED_UNCLASSIFIED = "DEFERRED_UNCLASSIFIED"


WRITE_PRIMITIVES = {
    "_write_secrets_file",
    "atomic_write_json",
    "chmod",
    "mkdir",
    "os.chmod",
    "os.open",
    "os.replace",
    "replace",
    "unlink",
    "write_bytes",
    "write_json_atomic",
    "write_state_file",
    "write_stable_runtime_consumer_snapshot",
    "write_text",
    "write_text_atomic",
    "write_toml_string_atomic",
    "materialize_selected_backend_snapshot_for_sync",
    "reconcile_stable_fallback",
    "refresh_last_known_good_proxy_from_healthcheck",
}

SUBPROCESS_PRIMITIVES = {
    "Popen",
    "run_current_proxy_owner_path_activation",
    "run_stable_runtime_launcher_attempt",
    "subprocess.Popen",
    "subprocess.run",
}

LOCK_PRIMITIVES = {
    "dual_lock",
    "serialized_lock",
}


@dataclass(frozen=True)
class Surface:
    path: Path
    function: str
    expected_class: str
    required_calls: frozenset[str] = frozenset()


OWNER_SURFACES = {
    "mode_get": Surface(
        RUNTIME,
        "mode_get",
        READ,
        frozenset({"build_command_payload", "read_json"}),
    ),
    "list_accounts": Surface(
        RUNTIME,
        "list_accounts",
        READ,
        frozenset({"build_command_payload", "read_json"}),
    ),
    "credential_status": Surface(
        CREDENTIALS,
        "credential_status",
        READ,
        frozenset(
            {
                "_ensure_sandbox_admission_target",
                "_parse_secrets_file",
                "ensure_secrets_permissions",
            }
        ),
    ),
    "admit_owner_credential": Surface(
        CREDENTIALS,
        "admit_owner_credential",
        MUTATE,
        frozenset({"_write_secrets_file", "ensure_secrets_permissions"}),
    ),
    "mode_set": Surface(
        RUNTIME,
        "mode_set",
        MUTATE,
        frozenset({"serialized_lock", "write_text_atomic"}),
    ),
    "run_sync": Surface(
        RUNTIME,
        "run_sync",
        SUBPROCESS_ADJACENT,
        frozenset(
            {
                "serialized_lock",
                "materialize_selected_backend_snapshot_for_sync",
                "subprocess.run",
                "write_json_atomic",
                "write_text_atomic",
                "write_toml_string_atomic",
            }
        ),
    ),
    "summarize_status": Surface(
        RUNTIME,
        "summarize_status",
        READ,
        frozenset({"build_status_snapshot_payload"}),
    ),
    "run_healthcheck": Surface(
        RUNTIME,
        "run_healthcheck",
        REPAIR,
        frozenset(
            {
                "detect_changed_files",
                "refresh_last_known_good_proxy_from_healthcheck",
                "reconcile_stable_fallback",
                "run_current_proxy_owner_path_activation",
                "run_stable_runtime_launcher_attempt",
            }
        ),
    ),
    "run_healthcheck_probe": Surface(
        RUNTIME,
        "run_healthcheck_probe",
        PROBE,
        frozenset({"run_healthcheck"}),
    ),
    "run_healthcheck_repair": Surface(
        RUNTIME,
        "run_healthcheck_repair",
        REPAIR,
        frozenset({"run_healthcheck"}),
    ),
    "run_onboard": Surface(
        RUNTIME,
        "run_onboard",
        SUBPROCESS_ADJACENT,
        frozenset({"serialized_lock", "subprocess.run", "run_accounts_command"}),
    ),
    "run_promote": Surface(
        RUNTIME,
        "run_promote",
        SUBPROCESS_ADJACENT,
        frozenset({"serialized_lock", "subprocess.run", "detect_changed_files"}),
    ),
    "run_demote": Surface(
        RUNTIME,
        "run_demote",
        SUBPROCESS_ADJACENT,
        frozenset(
            {
                "serialized_lock",
                "subprocess.run",
                "run_sync_for_owner_path_under_lock",
                "observe_status_proof_for_owner_path_under_lock",
            }
        ),
    ),
    "run_hold": Surface(
        RUNTIME,
        "run_hold",
        SUBPROCESS_ADJACENT,
        frozenset({"run_protective_lifecycle_owner_path"}),
    ),
    "run_release": Surface(
        RUNTIME,
        "run_release",
        SUBPROCESS_ADJACENT,
        frozenset({"run_protective_lifecycle_owner_path"}),
    ),
    "run_retire": Surface(
        RUNTIME,
        "run_retire",
        SUBPROCESS_ADJACENT,
        frozenset(
            {
                "serialized_lock",
                "subprocess.run",
                "run_sync_for_owner_path_under_lock",
                "observe_status_proof_for_owner_path_under_lock",
            }
        ),
    ),
    "_run_credentials_command": Surface(
        EXTERNAL_MODELS,
        "_run_credentials_command",
        WRITE_ADJACENT,
        frozenset({"admit_owner_credential", "credential_status"}),
    ),
    "main": Surface(
        CLI,
        "main",
        DEFERRED_UNCLASSIFIED,
        frozenset(
            {"emit_json", "run_healthcheck_probe", "run_healthcheck_repair", "summarize_status"}
        ),
    ),
}

KNOWN_EFFECT_CONTRACT_GAPS = {
    "mode_set_missing_mutate_effect": (
        RUNTIME,
        "mode_set",
        "effect=EFFECT_MUTATE",
    ),
    "cli_runtime_error_handler_missing_effect_context": (
        CLI,
        "main",
        '"effect"',
    ),
    "healthcheck_repair_missing_mutation_metadata": (
        RUNTIME,
        "run_healthcheck_repair",
        "mutation_id",
    ),
    "promote_missing_mutation_metadata": (
        RUNTIME,
        "run_promote",
        "mutation_id",
    ),
}


def _module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _function(path: Path, name: str) -> ast.FunctionDef:
    for node in _module(path).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"Function not found: {path}:{name}")


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Call):
        return _dotted_name(node.func)
    if isinstance(node, ast.Subscript):
        return _dotted_name(node.value)
    return ""


def _call_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            dotted = _dotted_name(child.func)
            if not dotted:
                continue
            names.add(dotted)
            names.add(dotted.rsplit(".", 1)[-1])
    return names


def _function_source(path: Path, function: str) -> str:
    source = path.read_text(encoding="utf-8")
    node = _function(path, function)
    segment = ast.get_source_segment(source, node)
    if segment is None:
        raise AssertionError(f"Source segment not found: {path}:{function}")
    return segment


class OwnerSurfaceEffectInventoryTests(unittest.TestCase):
    def test_inventory_is_scoped_to_selected_owner_surfaces(self) -> None:
        self.assertEqual(
            {
                (RUNTIME, "mode_get"),
                (RUNTIME, "list_accounts"),
                (CREDENTIALS, "credential_status"),
                (CREDENTIALS, "admit_owner_credential"),
                (RUNTIME, "mode_set"),
                (RUNTIME, "run_sync"),
                (RUNTIME, "summarize_status"),
                (RUNTIME, "run_healthcheck"),
                (RUNTIME, "run_healthcheck_probe"),
                (RUNTIME, "run_healthcheck_repair"),
                (RUNTIME, "run_onboard"),
                (RUNTIME, "run_promote"),
                (RUNTIME, "run_demote"),
                (RUNTIME, "run_hold"),
                (RUNTIME, "run_release"),
                (RUNTIME, "run_retire"),
                (EXTERNAL_MODELS, "_run_credentials_command"),
                (CLI, "main"),
            },
            {(surface.path, surface.function) for surface in OWNER_SURFACES.values()},
        )

    def test_read_owner_surfaces_have_no_write_subprocess_or_lock_primitives(self) -> None:
        forbidden = WRITE_PRIMITIVES | SUBPROCESS_PRIMITIVES | LOCK_PRIMITIVES
        for surface in OWNER_SURFACES.values():
            if surface.expected_class != READ:
                continue
            with self.subTest(function=surface.function):
                calls = _call_names(_function(surface.path, surface.function))
                self.assertTrue(surface.required_calls <= calls)
                self.assertEqual(set(), calls & forbidden)

    def test_mutating_owner_surfaces_keep_expected_write_primitives(self) -> None:
        for name in ("admit_owner_credential", "mode_set"):
            surface = OWNER_SURFACES[name]
            with self.subTest(function=surface.function):
                calls = _call_names(_function(surface.path, surface.function))
                self.assertEqual(MUTATE, surface.expected_class)
                self.assertTrue(surface.required_calls <= calls)
                self.assertTrue(calls & WRITE_PRIMITIVES)

    def test_run_sync_keeps_declared_lock_subprocess_and_write_adjacency(self) -> None:
        surface = OWNER_SURFACES["run_sync"]
        calls = _call_names(_function(surface.path, surface.function))
        self.assertEqual(SUBPROCESS_ADJACENT, surface.expected_class)
        self.assertTrue(surface.required_calls <= calls)
        self.assertTrue(calls & LOCK_PRIMITIVES)
        self.assertTrue(calls & SUBPROCESS_PRIMITIVES)
        self.assertTrue(calls & WRITE_PRIMITIVES)

    def test_sync_owner_path_uses_bounded_runner_without_raw_subprocess(self) -> None:
        calls = _call_names(_function(RUNTIME, "run_sync_for_owner_path_under_lock"))
        self.assertIn("run_bounded_process", calls)
        self.assertEqual(set(), calls & SUBPROCESS_PRIMITIVES)

    def test_account_lifecycle_surfaces_keep_declared_effect_adjacency(self) -> None:
        for name in (
            "run_onboard",
            "run_promote",
            "run_demote",
            "run_hold",
            "run_release",
            "run_retire",
        ):
            surface = OWNER_SURFACES[name]
            with self.subTest(function=surface.function):
                calls = _call_names(_function(surface.path, surface.function))
                self.assertEqual(SUBPROCESS_ADJACENT, surface.expected_class)
                self.assertTrue(surface.required_calls <= calls)

        for name in ("run_onboard", "run_promote", "run_demote", "run_retire"):
            surface = OWNER_SURFACES[name]
            with self.subTest(function=f"{surface.function}_raw_effects"):
                calls = _call_names(_function(surface.path, surface.function))
                self.assertTrue(calls & LOCK_PRIMITIVES)
                self.assertTrue(calls & SUBPROCESS_PRIMITIVES)

        for name in ("run_hold", "run_release"):
            surface = OWNER_SURFACES[name]
            with self.subTest(function=f"{surface.function}_delegates"):
                calls = _call_names(_function(surface.path, surface.function))
                self.assertEqual(set(), calls & LOCK_PRIMITIVES)
                self.assertEqual(set(), calls & SUBPROCESS_PRIMITIVES)

    def test_status_is_read_snapshot_and_healthcheck_remains_repair(self) -> None:
        status_surface = OWNER_SURFACES["summarize_status"]
        status_calls = _call_names(_function(status_surface.path, status_surface.function))
        status_source = _function_source(status_surface.path, status_surface.function)
        self.assertEqual(READ, status_surface.expected_class)
        self.assertTrue(status_surface.required_calls <= status_calls)
        self.assertNotIn("run_healthcheck", status_calls)
        self.assertNotIn("run_healthcheck(", status_source)

        health_surface = OWNER_SURFACES["run_healthcheck"]
        health_calls = _call_names(_function(health_surface.path, health_surface.function))
        self.assertEqual(REPAIR, health_surface.expected_class)
        self.assertTrue(health_surface.required_calls <= health_calls)
        self.assertTrue(health_calls & (WRITE_PRIMITIVES | LOCK_PRIMITIVES))

    def test_healthcheck_probe_wrapper_disables_repair_writes_and_stale_pid_cleanup(
        self,
    ) -> None:
        probe_surface = OWNER_SURFACES["run_healthcheck_probe"]
        probe_calls = _call_names(_function(probe_surface.path, probe_surface.function))
        probe_source = _function_source(probe_surface.path, probe_surface.function)
        self.assertEqual(PROBE, probe_surface.expected_class)
        self.assertTrue(probe_surface.required_calls <= probe_calls)
        self.assertNotIn("allow_recovery=True", probe_source)
        self.assertIn("allow_recovery=False", probe_source)
        self.assertIn("allow_last_known_good_proxy_write=False", probe_source)
        self.assertIn("allow_current_proxy_auto_adoption=False", probe_source)
        self.assertIn("allow_stable_fallback_write=False", probe_source)
        self.assertIn("allow_stale_pid_cleanup=False", probe_source)
        self.assertIn("effect=EFFECT_PROBE", probe_source)

    def test_healthcheck_repair_wrapper_declares_repair_enabled_path(self) -> None:
        repair_surface = OWNER_SURFACES["run_healthcheck_repair"]
        repair_calls = _call_names(_function(repair_surface.path, repair_surface.function))
        repair_source = _function_source(repair_surface.path, repair_surface.function)
        self.assertEqual(REPAIR, repair_surface.expected_class)
        self.assertTrue(repair_surface.required_calls <= repair_calls)
        self.assertIn("allow_recovery=True", repair_source)
        self.assertIn("allow_last_known_good_proxy_write=True", repair_source)
        self.assertIn("allow_current_proxy_auto_adoption=True", repair_source)
        self.assertIn("allow_stable_fallback_write=True", repair_source)
        self.assertIn("allow_stale_pid_cleanup=True", repair_source)
        self.assertIn("effect=EFFECT_REPAIR", repair_source)

    def test_dispatch_surfaces_do_not_own_raw_primitives(
        self,
    ) -> None:
        forbidden_raw_primitives = WRITE_PRIMITIVES | SUBPROCESS_PRIMITIVES | LOCK_PRIMITIVES
        for name, expected_class in (
            ("_run_credentials_command", WRITE_ADJACENT),
            ("main", DEFERRED_UNCLASSIFIED),
        ):
            surface = OWNER_SURFACES[name]
            with self.subTest(function=surface.function):
                calls = _call_names(_function(surface.path, surface.function))
                self.assertEqual(expected_class, surface.expected_class)
                self.assertTrue(surface.required_calls <= calls)
                self.assertEqual(set(), calls & forbidden_raw_primitives)

    def test_known_effect_contract_gaps_are_explicitly_tracked(self) -> None:
        self.assertEqual(
            {
                "mode_set_missing_mutate_effect",
                "cli_runtime_error_handler_missing_effect_context",
                "healthcheck_repair_missing_mutation_metadata",
                "promote_missing_mutation_metadata",
            },
            set(KNOWN_EFFECT_CONTRACT_GAPS),
        )
        for gap, (path, function, absent_text) in KNOWN_EFFECT_CONTRACT_GAPS.items():
            with self.subTest(gap=gap):
                source = _function_source(path, function)
                self.assertNotIn(absent_text, source)


if __name__ == "__main__":
    unittest.main()
