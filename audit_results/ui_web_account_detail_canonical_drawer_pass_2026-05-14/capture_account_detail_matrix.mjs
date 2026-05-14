import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";

const repo = resolve(".");
const uiDir = join(repo, "wild_boar_proxy", "web_design_ui");
const outDir = join(repo, "audit_results", "ui_web_account_detail_canonical_drawer_pass_2026-05-14");
const screenshotsDir = join(outDir, "screenshots", "after");
mkdirSync(screenshotsDir, { recursive: true });

const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const tmpRoot = join(tmpdir(), `wbp-account-detail-capture-${Date.now()}`);
mkdirSync(tmpRoot, { recursive: true });

const baseHtml = readFileSync(join(uiDir, "index.html"), "utf8");

const actionMetadata = {
  validate_account: {
    available: true,
    display_name: "Проверить аккаунт",
    human_meaning: "Запросить bounded проверку одного аккаунта.",
    action_role: "account_verification",
    mutates_runtime: true,
    confirmation_required: true,
    post_action_refresh_required: true,
    action_claim_scope: "account_lifecycle"
  },
  hold_account: {
    available: true,
    display_name: "Удержать аккаунт",
    human_meaning: "Запросить ручное удержание аккаунта.",
    action_role: "account_hold",
    mutates_runtime: true,
    confirmation_required: true,
    post_action_refresh_required: true,
    action_claim_scope: "account_lifecycle"
  },
  release_account: {
    available: true,
    display_name: "Снять удержание",
    human_meaning: "Запросить снятие ручного удержания.",
    action_role: "account_hold",
    mutates_runtime: true,
    confirmation_required: true,
    post_action_refresh_required: true,
    action_claim_scope: "account_lifecycle"
  },
  promote_account: {
    available: true,
    display_name: "Перевести в активные",
    human_meaning: "Запросить перевод аккаунта в active.",
    action_role: "account_placement",
    mutates_runtime: true,
    confirmation_required: true,
    post_action_refresh_required: true,
    action_claim_scope: "account_lifecycle"
  },
  demote_account: {
    available: true,
    display_name: "Перевести в резерв",
    human_meaning: "Запросить перевод аккаунта в reserve.",
    action_role: "account_placement",
    mutates_runtime: true,
    confirmation_required: true,
    post_action_refresh_required: true,
    action_claim_scope: "account_lifecycle"
  },
  retire_account: {
    available: true,
    display_name: "Вывести из пула",
    human_meaning: "Запросить вывод аккаунта из пула.",
    action_role: "account_retire",
    mutates_runtime: true,
    confirmation_required: true,
    post_action_refresh_required: true,
    action_claim_scope: "account_lifecycle"
  },
  onboard_account: {
    available: false,
    unavailable_reason: "not part of account detail capture"
  }
};

const scenarios = [
  { name: "active_account_detail", accountId: "acct-active-01" },
  { name: "reserve_account_detail", accountId: "acct-reserve-04" },
  { name: "held_account_detail", accountId: "acct-held-11" },
  { name: "problem_account_detail", accountId: "acct-problem-21" },
  { name: "missing_account", accountId: "acct-missing-99" },
  { name: "disabled_action_reasons", accountId: "acct-active-01" },
  { name: "last_command_success", accountId: "acct-active-01", actionResult: "success" },
  { name: "last_command_failed", accountId: "acct-active-01", actionResult: "failed" },
  { name: "retire_confirmation", accountId: "acct-active-01", confirmation: true }
];

const snapshot = {
  schema_version: 1,
  status: "ok",
  source: "accounts_readonly",
  primary_truth_ok: true,
  privacy: {
    redacted: true,
    raw_command_packet_included: false,
    forbidden_fields_excluded: ["secret_references", "tokens", "raw_paths", "raw_logs"]
  },
  registry_identity: {
    status: "ok",
    machine_error_code: "OK",
    next_action: "none"
  },
  summary: {
    active: 1,
    reserve: 2,
    retired: 1,
    hold: 1,
    problem: 1,
    healthy: 2,
    degraded: 1,
    down: 1,
    capacity_target: 20,
    visible_count: 4,
    human_message: "Accounts readonly packet for drawer capture.",
    machine_error_code: "OK",
    last_error: ""
  },
  accounts: [
    {
      id: "acct-active-01",
      label: "codex-primary@example.com",
      pool: "active",
      pool_label: "Активные",
      status: "healthy",
      status_label: "Работает",
      visual_state: "green",
      manual_hold: false,
      enabled: true,
      checks_24h: 17,
      success_count: 17,
      fail_count: 0,
      last_latency_ms: 124,
      recovery_attempts: 0,
      last_success: "Сегодня, 12:42",
      last_error_summary: "",
      timeline: [
        { at: "12:42", message: "Проверка OK", visual: "green", icon: "assets/icons/phosphor/check-circle.png" },
        { at: "12:40", message: "Переведён в active", visual: "blue", icon: "assets/icons/phosphor/play.png" },
        { at: "12:38", message: "Onboarded to reserve", visual: "neutral", icon: "assets/icons/phosphor/info.png" }
      ]
    },
    {
      id: "acct-reserve-04",
      label: "reserve-codex@example.com",
      pool: "reserve",
      pool_label: "Резерв",
      status: "healthy",
      status_label: "Готов",
      visual_state: "blue",
      manual_hold: false,
      enabled: true,
      checks_24h: 8,
      success_count: 8,
      fail_count: 0,
      last_latency_ms: 148,
      recovery_attempts: 0,
      last_success: "Сегодня, 12:37",
      last_error_summary: "",
      timeline: [
        { at: "12:37", message: "Проверка OK", visual: "green", icon: "assets/icons/phosphor/check-circle.png" },
        { at: "12:12", message: "Оставлен в резерве", visual: "blue", icon: "assets/icons/phosphor/info.png" }
      ]
    },
    {
      id: "acct-held-11",
      label: "held-account@example.com",
      pool: "reserve",
      pool_label: "Резерв",
      status: "degraded",
      status_label: "Удержан",
      visual_state: "amber",
      manual_hold: true,
      enabled: true,
      checks_24h: 4,
      success_count: 3,
      fail_count: 1,
      last_latency_ms: 210,
      recovery_attempts: 1,
      last_success: "Сегодня, 11:58",
      last_error_summary: "manual hold",
      timeline: [
        { at: "12:16", message: "Аккаунт удержан оператором", visual: "amber", icon: "assets/icons/phosphor/pause-circle.png" },
        { at: "11:58", message: "Последняя проверка OK", visual: "green", icon: "assets/icons/phosphor/check-circle.png" }
      ]
    },
    {
      id: "acct-problem-21",
      label: "broken-auth@example.com",
      pool: "reserve",
      pool_label: "Резерв",
      status: "down",
      status_label: "Недоступен",
      visual_state: "red",
      manual_hold: false,
      enabled: false,
      checks_24h: 9,
      success_count: 2,
      fail_count: 7,
      last_latency_ms: 0,
      recovery_attempts: 2,
      last_success: "Сегодня, 08:10",
      last_error_summary: "auth unavailable",
      timeline: [
        { at: "12:38", message: "auth unavailable", visual: "red", icon: "assets/icons/phosphor/x-circle.png" },
        { at: "12:36", message: "Повторная проверка не прошла", visual: "amber", icon: "assets/icons/phosphor/warning.png" }
      ]
    }
  ]
};

function injectedHtml(scenario) {
  const baseTag = `<base href="file://${uiDir}/">`;
  const preScript = `<script>
window.__captureActions = ${JSON.stringify(actionMetadata)};
window.__captureOverviewFixture = {
  schema_version: 1,
  state_id: "healthy",
  runtime: {
    visual_state: "healthy",
    status_label: "Работает",
    desired_mode: "managed",
    effective_mode: "managed",
    endpoint: "127.0.0.1:8320",
    machine_error_code: "OK",
    human_message: "Capture fixture",
    last_error: "",
    observed_at_utc: "capture"
  },
  pool_summary: {
    active: 1,
    reserve: 2,
    hold: 1,
    problem: 1,
    active_note: "capture",
    reserve_note: "capture",
    hold_note: "capture",
    problem_note: "capture"
  },
  events: []
};
const __captureOriginalFetch = window.fetch.bind(window);
window.fetch = async (input, init) => {
  const url = String(input);
  if (url === "api/actions" || url.endsWith("/api/actions")) {
    return new Response(JSON.stringify({ actions: window.__captureActions }), { status: 200, headers: { "Content-Type": "application/json" } });
  }
  if (url.startsWith("fixtures/") || url.includes("/fixtures/")) {
    return new Response(JSON.stringify(window.__captureOverviewFixture), { status: 200, headers: { "Content-Type": "application/json" } });
  }
  return __captureOriginalFetch(input, init);
};
</script>`;
  const postScript = `<script>
window.__captureScenario = ${JSON.stringify(scenario)};
window.__captureAccountsSnapshot = ${JSON.stringify(snapshot)};
function __captureMetricText(id) {
  const node = document.getElementById(id);
  return node ? node.textContent.trim() : "";
}
function __captureCollect() {
  const drawer = document.getElementById("accountDetailDrawer");
  const modal = document.getElementById("confirmModal");
  const target = window.__captureScenario.confirmation ? modal : drawer;
  const rect = target.getBoundingClientRect();
  const root = document.documentElement;
  const activeButtons = Array.from(document.querySelectorAll("#accountDetailDrawer .account-action")).map((button) => ({
    ui_action: button.dataset.uiAction || "",
    account_id: button.dataset.accountId || "",
    disabled: button.disabled,
    title: button.title || "",
    classes: button.className || ""
  }));
  const disabledButtons = Array.from(document.querySelectorAll("#accountDetailDrawer .account-detail-disabled-action")).map((button) => ({
    label: button.textContent.trim(),
    title: button.title || "",
    classes: button.className || ""
  }));
  const clipped = Array.from(document.querySelectorAll("#accountDetailDrawer button, #accountDetailDrawer .account-detail-timeline-row, #accountDetailDrawer .account-detail-facts div, #confirmModal button")).filter((node) => {
    const style = getComputedStyle(node);
    if (style.display === "none" || style.visibility === "hidden") return false;
    return node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 2;
  }).slice(0, 12).map((node) => ({
    tag: node.tagName,
    id: node.id || "",
    className: node.className || "",
    text: node.textContent.trim().slice(0, 80),
    scrollWidth: node.scrollWidth,
    clientWidth: node.clientWidth,
    scrollHeight: node.scrollHeight,
    clientHeight: node.clientHeight
  }));
  const visibleSvgIcons = Array.from(document.querySelectorAll("#accountDetailDrawer svg, #confirmModal svg")).filter((node) => node.getBoundingClientRect().width > 0).length;
  const visibleImgIcons = Array.from(document.querySelectorAll("#accountDetailDrawer img, #confirmModal img")).filter((node) => node.getBoundingClientRect().width > 0).length;
  return {
    scenario: window.__captureScenario.name,
    account_id: window.__captureScenario.accountId,
    viewport: { width: window.innerWidth, height: window.innerHeight },
    document: { scrollWidth: root.scrollWidth, scrollHeight: root.scrollHeight },
    targetRect: {
      left: rect.left,
      right: rect.right,
      top: rect.top,
      bottom: rect.bottom,
      width: rect.width,
      height: rect.height,
      scrollHeight: target.scrollHeight,
      clientHeight: target.clientHeight
    },
    overlayHidden: document.getElementById("accountDetailOverlay").hidden,
    missingHidden: document.getElementById("accountDetailMissing").hidden,
    statusChip: __captureMetricText("accountDetailStatusChip"),
    lifecycle: __captureMetricText("accountDetailLifecycle"),
    pool: __captureMetricText("accountDetailPoolValue"),
    lastError: __captureMetricText("accountDetailError"),
    checks24h: __captureMetricText("accountDetailChecks24h"),
    timelineRows: document.querySelectorAll("#accountDetailTimeline .account-detail-timeline-row").length,
    activeButtons,
    disabledButtons,
    dangerButtons: Array.from(document.querySelectorAll("#accountDetailDangerActions button")).map((button) => ({
      ui_action: button.dataset.uiAction || "",
      account_id: button.dataset.accountId || "",
      disabled: button.disabled,
      classes: button.className || "",
      title: button.title || ""
    })),
    lastCommandChip: __captureMetricText("accountDetailLastCommandChip"),
    lastCommandAction: __captureMetricText("accountDetailLastCommandAction"),
    lastCommandCode: __captureMetricText("accountDetailLastCommandCode"),
    lastCommandRefresh: __captureMetricText("accountDetailLastCommandRefresh"),
    confirmHidden: document.getElementById("confirmOverlay").hidden,
    confirmUiAction: __captureMetricText("confirmUiAction"),
    confirmAccountId: __captureMetricText("confirmAccountId"),
    visibleSvgIcons,
    visibleImgIcons,
    fileInputs: document.querySelectorAll("input[type=file]").length,
    editablePathInputs: Array.from(document.querySelectorAll("input")).filter((input) => /path|file|директ|каталог|путь/i.test(input.name || input.id || input.placeholder || "")).length,
    clipped
  };
}
function __captureRun() {
  const scenario = window.__captureScenario;
  setScreen("accounts", false);
  renderAccountsSnapshot(window.__captureAccountsSnapshot);
  openAccountDrawer(scenario.accountId);
  if (scenario.actionResult === "success") {
    setActionPanel({
      ui_action: "validate_account",
      action_role: "account_verification",
      account_id: scenario.accountId,
      post_action_refresh_required: true,
      result: {
        status: "ok",
        machine_error_code: "OK",
        human_message: "Проверка аккаунта выполнена.",
        next_action: "refresh_accounts",
        changed_files: []
      }
    }, "none");
  }
  if (scenario.actionResult === "failed") {
    setActionPanel({
      ui_action: "validate_account",
      action_role: "account_verification",
      account_id: scenario.accountId,
      post_action_refresh_required: true,
      result: {
        status: "command_error",
        machine_error_code: "VALIDATION_FAILED",
        human_message: "Проверка аккаунта не прошла.",
        next_action: "retry",
        changed_files: []
      }
    }, "failed");
  }
  if (scenario.confirmation) {
    const metadata = window.__captureActions.retire_account;
    openConfirmation("retire_account", metadata, confirmationPolicyFor("retire_account", metadata), { account_id: scenario.accountId });
  }
  const metrics = __captureCollect();
  const pre = document.createElement("pre");
  pre.id = "captureMetrics";
  pre.textContent = JSON.stringify(metrics);
  pre.hidden = true;
  document.body.append(pre);
  document.documentElement.dataset.captureReady = "true";
}
window.addEventListener("load", () => {
  window.setTimeout(__captureRun, 350);
});
</script>`;
  return baseHtml
    .replace("<head>", `<head>\n  ${baseTag}`)
    .replace("<script src=\"scripts/overview.js\"></script>", `${preScript}\n  <script src="scripts/overview.js"></script>\n  ${postScript}`);
}

const metrics = [];
for (const scenario of scenarios) {
  const htmlPath = join(tmpRoot, `${scenario.name}.html`);
  const screenshotPath = join(screenshotsDir, `${scenario.name}.png`);
  writeFileSync(htmlPath, injectedHtml(scenario));
  const fileUrl = `file://${htmlPath}`;
  const commonArgs = [
    "--headless=new",
    "--disable-gpu",
    "--disable-background-networking",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-sync",
    "--no-default-browser-check",
    "--no-first-run",
    "--hide-scrollbars",
    "--allow-file-access-from-files",
    "--run-all-compositor-stages-before-draw",
    "--window-size=1600,1000",
    `--user-data-dir=${join(tmpRoot, `profile-${scenario.name}`)}`,
    "--virtual-time-budget=2500"
  ];
  const screenshot = spawnSync(chrome, [...commonArgs, `--screenshot=${screenshotPath}`, fileUrl], {
    encoding: "utf8",
    maxBuffer: 1024 * 1024 * 4,
    timeout: 8000
  });
  if (screenshot.status !== 0 && !existsSync(screenshotPath)) {
    throw new Error(`Chrome screenshot failed for ${scenario.name}: ${screenshot.stderr || screenshot.stdout}`);
  }
  const dump = spawnSync(chrome, [...commonArgs, "--dump-dom", fileUrl], {
    encoding: "utf8",
    maxBuffer: 1024 * 1024 * 10,
    timeout: 8000
  });
  if (dump.status !== 0) {
    throw new Error(`Chrome dump failed for ${scenario.name}: ${dump.stderr || dump.stdout}`);
  }
  const match = dump.stdout.match(/<pre id="captureMetrics" hidden="">([^<]+)<\/pre>/);
  if (!match) {
    throw new Error(`Metrics marker missing for ${scenario.name}`);
  }
  const parsed = JSON.parse(match[1].replace(/&quot;/g, '"').replace(/&amp;/g, "&"));
  parsed.screenshot = join("screenshots", "after", basename(screenshotPath));
  metrics.push(parsed);
}

writeFileSync(join(outDir, "after_metrics.json"), JSON.stringify({ generated_at: new Date().toISOString(), metrics }, null, 2));
rmSync(tmpRoot, { recursive: true, force: true });
