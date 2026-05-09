"""Quarantine import checks for the isolated external agent lab."""

from __future__ import annotations

import importlib
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = REPO_ROOT / "external_agent_lab"
LEGACY_ROOT = LAB_ROOT / "legacy"


class ExternalAgentLabQuarantineImportTests(unittest.TestCase):
    def test_package_imports_without_main_runtime(self) -> None:
        package = importlib.import_module("external_agent_lab")

        self.assertTrue(hasattr(package, "__version__"))

    def test_expected_quarantine_files_exist(self) -> None:
        expected_paths = [
            LAB_ROOT / "__init__.py",
            LAB_ROOT / "model_registry_seed.json",
            LEGACY_ROOT / "run_lab.py",
            LEGACY_ROOT / "agent_eval.py",
            LEGACY_ROOT / "proxy_server.py",
            REPO_ROOT / "run_lab.py",
            REPO_ROOT / "agent_eval.py",
        ]

        for path in expected_paths:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), path)

    def test_model_registry_seed_is_valid_json_with_entries(self) -> None:
        payload = json.loads((LAB_ROOT / "model_registry_seed.json").read_text(encoding="utf-8"))

        self.assertIsInstance(payload, dict)
        self.assertIn("entries", payload)
        self.assertIsInstance(payload["entries"], list)
        self.assertGreater(len(payload["entries"]), 0)
        for entry in payload["entries"]:
            with self.subTest(model_id=entry.get("model_id")):
                self.assertIn("model_id", entry)
                self.assertIn("provider", entry)
                self.assertIn("availability_state", entry)
                self.assertIn("lane_role", entry)
                self.assertIn("evidence_level", entry)

    def test_root_wrappers_are_thin_compatibility_shims(self) -> None:
        for wrapper_name, expected_import in (
            ("run_lab.py", "from external_agent_lab.cli import main"),
            ("agent_eval.py", "from external_agent_lab.cli import main"),
        ):
            path = REPO_ROOT / wrapper_name
            text = path.read_text(encoding="utf-8")
            with self.subTest(wrapper=wrapper_name):
                self.assertIn(expected_import, text)
                self.assertLessEqual(len(text.splitlines()), 8)

    def test_root_wrappers_share_the_same_cli_path(self) -> None:
        wrappers = {
            "run_lab.py": 'raise SystemExit(main(default_command="run"))',
            "agent_eval.py": 'raise SystemExit(main(default_command="eval"))',
        }

        for wrapper_name, expected_call in wrappers.items():
            text = (REPO_ROOT / wrapper_name).read_text(encoding="utf-8")
            with self.subTest(wrapper=wrapper_name):
                self.assertIn(expected_call, text)

    def test_forbidden_source_artifacts_were_not_imported(self) -> None:
        forbidden_names = {
            ".env",
            "eval_results",
            "route_results",
            "response_results",
            "provider_results",
            "decision_results",
            "verification_results",
        }

        for name in forbidden_names:
            with self.subTest(name=name):
                self.assertFalse((LAB_ROOT / name).exists(), name)
                self.assertFalse((LEGACY_ROOT / name).exists(), name)

    def test_imported_lab_has_no_main_runtime_dependency(self) -> None:
        for path in sorted(LAB_ROOT.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(REPO_ROOT)):
                self.assertNotIn("import wild_boar_proxy", text)
                self.assertNotIn("from wild_boar_proxy", text)

    def test_legacy_agent_eval_imports_relocated_run_lab_module(self) -> None:
        text = (LEGACY_ROOT / "agent_eval.py").read_text(encoding="utf-8")

        self.assertIn("from external_agent_lab.legacy.run_lab import (", text)
        self.assertNotIn("from run_lab import (", text)


class ExternalAgentLabCliContractTests(unittest.TestCase):
    def test_run_preflight_failure_returns_single_json_packet(self) -> None:
        cli = importlib.import_module("external_agent_lab.cli")
        stdout = io.StringIO()

        with mock.patch.object(cli, "ensure_supported_python", side_effect=cli.LabError("External Agent Lab requires Python >= 3.9.")):
            with redirect_stdout(stdout):
                return_code = cli.main([])

        packet_text = stdout.getvalue().strip()
        packet = json.loads(packet_text)
        self.assertEqual(return_code, 1)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["exit_code"], 1)
        self.assertEqual(packet["machine_error_code"], "invalid_request")
        self.assertEqual(packet["human_message"], "External Agent Lab requires Python >= 3.9.")
        self.assertTrue(packet["lab_mode"])
        self.assertNotIn("Traceback", packet_text)

    def test_eval_preflight_failure_returns_single_json_packet(self) -> None:
        cli = importlib.import_module("external_agent_lab.cli")
        stdout = io.StringIO()

        with mock.patch.object(cli, "ensure_supported_python", side_effect=cli.LabError("External Agent Lab requires Python >= 3.9.")):
            with redirect_stdout(stdout):
                return_code = cli.main(["eval", "--model", "mock", "--dry-run"])

        packet_text = stdout.getvalue().strip()
        packet = json.loads(packet_text)
        self.assertEqual(return_code, 1)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["exit_code"], 1)
        self.assertEqual(packet["machine_error_code"], "invalid_request")
        self.assertEqual(packet["human_message"], "External Agent Lab requires Python >= 3.9.")
        self.assertTrue(packet["lab_mode"])
        self.assertNotIn("Traceback", packet_text)


if __name__ == "__main__":
    unittest.main()
