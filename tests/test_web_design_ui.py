# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import re
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
                or "не является runtime truth" in payload["fixture_notice"].lower()
                or "не является runtime evidence" in payload["fixture_notice"].lower()
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
            "routes.json",
            "secrets.env",
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
            self.assertIn("Wild Boar Proxy - предпросмотр операторского интерфейса", index)
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
        self.assertIn('@media (max-width: 1320px)', css)
        self.assertIn('--font-ui: "SF Mono"', css)
        self.assertIn("font-family: var(--font-ui);", css)
        self.assertNotIn("--preview-scale", css)
        self.assertNotIn("fitPreviewToViewport", js)

    def test_visual_stabilization_keeps_layout_guards_css_only(self) -> None:
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn("max-width: min(100%, 840px);", css)
        self.assertIn("width: min(236px, 100%);", css)
        self.assertIn("overflow-x: auto;", css)
        self.assertIn("min-width: 980px;", css)
        self.assertIn("flex: 1 1 78px;", css)
        self.assertIn("max-width: 640px;", css)
        self.assertIn("max-height: calc(100vh - 96px);", css)
        self.assertIn("grid-template-columns: repeat(3, minmax(150px, 1fr));", css)
        self.assertIn(".accounts-filter-row", css)
        self.assertIn(".accounts-chips", css)

        self.assertIn("JSON.stringify({ ui_action: uiAction, ...extraPayload })", js)
        self.assertNotIn("JSON.stringify({ command_id", js)
        self.assertNotIn('data-ui-action="stable_repair_apply"', (WEB_DESIGN_UI / "index.html").read_text())

    def test_static_preview_can_request_live_readonly_source_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('<option value="live">live только чтение</option>', html)
        self.assertIn('fetch("api/live-readonly"', js)
        self.assertIn('fetch("api/accounts-readonly"', js)
        self.assertIn('fetch("api/api-connections-readonly"', js)
        self.assertIn('fetch("api/actions"', js)
        self.assertIn('snapshot.source === "live_readonly"', js)
        self.assertIn('safeSnapshot.source === "accounts_readonly"', js)
        self.assertIn('safeSnapshot.state_id || safeSnapshot.ui_state', js)
        self.assertNotIn("command_id", js)
        self.assertNotIn("client_path", js)

    def test_overview_nav_and_action_hierarchy_are_product_first(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()

        nav_match = re.search(r'<nav class="nav"[^>]*>(.*?)</nav>', html, re.S)
        self.assertIsNotNone(nav_match)
        nav = nav_match.group(1)
        self.assertIn('data-screen-link="overview"', nav)
        self.assertIn('data-screen-link="accounts"', nav)
        self.assertIn('data-screen-link="api-connections"', nav)
        self.assertIn('data-screen-link="diagnostics"', nav)
        self.assertIn('data-screen-link="settings"', nav)
        self.assertNotIn('data-screen-link="setup"', nav)
        self.assertNotIn('data-screen-link="select-client"', nav)
        self.assertNotIn('data-screen-link="import-existing"', nav)

        overview = self._section_html(html, "overviewScreen")
        self.assertEqual(html.count('class="button primary live-action overview-only"'), 1)
        self.assertIn('id="launchClientAction" class="button primary live-action overview-only"', html)
        self.assertIn('aria-label="Запустить клиент"', html)
        self.assertIn('class="button ghost live-action overview-only"', html)
        self.assertIn("secondary-action-tile", overview)
        self.assertIn("overview-utility-strip", overview)
        self.assertIn("compact-action-panel", overview)
        self.assertLess(overview.find('class="card system-card"'), overview.find('id="actionPanel"'))
        self.assertLess(overview.find('id="eventList"'), overview.find('id="actionPanel"'))
        self.assertIn(".secondary-action-tile", css)
        self.assertIn(".overview-utility-strip", css)
        self.assertIn(".compact-action-panel", css)
        self.assertIn("events.slice(0, 2)", (WEB_DESIGN_UI / "scripts" / "overview.js").read_text())
        self.assertIn("log-empty", css + (WEB_DESIGN_UI / "scripts" / "overview.js").read_text())

    def test_accounts_screen_is_readonly_and_redacted(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('data-screen-link="accounts"', html)
        self.assertIn('id="accountsScreen"', html)
        self.assertIn('id="accountsTableBody"', html)
        self.assertIn("renderAccountsSnapshot", js)
        self.assertIn("accountsFixtureFromOverview", js)
        self.assertIn("Массовые lifecycle-действия отложены", js)
        self.assertIn("validate_account", js)
        self.assertIn("promote_account", js)
        self.assertIn("demote_account", js)
        self.assertIn("retire_account", js)
        self.assertIn("onboard_account", html + js)
        self.assertIn('id="accountAddAction" class="button primary accounts-only onboard-action"', html)
        self.assertIn('data-ui-action="onboard_account"', html)

    def test_api_connections_screen_is_readonly_and_product_safe(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('data-screen-link="api-connections"', html)
        self.assertIn('id="apiConnectionsScreen"', html)
        self.assertIn('id="apiConnectionsTableBody"', html)
        self.assertIn("renderApiConnectionsSnapshot", js)
        self.assertIn("apiConnectionsFixtureFromOverview", js)
        self.assertIn("loadApiConnectionsReadonly", js)
        self.assertIn("api_route_validate", js)
        self.assertIn("api_route_check", js)
        self.assertIn("api_route_allow", js)
        self.assertIn("api_route_disable", js)
        self.assertIn("api_route_remove", js)
        self.assertIn("api_route_profile", js)
        self.assertIn("api_route_evidence_capture", js)
        self.assertIn("routeActionButtons", js)
        self.assertIn("routeActionButton", js)
        self.assertIn("apiRouteStateRequirement", js)
        self.assertIn('maybeConfirmAndRun(uiAction, { route_id: button.dataset.routeId })', js)

        api_screen = self._section_html(html, "apiConnectionsScreen")
        self.assertIn("API-подключения пока не настроены", js)
        self.assertIn("Разрешён", api_screen + js)
        self.assertIn("Отключён", api_screen + js)
        self.assertIn("Пакет профиля", js)
        self.assertIn("Свидетельство", js)
        self.assertIn("UI не читает evidence file", js)
        self.assertNotIn('data-ui-action=', api_screen)
        self.assertNotIn("Вкл", api_screen + js)
        self.assertNotIn("Сделать активным", api_screen + js)
        self.assertNotIn("Подключить Codex", api_screen + js)
        self.assertNotIn("Профиль готов", api_screen + js)
        self.assertNotIn("Основной", api_screen + js)
        self.assertNotIn("Непрерывный поток", api_screen + js)
        self.assertNotIn("Сетка", api_screen + js)
        self.assertIn('id="onboardOverlay"', html)
        self.assertIn('id="runOnboardAction"', html)
        self.assertIn('id="actionOnboardingOutcome"', html)
        self.assertIn('id="actionOnboardingReserveProof"', html)
        self.assertIn('id="actionOnboardingBackend"', html)
        self.assertIn("hold_account", js)
        self.assertIn("release_account", js)
        self.assertIn("account_id", js)
        self.assertIn("route_id", js)
        self.assertIn('maybeConfirmAndRun(uiAction, { account_id: button.dataset.accountId })', js)
        self.assertIn('maybeConfirmAndRun("onboard_account")', js)
        self.assertIn(".live-action, .account-action, .onboard-action, .api-route-action", js)
        self.assertIn("только сначала в резерв", html)
        self.assertIn("no-new-auth и ambiguous identity требуют действия оператора", html)
        self.assertIn("active routing", html)
        self.assertIn("терминальный вывод из lifecycle", js)
        self.assertIn("accountActionButtons", js)
        self.assertIn("Маршрут отключён. Это действие доступно только для разрешённых маршрутов.", js)
        self.assertIn("Маршрут уже разрешён. Это действие доступно только для отключённых маршрутов.", js)
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
        self.assertIn("Диагностический пакет поддержки", html + js)
        self.assertIn("Истина о здоровье runtime не изменялась", js)
        self.assertIn("только метаданные:", js)
        self.assertIn("Просмотр артефакта отложен", html)
        self.assertIn("Сырой текст диагностики недоступен", html)
        self.assertIn(
            'const SCREENS = ["overview", "accounts", "api-connections", "diagnostics", "settings", "setup", "select-client", "import-existing"]',
            js,
        )
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
        self.assertIn("Наблюдаемая конфигурация и статус", html)
        self.assertIn("Безопасные доступные действия", html)
        self.assertIn("Отложенные элементы настроек", html)
        self.assertIn("Настройки в этом контуре доступны только для чтения", html + js)
        self.assertIn("Безопасные действия являются запросами", js)
        self.assertIn("наблюдается, не редактируется", js)
        self.assertIn("renderSettingsSnapshot", js)
        self.assertIn("updateSettingsActionMetadata", js)
        self.assertIn('data-ui-action="set_mode_stable"', html)
        self.assertIn('data-ui-action="set_mode_managed"', html)
        self.assertIn('data-ui-action="stable_repair_plan"', html)
        self.assertIn('data-ui-action="launch_smoke"', html)
        self.assertIn('data-ui-action="launch_client_dispatch"', html)
        self.assertIn('data-ui-action="export_diagnostics"', html)
        self.assertIn("браузер не отправляет произвольные пути", html)
        self.assertIn("прямой доступ к файловой системе отложен", html)
        self.assertIn("изменение конфигурации runtime вне границ контура", html)
        self.assertIn("изменение политики требует owner command surface", html)
        self.assertIn("изменение стартовой политики отложено", html)
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

    def test_setup_select_import_screens_are_inert_skeletons(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertNotIn('id="setupNav"', html)
        self.assertNotIn('id="selectClientNav"', html)
        self.assertNotIn('id="importExistingNav"', html)
        self.assertIn('id="setupScreen"', html)
        self.assertIn('id="selectClientScreen"', html)
        self.assertIn('id="importExistingScreen"', html)
        self.assertIn('data-screen="setup"', html)
        self.assertIn('data-screen="select-client"', html)
        self.assertIn('data-screen="import-existing"', html)
        self.assertIn("Экраны настройки, выбора и импорта инертны", js)
        self.assertIn("simulated truth нет", js)
        self.assertIn("отправка путей из браузера запрещена", html.lower())
        self.assertIn("нет команды обнаружения", html)
        self.assertIn("будущий desktop/native picker", html)
        self.assertIn("нужен command-owned идентификатор кандидата", html)
        self.assertIn("нужен немутационный dry-run пакет импорта", html)
        self.assertIn("нет медиации исходного расположения и сильного подтверждения", html)
        self.assertIn("существующая установка здесь не обнаружена", html)

        for screen_id in ["setupScreen", "selectClientScreen", "importExistingScreen"]:
            section = self._section_html(html, screen_id)
            self.assertNotIn("data-ui-action", section)
            self.assertNotIn("live-action", section)
            self.assertNotIn('type="file"', section)
            self.assertNotIn("readAsText", section)
            self.assertNotIn("window.open", section)
            self.assertNotIn("localStorage", section)
            self.assertNotIn("client_path", section)
            self.assertNotIn("source_dir", section)
            self.assertNotIn("source-dir", section)
            self.assertNotIn("auth_ref", section)
            self.assertNotIn("password", section)
            self.assertNotIn("backend_id", section)
            self.assertNotIn("installer init", section)
            self.assertNotIn("legacy import", section)
            self.assertNotIn("Проверка завершена. Импорт можно применить.", section)
            self.assertNotIn("28 accounts", section)
            self.assertNotIn("Применить</button>", section)

    def test_setup_select_import_routes_are_static_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('"setup"', js)
        self.assertIn('"select-client"', js)
        self.assertIn('"import-existing"', js)
        self.assertNotIn('?screen=setup', html)
        self.assertNotIn('?screen=select-client', html)
        self.assertNotIn('?screen=import-existing', html)
        self.assertNotIn("setup_discovery", html + js)
        self.assertNotIn("verify_path", html + js)
        self.assertNotIn("save_selection", html + js)
        self.assertNotIn("legacy_import", html + js)
        self.assertNotIn("installer_init", html + js)
        self.assertNotIn("import_apply", html + js)

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
        self.assertIn("confirmSeverity", html)
        self.assertIn("confirmPolicy", html)
        self.assertIn("confirmTruthWarning", html)
        self.assertIn("confirmDispatchState", html)
        self.assertIn("CONFIRMATION_POLICY", js)
        self.assertIn("CONSERVATIVE_CONFIRMATION_POLICY", js)
        self.assertIn("confirmationInFlight", js)
        self.assertIn("setConfirmationInFlight", js)
        self.assertIn("maybeConfirmAndRun", js)
        self.assertIn("metadata.confirmation_required", js)
        self.assertIn("confirmationPolicyFor(uiAction, metadata)", js)
        self.assertIn("function closeConfirmation()", js)
        self.assertIn("if (confirmationInFlight)", js)
        self.assertIn("pendingConfirmedAction = null;", js)
        self.assertIn("runUiAction(pending.uiAction, pending.extraPayload);", js)
        self.assertIn("post_action_refresh_required", js)
        self.assertIn("setLiveReadonly(false)", js)

    def test_action_ledger_normalizes_error_states_without_false_green(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()

        self.assertIn('id="actionDisplayState"', html)
        self.assertIn('id="actionTruthNote"', html)
        self.assertIn('id="actionSupportDetails"', html)
        self.assertIn('id="actionPanel" class="action-panel neutral compact-action-panel"', html)
        self.assertIn("ACTION_STATUS_VISUAL_CLASS", js)
        self.assertIn('command_error: "red"', js)
        self.assertIn('integration_failure: "red"', js)
        self.assertIn('invalid_json: "red"', js)
        self.assertIn('timeout: "amber"', js)
        self.assertIn('stale: "amber"', js)
        self.assertIn('unknown: "neutral"', js)
        self.assertIn("payload.status || result.status", js)
        self.assertIn("actionSupportDetails(payload)", js)
        self.assertIn("artifactReference(data.evidence_path)", js)
        self.assertIn('displayState = "stale"', js)
        self.assertIn("live-обновление не удалось; состояние устарело", js)
        self.assertIn("UI_ACTION_INVALID_JSON", js)
        self.assertIn("UI_ACTION_TIMEOUT", js)
        self.assertIn("а не успех", js)
        self.assertIn(".action-panel.green", css)
        self.assertIn(".action-panel.amber", css)
        self.assertIn(".action-panel.red", css)
        self.assertIn(".action-panel.neutral", css)

    def test_action_ledger_rendering_executes_status_mapping(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");
const ids = [
  "actionPanel",
  "actionUiAction",
  "actionRole",
  "actionAccountId",
  "actionStatus",
  "actionDisplayState",
  "actionMachineCode",
  "actionMessage",
  "actionNextAction",
  "actionChangedFiles",
  "actionRefreshStatus",
  "actionTruthNote",
  "actionSupportDetails",
  "actionOnboardingOutcome",
  "actionOnboardingReserveProof",
  "actionOnboardingBackend"
];
const elements = Object.fromEntries(ids.map((id) => [id, {
  className: "",
  textContent: "",
  lastElementChild: { textContent: "" }
}]));
const sandbox = {
  console,
  Node: function Node() {},
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = { className: "", textContent: "", lastElementChild: { textContent: "" } };
      }
      return elements[id];
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "overview", source: "fixture" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

function render(payload, refreshState) {
  sandbox.setActionPanel(payload, refreshState);
  return {
    panel: elements.actionPanel.className,
    status: elements.actionStatus.textContent,
    display: elements.actionDisplayState.textContent,
    truth: elements.actionTruthNote.textContent,
    support: elements.actionSupportDetails.textContent
  };
}

const commandError = render({
  status: "command_error",
  ui_action: "sync_runtime",
  action_role: "runtime_sync",
  post_action_refresh_required: false,
  result: {
    status: "ok",
    machine_error_code: "COMMAND_FAILED",
    human_message: "nested ok must not win",
    next_action: "retry",
    changed_files: []
  }
});
const invalidJson = render({
  ui_action: "refresh_health_detail",
  action_role: "read_only_detail",
  post_action_refresh_required: false,
  result: {
    status: "invalid_json",
    machine_error_code: "UI_ACTION_INVALID_JSON",
    human_message: "invalid json",
    next_action: "retry",
    changed_files: []
  }
});
const staleRefresh = render({
  status: "ok",
  ui_action: "set_mode_managed",
  action_role: "mode_set",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "ok",
    next_action: "none",
    changed_files: []
  }
}, "failed");
const profileSupport = render({
  status: "ok",
  ui_action: "api_route_profile",
  action_role: "api_route_profile_packet",
  post_action_refresh_required: false,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "profile packet",
    next_action: "none",
    changed_files: [],
    data: {
      writes_external_config: false,
      profile_ready: false,
      listener_proven: false,
      runtime_claim_blocked: true
    }
  }
});
const evidenceSupport = render({
  status: "ok",
  ui_action: "api_route_evidence_capture",
  action_role: "api_route_local_evidence_capture",
  post_action_refresh_required: false,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "evidence packet",
    next_action: "none",
    changed_files: ["/tmp/wbp-evidence/wbp-deepseek-v3.json"],
    data: {
      evidence_path: "/tmp/wbp-evidence/wbp-deepseek-v3.json"
    }
  }
});

if (commandError.panel !== "action-panel compact-action-panel red" || commandError.status !== "command_error") {
  throw new Error(`command_error not red: ${JSON.stringify(commandError)}`);
}
if (invalidJson.panel !== "action-panel compact-action-panel red" || invalidJson.display !== "invalid_json") {
  throw new Error(`invalid_json not red: ${JSON.stringify(invalidJson)}`);
}
if (staleRefresh.panel !== "action-panel compact-action-panel amber" || staleRefresh.display !== "stale") {
  throw new Error(`failed refresh not stale amber: ${JSON.stringify(staleRefresh)}`);
}
if (!profileSupport.support.includes("writes_external_config=false") || !profileSupport.support.includes("runtime_claim_blocked=true")) {
  throw new Error(`profile support packet details missing: ${JSON.stringify(profileSupport)}`);
}
if (!evidenceSupport.support.includes("wbp-deepseek-v3.json") || evidenceSupport.support.includes("/tmp/wbp-evidence/")) {
  throw new Error(`evidence support should show only artifact basename metadata: ${JSON.stringify(evidenceSupport)}`);
}
        if (!commandError.truth.includes("не должен показывать это как успех")) {
  throw new Error(`missing command_error truth note: ${commandError.truth}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_static_confirmation_policy_covers_risky_actions(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        for ui_action in [
            "sync_runtime",
            "set_mode_stable",
            "set_mode_managed",
            "launch_client_dispatch",
            "onboard_account",
            "validate_account",
            "promote_account",
            "demote_account",
            "hold_account",
            "release_account",
            "retire_account",
            "api_route_validate",
            "api_route_check",
            "api_route_allow",
            "api_route_disable",
            "api_route_remove",
            "api_route_profile",
            "api_route_evidence_capture",
        ]:
            self.assertIn(f"{ui_action}:", js)

        self.assertIn("terminal-account-lifecycle", js)
        self.assertIn("api-route-validate", js)
        self.assertIn("api-route-check", js)
        self.assertIn("api-route-allow", js)
        self.assertIn("api-route-disable", js)
        self.assertIn("api-route-registry-cleanup", js)
        self.assertIn("api-route-profile-packet", js)
        self.assertIn("api-route-local-evidence", js)
        self.assertIn("metadata-fallback", js)
        self.assertIn("однократная отправка", js)
        self.assertIn("доказательство ёмкости", js)
        self.assertIn("evidence готовности", js)
        self.assertNotIn('data-ui-action="stable_repair_apply"', html)
        self.assertNotIn("stable_repair_apply:", js)
        self.assertNotIn("setup_discovery:", js)
        self.assertNotIn("select_client:", js)
        self.assertNotIn("legacy_import:", js)
        self.assertNotIn("installer_init:", js)

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
        self.assertIn(".live-action, .account-action, .onboard-action, .api-route-action", js)
        self.assertIn(".diagnostics-only", js)
        self.assertIn(".settings-only", js)

    def test_api_route_action_buttons_require_live_source_and_enabled_route(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function makeClassList(classes) {
  return { contains(name) { return classes.includes(name); } };
}

const settingsLaunchAvailability = { textContent: "" };
const desktop = { dataset: { source: "fixture", screen: "api-connections" } };
const enabledButton = {
  dataset: { uiAction: "api_route_validate", routeEnabled: "true", routeId: "wbp-deepseek-v3", routeStateRequirement: "enabled" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const disabledRouteButton = {
  dataset: { uiAction: "api_route_check", routeEnabled: "false", routeId: "wbp-disabled", routeStateRequirement: "enabled" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const allowDisabledRouteButton = {
  dataset: { uiAction: "api_route_allow", routeEnabled: "false", routeId: "wbp-disabled", routeStateRequirement: "disabled" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const allowEnabledRouteButton = {
  dataset: { uiAction: "api_route_allow", routeEnabled: "true", routeId: "wbp-deepseek-v3", routeStateRequirement: "disabled" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const removeDisabledRouteButton = {
  dataset: { uiAction: "api_route_remove", routeEnabled: "false", routeId: "wbp-disabled", routeStateRequirement: "disabled" },
  classList: makeClassList(["api-route-action", "api-route-destructive-action"]),
  disabled: false,
  title: ""
};
const removeEnabledRouteButton = {
  dataset: { uiAction: "api_route_remove", routeEnabled: "true", routeId: "wbp-deepseek-v3", routeStateRequirement: "disabled" },
  classList: makeClassList(["api-route-action", "api-route-destructive-action"]),
  disabled: false,
  title: ""
};
const profileDisabledRouteButton = {
  dataset: { uiAction: "api_route_profile", routeEnabled: "false", routeId: "wbp-disabled", routeStateRequirement: "any" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const evidenceDisabledRouteButton = {
  dataset: { uiAction: "api_route_evidence_capture", routeEnabled: "false", routeId: "wbp-disabled", routeStateRequirement: "any" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};

const sandbox = {
  console,
  Node: function Node() {},
  document: {
    getElementById(id) {
      if (id === "settingsLaunchAvailability") {
        return settingsLaunchAvailability;
      }
      return { textContent: "", className: "", lastElementChild: { textContent: "" } };
    },
    addEventListener() {},
    querySelectorAll(selector) {
      if (selector === ".live-action, .account-action, .onboard-action, .api-route-action") {
        return [
          enabledButton,
          disabledRouteButton,
          allowDisabledRouteButton,
          allowEnabledRouteButton,
          removeDisabledRouteButton,
          removeEnabledRouteButton,
          profileDisabledRouteButton,
          evidenceDisabledRouteButton
        ];
      }
      return [];
    },
    querySelector(selector) {
      if (selector === ".desktop") {
        return desktop;
      }
      return { dataset: { source: "fixture", screen: "overview" } };
    }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
vm.runInContext(`
actionMetadata = {
  api_route_validate: { available: true, unavailable_reason: "", ui_action: "api_route_validate" },
  api_route_check: { available: true, unavailable_reason: "", ui_action: "api_route_check" },
  api_route_allow: { available: true, unavailable_reason: "", ui_action: "api_route_allow" },
  api_route_remove: { available: true, unavailable_reason: "", ui_action: "api_route_remove" },
  api_route_profile: { available: true, unavailable_reason: "", ui_action: "api_route_profile" },
  api_route_evidence_capture: { available: true, unavailable_reason: "", ui_action: "api_route_evidence_capture" },
  launch_client_dispatch: { available: false, unavailable_reason: "server-owned path недоступен", ui_action: "launch_client_dispatch" }
};
`, sandbox);

desktop.dataset.source = "fixture";
sandbox.applyActionAvailability();
if (!enabledButton.disabled || !enabledButton.title.includes("Переключите экран на live-источник")) {
  throw new Error(`enabled route in fixture source should be blocked: ${JSON.stringify(enabledButton)}`);
}

desktop.dataset.source = "live";
sandbox.applyActionAvailability();
if (enabledButton.disabled) {
  throw new Error(`enabled route in live source should be available: ${JSON.stringify(enabledButton)}`);
}
if (!disabledRouteButton.disabled || !disabledRouteButton.title.includes("Маршрут отключён")) {
  throw new Error(`disabled route should stay blocked: ${JSON.stringify(disabledRouteButton)}`);
}
if (allowDisabledRouteButton.disabled) {
  throw new Error(`allow should be available for disabled route in live source: ${JSON.stringify(allowDisabledRouteButton)}`);
}
if (!allowEnabledRouteButton.disabled || !allowEnabledRouteButton.title.includes("Маршрут уже разрешён")) {
  throw new Error(`allow should be blocked for enabled route: ${JSON.stringify(allowEnabledRouteButton)}`);
}
if (removeDisabledRouteButton.disabled) {
  throw new Error(`remove should be available for disabled route in live source: ${JSON.stringify(removeDisabledRouteButton)}`);
}
if (!removeEnabledRouteButton.disabled || !removeEnabledRouteButton.title.includes("Маршрут уже разрешён")) {
  throw new Error(`remove should be blocked for enabled route: ${JSON.stringify(removeEnabledRouteButton)}`);
}
if (profileDisabledRouteButton.disabled) {
  throw new Error(`profile packet should be available for disabled route in live source: ${JSON.stringify(profileDisabledRouteButton)}`);
}
if (evidenceDisabledRouteButton.disabled) {
  throw new Error(`evidence capture should be available for disabled route in live source: ${JSON.stringify(evidenceDisabledRouteButton)}`);
}
if (settingsLaunchAvailability.textContent.indexOf("недоступно") === -1) {
  throw new Error(`settings availability was not updated: ${settingsLaunchAvailability.textContent}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_boar_logo_is_sharp_and_transparent(self) -> None:
        logo_path = WEB_DESIGN_UI / "assets" / "boar_mark.png"
        image = Image.open(logo_path).convert("RGBA")
        alpha = image.getchannel("A")
        transparent_pixels = sum(1 for value in alpha.getdata() if value == 0)

        self.assertGreaterEqual(image.width, 800)
        self.assertGreaterEqual(image.height, 800)
        self.assertGreater(transparent_pixels, 0)

    def _section_html(self, html: str, section_id: str) -> str:
        needle = f'<section id="{section_id}"'
        start = html.find(needle)
        self.assertNotEqual(start, -1, f"Missing section {section_id}")
        next_match = re.search(r'\n        <section id="[^"]+" class="screen', html[start + len(needle):])
        if next_match is None:
            next_overlay = html.find('\n      <div id="onboardOverlay"', start + len(needle))
            end = next_overlay if next_overlay != -1 else len(html)
        else:
            end = start + len(needle) + next_match.start()
        return html[start:end]

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
