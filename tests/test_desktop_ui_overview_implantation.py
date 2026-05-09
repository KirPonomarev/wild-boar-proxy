from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_UI = ROOT / "wild_boar_proxy" / "desktop_ui"
OVERVIEW_JS = DESKTOP_UI / "screens" / "overview.js"
README = DESKTOP_UI / "README.md"


class DesktopUiOverviewImplantationTests(unittest.TestCase):
    def test_transport_gate_is_red_and_not_full_implantation(self) -> None:
        overview = OVERVIEW_JS.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")

        self.assertIn('const TRANSPORT_GATE = "RED";', overview)
        self.assertIn("TRANSPORT_GATE=RED", readme)
        self.assertIn("does not call backend commands from the browser", readme)

    def test_browser_builds_only_fixed_bridge_operation_shapes(self) -> None:
        overview = OVERVIEW_JS.read_text(encoding="utf-8")

        self.assertIn('operation_id: "refresh_overview"', overview)
        self.assertIn('operation_id: "run_overview_action"', overview)
        for action_id in (
            "switch_stable",
            "run_sync",
            "launch_client",
            "run_smoke",
        ):
            self.assertIn(action_id, overview)

    def test_browser_forbidden_field_guard_is_present(self) -> None:
        overview = OVERVIEW_JS.read_text(encoding="utf-8")

        for field in (
            "command",
            "argv",
            "shell",
            "path",
            "state_path",
            "log_path",
            "registry_path",
            "snapshot_path",
            "runtime_file",
            "env",
            "cwd",
        ):
            self.assertIn(f'"{field}"', overview)

    def test_browser_does_not_contain_transport_escape_hatches(self) -> None:
        overview = OVERVIEW_JS.read_text(encoding="utf-8")

        for forbidden in (
            "window.pywebview",
            "child_process",
            "XMLHttpRequest",
            "http://127.0.0.1",
            "localhost",
            "overview_bridge",
            "command_adapter",
        ):
            self.assertNotIn(forbidden, overview)

    def test_simulated_lifecycle_is_labeled(self) -> None:
        overview = OVERVIEW_JS.read_text(encoding="utf-8")

        self.assertIn("SIMULATED_TRANSPORT_GATE_RED", overview)
        self.assertIn("ui_desktop_html_overview_implantation_simulated", overview)
        self.assertIn("transport_unavailable", overview)


if __name__ == "__main__":
    unittest.main()
