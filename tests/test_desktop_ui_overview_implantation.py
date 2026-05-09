from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_UI = ROOT / "wild_boar_proxy" / "desktop_ui"
OVERVIEW_JS = DESKTOP_UI / "screens" / "overview.js"
README = DESKTOP_UI / "README.md"


class DesktopUiOverviewImplantationTests(unittest.TestCase):
    def test_safe_transport_is_admitted_for_first_screen_only(self) -> None:
        overview = OVERVIEW_JS.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")

        self.assertIn('const TRANSPORT_GATE = "ADMITTED_LOCAL_ONLY";', overview)
        self.assertIn("OVERVIEW_SAFE_TRANSPORT=ADMITTED_LOCAL_ONLY", readme)
        self.assertIn("Full implantation status", readme)
        self.assertIn("does not send CLI commands from the browser", readme)

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
            "localhost",
            "overview_bridge",
            "command_adapter",
        ):
            self.assertNotIn(forbidden, overview)

    def test_transport_endpoint_validation_is_strict(self) -> None:
        overview = OVERVIEW_JS.read_text(encoding="utf-8")

        self.assertIn("window.__WBP_OVERVIEW_TRANSPORT_ENDPOINT", overview)
        self.assertIn('parsed.protocol !== "http:"', overview)
        self.assertIn("parsed.hostname !== TRANSPORT_HOST", overview)
        self.assertIn("parsed.pathname !== TRANSPORT_ROUTE", overview)
        self.assertIn("parsed.username || parsed.password || parsed.hash || parsed.search", overview)
        self.assertIn('const TRANSPORT_HOST = "127.0.0.1";', overview)
        self.assertIn('const TRANSPORT_ROUTE = "/overview-bridge";', overview)

    def test_real_transport_mode_uses_fetch_without_raw_commands(self) -> None:
        overview = OVERVIEW_JS.read_text(encoding="utf-8")

        self.assertIn("runTransportBridgeAction", overview)
        self.assertIn("callTransportBridge", overview)
        self.assertIn('method: "POST"', overview)
        self.assertIn("JSON.stringify(request)", overview)
        self.assertNotIn("status --json", overview)
        self.assertNotIn("healthcheck --json", overview)
        self.assertNotIn("mode set", overview)

    def test_simulated_lifecycle_is_labeled_as_fallback(self) -> None:
        overview = OVERVIEW_JS.read_text(encoding="utf-8")

        self.assertIn("SIMULATED_TRANSPORT_GATE_RED", overview)
        self.assertIn("ui_desktop_html_overview_implantation_simulated", overview)
        self.assertIn("transport_unavailable", overview)


if __name__ == "__main__":
    unittest.main()
