# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""R51: production/test separation static proofs.

These tests fail if any R4-era test seam reappears in production code:
runtime grants, test-config injection, environment hooks, caller-provided
env/sandbox parameters on production callables, `(allow default)` sandbox
profiles, or production modules importing test helpers.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from wild_boar_proxy import one_shot_cli_runtime as osr

REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_MODULES = (
    REPO_ROOT / "wild_boar_proxy" / "one_shot_cli_runtime.py",
    REPO_ROOT / "wild_boar_proxy" / "qwen_one_shot_cli.py",
    REPO_ROOT / "wild_boar_proxy" / "kimi_one_shot_cli.py",
)

REMOVED_SEAM_TOKENS = (
    "grant_cli_security_admission",
    "_CLI_SECURITY_ADMISSION_GRANTED",
    "_inject_test_config",
    "_clear_test_config",
    "_TEST_FAKE_MANIFEST",
    "_TEST_HOMES_ROOT",
    "_TEST_ENV_OVERRIDE",
    "WBP_ONE_SHOT_FAKE_MANIFEST",
    "WBP_ONE_SHOT_HOMES_ROOT",
)

FORBIDDEN_PUBLIC_PARAM_NAMES = {
    "env",
    "sandbox",
    "sandbox_profile",
    "executable",
    "fake_manifest",
    "test_config",
    "grant",
    "admission",
    "allow_unsandboxed",
}


def _public_module_functions(path: Path) -> list[ast.FunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]


class TestSeamsRemovedFromProduction(unittest.TestCase):
    def test_removed_seam_tokens_absent_from_production_package(self) -> None:
        offenders: list[str] = []
        for path in sorted((REPO_ROOT / "wild_boar_proxy").rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for token in REMOVED_SEAM_TOKENS:
                if token in text:
                    offenders.append(f"{path.name}:{token}")
        self.assertEqual(offenders, [])

    def test_no_allow_default_sandbox_in_production(self) -> None:
        offenders: list[str] = []
        for path in PRODUCTION_MODULES:
            text = path.read_text(encoding="utf-8")
            if "(allow default)" in text:
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_removed_seams_absent_from_module_namespace(self) -> None:
        for name in REMOVED_SEAM_TOKENS:
            self.assertFalse(hasattr(osr, name), f"{name} is back on the runtime module")

    def test_production_public_functions_have_no_caller_env_or_sandbox(self) -> None:
        """F04/F06 regression: no production public module-level function may
        accept a caller-controlled environment, sandbox posture, or grant."""
        offenders: list[str] = []
        for path in PRODUCTION_MODULES:
            for func in _public_module_functions(path):
                params = {a.arg for a in func.args.args + func.args.kwonlyargs}
                bad = params & FORBIDDEN_PUBLIC_PARAM_NAMES
                if bad:
                    offenders.append(f"{path.name}.{func.name}({sorted(bad)})")
        self.assertEqual(offenders, [])

    def test_production_modules_do_not_import_tests(self) -> None:
        offenders: list[str] = []
        for path in PRODUCTION_MODULES:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    if name == "tests" or name.startswith("tests.") or name == "fakes":
                        offenders.append(f"{path.name}: imports {name}")
        self.assertEqual(offenders, [])


class ProductionFacadeFailClosed(unittest.TestCase):
    def test_default_facade_disabled_before_any_side_effect(self) -> None:
        facade = osr.default_production_facade()
        packet = facade.run("qwen-cli")
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"], osr.CLI_DISABLED_PENDING_SECURITY_ADMISSION
        )
        receipt = facade.receipt()
        self.assertTrue(receipt["cli_disabled"])
        self.assertFalse(receipt["runtime_grant_available"])

    def test_runtime_has_no_module_level_mutable_state(self) -> None:
        """R5: engine configuration lives on instances, not module globals."""
        self.assertEqual(osr.SERVER_OWNED_TOOL_MANIFEST, ())
        # The only module-level facade object is the sealed singleton getter.
        self.assertIs(osr.default_production_facade(), osr.default_production_facade())


if __name__ == "__main__":
    unittest.main()
