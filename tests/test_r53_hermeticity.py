# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""R53: hermeticity regression tests.

R4 greenwash patterns being closed here:

- a module-level grant in one test file silently enabled other files
  (F10/F12: standalone fail, combined pass);
- environment hooks changed engine behavior depending on who ran first;
- importing test modules mutated production admission state.

R60 keeps those properties while adding a fixed external admission store:
there is still no grant, env hook, or module-level engine mutation.
"""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path

import fakes

from wild_boar_proxy import final_candidate_assurance as fca
from wild_boar_proxy import kimi_one_shot_cli as km
from wild_boar_proxy import one_shot_cli_runtime as osr
from wild_boar_proxy import qwen_one_shot_cli as qw

QWEN_FAKE = """#!/bin/sh
case "$1" in
  --version) echo "fake-qwen-cli 0.1.0" ;;
  --respond) echo "Qwen: $2" ;;
esac
exit 0
"""


class HermeticityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def _qwen_runtime(self) -> osr.OneShotRuntime:
        script = fakes.write_fake_cli(self.root, "fake-qwen-cli.sh", QWEN_FAKE)
        manifest = fakes.write_manifest(
            self.root,
            [{"tool_id": qw.QWEN_CLI_TOOL_ID, "binary_name": str(script)}],
        )
        return fakes.make_test_runtime(
            self.root / "homes", fakes.load_manifest_entries(manifest)
        )

    def test_importing_test_modules_does_not_change_production_facade(self) -> None:
        before = osr.default_production_facade().run(qw.QWEN_CLI_TOOL_ID)
        for module_name in (
            "test_one_shot_cli_runtime",
            "test_qwen_one_shot_cli",
            "test_kimi_one_shot_cli",
            "test_r51_production_test_separation",
            "test_r52_sandbox_adversarial",
        ):
            importlib.import_module(module_name)
        after = osr.default_production_facade().run(qw.QWEN_CLI_TOOL_ID)
        for packet in (before, after):
            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                osr.CLI_PROVIDER_ADAPTER_NOT_ADMITTED,
            )
        receipt = osr.default_production_facade().receipt()
        self.assertFalse(receipt["cli_disabled"])
        self.assertFalse(receipt["cli_operational"])
        self.assertFalse(receipt["runtime_grant_available"])

    def test_test_runtime_activity_does_not_change_production_facade(self) -> None:
        """A full test-runtime session + run must leave the production
        facade exactly as sealed as before (F10/F12 root cause)."""
        before = osr.default_production_facade().receipt()
        runtime = self._qwen_runtime()
        session = qw.qwen_one_shot_session(runtime=runtime)
        self.assertEqual(session["status"], "ok")
        run = qw.qwen_one_shot_run("ping", session=session, runtime=runtime)
        self.assertEqual(run["status"], "ok")
        after = osr.default_production_facade().receipt()
        self.assertEqual(before["cli_disabled"], after["cli_disabled"])
        self.assertEqual(
            before["runtime_grant_available"], after["runtime_grant_available"]
        )
        disabled = osr.default_production_facade().run(qw.QWEN_CLI_TOOL_ID)
        self.assertEqual(
            disabled["machine_error_code"],
            osr.CLI_PROVIDER_ADAPTER_NOT_ADMITTED,
        )

    def test_final_assurance_checks_independent_of_one_shot_activity(self) -> None:
        """The typed fail-closed checks must give identical results before
        and after arbitrary test-runtime activity, in either order."""
        cli_before = fca._check_cli()
        iso_before = fca._check_account_isolation()
        runtime = self._qwen_runtime()
        session = qw.qwen_one_shot_session(runtime=runtime)
        qw.qwen_one_shot_run("ping", session=session, runtime=runtime)
        km.kimi_one_shot_session(runtime=runtime)
        cli_after = fca._check_cli()
        iso_after = fca._check_account_isolation()
        # These private compatibility probes still encode the pre-R60
        # permanently-disabled contract and are not part of the assurance run
        # path. Test-runtime activity must not change their result either way.
        self.assertEqual(cli_before.passed, cli_after.passed)
        self.assertEqual(iso_before.passed, iso_after.passed)
        self.assertEqual(cli_before.detail, cli_after.detail)
        self.assertEqual(iso_before.detail, iso_after.detail)

    def test_legacy_env_hooks_are_ignored(self) -> None:
        """R4-era env hook names must have zero effect on the engine."""
        saved: dict[str, str | None] = {}
        hook_names = (
            "WBP_ONE_SHOT_FAKE_MANIFEST",
            "WBP_ONE_SHOT_HOMES_ROOT",
            "WBP_ONE_SHOT_CLI_ADMISSION",
        )
        for name in hook_names:
            saved[name] = os.environ.get(name)
            os.environ[name] = str(self.root / "junk")
        try:
            # The facade stays sealed and the provider adapter stays pending.
            packet = osr.default_production_facade().run(qw.QWEN_CLI_TOOL_ID)
            self.assertEqual(
                packet["machine_error_code"],
                osr.CLI_PROVIDER_ADAPTER_NOT_ADMITTED,
            )
            # A fresh engine instance sees only its explicit manifest.
            runtime = osr.OneShotRuntime(homes_root=self.root / "homes2")
            self.assertIsNone(runtime.resolve_manifest_entry(qw.QWEN_CLI_TOOL_ID))
            unknown = runtime.one_shot_cli_run(qw.QWEN_CLI_TOOL_ID)
            self.assertEqual(
                unknown["machine_error_code"], osr.ONE_SHOT_TOOL_UNKNOWN
            )
        finally:
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_engine_instances_are_isolated_from_each_other(self) -> None:
        script = fakes.write_fake_cli(self.root, "fake-qwen-cli.sh", QWEN_FAKE)
        manifest_dir = self.root / "a"
        manifest_dir.mkdir()
        manifest_a = fakes.write_manifest(
            manifest_dir, [{"tool_id": "tool-a", "binary_name": str(script)}]
        )
        runtime_a = fakes.make_test_runtime(
            self.root / "homes-a", fakes.load_manifest_entries(manifest_a)
        )
        runtime_b = osr.OneShotRuntime(homes_root=self.root / "homes-b")
        # runtime_b cannot see runtime_a's tool.
        self.assertIsNone(runtime_b.resolve_manifest_entry("tool-a"))
        # Homes roots are sealed per instance.
        self.assertNotEqual(runtime_a.homes_root, runtime_b.homes_root)
        packet_a = runtime_a.create_provider_home("qwen")
        self.assertTrue(
            str(packet_a["home_path"]).startswith(str(runtime_a.homes_root))
        )

    def test_no_module_level_state_mutation_after_test_runtime_use(self) -> None:
        names_before = set(vars(osr))
        facade_before = osr.default_production_facade()
        runtime = self._qwen_runtime()
        session = qw.qwen_one_shot_session(runtime=runtime)
        qw.qwen_one_shot_run("ping", session=session, runtime=runtime)
        names_after = set(vars(osr))
        self.assertEqual(names_before, names_after)
        self.assertIs(facade_before, osr.default_production_facade())


if __name__ == "__main__":
    unittest.main()
