# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import socket
import subprocess
import time
import unittest
import urllib.request
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
WEB_DESIGN_UI = ROOT / "wild_boar_proxy" / "web_design_ui"
FIXTURES = WEB_DESIGN_UI / "fixtures"
NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class WebDesignUiTests(unittest.TestCase):
    def test_first_screen_design_assets_exist(self) -> None:
        self.assertTrue((WEB_DESIGN_UI / "index.html").is_file())
        self.assertTrue((WEB_DESIGN_UI / "styles" / "overview.css").is_file())
        self.assertTrue((WEB_DESIGN_UI / "scripts" / "overview.js").is_file())
        self.assertTrue((WEB_DESIGN_UI / "assets" / "boar_mark.png").is_file())

    def test_fixture_states_are_present_and_distinct(self) -> None:
        expected = {
            "healthy",
            "degraded",
            "down",
            "stale",
            "unknown",
            "integration_failure",
        }
        actual = {path.stem for path in FIXTURES.glob("*.json")}
        self.assertLessEqual(expected, actual)

        visual_states = {}
        for state in expected:
            payload = json.loads((FIXTURES / f"{state}.json").read_text())
            self.assertEqual(payload["state_id"], state)
            visual_states[state] = payload["runtime"]["visual_state"]

        self.assertEqual(visual_states["healthy"], "healthy")
        self.assertEqual(visual_states["down"], "down")
        self.assertEqual(visual_states["unknown"], "unknown")
        self.assertEqual(visual_states["integration_failure"], "integration_failure")
        self.assertNotEqual(visual_states["healthy"], visual_states["stale"])

    def test_fixtures_have_required_runtime_shape(self) -> None:
        required_top = {
            "schema_version",
            "state_id",
            "fixture_notice",
            "runtime",
            "pool_summary",
            "events",
        }
        required_runtime = {
            "visual_state",
            "status_label",
            "desired_mode",
            "effective_mode",
            "endpoint",
            "machine_error_code",
            "human_message",
            "last_error",
            "observed_at_utc",
        }
        required_pool = {
            "active",
            "reserve",
            "hold",
            "problem",
            "active_note",
            "reserve_note",
            "hold_note",
            "problem_note",
        }

        for path in FIXTURES.glob("*.json"):
            payload = json.loads(path.read_text())
            self.assertLessEqual(required_top, set(payload), path)
            self.assertLessEqual(required_runtime, set(payload["runtime"]), path)
            self.assertLessEqual(required_pool, set(payload["pool_summary"]), path)
            self.assertIsInstance(payload["events"], list, path)
            self.assertTrue(
                "not runtime truth" in payload["fixture_notice"].lower()
                or payload["state_id"] != "healthy",
                path,
            )

    def test_static_design_ui_does_not_execute_live_commands_or_read_runtime_files(
        self,
    ) -> None:
        combined = "\n".join(
            [
                (WEB_DESIGN_UI / "index.html").read_text(),
                (WEB_DESIGN_UI / "scripts" / "overview.js").read_text(),
            ]
        )
        forbidden_fragments = [
            "subprocess",
            "child_process",
            "exec(",
            "spawn(",
            "status --json",
            "healthcheck --json",
            "accounts list --json",
            "rollout rotation inspect --json",
            "state.json",
            "supervisor-state",
            ".codex-custom-cli",
            ".cli-proxy-api",
        ]
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, combined)

    def test_static_preview_serves_index_and_fixture_payloads(self) -> None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        process = subprocess.Popen(
            [
                "python3",
                "-m",
                "http.server",
                str(port),
                "--bind",
                "127.0.0.1",
                "--directory",
                str(WEB_DESIGN_UI),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            base_url = f"http://127.0.0.1:{port}"
            index = self._fetch_with_retry(f"{base_url}/?state=healthy")
            self.assertIn("Wild Boar Proxy - Overview Design Preview", index)
            self.assertIn("sourcePicker", index)
            self.assertIn("statePicker", index)
            self.assertIn("fixtureBanner", index)

            for state in [
                "healthy",
                "degraded",
                "down",
                "stale",
                "unknown",
                "integration_failure",
            ]:
                body = self._fetch_with_retry(f"{base_url}/fixtures/{state}.json")
                payload = json.loads(body)
                self.assertEqual(payload["state_id"], state)
        finally:
            process.terminate()
            process.wait(timeout=5)

    def test_preview_uses_desktop_containment_and_svg_icons(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('content="width=device-width, initial-scale=1"', html)
        self.assertIn('class="ui-icon nav-icon"', html)
        self.assertIn('class="ui-icon tile-icon"', html)
        self.assertIn("width: min(1544px, calc(100vw - 56px));", css)
        self.assertIn("overflow-x: hidden;", css)
        self.assertIn("@media (max-width: 1420px)", css)
        self.assertNotIn("--preview-scale", css)
        self.assertNotIn("fitPreviewToViewport", js)

    def test_static_preview_can_request_live_readonly_source_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('<option value="live">live read-only</option>', html)
        self.assertIn('fetch("api/live-readonly"', js)
        self.assertIn('fetch("api/accounts-readonly"', js)
        self.assertIn('fetch("api/actions"', js)
        self.assertIn('snapshot.source === "live_readonly"', js)
        self.assertIn('safeSnapshot.source === "accounts_readonly"', js)
        self.assertIn('safeSnapshot.state_id || safeSnapshot.ui_state', js)
        self.assertNotIn("command_id", js)
        self.assertNotIn("client_path", js)

    def test_accounts_screen_is_readonly_and_redacted(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('data-screen-link="accounts"', html)
        self.assertIn('id="accountsScreen"', html)
        self.assertIn('id="accountsTableBody"', html)
        self.assertIn("renderAccountsSnapshot", js)
        self.assertIn("accountsFixtureFromOverview", js)
        self.assertIn("Bulk lifecycle actions are deferred", js)
        self.assertIn("validate_account", js)
        self.assertIn("promote_account", js)
        self.assertIn("demote_account", js)
        self.assertIn("retire_account", js)
        self.assertIn("onboard_account", html + js)
        self.assertIn('id="accountAddAction" class="button primary accounts-only onboard-action"', html)
        self.assertIn('data-ui-action="onboard_account"', html)
        self.assertIn('id="onboardOverlay"', html)
        self.assertIn('id="runOnboardAction"', html)
        self.assertIn('id="actionOnboardingOutcome"', html)
        self.assertIn('id="actionOnboardingReserveProof"', html)
        self.assertIn('id="actionOnboardingBackend"', html)
        self.assertIn("hold_account", js)
        self.assertIn("release_account", js)
        self.assertIn("account_id", js)
        self.assertIn('maybeConfirmAndRun(uiAction, { account_id: button.dataset.accountId })', js)
        self.assertIn('maybeConfirmAndRun("onboard_account")', js)
        self.assertIn(".live-action, .account-action, .onboard-action", js)
        self.assertIn("reserve-first only", html)
        self.assertIn("no-new-auth and ambiguous identity require operator action", html)
        self.assertIn("active routing", html)
        self.assertIn("terminal lifecycle retirement", js)
        self.assertIn("accountActionButtons", js)
        self.assertIn("secret_references", js)
        self.assertNotIn("auth_ref", html + js)
        self.assertNotIn("accounts validate", html + js)
        self.assertNotIn("accounts hold", html + js)
        self.assertNotIn("accounts promote", html + js)
        self.assertNotIn("accounts demote", html + js)
        self.assertNotIn("accounts release", html + js)
        self.assertNotIn("accounts retire", html + js)
        self.assertNotIn("accounts onboard", html + js)
        self.assertNotIn("auth_ref", html + js)
        self.assertNotIn("source_dir", html + js)
        self.assertNotIn('type="file"', html)
        self.assertNotIn('name="password"', html)
        self.assertNotIn('name="credentials"', html)
        self.assertNotIn('name="backend_id"', html)
        self.assertNotIn("auto-promote", html + js)
        self.assertNotIn("delete", html + js)
        self.assertNotIn("reactivation", html + js)
        self.assertNotIn("reactivate", html + js)
        self.assertNotIn("restore later", html + js)
        self.assertNotIn("pilot", html + js)
        self.assertNotIn("scale proof", html + js)

    def test_diagnostics_screen_is_support_artifact_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('data-screen-link="diagnostics"', html)
        self.assertIn('id="diagnosticsScreen"', html)
        self.assertIn('class="button primary live-action diagnostics-only"', html)
        self.assertIn('data-ui-action="export_diagnostics"', html)
        self.assertIn("Diagnostics support artifact", html + js)
        self.assertIn("Runtime health truth was not changed", js)
        self.assertIn("metadata only:", js)
        self.assertIn("Artifact inspection deferred", html)
        self.assertIn("Raw diagnostic text unavailable", html)
        self.assertIn('const SCREENS = ["overview", "accounts", "diagnostics", "settings"]', js)
        self.assertIn("renderDiagnosticsAction", js)
        self.assertIn("artifactReference(data.bundle_path)", js)
        self.assertNotIn("Показать журнал", html)
        self.assertNotIn("Открыть auth", html)
        self.assertNotIn("В резерв", html)
        self.assertNotIn('type="file"', html)
        self.assertNotIn("readAsText", js)
        self.assertNotIn("localStorage", js)
        self.assertNotIn("window.open", js)
        self.assertNotIn("diagnostics export --json", html + js)
        self.assertNotIn("runtime healthy", (html + js).lower())
        self.assertNotIn("pilot", html + js)
        self.assertNotIn("scale proof", html + js)

    def test_settings_screen_is_readonly_with_safe_actions_and_deferred_controls(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('data-screen-link="settings"', html)
        self.assertIn('id="settingsScreen"', html)
        self.assertIn("Observed configuration / status", html)
        self.assertIn("Safe existing actions", html)
        self.assertIn("Deferred settings controls", html)
        self.assertIn("Settings is read-only in this contour", html + js)
        self.assertIn("Safe actions are requests, not saved preferences", js)
        self.assertIn("observed, not editable", js)
        self.assertIn("renderSettingsSnapshot", js)
        self.assertIn("updateSettingsActionMetadata", js)
        self.assertIn('data-ui-action="set_mode_stable"', html)
        self.assertIn('data-ui-action="set_mode_managed"', html)
        self.assertIn('data-ui-action="stable_repair_plan"', html)
        self.assertIn('data-ui-action="launch_smoke"', html)
        self.assertIn('data-ui-action="launch_client_dispatch"', html)
        self.assertIn('data-ui-action="export_diagnostics"', html)
        self.assertIn("browser path submission forbidden", html)
        self.assertIn("direct filesystem access deferred", html)
        self.assertIn("runtime config mutation out of scope", html)
        self.assertIn("policy mutation requires owner command surface", html)
        self.assertIn("startup policy mutation deferred", html)
        self.assertNotIn("Save settings", html)
        self.assertNotIn("Cancel settings", html)
        self.assertNotIn("Finder", html)
        self.assertNotIn('type="file"', html)
        self.assertNotIn('contenteditable="true"', html)
        self.assertNotIn('data-ui-action="stable_repair_apply"', html)
        self.assertNotIn("policy_stage", html + js)
        self.assertNotIn("rollout stage", html + js)
        self.assertNotIn("JSON.stringify({ command_id", js)
        self.assertNotIn("client_path", html + js)
        self.assertNotIn("config.toml", html + js)
        self.assertNotIn("state.json", html + js)
        self.assertNotIn("supervisor-state", html + js)

    def test_static_preview_uses_ui_action_for_basic_actions(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('data-ui-action="refresh_health_detail"', html)
        self.assertIn('data-ui-action="export_diagnostics"', html)
        self.assertIn('data-ui-action="stable_repair_plan"', html)
        self.assertIn('data-ui-action="sync_runtime"', html)
        self.assertIn('data-ui-action="set_mode_stable"', html)
        self.assertIn('data-ui-action="set_mode_managed"', html)
        self.assertIn('data-ui-action="launch_smoke"', html)
        self.assertIn('data-ui-action="launch_client_dispatch"', html)
        self.assertNotIn('data-ui-action="launch_client"', html)
        self.assertNotIn('data-ui-action="stable_repair_apply"', html)
        self.assertIn('fetch("api/action"', js)
        self.assertIn("JSON.stringify({ ui_action: uiAction, ...extraPayload })", js)
        self.assertNotIn("JSON.stringify({ command_id", js)
        self.assertNotIn("client_path", html + js)
        self.assertNotIn("sync --json", html + js)
        self.assertNotIn("mode set stable --json", html + js)
        self.assertNotIn("launch smoke --json", html + js)
        self.assertNotIn("launch client", html + js)

    def test_static_preview_requires_confirmation_for_mutating_actions(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn("confirmOverlay", html)
        self.assertIn("confirmAction", html)
        self.assertIn("cancelAction", html)
        self.assertIn("maybeConfirmAndRun", js)
        self.assertIn("metadata.confirmation_required", js)
        self.assertIn("closeConfirmation();", js)
        self.assertIn("runUiAction(pending.uiAction, pending.extraPayload);", js)
        self.assertIn("post_action_refresh_required", js)
        self.assertIn("setLiveReadonly(false)", js)

    def test_static_preview_applies_action_availability_from_metadata(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('id="launchClientAction"', html)
        self.assertIn('data-ui-action="launch_client_dispatch"', html)
        self.assertIn("disabled", html)
        self.assertIn("applyActionAvailability", js)
        self.assertIn("metadata.available !== false", js)
        self.assertIn("metadata.unavailable_reason", js)
        self.assertIn("UI_ACTION_UNAVAILABLE", js)
        self.assertIn(".live-action, .account-action", js)
        self.assertIn(".diagnostics-only", js)
        self.assertIn(".settings-only", js)

    def test_boar_logo_is_sharp_and_transparent(self) -> None:
        logo_path = WEB_DESIGN_UI / "assets" / "boar_mark.png"
        image = Image.open(logo_path).convert("RGBA")
        alpha = image.getchannel("A")
        transparent_pixels = sum(1 for value in alpha.getdata() if value == 0)

        self.assertGreaterEqual(image.width, 800)
        self.assertGreaterEqual(image.height, 800)
        self.assertGreater(transparent_pixels, 0)

    def _fetch_with_retry(self, url: str) -> str:
        last_error: Exception | None = None
        for _ in range(20):
            try:
                with NO_PROXY_OPENER.open(url, timeout=1) as response:
                    return response.read().decode("utf-8")
            except Exception as exc:  # pragma: no cover - diagnostic path
                last_error = exc
                time.sleep(0.05)
        raise AssertionError(f"Could not fetch {url}: {last_error}")


if __name__ == "__main__":
    unittest.main()
