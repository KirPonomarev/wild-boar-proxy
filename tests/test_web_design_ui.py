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

    def test_preview_uses_desktop_containment_and_icon_hooks(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()

        self.assertIn('content="width=device-width, initial-scale=1"', html)
        self.assertIn('class="ui-icon nav-icon"', html)
        self.assertIn('class="ui-icon tile-icon"', html)
        self.assertIn("--window-width: 1544px;", css)
        self.assertIn("--window-height: 944px;", css)
        self.assertIn("--sidebar-width: 304px;", css)
        self.assertIn("width: min(var(--window-width), calc(100vw - 56px));", css)
        self.assertIn("height: min(var(--window-height), calc(100vh - 56px));", css)
        self.assertIn("padding: 66px 24px 28px;", css)
        self.assertIn("width: 92px;", css)
        self.assertIn("padding: 48px 40px 32px;", css)
        self.assertIn("--radius-window: 24px;", css)
        self.assertIn("--radius-card: 18px;", css)
        self.assertIn("--radius-button: 12px;", css)
        self.assertIn("--radius-chip: 999px;", css)
        self.assertIn("border-radius: var(--radius-window);", css)
        self.assertIn("border-radius: var(--radius-card);", css)
        self.assertIn("border-radius: var(--radius-button);", css)
        self.assertIn("border-radius: var(--radius-chip);", css)
        self.assertIn("line-height: 20px;", css)
        self.assertIn("line-height: 28px;", css)
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

        self.assertIn("max-width: min(100%, 660px);", css)
        self.assertIn("width: min(236px, 100%);", css)
        self.assertIn("overflow-x: auto;", css)
        self.assertIn("min-width: 980px;", css)
        self.assertIn("flex: 1 1 calc(50% - 4px);", css)
        self.assertIn("max-height: calc(100vh - 372px);", css)
        self.assertIn("max-height: calc(100vh - 520px);", css)
        self.assertIn(".api-route-action-group", css)
        self.assertIn(".api-route-builder-card", css)
        self.assertIn("max-width: 640px;", css)
        self.assertIn("max-height: calc(100vh - 96px);", css)
        self.assertIn("grid-template-columns: repeat(3, minmax(150px, 1fr));", css)
        self.assertIn(".accounts-filter-row", css)
        self.assertIn(".accounts-chips", css)

        self.assertIn("boundedUiActionPayload(uiAction, extraPayload)", js)
        self.assertIn("BROWSER_ACTION_PAYLOAD_KEYS", js)
        self.assertIn("body: JSON.stringify(requestPayload)", js)
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
        self.assertLess(nav.find('data-screen-link="quick-start"'), nav.find('data-screen-link="overview"'))
        self.assertIn('data-screen-link="quick-start"', nav)
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

    def test_quick_start_daily_control_panel_is_summary_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()

        nav_match = re.search(r'<nav class="nav"[^>]*>(.*?)</nav>', html, re.S)
        self.assertIsNotNone(nav_match)
        nav = nav_match.group(1)
        self.assertLess(nav.find('data-screen-link="quick-start"'), nav.find('data-screen-link="overview"'))
        self.assertIn('href="?screen=quick-start"', nav)
        self.assertIn('src="assets/icons/phosphor/lightning.png"', nav)
        self.assertIn(
            'const SCREENS = ["quick-start", "overview", "accounts", "api-connections", "diagnostics", "settings", "setup", "select-client", "import-existing"]',
            js,
        )

        section = self._section_html(html, "quickStartScreen")
        self.assertIn('data-screen="quick-start"', section)
        self.assertIn("Аккаунты Codex", section)
        self.assertIn("Основной API", section)
        self.assertIn("Упрощённый режим показывает только итоговые статусы и безопасные действия.", section + js)
        self.assertIn("Первый запуск: пустые состояния не являются ошибкой.", js)
        self.assertIn("Live-readonly данные недоступны. Предыдущие fixture-данные не используются.", js)
        self.assertIn("Основной route не подтверждён", section + js)
        self.assertIn("secret_ref: —", section)
        self.assertIn('href="?screen=api-connections"', section)
        self.assertIn('href="?screen=accounts"', section)
        self.assertIn('data-ui-action="onboard_account"', section)
        self.assertIn('data-ui-action="api_route_check"', section)
        self.assertIn('data-route-id=""', section)
        self.assertIn("quickStartAccountsFixtureFromOverview", js)
        self.assertIn("quickStartApiFixtureFromOverview", js)
        self.assertIn("quickStartApiModel", js)
        self.assertIn("Live snapshot не содержит confirmed main route", js)
        self.assertIn(".quick-start-grid", css)
        self.assertIn(".quick-start-card", css)
        self.assertIn(".quick-start-account-row", css)
        self.assertIn(".quick-start-api-status", css)
        self.assertIn("grid-template-columns: minmax(0, 1.24fr) minmax(360px, .92fr)", css)

        for forbidden in (
            "<canvas",
            "<textarea",
            "<pre",
            'type="file"',
            "raw JSON",
            "raw logs",
            "machine-code dump",
            "route table",
            "secret value",
            "route JSON",
            "provider config",
            "auth file",
        ):
            self.assertNotIn(forbidden, section)
        self.assertNotIn("<svg", section.lower())
        self.assertNotIn("command_id", section + js)
        self.assertNotIn("client_path", section + js)
        self.assertNotIn("source_dir", section + js)
        self.assertNotIn("showOpenFilePicker", section + js)
        self.assertIn('src="assets/icons/phosphor/users.png"', section)
        self.assertIn('src="assets/icons/phosphor/share-network.png"', section)
        self.assertIn('src="assets/icons/phosphor/key.png"', section)
        self.assertIn('src="assets/icons/phosphor/terminal-window.png"', section)
        self.assertIn('src="assets/icons/phosphor/shield-check.png"', section)
        self.assertIn("missing_secret_ref", js)
        self.assertIn('setQuickStartChecklistChip("quickStartApiSecretChip", apiModel.state === "missing_secret_ref" ? "amber"', js)
        self.assertIn('const primary = source === "live"', js)

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

    def test_account_detail_drawer_projects_accounts_snapshot_only(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()

        self.assertIn('id="accountDetailOverlay"', html)
        self.assertIn('id="accountDetailDrawer"', html)
        self.assertIn('id="accountDetailActions"', html)
        self.assertIn("currentAccountsSnapshot", js)
        self.assertIn("selectedAccountId", js)
        self.assertIn("function openAccountDrawer", js)
        self.assertIn("function renderAccountDetailDrawer", js)
        self.assertIn("function renderMissingAccountDrawer", js)
        self.assertIn("function renderAccountDetailTimeline", js)
        self.assertIn("function renderAccountDetailActions", js)
        self.assertIn("function renderAccountDetailLastCommand", js)
        self.assertIn("function isInteractiveAccountRowTarget", js)
        self.assertIn("function safeAccountDetailText", js)
        self.assertIn("function redactUiSensitiveText", js)
        self.assertIn("accountActionEligibility(account).filter((item) => item.enabled)", js)
        self.assertIn("account_missing_after_refresh", html + js)
        self.assertIn("Открыть drawer. Данные берутся только из текущего accounts JSON.", js)
        self.assertIn('maybeConfirmAndRun(uiAction, { account_id: button.dataset.accountId })', js)
        self.assertIn('row.addEventListener("click"', js)
        self.assertIn("Открыть детали", js)
        self.assertIn('id="accountDetailDangerActions"', html)
        self.assertIn('id="accountDetailTimeline"', html)
        self.assertIn('id="accountDetailLastCommandChip"', html)
        self.assertIn("Payload только ui_action + account_id", html)
        self.assertIn("Command result не является состоянием аккаунта до refresh", html)
        self.assertNotIn("localStorage", js)
        self.assertNotIn("sessionStorage", js)
        self.assertNotIn('type="file"', html)
        self.assertNotIn("readAsText", js)
        self.assertIn(".account-detail-drawer", css)
        self.assertIn(".account-detail-action-group", css)
        self.assertIn(".account-detail-timeline", css)
        self.assertIn(".account-detail-danger", css)

        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.dataset = {};
    this.hidden = false;
    this.disabled = false;
    this.className = "";
    this.textContent = "";
    this.title = "";
    this.type = "";
    this.lastElementChild = { textContent: "" };
    this.classList = {
      contains: (name) => String(this.className || "").split(/\s+/).includes(name),
      add: (name) => {
        if (!this.classList.contains(name)) {
          this.className = `${this.className} ${name}`.trim();
        }
      },
      toggle: () => {}
    };
  }
  append(...nodes) {
    for (const node of nodes) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
        allNodes.push(node);
        this.lastElementChild = node;
      }
    }
  }
  replaceChildren(...nodes) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...nodes);
  }
  addEventListener() {}
  focus() {}
  remove() {
    if (!this.parentNode) {
      return;
    }
    this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
  }
  querySelector(selector) {
    const className = selector.startsWith(".") ? selector.slice(1) : "";
    return this.children.find((child) => child.classList?.contains(className)) || null;
  }
}

const allNodes = [];
const nodes = {};
function node(id) {
  if (!nodes[id]) {
    nodes[id] = new Node();
    nodes[id].id = id;
    allNodes.push(nodes[id]);
  }
  return nodes[id];
}

for (const id of [
  "sourcePicker", "statePicker", "brandCaption", "refreshFixture", "accountsBanner",
  "accountsActiveChip", "accountsReserveChip", "accountsHoldChip", "accountsProblemChip",
  "accountsRegistryStatus", "accountsVisibleCount", "accountsPagination",
  "accountsTableBody", "sidebarDot", "sidebarStatus", "sourceFooter", "subtitleText",
  "diagnosticsFixtureChart", "diagnosticsFixtureRecords", "diagnosticsHistoryDeferred",
  "diagnosticsRecordsDeferred", "diagnosticsHistoryModeChip", "diagnosticsRecordsModeChip",
  "accountDetailOverlay", "accountDetailBackdrop", "accountDetailDrawer", "accountDetailClose",
  "accountDetailMissing", "accountDetailTitle", "accountDetailSubtitle",
  "accountDetailStatusChip", "accountDetailPoolChip", "accountDetailHoldChip",
  "accountDetailTruthChip", "accountDetailId", "accountDetailLabel", "accountDetailPoolValue",
  "accountDetailLifecycle", "accountDetailHoldValue", "accountDetailEnabled",
  "accountDetailChecks24h", "accountDetailFail", "accountDetailLatency", "accountDetailRecovery",
  "accountDetailLastSuccess", "accountDetailError", "accountDetailCounterNote",
  "accountDetailTimeline", "accountDetailActions", "accountDetailDangerActions",
  "accountDetailLastCommandChip", "accountDetailLastCommandAction", "accountDetailLastCommandCode",
  "accountDetailLastCommandNext", "accountDetailLastCommandRefresh", "settingsLaunchAvailability"
]) {
  node(id);
}
node("refreshFixture").lastElementChild = { textContent: "" };
for (const id of ["accountDetailStatusChip", "accountDetailPoolChip", "accountDetailHoldChip", "accountDetailTruthChip", "accountDetailLastCommandChip", "diagnosticsHistoryModeChip", "diagnosticsRecordsModeChip"]) {
  node(id).lastElementChild = { textContent: "" };
}
node("accountDetailOverlay").hidden = true;

const desktop = new Node();
desktop.dataset = { screen: "accounts", source: "live" };
allNodes.push(desktop);

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) { return node(id); },
    createElement(tag) {
      const created = new Node(tag);
      allNodes.push(created);
      return created;
    },
    addEventListener() {},
    querySelector(selector) {
      if (selector === ".desktop") {
        return desktop;
      }
      return null;
    },
    querySelectorAll(selector) {
      if (selector.includes(".account-action")) {
        return allNodes.filter((item) => item.classList?.contains("account-action"));
      }
      return [];
    }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=accounts&source=live" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);
sandbox.actionMetadata = {
  validate_account: { available: true },
  demote_account: { available: true },
  hold_account: { available: true },
  retire_account: { available: true }
};

const snapshot = {
  schema_version: 1,
  status: "ok",
  source: "accounts_readonly",
  registry_identity: { status: "ok", machine_error_code: "OK", next_action: "none" },
  summary: {
    active: 1,
    reserve: 0,
    retired: 0,
    hold: 0,
    problem: 0,
    visible_count: 1,
    human_message: "Accounts listed.",
    machine_error_code: "OK"
  },
  accounts: [{
    id: "backend-a",
    label: "operator@example.com",
    pool: "active",
    pool_label: "Активные",
    status: "healthy",
    status_label: "Работает",
    visual_state: "green",
    manual_hold: false,
    enabled: true,
    fail_count: 0,
    success_count: 3,
    last_success: "Сегодня, 12:00",
    last_error_summary: "",
    cooldown_until: "",
    notes_summary: "snapshot note"
  }]
};

sandbox.renderAccountsSnapshot(snapshot);
sandbox.openAccountDrawer("backend-a");
if (node("accountDetailOverlay").hidden) {
  throw new Error("drawer should open");
}
if (node("accountDetailId").textContent !== "backend-a") {
  throw new Error(`drawer did not render selected account id: ${node("accountDetailId").textContent}`);
}
if (!node("accountDetailSubtitle").textContent.includes("ope***@***.com")) {
  throw new Error(`drawer label was not redacted: ${node("accountDetailSubtitle").textContent}`);
}
if (node("accountDetailLifecycle").textContent !== "available") {
  throw new Error(`drawer did not derive bounded lifecycle: ${node("accountDetailLifecycle").textContent}`);
}
if (node("accountDetailChecks24h").textContent !== "3") {
  throw new Error(`drawer did not render bounded checks: ${node("accountDetailChecks24h").textContent}`);
}
if (!node("accountDetailTimeline").children.length) {
  throw new Error("drawer timeline should render bounded fixture/check summary");
}
const actionButtons = node("accountDetailActions").children.filter((child) => child.dataset?.accountId === "backend-a");
if (!actionButtons.length || actionButtons.some((child) => child.dataset.uiAction === undefined)) {
  throw new Error("drawer did not reuse bounded account action buttons");
}
const disabledRoutine = node("accountDetailActions").children.filter((child) => child.disabled);
if (!disabledRoutine.length) {
  throw new Error("drawer should show disabled routine actions with reasons");
}
const dangerButtons = node("accountDetailDangerActions").children.filter((child) => child.dataset?.uiAction === "retire_account");
if (dangerButtons.length !== 1 || dangerButtons[0].dataset.accountId !== "backend-a") {
  throw new Error("drawer did not isolate retire action in danger zone");
}

sandbox.renderAccountsSnapshot({
  ...snapshot,
  accounts: [{
    ...snapshot.accounts[0],
    last_error_summary: "/Users/kirill/.codex auth_token=SECRET123",
    timeline: [{
      at: "/Volumes/Work/private-state.json",
      message: "secret=VERYSECRET path=/tmp/private-state.json",
      visual_state: "red"
    }]
  }]
});
sandbox.openAccountDrawer("backend-a");
function collectText(item) {
  if (!item) {
    return "";
  }
  return [
    item.textContent || "",
    ...((item.children || []).map((child) => collectText(child)))
  ].join(" ");
}
const sensitiveDrawerText = [
  collectText(node("accountDetailError")),
  collectText(node("accountDetailTimeline"))
].join(" ");
if (sensitiveDrawerText.includes("/Users/") || sensitiveDrawerText.includes("/Volumes/") || sensitiveDrawerText.includes("/tmp/private-state") || sensitiveDrawerText.includes("SECRET123") || sensitiveDrawerText.includes("VERYSECRET")) {
  throw new Error(`drawer leaked sensitive account text: ${sensitiveDrawerText}`);
}

sandbox.renderAccountsSnapshot({ ...snapshot, accounts: [], summary: { ...snapshot.summary, visible_count: 0 } });
if (node("accountDetailMissing").hidden) {
  throw new Error("missing account state should be visible after refresh");
}
if (node("accountDetailLabel").textContent !== "account_missing_after_refresh") {
  throw new Error("missing state did not replace stale account values");
}
if (!node("accountDetailActions").children[0].disabled) {
  throw new Error("missing account state should disable lifecycle actions");
}
if (!node("accountDetailDangerActions").children[0].disabled) {
  throw new Error("missing account state should disable danger actions");
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

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
        self.assertIn("routeValidationChip", js)
        self.assertIn("routeSecretRef", js)
        self.assertIn("routeDisabledMenuButton", js)
        self.assertIn("apiRouteRemoveDisabledReason", js)
        self.assertIn("isApiRouteActionDeferredInReadonlyRegistry", js)
        self.assertIn("apiRouteStateRequirement", js)
        self.assertIn('maybeConfirmAndRun(uiAction, { route_id: button.dataset.routeId })', js)

        api_screen = self._section_html(html, "apiConnectionsScreen")
        self.assertIn('data-api-connections-mode="readonly-registry"', api_screen)
        self.assertIn('data-api-registry-surface="readonly-list"', api_screen)
        self.assertIn('data-api-builder-mode="deferred"', api_screen)
        self.assertIn("Маршруты недоступны", js)
        self.assertIn("Демо-режим. Маршруты показаны как bounded fixture view", api_screen + js)
        self.assertIn("Live-readonly маршруты недоступны", js)
        self.assertIn("Создание маршрута", api_screen)
        self.assertIn("Черновик маршрута", api_screen)
        self.assertIn("Registry enabled", api_screen)
        self.assertIn("<th>Registry</th>", api_screen)
        self.assertIn("<th>Validation</th>", api_screen)
        self.assertIn("enabled", api_screen + js)
        self.assertIn("disabled", api_screen + js)
        self.assertIn("not checked", js)
        self.assertIn("blocked by secret", js)
        self.assertIn("Secret ref", api_screen)
        self.assertIn("OPENROUTER_PRIMARY", js)
        self.assertIn("available", js)
        self.assertIn("missing", js)
        self.assertIn("Пакет профиля", js)
        self.assertIn("Свидетельство", js)
        self.assertIn("UI не читает evidence file", js)
        self.assertNotIn('data-ui-action=', api_screen)
        self.assertNotIn("<textarea", api_screen)
        self.assertNotIn("<input", api_screen)
        self.assertNotIn("<select", api_screen)
        self.assertNotIn('type="file"', api_screen)
        self.assertNotIn("raw_route_json", api_screen + js)
        self.assertNotIn("route_config", api_screen + js)
        self.assertNotIn("endpoint_path", api_screen + js)
        self.assertNotIn("base_url", api_screen + js)
        self.assertNotIn("api_route_create", api_screen + js)
        self.assertNotIn("api_route_update", api_screen + js)
        self.assertNotIn("api_route_draft", api_screen + js)
        self.assertNotIn('routeActionButton(route, "api_route_allow"', js)
        self.assertNotIn('routeActionButton(route, "api_route_disable"', js)
        self.assertIn('routeActionButton(route, "api_route_remove", "Удалить route"', js)
        self.assertNotIn('routeActionButton(route, "api_route_profile"', js)
        self.assertNotIn('routeActionButton(route, "api_route_evidence_capture"', js)
        self.assertNotIn("Вкл", api_screen + js)
        self.assertNotIn("Сделать активным", api_screen + js)
        self.assertNotIn("Подключить Codex", api_screen + js)
        self.assertNotIn("Профиль готов", api_screen + js)
        self.assertNotIn("Основной", api_screen)
        self.assertNotIn("Непрерывный поток", api_screen + js)
        self.assertNotIn("Сетка", api_screen + js)
        self.assertNotIn("primary route", api_screen + js)
        self.assertNotIn("failover", api_screen + js)
        self.assertNotIn("provider healthy", api_screen + js)
        self.assertNotIn("token valid", api_screen + js)
        self.assertNotIn("config saved", api_screen + js)
        self.assertIn('id="onboardOverlay"', html)
        self.assertIn('id="runOnboardAction"', html)
        self.assertIn('id="actionOnboardingOutcome"', html)
        self.assertIn('id="actionOnboardingReserveProof"', html)
        self.assertIn('id="actionOnboardingBackend"', html)
        self.assertIn('id="onboardingResultFlow"', html)
        self.assertIn('id="onboardingResultBanner"', html)
        self.assertIn('id="onboardingResultNewIds"', html)
        self.assertIn('id="onboardingResultSelected"', html)
        self.assertIn('id="onboardingResultReserveChip"', html)
        self.assertIn('id="onboardingResultNextAction"', html)
        self.assertIn("Итог onboarding", html)
        self.assertIn("Аккаунт добавлен в резерв", js)
        self.assertIn('class="onboard-stepper"', html)
        self.assertIn('class="onboard-source-card"', html)
        self.assertIn('id="onboardingResultStatusProofChip"', html)
        self.assertIn('id="onboardingResultPoolChip"', html)
        self.assertIn("hold_account", js)
        self.assertIn("release_account", js)
        self.assertIn("account_id", js)
        self.assertIn("route_id", js)
        self.assertIn('maybeConfirmAndRun(uiAction, { account_id: button.dataset.accountId })', js)
        self.assertIn('maybeConfirmAndRun("onboard_account")', js)
        self.assertIn(".live-action, .account-action, .onboard-action, .api-route-action", js)
        self.assertIn("только сначала в резерв", html)
        self.assertIn("no-new-auth и ambiguous identity требуют действия оператора", html)
        self.assertIn("не доказывает включение в рабочий поток", html)
        self.assertIn("терминальный вывод из lifecycle", js)
        self.assertIn("accountActionButtons", js)
        self.assertIn("Маршрут отключён. Это действие доступно только для разрешённых маршрутов.", js)
        self.assertIn("Маршрут уже разрешён. Это действие доступно только для отключённых маршрутов.", js)
        self.assertIn("Это действие маршрута отложено", js)
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
        self.assertIn('id="diagnosticsExportAction" class="button live-action diagnostics-only"', html)
        self.assertIn('id="diagnosticsFullCheckAction" class="button diagnostics-only diagnostics-blocked-action"', html)
        self.assertIn("Полная проверка требует отдельной admitted command surface", html)
        self.assertIn('data-ui-action="export_diagnostics"', html)
        self.assertIn("Диагностический пакет поддержки", html + js)
        self.assertIn("Истина о здоровье runtime не изменялась", js)
        self.assertIn("только метаданные:", js)
        self.assertIn("const data = result.data || {}", js)
        self.assertIn("actionVisualClass", js)
        self.assertIn('payload.action_role === "support_artifact"', js)
        self.assertIn("Пакет поддержки", html)
        self.assertIn('data-diagnostics-region="history_chart_slot"', html)
        self.assertIn('data-diagnostics-region="latest_records"', html)
        self.assertIn('data-diagnostics-mode="fixture-demo"', html)
        self.assertIn('data-fixture-only="true"', html)
        self.assertIn('data-live-state="deferred"', html)
        self.assertIn("bounded history view", html)
        self.assertIn('class="diagnostics-line-chart"', html)
        self.assertIn('class="telemetry-scale"', html)
        self.assertIn('class="tick failure"', html)
        self.assertIn('class="tick success"', html)
        self.assertEqual(html.count('class="tick '), 100)
        self.assertIn("failures", html)
        self.assertIn("stale", html)
        self.assertIn("no data", html)
        self.assertIn("Live-история появится только после bounded redacted JSON command surface", html)
        self.assertIn("Live-записи не выводятся из журнального потока", html)
        self.assertIn("updateDiagnosticsDetailSource", js)
        self.assertIn('node.hidden = !fixtureOnly', js)
        self.assertIn('node.hidden = fixtureOnly', js)
        self.assertIn(".diagnostics-fixture-chart[hidden]", css := (WEB_DESIGN_UI / "styles" / "overview.css").read_text())
        self.assertIn(".fixture-banner.blue", css)
        self.assertIn(".diagnostics-line-chart", css)
        self.assertIn("grid-template-columns: repeat(48", css)
        self.assertIn(".diagnostics-detail-stack", css)
        self.assertIn(".diagnostics-support-meta", css)
        self.assertIn(".diagnostics-deferred-state[hidden]", css)
        self.assertNotIn("runtime summary", (html + js).lower())
        self.assertIn("missing command surface", html)
        self.assertIn("human-open deferred", html)
        self.assertNotIn("Ссылка на артефакт", html)
        self.assertIn(
            'const SCREENS = ["quick-start", "overview", "accounts", "api-connections", "diagnostics", "settings", "setup", "select-client", "import-existing"]',
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
        diagnostics_markup = html.split('id="diagnosticsScreen"', 1)[1].split('id="settingsScreen"', 1)[0]
        self.assertEqual(diagnostics_markup.count('data-ui-action="export_diagnostics"'), 0)
        self.assertNotIn('data-ui-action="stable_repair_apply"', diagnostics_markup)
        self.assertNotIn('data-ui-action="promote_account"', diagnostics_markup)
        self.assertNotIn('data-ui-action="demote_account"', diagnostics_markup)
        self.assertNotIn('data-ui-action="hold_account"', diagnostics_markup)
        self.assertNotIn('data-ui-action="release_account"', diagnostics_markup)
        self.assertNotIn('data-ui-action="retire_account"', diagnostics_markup)

    def test_diagnostics_detail_switches_fixture_visuals_and_live_deferred_state(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

function node(id) {
  return {
    id,
    hidden: false,
    className: "",
    lastElementChild: { textContent: "" }
  };
}

const nodes = {
  diagnosticsFixtureChart: node("diagnosticsFixtureChart"),
  diagnosticsFixtureRecords: node("diagnosticsFixtureRecords"),
  diagnosticsHistoryDeferred: node("diagnosticsHistoryDeferred"),
  diagnosticsRecordsDeferred: node("diagnosticsRecordsDeferred"),
  diagnosticsHistoryModeChip: node("diagnosticsHistoryModeChip"),
  diagnosticsRecordsModeChip: node("diagnosticsRecordsModeChip")
};

const sandbox = {
  console,
  Node: function Node() {},
  document: {
    getElementById(id) {
      return nodes[id] || { textContent: "", className: "", lastElementChild: { textContent: "" } };
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "diagnostics", source: "fixture" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=diagnostics" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

sandbox.updateDiagnosticsDetailSource("fixture");
if (nodes.diagnosticsFixtureChart.hidden || nodes.diagnosticsFixtureRecords.hidden) {
  throw new Error("fixture diagnostics visuals should be visible in fixture source");
}
if (!nodes.diagnosticsHistoryDeferred.hidden || !nodes.diagnosticsRecordsDeferred.hidden) {
  throw new Error("deferred live states should be hidden in fixture source");
}
if (nodes.diagnosticsHistoryModeChip.lastElementChild.textContent !== "fixture/demo") {
  throw new Error("fixture chip was not marked fixture/demo");
}

sandbox.updateDiagnosticsDetailSource("live");
if (!nodes.diagnosticsFixtureChart.hidden || !nodes.diagnosticsFixtureRecords.hidden) {
  throw new Error("fixture diagnostics visuals should be hidden in live source");
}
if (nodes.diagnosticsHistoryDeferred.hidden || nodes.diagnosticsRecordsDeferred.hidden) {
  throw new Error("deferred live states should be visible in live source");
}
if (nodes.diagnosticsRecordsModeChip.lastElementChild.textContent !== "deferred") {
  throw new Error("live chip was not marked deferred");
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_settings_screen_is_readonly_with_safe_actions_and_deferred_controls(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        settings_markup = html.split('<section id="settingsScreen"', 1)[1].split('<section id="setupScreen"', 1)[0]

        self.assertIn('data-screen-link="settings"', html)
        self.assertIn('id="settingsScreen"', html)
        self.assertIn('data-visual-reference="14_settings_main_hub"', settings_markup)
        self.assertIn('data-config-mode="readonly"', settings_markup)
        self.assertIn('data-settings-subscreen-mode="hub-only"', settings_markup)
        for section in [
            "runtime-mode",
            "client-launch",
            "accounts-policy",
            "api-routes",
            "diagnostics-privacy",
            "security-boundary",
            "advanced-boundary",
            "about",
            "data-installer",
        ]:
            self.assertIn(f'data-settings-section="{section}"', settings_markup)
        self.assertEqual(settings_markup.count('data-settings-card="true"'), 9)
        self.assertIn("Runtime / Mode", settings_markup)
        self.assertIn("Client / Launch", settings_markup)
        self.assertIn("Accounts Policy", settings_markup)
        self.assertIn("API Routes", settings_markup)
        self.assertIn("Diagnostics / Privacy", settings_markup)
        self.assertIn("Security", settings_markup)
        self.assertIn("Advanced", settings_markup)
        self.assertIn("About", settings_markup)
        self.assertIn("Data / Installer", settings_markup)
        self.assertIn("Wild Boar Proxy", settings_markup)
        self.assertIn("AGPL-3.0-or-later", settings_markup)
        self.assertIn("Readonly metadata, not release proof.", settings_markup)
        self.assertIn("local control layer", settings_markup)
        self.assertIn("web design preview", settings_markup)
        self.assertIn("not packaged", settings_markup)
        self.assertIn("local preview not published", settings_markup)
        self.assertIn("not exposed to browser UI", settings_markup)
        self.assertIn("CLIProxyAPI boundary", settings_markup)
        self.assertIn("desktop owner-gated", settings_markup)
        self.assertIn("readonly metadata", settings_markup)
        self.assertIn("About does not read runtime state, git metadata, or package metadata.", settings_markup)
        self.assertIn("Демо-режим настроек", settings_markup + js)
        self.assertIn("admitted layout, не runtime config truth", settings_markup + js)
        self.assertIn("Live-readonly настройки недоступны", js)
        self.assertIn("saved state", js)
        self.assertIn("наблюдается, не редактируется", js)
        self.assertIn("renderSettingsSnapshot", js)
        self.assertIn("updateSettingsActionMetadata", js)
        self.assertIn("missing surface", settings_markup)
        self.assertIn("manual picker deferred", settings_markup)
        self.assertIn("owner approval", settings_markup)
        self.assertIn("support artifact", settings_markup)
        self.assertIn("display deferred", settings_markup)
        self.assertIn("separate packet", settings_markup)
        self.assertIn("protected", settings_markup)
        self.assertIn("admitted", settings_markup)
        self.assertIn('data-screen-link="api-connections"', settings_markup)
        self.assertIn('data-screen-link="diagnostics"', settings_markup)
        self.assertNotIn("Безопасные доступные действия", settings_markup)
        self.assertNotIn("Отложенные элементы настроек", settings_markup)
        self.assertNotIn("Save settings", settings_markup)
        self.assertNotIn("Cancel settings", settings_markup)
        self.assertNotIn("Save", settings_markup)
        self.assertNotIn("Apply", settings_markup)
        self.assertNotIn("Browse", settings_markup)
        self.assertNotIn("Open installer", settings_markup)
        self.assertNotIn("Install now", settings_markup)
        self.assertNotIn("Сохранить", settings_markup)
        self.assertNotIn("Отмена", settings_markup)
        self.assertNotIn("Finder", settings_markup)
        self.assertNotIn('data-ui-action=', settings_markup)
        self.assertNotIn("live-action", settings_markup)
        self.assertNotIn("account-action", settings_markup)
        self.assertNotIn("onboard-action", settings_markup)
        self.assertNotIn("api-route-action", settings_markup)
        self.assertNotIn("<svg", settings_markup)
        self.assertNotIn("<input", settings_markup)
        self.assertNotIn("<textarea", settings_markup)
        self.assertNotIn("<select", settings_markup)
        self.assertNotIn('type="file"', settings_markup)
        self.assertNotIn('contenteditable="true"', settings_markup)
        self.assertNotIn('data-ui-action="stable_repair_apply"', settings_markup)
        self.assertNotIn("installer_init", settings_markup + js)
        self.assertNotIn("save_selection", settings_markup + js)
        self.assertNotIn("import_apply", settings_markup + js)
        self.assertNotIn("showOpenFilePicker", settings_markup + js)
        self.assertNotIn("webkitdirectory", settings_markup + js)
        self.assertNotIn("readAsText", settings_markup + js)
        self.assertNotIn("localStorage", settings_markup + js)
        self.assertNotIn("window.open", settings_markup + js)
        self.assertNotIn("policy_stage", html + js)
        self.assertNotIn("rollout stage", html + js)
        self.assertNotIn("JSON.stringify({ command_id", js)
        self.assertNotIn("client_path", settings_markup)
        self.assertNotIn("source_dir", settings_markup)
        self.assertNotIn("data_dir", settings_markup)
        self.assertNotIn("secret_ref", settings_markup)
        self.assertNotIn("base_url", settings_markup)
        self.assertNotIn("endpoint_path", settings_markup)
        self.assertNotIn("api_route_create", settings_markup)
        self.assertNotIn("api_route_update", settings_markup)
        self.assertNotIn("config.toml", settings_markup)
        self.assertNotIn("state.json", settings_markup)
        self.assertNotIn("supervisor-state", settings_markup)
        self.assertNotIn("routes.json", settings_markup)
        self.assertNotIn("secrets.env", settings_markup)
        self.assertNotIn("installer init", settings_markup.lower())
        self.assertNotIn("settings ready", settings_markup.lower() + js.lower())
        self.assertNotIn("token value", settings_markup.lower())
        self.assertNotIn("password value", settings_markup.lower())
        self.assertNotIn("saved successfully", settings_markup.lower() + js.lower())
        self.assertNotIn("settings saved", settings_markup.lower() + js.lower())
        for forbidden_claim in [
            "verified package",
            "package verified",
            "release ready",
            "desktop ready",
            "runtime version confirmed",
            "installed version",
            "update available",
            "all dependencies compliant",
            "third-party notices complete",
            "license audit passed",
            "packaging contents verified",
            "production ready",
            "release build",
            "certified",
            "support available",
            "shipped app",
            "stable release",
            "cliproxyapi licensed as our product",
            "git rev-parse",
            "api/about",
            "api/version",
        ]:
            self.assertNotIn(forbidden_claim, settings_markup.lower())
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        self.assertIn(".settings-layout", css)
        self.assertIn(".settings-hub", css)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", css)
        self.assertIn("min-height: 144px", css)
        self.assertNotIn("min-height: 216px", css)
        self.assertIn(".settings-card-head", css)
        self.assertIn(".settings-card-icon", css)
        self.assertIn(".settings-card-facts", css)
        self.assertIn(".settings-hidden-field", css)

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
        self.assertIn('data-setup-mode="admission-wizard"', html)
        self.assertIn('data-setup-flow-frame="left-step-rail"', html)
        self.assertIn('data-visual-reference="10_first_run_setup_wizard"', html)
        self.assertIn('data-visual-reference="11_select_client_screen"', html)
        self.assertIn('data-visual-reference="12_import_existing_wizard"', html)
        self.assertIn("setup-flow-rail", html)
        self.assertIn("setup-bottom-bar", html)
        self.assertIn("Настройка Wild Boar Proxy", js)
        self.assertIn("Безопасная подготовка локального контура без изменения рабочих файлов Codex.", html + js)
        self.assertIn("Live-readonly setup недоступен. Предыдущие fixture-данные не используются.", js)
        self.assertIn("Экран показывает setup preview, не результат настройки.", html + js)
        self.assertIn("setup preview, не результат настройки", js)
        self.assertIn("Первичная настройка", html)
        self.assertIn("Готовность локального контура", html)
        self.assertIn("admission state", html)
        self.assertIn("Codex client candidate", html)
        self.assertIn("Manual picker", html)
        self.assertIn("Data directory", html)
        self.assertIn("Проверка", html)
        self.assertIn("Runtime status", html)
        self.assertIn("Client surface", html)
        self.assertIn("Accounts pool", html)
        self.assertIn("Diagnostics export", html)
        self.assertIn("Desktop bridge", html)
        self.assertIn("Setup proof", html)
        self.assertNotIn("Setup complete", html)
        self.assertIn("no browser path", html)
        self.assertIn("command surface missing", html)
        self.assertIn("future desktop/native flow", html)
        self.assertIn("owner-gated", html)
        self.assertIn("Продолжить · requires proof", html)
        self.assertIn("Проверить готовность · missing surface", html)
        self.assertIn("setup proof packet", html)
        self.assertIn("Закрыть", html)
        self.assertIn("source_id не заявляется", html)
        self.assertIn('data-select-client-mode="candidate-preview"', html)
        self.assertIn("Демо-режим. Кандидаты показаны как fixture preview", html)
        self.assertIn("Выберите локальный клиент Codex из безопасно предоставленных кандидатов.", js)
        self.assertIn("Список клиентов недоступен. Ручной выбор ожидает desktop/native flow.", js)
        self.assertIn("Клиент", html)
        self.assertIn("candidate preview", html)
        self.assertIn("Поиск по кандидату · local filter only", html)
        self.assertIn("source: fixture candidate display", html)
        self.assertIn("Предпросмотр выбора", html)
        self.assertIn("Preview не является saved selection или runtime readiness.", html)
        self.assertIn("browser path payload forbidden", html)
        self.assertIn("Выбрать кандидата · disabled", html)
        self.assertIn("Проверить кандидатов · missing surface", html)
        self.assertIn("Сохранить выбор · requires candidate proof", html)
        self.assertIn("inert display only", html)
        self.assertIn("not claimed here", html)
        self.assertIn("нужен немутационный dry-run пакет импорта", html)
        self.assertIn("нет медиации исходного расположения и сильного подтверждения", html)
        self.assertIn("существующая установка здесь не обнаружена", html)
        self.assertIn("Dry-run preview", html)
        self.assertIn("Rollback packet", html)

        for screen_id in ["setupScreen", "selectClientScreen", "importExistingScreen"]:
            section = self._section_html(html, screen_id)
            self.assertNotIn("data-ui-action", section)
            self.assertNotIn("live-action", section)
            self.assertNotIn('type="file"', section)
            self.assertNotIn("<input", section)
            self.assertNotIn("<select", section)
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
        setup_section = self._section_html(html, "setupScreen")
        self.assertIn('src="assets/icons/phosphor/shield-check.png"', setup_section)
        self.assertIn('src="assets/icons/phosphor/sliders-horizontal.png"', setup_section)
        self.assertIn('src="assets/icons/phosphor/squares-four.png"', setup_section)
        self.assertNotIn('src="assets/icons/phosphor/x-circle.png"', setup_section)
        self.assertNotIn("setup-component-icon red", setup_section)
        self.assertNotIn("setup-card-icon red", setup_section)
        self.assertNotIn("chip red", setup_section)
        self.assertNotIn("<svg", setup_section.lower())
        for forbidden in (
            "Установка завершена",
            "Клиент найден",
            "Конфигурация сохранена",
            "найдено приложение",
            "production",
            "путь сохранён",
            "данные инициализированы",
        ):
            self.assertNotIn(forbidden, setup_section + js)
        self.assertNotIn('class="button primary small">Продолжить', setup_section)
        self.assertNotIn('class="button primary small disabled" type="button" disabled title="Continue requires setup proof packet.">Продолжить', setup_section)
        self.assertRegex(
            setup_section,
            r'<button class="button small disabled setup-continue-disabled"[^>]*disabled[^>]*>Продолжить · requires proof</button>',
        )
        select_client_section = self._section_html(html, "selectClientScreen")
        self.assertIn('src="assets/icons/phosphor/magnifying-glass.png"', select_client_section)
        self.assertIn('src="assets/icons/phosphor/shield-check.png"', select_client_section)
        self.assertIn('src="assets/icons/phosphor/x-circle.png"', select_client_section)
        self.assertNotIn("<svg", select_client_section.lower())
        self.assertNotIn("Поиск по имени или пути", select_client_section)
        self.assertNotIn("Поиск по пути", select_client_section)
        self.assertNotIn('class="button primary small">Сохранить', select_client_section)
        self.assertNotIn('class="button primary small disabled"', select_client_section)
        self.assertRegex(
            select_client_section,
            r'<button class="button small disabled setup-save-disabled"[^>]*disabled[^>]*>Сохранить выбор · requires candidate proof</button>',
        )
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()
        self.assertIn(".setup-flow-layout", css)
        self.assertIn("grid-template-columns: 276px minmax(0, 1fr)", css)
        self.assertIn(".setup-flow-rail", css)
        self.assertIn(".setup-bottom-bar", css)
        self.assertIn(".setup-card-head", css)
        self.assertIn(".setup-card-icon", css)
        self.assertIn(".setup-readiness-card", css)
        self.assertIn("grid-template-columns: repeat(4, minmax(0, 1fr))", css)
        self.assertIn(".setup-component-row", css)
        self.assertIn(".setup-boundary-grid", css)
        self.assertIn(".setup-action-reasons", css)
        self.assertIn(".select-client-candidate-row", css)
        self.assertIn(".candidate-path", css)
        self.assertIn(".select-client-detail-grid", css)
        self.assertIn(".import-phase-row", css)
        self.assertIn("padding: 24px", css)

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
        self.assertIn("boundedUiActionPayload(uiAction, extraPayload)", js)
        self.assertIn("body: JSON.stringify(requestPayload)", js)
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
        self.assertIn('id="confirmModal"', html)
        self.assertIn('data-modal-surface="action-command-request"', html)
        self.assertIn('data-modal-surface="onboard-reserve-request"', html)
        self.assertIn('class="confirm-boundary"', html)
        self.assertIn('class="modal-state-list"', html)
        self.assertIn("reserve-only success", html)
        self.assertIn("no-new-auth", html)
        self.assertIn("ambiguous identity", html)
        self.assertIn("автоповышения нет", html)
        self.assertIn("Не меняет другие routes и не утверждает runtime readiness.", js)
        self.assertIn("command request", html)
        self.assertIn("не runtime truth", html)
        self.assertIn("нужен JSON refresh", html)
        self.assertIn("confirmAction", html)
        self.assertIn("cancelAction", html)
        self.assertIn("confirmSeverity", html)
        self.assertIn("confirmPolicy", html)
        self.assertIn("confirmTruthWarning", html)
        self.assertIn("confirmDispatchState", html)
        self.assertIn("accountActionPreflight", html)
        self.assertIn("Account action summary", html)
        self.assertIn("Current pool", html)
        self.assertIn("Requested action", html)
        self.assertIn("Подтверждением результата остаётся command packet плюс canonical refresh.", html)
        self.assertIn("apiRouteRemovePreflight", html)
        self.assertIn("Route exists", html)
        self.assertIn("remove registry route", html)
        self.assertIn("Сервер повторно проверит disabled-state", html)
        self.assertIn("CONFIRMATION_POLICY", js)
        self.assertIn("CONSERVATIVE_CONFIRMATION_POLICY", js)
        self.assertIn("confirmationInFlight", js)
        self.assertIn("setConfirmationInFlight", js)
        self.assertIn("maybeConfirmAndRun", js)
        self.assertIn("metadata.confirmation_required", js)
        self.assertIn("confirmationPolicyFor(uiAction, metadata)", js)
        self.assertIn("confirmModal.dataset.confirmSeverity", js)
        self.assertIn("function closeConfirmation()", js)
        self.assertIn("if (confirmationInFlight)", js)
        self.assertIn("pendingConfirmedAction = null;", js)
        self.assertIn("runUiAction(pending.uiAction, pending.extraPayload);", js)
        self.assertIn("post_action_refresh_required", js)
        self.assertIn("setLiveReadonly(false)", js)
        self.assertIn("ACCOUNT_UI_ACTIONS", js)
        self.assertIn("renderAccountActionPreflight", js)
        self.assertIn("findAccountById", js)
        self.assertIn("confirmationReadyLabel", js)
        self.assertIn("renderApiRouteRemovePreflight", js)
        self.assertIn("apiRouteRemoveRefreshState", js)
        self.assertIn("apiRoutePresentInSnapshot", js)

    def test_static_confirmation_modal_matches_locked_visual_tokens(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()

        self.assertIn('class="confirm-modal onboard-modal"', html)
        self.assertIn('class="confirm-modal action-confirm-modal"', html)
        self.assertIn("padding: 40px;", css)
        self.assertIn("border-radius: 24px;", css)
        self.assertIn("padding: 32px;", css)
        self.assertIn("0 32px 96px rgba(30, 27, 24, .18)", css)
        self.assertIn("width: min(100%, 640px);", css)
        self.assertIn("width: min(100%, 680px);", css)
        self.assertIn(".confirm-modal-header", css)
        self.assertIn(".confirm-boundary", css)
        self.assertIn(".modal-state-list", css)
        self.assertIn(".modal-state-row", css)
        self.assertIn(".confirm-modal[data-confirm-severity=\"critical\"]::before", css)
        self.assertIn(".confirm-modal[data-confirm-severity=\"high\"]::before", css)
        self.assertIn(".confirm-modal[data-confirm-severity=\"medium\"]::before", css)
        self.assertIn("@media (max-width: 1120px)", css)
        self.assertIn(".confirm-actions .button", css)

    def test_action_ledger_normalizes_error_states_without_false_green(self) -> None:
        html = (WEB_DESIGN_UI / "index.html").read_text()
        js = (WEB_DESIGN_UI / "scripts" / "overview.js").read_text()
        css = (WEB_DESIGN_UI / "styles" / "overview.css").read_text()

        self.assertIn('id="actionDisplayState"', html)
        self.assertIn('id="actionTruthNote"', html)
        self.assertIn('id="actionSupportDetails"', html)
        self.assertIn('id="actionPanel" class="action-panel neutral compact-action-panel"', html)
        self.assertIn('id="actionDisplayChip"', html)
        self.assertIn('id="actionOpenLedgerAction"', html)
        self.assertIn('id="actionLedgerOverlay"', html)
        self.assertIn('id="actionLedgerPanel"', html)
        self.assertIn('id="actionLedgerList"', html)
        self.assertIn('id="actionLedgerScope"', html)
        self.assertIn("Текущая UI-сессия", html)
        self.assertIn("не сохраняется", html)
        self.assertIn("ACTION_STATUS_VISUAL_CLASS", js)
        self.assertIn("ACTION_LEDGER_LIMIT = 5", js)
        self.assertIn("let actionLedger = []", js)
        self.assertIn("let actionLedgerFilter = \"all\"", js)
        self.assertIn("let activeActionRequestKey = \"\"", js)
        self.assertIn("recordActionLedgerEntry", js)
        self.assertIn("renderActionLedger", js)
        self.assertIn("openActionLedgerPanel", js)
        self.assertIn("setActionLedgerFilter", js)
        self.assertIn("safeLedgerText", js)
        self.assertIn("row.open = false", js)
        self.assertIn("changedFilesCount", js)
        self.assertIn('duplicate_blocked: "neutral"', js)
        self.assertIn('ok_refresh_pending: "amber"', js)
        self.assertIn('ok_refresh_complete: "green"', js)
        self.assertIn('ok_refresh_failed: "amber"', js)
        self.assertIn('refresh_mismatch: "amber"', js)
        self.assertIn('command_error: "red"', js)
        self.assertIn('integration_failure: "red"', js)
        self.assertIn('invalid_json: "red"', js)
        self.assertIn('timeout: "amber"', js)
        self.assertIn('stale: "amber"', js)
        self.assertIn('unknown: "neutral"', js)
        self.assertIn("payload.status || result.status", js)
        self.assertIn("actionSupportDetails(payload)", js)
        self.assertIn("artifactReference(data.evidence_path)", js)
        self.assertIn('displayState = "ok_refresh_failed"', js)
        self.assertIn('displayState = "refresh_mismatch"', js)
        self.assertIn("canonical refresh failed", js)
        self.assertIn("canonical refresh mismatch", js)
        self.assertIn("UI_ACTION_INVALID_JSON", js)
        self.assertIn("UI_ACTION_TIMEOUT", js)
        self.assertIn("UI_DUPLICATE_SUBMIT_BLOCKED", js)
        self.assertIn("а не успех", js)
        self.assertIn(".action-ledger-panel", css)
        self.assertIn(".action-summary-head", css)
        self.assertIn(".action-panel.green", css)
        self.assertIn(".action-panel.blue", css)
        self.assertIn(".action-panel.amber", css)
        self.assertIn(".action-panel.red", css)
        self.assertIn(".action-panel.neutral", css)
        self.assertIn(".action-ledger-row.green", css)
        self.assertIn(".action-ledger-row.blue", css)
        self.assertIn(".action-ledger-row.amber", css)
        self.assertIn(".action-ledger-row.red", css)
        self.assertIn(".onboarding-result-flow", css)
        self.assertIn(".onboarding-result-banner.green", css)
        self.assertIn(".onboarding-state-row", css)

    def test_onboarding_result_flow_renders_reserve_first_without_active_claim(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.children = [];
    this.lastElementChild = { textContent: "" };
  }
  append(...items) {
    for (const item of items) {
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
}

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
  "actionOnboardingBackend",
  "actionLedgerList",
  "onboardingResultFlow",
  "onboardingResultModeChip",
  "onboardingResultTitle",
  "onboardingResultSummary",
  "onboardingResultSummaryNote",
  "onboardingResultBanner",
  "onboardingResultNewIds",
  "onboardingResultSelected",
  "onboardingResultSelectionChip",
  "onboardingResultPoolChip",
  "onboardingResultReserveChip",
  "onboardingResultValidateChip",
  "onboardingResultSyncChip",
  "onboardingResultStatusProofChip",
  "onboardingResultRefreshChip",
  "onboardingResultNextAction"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.onboardingResultModeChip.lastElementChild = { textContent: "" };

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "accounts", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=accounts" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

sandbox.setActionPanel({
  status: "ok",
  ui_action: "onboard_account",
  action_role: "account_onboarding",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK",
      human_message: "Onboarding owner packet emitted.",
      next_action: "none",
      changed_files: [],
      onboarding: {
        ui_state: "success",
      final_outcome: "reserve_only_success",
      selected_backend_id: "acct-new",
      new_backend_ids: ["acct-new"],
      reserve_first_proven: true,
      selection_status: "selected_unique_backend",
      pool_after_onboarding: "reserve",
      active_routing_changed: false,
      validate_outcome: "ok",
      sync_outcome: "ok",
      status_observed: { command_status: "ok" }
    }
  }
	}, "complete");

const serialized = JSON.stringify(elements);
if (elements.onboardingResultFlow.hidden !== false) {
  throw new Error("onboarding result flow must be visible for onboard_account");
}
if (elements.onboardingResultBanner.className !== "onboarding-result-banner green") {
  throw new Error(`success banner must be green: ${elements.onboardingResultBanner.className}`);
}
if (elements.actionPanel.className !== "action-panel compact-action-panel green") {
  throw new Error(`success panel must be green: ${elements.actionPanel.className}`);
}
if (!elements.onboardingResultBanner.textContent.includes("Аккаунт добавлен в резерв")) {
  throw new Error(`reserve-first success copy missing: ${elements.onboardingResultBanner.textContent}`);
}
if (elements.onboardingResultSelected.textContent !== "acct-new") {
  throw new Error(`safe selected backend id missing: ${elements.onboardingResultSelected.textContent}`);
}
if (elements.onboardingResultReserveChip.textContent !== "доказано") {
  throw new Error(`reserve proof chip missing: ${elements.onboardingResultReserveChip.textContent}`);
}
if (elements.onboardingResultStatusProofChip.textContent !== "confirmed") {
  throw new Error(`status proof chip missing: ${elements.onboardingResultStatusProofChip.textContent}`);
}
if (elements.onboardingResultPoolChip.textContent !== "Резерв") {
  throw new Error(`pool chip must show reserve: ${elements.onboardingResultPoolChip.textContent}`);
}
if (!elements.onboardingResultNextAction.textContent.includes("отдельным действием оператора")) {
  throw new Error(`next action must keep promotion separate: ${elements.onboardingResultNextAction.textContent}`);
}
if (serialized.includes("Аккаунт активен") || serialized.includes("Аккаунт продвинут")) {
  throw new Error(`onboarding result overclaimed active/promoted state: ${serialized}`);
}

sandbox.setActionPanel({
  status: "ok",
  ui_action: "onboard_account",
  action_role: "account_onboarding",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK_REFRESH_FAILED",
    human_message: "Onboarding owner packet emitted.",
    next_action: "refresh_accounts",
    changed_files: [],
    onboarding: {
      ui_state: "success",
      final_outcome: "reserve_only_success",
      selected_backend_id: "acct-refresh-failed",
      new_backend_ids: ["acct-refresh-failed"],
      reserve_first_proven: true,
      selection_status: "selected_unique_backend",
      pool_after_onboarding: "reserve",
      active_routing_changed: false,
      validate_outcome: "ok",
      sync_outcome: "ok",
      status_observed: { command_status: "ok" }
    }
  }
}, "failed");
if (elements.actionPanel.className === "action-panel compact-action-panel green") {
  throw new Error("refresh-failed onboarding must not keep outer panel green");
}
if (elements.actionDisplayState.textContent !== "ok_refresh_failed") {
  throw new Error(`refresh-failed onboarding must show ok_refresh_failed: ${elements.actionDisplayState.textContent}`);
}

sandbox.setActionPanel({
  status: "ok",
  ui_action: "onboard_account",
  action_role: "account_onboarding",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "Onboarding owner packet emitted.",
    next_action: "user_action",
    changed_files: [],
    onboarding: {
      ui_state: "needs_user_action",
      final_outcome: "no_new_auth_detected",
      selected_backend_id: "",
      reserve_first_proven: false,
      selection_status: "not_selected"
    }
  }
});
if (elements.onboardingResultBanner.className !== "onboarding-result-banner amber") {
  throw new Error(`needs_user_action must be amber: ${elements.onboardingResultBanner.className}`);
}
if (elements.actionPanel.className === "action-panel compact-action-panel green") {
  throw new Error("no-new-auth outer panel must not be green");
}
if (elements.onboardingResultSelected.textContent !== "-") {
  throw new Error("non-success onboarding must not show selected backend");
}
if (!elements.onboardingResultBanner.textContent.includes("не добавило аккаунт")) {
  throw new Error(`non-success copy must not be green: ${elements.onboardingResultBanner.textContent}`);
}

sandbox.setActionPanel({
  status: "ok",
  ui_action: "onboard_account",
  action_role: "account_onboarding",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "Onboarding owner packet emitted.",
    next_action: "operator_action",
    changed_files: [],
    onboarding: {
      ui_state: "needs_user_action",
      final_outcome: "ambiguous_new_auth_detection",
      selected_backend_id: "acct-hidden",
      reserve_first_proven: false,
      selection_status: "ambiguous"
    }
  }
});
if (elements.onboardingResultSelected.textContent !== "-") {
  throw new Error("ambiguous onboarding must hide selected backend");
}
if (!elements.onboardingResultBanner.textContent.includes("Требуется действие оператора")) {
  throw new Error(`ambiguous copy must require operator action: ${elements.onboardingResultBanner.textContent}`);
}
if (elements.actionPanel.className === "action-panel compact-action-panel green") {
  throw new Error("ambiguous outer panel must not be green");
}

sandbox.setActionPanel({
  status: "ok",
  ui_action: "onboard_account",
  action_role: "account_onboarding",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "Onboarding owner packet emitted.",
    next_action: "retry",
    changed_files: [],
    onboarding: {
      ui_state: "success",
      final_outcome: "reserve_only_success",
      selected_backend_id: "acct-leaky",
      new_backend_ids: ["acct-leaky"],
      reserve_first_proven: true,
      selection_status: "selected_unique_backend",
      pool_after_onboarding: "active",
      active_routing_changed: true,
      validate_outcome: "ok",
      sync_outcome: "ok",
      status_observed: { command_status: "ok" }
    }
  }
});
if (elements.onboardingResultBanner.className === "onboarding-result-banner green") {
  throw new Error("active routing change must not be rendered green");
}
if (elements.actionPanel.className === "action-panel compact-action-panel green") {
  throw new Error("active routing contradiction must not keep outer panel green");
}
if (elements.onboardingResultSelected.textContent !== "-") {
  throw new Error("selected backend must be hidden when reserve proof contradicts pool");
}

sandbox.setActionPanel({
  ui_action: "onboard_account",
  action_role: "integration_failure",
  post_action_refresh_required: false,
  result: {
    status: "invalid_json",
    machine_error_code: "UI_ACTION_INVALID_JSON",
    human_message: "invalid json",
    next_action: "retry",
    changed_files: []
  }
});
if (elements.onboardingResultBanner.className !== "onboarding-result-banner red") {
  throw new Error(`onboarding invalid_json banner must be red: ${elements.onboardingResultBanner.className}`);
}
if (elements.actionPanel.className !== "action-panel compact-action-panel red") {
  throw new Error(`onboarding invalid_json outer panel must be red: ${elements.actionPanel.className}`);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

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
const diagnosticsSupport = render({
  status: "ok",
  ui_action: "export_diagnostics",
  action_role: "support_artifact",
  post_action_refresh_required: false,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "diagnostics exported",
    next_action: "none",
    changed_files: ["/private/tmp/wbp-diagnostics-secret"],
    data: {
      bundle_path: "/private/tmp/wbp-diagnostics-secret"
    }
  }
});

if (commandError.panel !== "action-panel compact-action-panel red" || commandError.status !== "command_error") {
  throw new Error(`command_error not red: ${JSON.stringify(commandError)}`);
}
if (invalidJson.panel !== "action-panel compact-action-panel red" || invalidJson.display !== "invalid_json") {
  throw new Error(`invalid_json not red: ${JSON.stringify(invalidJson)}`);
}
if (staleRefresh.panel !== "action-panel compact-action-panel amber" || staleRefresh.display !== "ok_refresh_failed") {
  throw new Error(`failed refresh not refresh-failed amber: ${JSON.stringify(staleRefresh)}`);
}
if (!profileSupport.support.includes("writes_external_config=false") || !profileSupport.support.includes("runtime_claim_blocked=true")) {
  throw new Error(`profile support packet details missing: ${JSON.stringify(profileSupport)}`);
}
if (!evidenceSupport.support.includes("wbp-deepseek-v3.json") || evidenceSupport.support.includes("/tmp/wbp-evidence/")) {
  throw new Error(`evidence support should show only artifact basename metadata: ${JSON.stringify(evidenceSupport)}`);
}
if (diagnosticsSupport.panel !== "action-panel compact-action-panel amber" || diagnosticsSupport.display !== "redaction_unreported") {
  throw new Error(`diagnostics support artifact without redaction proof should be amber, not runtime green: ${JSON.stringify(diagnosticsSupport)}`);
}
if (!diagnosticsSupport.support.includes("wbp-diagnostics-secret") || diagnosticsSupport.support.includes("/private/tmp/")) {
  throw new Error(`diagnostics support should show only artifact basename metadata: ${JSON.stringify(diagnosticsSupport)}`);
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

    def test_action_ledger_blocks_duplicate_dispatch_in_ui_session(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.dataset = {};
    this.classList = {
      contains: () => false,
      toggle: () => {},
      add: () => {},
      remove: () => {}
    };
  }
  append(...items) {
    for (const item of items) {
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
}

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
  "actionOnboardingBackend",
  "actionDisplayChip",
  "actionSummaryTitle",
  "actionSummaryMeta",
  "actionSummaryMessage",
  "actionSummaryTarget",
  "actionSummaryRefresh",
  "actionLedgerList"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
let fetchCount = 0;
let resolveFetch;
const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "accounts", source: "live" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?source=live&screen=accounts" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() {
    fetchCount += 1;
    return new Promise((resolve) => {
      resolveFetch = () => resolve({
        ok: true,
        json: async () => ({
          status: "ok",
          ui_action: "validate_account",
          account_id: "acc-021",
          action_role: "account_lifecycle",
          post_action_refresh_required: false,
          result: {
            status: "ok",
            machine_error_code: "OK",
            human_message: "validated",
            next_action: "none",
            changed_files: []
          }
        })
      });
    });
  }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

(async () => {
  const first = sandbox.runUiAction("validate_account", { account_id: "acc-021" });
  const second = sandbox.runUiAction("validate_account", { account_id: "acc-021" });
  if (fetchCount !== 1) {
    throw new Error(`duplicate dispatch should not call fetch twice: ${fetchCount}`);
  }
  if (elements.actionDisplayState.textContent !== "duplicate_blocked") {
    throw new Error(`duplicate should render duplicate_blocked: ${elements.actionDisplayState.textContent}`);
  }
  if (!JSON.stringify(elements.actionLedgerList).includes("UI_DUPLICATE_SUBMIT_BLOCKED")) {
    throw new Error(`duplicate ledger entry missing: ${JSON.stringify(elements.actionLedgerList)}`);
  }
  resolveFetch();
  await Promise.all([first, second]);
  if (fetchCount !== 1) {
    throw new Error(`duplicate dispatch leaked after resolve: ${fetchCount}`);
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=WEB_DESIGN_UI,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_diagnostics_export_result_renders_safe_artifact_metadata(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.className = "";
    this.textContent = "";
    this.lastElementChild = { textContent: "" };
  }
  append(...items) {
    for (const item of items) {
      if (!item) {
        continue;
      }
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
}

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
  "actionOnboardingBackend",
  "actionLedgerList",
  "diagnosticsStatusChip",
  "diagnosticsMessage",
  "diagnosticsPacketStatus",
  "diagnosticsExitCode",
  "diagnosticsMachineCode",
  "diagnosticsNextAction",
  "diagnosticsChangedFiles",
  "diagnosticsBundleRef",
  "diagnosticsBanner"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.diagnosticsStatusChip.lastElementChild = { textContent: "" };

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "diagnostics", source: "fixture" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=diagnostics" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

sandbox.setActionPanel({
  status: "ok",
  ui_action: "export_diagnostics",
  action_role: "support_artifact",
  mutates_runtime: false,
  affects_primary_truth: false,
  post_action_refresh_required: false,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "Diagnostics exported.",
    exit_code: 0,
    next_action: "none",
    changed_files: ["/private/tmp/wild-boar-proxy-diagnostics-secret"],
    data: {
      bundle_path: "/private/tmp/wild-boar-proxy-diagnostics-secret"
    }
  }
});

const domText = JSON.stringify(elements);
if (elements.diagnosticsStatusChip.className !== "chip amber") {
  throw new Error(`diagnostics status chip must be amber when redaction is unreported: ${elements.diagnosticsStatusChip.className}`);
}
if (elements.diagnosticsBanner.className !== "fixture-banner amber") {
  throw new Error(`diagnostics banner must be amber when redaction is unreported: ${elements.diagnosticsBanner.className}`);
}
if (elements.actionPanel.className !== "action-panel compact-action-panel amber") {
  throw new Error(`action panel must be amber when redaction is unreported: ${elements.actionPanel.className}`);
}
if (elements.diagnosticsChangedFiles.textContent !== "1") {
  throw new Error(`changed_files should render count only: ${elements.diagnosticsChangedFiles.textContent}`);
}
if (!elements.diagnosticsBundleRef.textContent.includes("wild-boar-proxy-diagnostics-secret")) {
  throw new Error(`artifact basename missing: ${elements.diagnosticsBundleRef.textContent}`);
}
if (elements.diagnosticsBundleRef.textContent.includes("/private/tmp/") || domText.includes("/private/tmp/")) {
  throw new Error(`diagnostics DOM leaked full local path: ${domText}`);
}
if (!elements.diagnosticsBanner.textContent.includes("runtime health truth")) {
  throw new Error(`diagnostics banner broadened truth claim: ${elements.diagnosticsBanner.textContent}`);
}
if (!elements.diagnosticsBanner.textContent.includes("redaction не подтверждена")) {
  throw new Error(`diagnostics banner should not invent redaction proof: ${elements.diagnosticsBanner.textContent}`);
}
if (!elements.actionSupportDetails.textContent.includes("redaction=unreported")) {
  throw new Error(`support details should show unreported redaction: ${elements.actionSupportDetails.textContent}`);
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

    def test_diagnostics_export_result_maps_redaction_states_without_runtime_green(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.className = "";
    this.textContent = "";
    this.lastElementChild = { textContent: "" };
  }
  append(...items) {
    for (const item of items) {
      if (!item) {
        continue;
      }
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
}

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
  "actionOnboardingBackend",
  "actionLedgerList",
  "diagnosticsStatusChip",
  "diagnosticsMessage",
  "diagnosticsPacketStatus",
  "diagnosticsExitCode",
  "diagnosticsMachineCode",
  "diagnosticsNextAction",
  "diagnosticsChangedFiles",
  "diagnosticsBundleRef",
  "diagnosticsBanner"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.diagnosticsStatusChip.lastElementChild = { textContent: "" };

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { screen: "diagnostics", source: "fixture" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/?screen=diagnostics" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

function render(redactionStatus) {
  sandbox.setActionPanel({
    status: "ok",
    ui_action: "export_diagnostics",
    action_role: "support_artifact",
    mutates_runtime: false,
    affects_primary_truth: false,
    post_action_refresh_required: false,
    result: {
      status: "ok",
      machine_error_code: "OK",
      human_message: "Diagnostics exported.",
      exit_code: 0,
      next_action: "none",
      changed_files: ["diagnostics_bundle"],
      data: {
        bundle_path: "wbp-diagnostics.zip",
        redaction_status: redactionStatus
      }
    }
  });
}

render("enabled");
if (elements.actionPanel.className !== "action-panel compact-action-panel blue") {
  throw new Error(`enabled redaction should be blue support artifact: ${elements.actionPanel.className}`);
}
if (elements.actionDisplayState.textContent !== "created") {
  throw new Error(`enabled redaction should render created: ${elements.actionDisplayState.textContent}`);
}
if (elements.actionPanel.className.includes("green") || elements.diagnosticsStatusChip.className.includes("green")) {
  throw new Error("support artifact must not render runtime-health green");
}
if (!elements.diagnosticsBanner.textContent.includes("support artifact")) {
  throw new Error(`enabled copy should preserve support-artifact scope: ${elements.diagnosticsBanner.textContent}`);
}

render("failed");
if (elements.actionPanel.className !== "action-panel compact-action-panel red") {
  throw new Error(`failed redaction should be red: ${elements.actionPanel.className}`);
}
if (elements.actionDisplayState.textContent !== "redaction_failed") {
  throw new Error(`failed redaction should render redaction_failed: ${elements.actionDisplayState.textContent}`);
}
if (!elements.diagnosticsBanner.textContent.includes("redaction failure")) {
  throw new Error(`failed copy should name redaction failure: ${elements.diagnosticsBanner.textContent}`);
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

    def test_action_ledger_recent_entries_are_session_only_and_count_paths(self) -> None:
        script = r"""
const fs = require("fs");
const vm = require("vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.className = "";
    this.textContent = "";
    this.lastElementChild = { textContent: "" };
    this.dataset = {};
    this.classList = {
      contains: (name) => String(this.className || "").split(/\s+/).includes(name),
      add: (name) => {
        if (!this.classList.contains(name)) {
          this.className = `${this.className} ${name}`.trim();
        }
      }
    };
  }
  append(...items) {
    for (const item of items) {
      if (!item) {
        continue;
      }
      this.children.push(item);
      this.lastElementChild = item;
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this.lastElementChild = { textContent: "" };
    this.append(...items);
  }
  addEventListener() {}
}

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
  "actionOnboardingBackend",
  "actionLedgerList",
  "actionLedgerScope"
];
const elements = Object.fromEntries(ids.map((id) => [id, new Node()]));
elements.actionLedgerScope.lastElementChild = { textContent: "" };

const sandbox = {
  console,
  Node,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = new Node();
      }
      return elements[id];
    },
    createElement(tag) {
      return new Node(tag);
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

const bounded = sandbox.boundedUiActionPayload("validate_account", {
  account_id: "backend-a",
  route_id: "wbp-route",
  ["command" + "_id"]: "forbidden",
  argv: "forbidden",
  path: "/tmp/forbidden"
});
if (bounded["command" + "_id"] || bounded.argv || bounded.path) {
  throw new Error(`bounded action payload leaked forbidden fields: ${JSON.stringify(bounded)}`);
}
if (bounded.ui_action !== "validate_account" || bounded.account_id !== "backend-a" || bounded.route_id !== "wbp-route") {
  throw new Error(`bounded action payload dropped admitted fields: ${JSON.stringify(bounded)}`);
}

sandbox.setActionPanel({
  status: "ok",
  ui_action: "sync_runtime",
  action_role: "runtime_sync",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "sync packet ok",
    next_action: "none",
    changed_files: ["/tmp/runtime-state-a.json", "/tmp/runtime-state-b.json"]
  }
});
let first = elements.actionLedgerList.children[0];
const firstText = JSON.stringify(first);
if (!first.className.includes("amber") || !firstText.includes("ok_refresh_pending")) {
  throw new Error(`ok command packet requiring refresh should stay amber pending: ${first.className} ${firstText}`);
}
if (!firstText.includes("changed files") || !firstText.includes("2 metadata entries")) {
  throw new Error(`ledger should show changed_files count only: ${firstText}`);
}
if (firstText.includes("/tmp/runtime-state") || firstText.includes("runtime-state-b.json")) {
  throw new Error(`ledger leaked changed_files path identity: ${firstText}`);
}
if (!firstText.includes("command packet outcome only")) {
  throw new Error(`ledger did not keep not-runtime-truth copy: ${firstText}`);
}
if (!firstText.includes("target - · machine OK · refresh canonical refresh pending")) {
  throw new Error(`ledger collapsed meta should be operator-readable, not debug key/value dump: ${firstText}`);
}

sandbox.setActionPanel({
  status: "ok",
  ui_action: "sync_runtime",
  action_role: "runtime_sync",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK",
    human_message: "sync packet ok",
    next_action: "none",
    changed_files: []
  }
}, "complete");
first = elements.actionLedgerList.children[0];
if (!first.className.includes("green") || !JSON.stringify(first).includes("ok_refresh_complete")) {
  throw new Error(`refresh-complete action should become green: ${JSON.stringify(first)}`);
}

sandbox.setActionPanel({
  status: "command_error",
  ui_action: "set_mode_managed",
  action_role: "",
  post_action_refresh_required: false,
  result: {
    status: "ok",
    machine_error_code: "COMMAND_FAILED",
    human_message: "nested ok must not win",
    next_action: "retry",
    changed_files: []
  }
});
if (!elements.actionLedgerList.children[0].className.includes("red")) {
  throw new Error("command_error ledger row must not be green");
}
const commandErrorText = JSON.stringify(elements.actionLedgerList.children[0]);
if (commandErrorText.includes("command_id=") || commandErrorText.includes("argv=")) {
  throw new Error(`ledger leaked raw dispatch fields: ${commandErrorText}`);
}

sandbox.setActionPanel({
  status: "command_error",
  ui_action: "export_diagnostics",
  action_role: "support_artifact",
  post_action_refresh_required: false,
  result: {
    status: "command_error",
    machine_error_code: "COMMAND_FAILED",
    human_message: "failed command_id=diagnostics_export argv=diagnostics secret=VERYSECRET /Users/kirill/private.log",
    next_action: "retry /tmp/private-state.json",
    changed_files: []
  }
});
const sensitiveLedgerText = JSON.stringify(elements.actionLedgerList.children[0]);
const sensitiveCompactText = [
  elements.actionSummaryMessage.textContent,
  elements.actionMessage.textContent,
  elements.actionNextAction.textContent,
  elements.actionSupportDetails.textContent
].join(" ");
if (sensitiveLedgerText.includes("diagnostics_export") || sensitiveLedgerText.includes("argv=diagnostics") || sensitiveLedgerText.includes("VERYSECRET") || sensitiveLedgerText.includes("/Users/") || sensitiveLedgerText.includes("/tmp/private-state")) {
  throw new Error(`ledger leaked sensitive or raw dispatch text: ${sensitiveLedgerText}`);
}
if (sensitiveCompactText.includes("diagnostics_export") || sensitiveCompactText.includes("argv=diagnostics") || sensitiveCompactText.includes("VERYSECRET") || sensitiveCompactText.includes("/Users/") || sensitiveCompactText.includes("/tmp/private-state")) {
  throw new Error(`compact action summary leaked sensitive or raw dispatch text: ${sensitiveCompactText}`);
}

sandbox.setActionPanel({
  status: "ok",
  ui_action: "set_mode_managed",
  action_role: "mode_set",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK_REFRESH",
    human_message: "mode packet ok",
    next_action: "none",
    changed_files: []
  }
});
sandbox.setActionPanel({
  status: "ok",
  ui_action: "set_mode_managed",
  action_role: "mode_set",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK_REFRESH",
    human_message: "mode packet ok",
    next_action: "none",
    changed_files: []
  }
}, "failed");
const staleRow = elements.actionLedgerList.children[0];
if (!staleRow.className.includes("amber") || !JSON.stringify(staleRow).includes("ok_refresh_failed")) {
  throw new Error(`failed refresh should replace ok row with refresh-failed amber: ${JSON.stringify(staleRow)}`);
}
sandbox.setActionPanel({
  status: "ok",
  ui_action: "api_route_remove",
  route_id: "wbp-disabled",
  action_role: "api_route_registry_cleanup",
  post_action_refresh_required: true,
  result: {
    status: "ok",
    machine_error_code: "OK_REFRESH",
    human_message: "route remove packet ok",
    next_action: "refresh_api_connections",
    changed_files: ["/tmp/registry.json"]
  }
}, "mismatch");
const mismatchRow = elements.actionLedgerList.children[0];
const mismatchText = JSON.stringify(mismatchRow);
if (!mismatchRow.className.includes("amber") || !mismatchText.includes("refresh_mismatch")) {
  throw new Error(`route still present after refresh must be mismatch amber: ${mismatchText}`);
}
if (!mismatchText.includes("canonical refresh mismatch") || mismatchText.includes("/tmp/registry.json")) {
  throw new Error(`mismatch row should show bounded refresh label and no path: ${mismatchText}`);
}
if (elements.actionLedgerList.children.length > 5) {
  throw new Error("ledger should stay bounded to five rows");
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
  dataset: { uiAction: "api_route_validate", routeEnabled: "true", routeStateProven: "true", routeId: "wbp-deepseek-v3", routeStateRequirement: "enabled" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const disabledRouteButton = {
  dataset: { uiAction: "api_route_check", routeEnabled: "false", routeStateProven: "true", routeId: "wbp-disabled", routeStateRequirement: "enabled" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const allowDisabledRouteButton = {
  dataset: { uiAction: "api_route_allow", routeEnabled: "false", routeStateProven: "true", routeId: "wbp-disabled", routeStateRequirement: "disabled" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const allowEnabledRouteButton = {
  dataset: { uiAction: "api_route_allow", routeEnabled: "true", routeStateProven: "true", routeId: "wbp-deepseek-v3", routeStateRequirement: "disabled" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const removeDisabledRouteButton = {
  dataset: { uiAction: "api_route_remove", routeEnabled: "false", routeStateProven: "true", routeId: "wbp-disabled", routeStateRequirement: "disabled" },
  classList: makeClassList(["api-route-action", "api-route-destructive-action"]),
  disabled: false,
  title: ""
};
const removeEnabledRouteButton = {
  dataset: { uiAction: "api_route_remove", routeEnabled: "true", routeStateProven: "true", routeId: "wbp-deepseek-v3", routeStateRequirement: "disabled" },
  classList: makeClassList(["api-route-action", "api-route-destructive-action"]),
  disabled: false,
  title: ""
};
const profileDisabledRouteButton = {
  dataset: { uiAction: "api_route_profile", routeEnabled: "false", routeStateProven: "true", routeId: "wbp-disabled", routeStateRequirement: "any" },
  classList: makeClassList(["api-route-action"]),
  disabled: false,
  title: ""
};
const evidenceDisabledRouteButton = {
  dataset: { uiAction: "api_route_evidence_capture", routeEnabled: "false", routeStateProven: "true", routeId: "wbp-disabled", routeStateRequirement: "any" },
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
if (!allowDisabledRouteButton.disabled) {
  throw new Error(`allow should stay deferred in readonly registry: ${JSON.stringify(allowDisabledRouteButton)}`);
}
if (!allowDisabledRouteButton.title.includes("отложено")) {
  throw new Error(`allow should explain deferred route mutation: ${JSON.stringify(allowDisabledRouteButton)}`);
}
if (!allowEnabledRouteButton.disabled) {
  throw new Error(`allow should be blocked for enabled route: ${JSON.stringify(allowEnabledRouteButton)}`);
}
if (removeDisabledRouteButton.disabled) {
  throw new Error(`remove should be available only for proven disabled route in live source: ${JSON.stringify(removeDisabledRouteButton)}`);
}
if (!removeEnabledRouteButton.disabled || !removeEnabledRouteButton.title.includes("Маршрут уже разрешён")) {
  throw new Error(`remove should be blocked for enabled route: ${JSON.stringify(removeEnabledRouteButton)}`);
}
if (!profileDisabledRouteButton.disabled || !profileDisabledRouteButton.title.includes("отложено")) {
  throw new Error(`profile packet should stay deferred in readonly registry: ${JSON.stringify(profileDisabledRouteButton)}`);
}
if (!evidenceDisabledRouteButton.disabled || !evidenceDisabledRouteButton.title.includes("отложено")) {
  throw new Error(`evidence capture should stay deferred in readonly registry: ${JSON.stringify(evidenceDisabledRouteButton)}`);
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
