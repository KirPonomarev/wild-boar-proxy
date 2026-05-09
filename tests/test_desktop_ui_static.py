"""Static checks for the fixture-only desktop HTML overview slice."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_UI = ROOT / "wild_boar_proxy" / "desktop_ui"
FIXTURES = DESKTOP_UI / "fixtures"


class DesktopUiStaticTests(unittest.TestCase):
    def test_expected_static_files_exist(self) -> None:
        expected = [
            DESKTOP_UI / "README.md",
            DESKTOP_UI / "index.html",
            DESKTOP_UI / "styles" / "tokens.css",
            DESKTOP_UI / "styles" / "overview.css",
            DESKTOP_UI / "screens" / "overview.js",
            DESKTOP_UI / "overview_bridge.py",
            DESKTOP_UI / "live_overview.py",
            DESKTOP_UI / "overview_actions.py",
            DESKTOP_UI / "assets" / "boar_mark.png",
        ]
        for path in expected:
            self.assertTrue(path.exists(), path)

    def test_fixture_packets_are_synthetic_and_command_shaped(self) -> None:
        fixture_paths = sorted(FIXTURES.glob("overview_*.json"))
        self.assertGreaterEqual(len(fixture_paths), 8)
        for path in fixture_paths:
            packet = json.loads(path.read_text(encoding="utf-8"))
            self.assertIs(packet.get("synthetic"), True, path.name)
            self.assertEqual(packet.get("source"), "ui_desktop_html_static_overview_fixture")
            self.assertIn("fixture_state", packet)
            self.assertIn("fixture_id", packet)
            for key in ("status_packet", "mode_packet", "accounts_packet"):
                if packet.get(key) is None:
                    continue
                self.assertIn("status", packet[key], f"{path.name}:{key}")
                self.assertIn("exit_code", packet[key], f"{path.name}:{key}")
                self.assertIn("machine_error_code", packet[key], f"{path.name}:{key}")

    def test_desired_and_effective_mode_are_distinct_fixture_fields(self) -> None:
        mismatch = json.loads((FIXTURES / "overview_managed_mismatch.json").read_text(encoding="utf-8"))
        mode_packet = mismatch["mode_packet"]
        self.assertEqual(mode_packet["desired_mode"], "managed")
        self.assertEqual(mode_packet["effective_mode"], "stable")

    def test_static_shell_has_no_live_command_or_runtime_file_access(self) -> None:
        forbidden = [
            "subprocess",
            "Popen",
            "os.system",
            "~/.codex",
            "backend-registry",
            "supervisor-state",
            "runtime.py",
            "cli.py",
        ]
        for path in sorted(DESKTOP_UI.rglob("*")):
            if path.is_dir() or path.suffix == ".png":
                continue
            if path.name == "command_adapter.py":
                continue
            text = path.read_text(encoding="utf-8")
            for needle in forbidden:
                self.assertNotIn(needle, text, f"{needle} found in {path}")

    def test_command_adapter_boundary_has_no_direct_truth_fallbacks(self) -> None:
        adapter = DESKTOP_UI / "command_adapter.py"
        self.assertTrue(adapter.exists(), adapter)
        text = adapter.read_text(encoding="utf-8")
        for needle in (
            "shell=True",
            "Popen",
            "os.system",
            "~/.codex",
            "backend-registry",
            "supervisor-state",
            "runtime.py",
            "cli.py",
            "policy stage",
            "rollout stage",
            "evidence capture",
            "stable target switch",
        ):
            self.assertNotIn(needle, text, f"{needle} found in {adapter}")

    def test_browser_shell_does_not_import_command_adapter(self) -> None:
        for path in sorted((DESKTOP_UI / "screens").glob("*.js")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("command_adapter", text, path)

    def test_browser_shell_has_no_command_surface_strings(self) -> None:
        for path in sorted((DESKTOP_UI / "screens").glob("*.js")):
            text = path.read_text(encoding="utf-8")
            for forbidden in (
                "status --json",
                "healthcheck --json",
                "mode set",
                "accounts promote",
                "rollout stage",
                "stable target",
            ):
                self.assertNotIn(forbidden, text, path)

    def test_overview_action_runner_does_not_enable_browser_bridge(self) -> None:
        index = (DESKTOP_UI / "index.html").read_text(encoding="utf-8")
        overview = (DESKTOP_UI / "screens" / "overview.js").read_text(encoding="utf-8")
        self.assertNotIn("overview_actions", index)
        self.assertNotIn("overview_actions", overview)
        self.assertNotIn("overview_bridge", index)
        self.assertNotIn("overview_bridge", overview)

    def test_deferred_stage_actions_are_not_present(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(DESKTOP_UI.rglob("*"))
            if path.is_file() and path.suffix != ".png"
        )
        for forbidden in (
            "policy stage",
            "rollout stage",
            "evidence capture",
            "stable target switch",
        ):
            self.assertNotIn(forbidden, text.lower())


if __name__ == "__main__":
    unittest.main()
