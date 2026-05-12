// SPDX-FileCopyrightText: 2026 Kirill Ponomarev
// SPDX-License-Identifier: AGPL-3.0-or-later

const FIXTURE_STATES = [
  "healthy",
  "degraded",
  "down",
  "stale",
  "unknown",
  "integration_failure",
];

const FALLBACK_FIXTURE = {
  schema_version: 1,
  state_id: "unknown",
  fixture_notice: "Embedded fallback fixture. Not runtime truth.",
  runtime: {
    visual_state: "unknown",
    status_label: "Неизвестно",
    desired_mode: "managed",
    effective_mode: "unknown",
    endpoint: "unknown",
    machine_error_code: "fixture_fallback",
    human_message: "Fixture file could not be loaded.",
    last_error: "fixture fetch failed",
    observed_at_utc: "2026-05-12T21:00:00Z"
  },
  pool_summary: {
    active: 0,
    reserve: 0,
    hold: 0,
    problem: 0,
    active_note: "нет данных",
    reserve_note: "нет данных",
    hold_note: "нет данных",
    problem_note: "нет данных"
  },
  events: [
    {
      level: "amber",
      message: "Fixture fallback loaded; no live command was executed.",
      observed_at: "fixture"
    }
  ]
};

const VISUAL_CLASS = {
  healthy: "green",
  degraded: "amber",
  down: "red",
  stale: "amber",
  unknown: "neutral",
  integration_failure: "red"
};

const EVENT_ICON = {
  green: "✓",
  blue: "↻",
  amber: "!",
  red: "!",
  neutral: "·"
};

const SCREENS = ["overview", "accounts"];
const ACCOUNT_VISUAL_CLASS = {
  green: "green",
  blue: "blue",
  amber: "amber",
  red: "red",
  neutral: "neutral"
};

let actionMetadata = {};
let pendingConfirmedAction = null;

function text(id, value) {
  document.getElementById(id).textContent = String(value ?? "-");
}

function setClassName(node, base, visualState) {
  node.className = `${base} ${VISUAL_CLASS[visualState] || "neutral"}`;
}

function canonicalState(requestedState) {
  return FIXTURE_STATES.includes(requestedState) ? requestedState : "healthy";
}

function stateFromLocation() {
  const params = new URLSearchParams(window.location.search);
  return canonicalState(params.get("state") || "healthy");
}

function sourceFromLocation() {
  const params = new URLSearchParams(window.location.search);
  return params.get("source") === "live" ? "live" : "fixture";
}

function screenFromLocation() {
  const params = new URLSearchParams(window.location.search);
  const screen = params.get("screen") || "overview";
  return SCREENS.includes(screen) ? screen : "overview";
}

function currentScreen() {
  return document.querySelector(".desktop").dataset.screen || "overview";
}

async function loadFixture(stateId) {
  try {
    const response = await fetch(`fixtures/${stateId}.json`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`fixture http ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    return {
      ...FALLBACK_FIXTURE,
      state_id: "unknown",
      fixture_notice: `${FALLBACK_FIXTURE.fixture_notice} (${error.message})`
    };
  }
}

async function loadLiveReadonly() {
  try {
    const response = await fetch("api/live-readonly", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`live http ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    return {
      ...FALLBACK_FIXTURE,
      schema_version: 1,
      state_id: "integration_failure",
      status: "integration_failure",
      ui_state: "integration_failure",
      source: "live_readonly",
      fixture_notice: `Live read-only request failed: ${error.message}`,
      runtime: {
        ...FALLBACK_FIXTURE.runtime,
        visual_state: "integration_failure",
        status_label: "Ошибка интеграции",
        machine_error_code: "UI_LIVE_READONLY_FETCH_FAILED",
        human_message: "Live read-only request failed.",
        last_error: error.message,
        observed_at_utc: "live-readonly"
      },
      events: [
        {
          level: "red",
          message: "Live read-only request failed.",
          observed_at: "live-readonly"
        }
      ]
    };
  }
}

async function loadAccountsReadonly() {
  try {
    const response = await fetch("api/accounts-readonly", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`accounts http ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    return {
      schema_version: 1,
      status: "integration_failure",
      source: "accounts_readonly",
      primary_truth_ok: false,
      privacy: {
        redacted: true,
        raw_command_packet_included: false,
        forbidden_fields_excluded: ["secret_references", "tokens", "raw_paths", "raw_logs"]
      },
      registry_identity: {
        status: "unknown",
        machine_error_code: "UI_ACCOUNTS_READONLY_FETCH_FAILED",
        next_action: "retry"
      },
      summary: {
        active: 0,
        reserve: 0,
        retired: 0,
        hold: 0,
        problem: 0,
        healthy: 0,
        degraded: 0,
        down: 0,
        capacity_target: 20,
        visible_count: 0,
        human_message: "Accounts read-only request failed.",
        machine_error_code: "UI_ACCOUNTS_READONLY_FETCH_FAILED",
        last_error: error.message
      },
      accounts: []
    };
  }
}

async function loadActionMetadata() {
  try {
    const response = await fetch("api/actions", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`metadata http ${response.status}`);
    }
    const payload = await response.json();
    actionMetadata = payload.actions || {};
  } catch (error) {
    actionMetadata = {};
  }
}

function metadataFor(uiAction) {
  return actionMetadata[uiAction] || {
    ui_action: uiAction,
    display_name: uiAction,
    human_meaning: "Action metadata could not be loaded.",
    action_role: "unknown",
    mutates_runtime: true,
    confirmation_required: true,
    post_action_refresh_required: true,
    action_claim_scope: "unknown",
    available: false,
    unavailable_reason: "Action metadata could not be loaded."
  };
}

async function runUiAction(uiAction, extraPayload = {}) {
  setActionsBusy(true);
  setActionPanel({
    ui_action: uiAction,
    action_role: "running",
    account_id: extraPayload.account_id || "",
    post_action_refresh_required: false,
    result: {
      status: "running",
      machine_error_code: "RUNNING",
      human_message: "Action is running.",
      next_action: "wait",
      changed_files: []
    }
  });
  try {
    const response = await fetch("api/action", {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ui_action: uiAction, ...extraPayload })
    });
    if (!response.ok) {
      throw new Error(`action http ${response.status}`);
    }
    const payload = await response.json();
    setActionPanel(payload);
    if (payload.post_action_refresh_required) {
      const refreshTarget = currentScreen() === "accounts" ? "accounts" : "overview";
      text("actionRefreshStatus", `refreshing live ${refreshTarget}`);
      const refreshed = await setLiveReadonly(false);
      text("actionRefreshStatus", refreshed.status === "ok" ? "live refresh ok" : "live refresh failed");
    }
  } catch (error) {
    setActionPanel({
      ui_action: uiAction,
      action_role: "integration_failure",
      account_id: extraPayload.account_id || "",
      post_action_refresh_required: false,
      result: {
        status: "integration_failure",
        machine_error_code: "UI_ACTION_FETCH_FAILED",
        human_message: error.message,
        next_action: "retry",
        changed_files: []
      }
    });
  } finally {
    setActionsBusy(false);
  }
}

function applyActionAvailability() {
  for (const button of document.querySelectorAll(".live-action, .account-action")) {
    const metadata = metadataFor(button.dataset.uiAction);
    const requiresLive = button.classList.contains("account-action");
    const isLiveSource = document.querySelector(".desktop").dataset.source === "live";
    const available = metadata.available !== false && (!requiresLive || isLiveSource);
    button.disabled = !available;
    button.dataset.available = available ? "true" : "false";
    button.title = available
      ? ""
      : (requiresLive && !isLiveSource ? "Switch Accounts to live source before validation." : (metadata.unavailable_reason || "Action unavailable"));
  }
}

function validateSnapshot(snapshot) {
  const requiredTop = snapshot.source === "live_readonly"
    ? ["schema_version", "runtime", "pool_summary", "events"]
    : ["schema_version", "state_id", "runtime", "pool_summary", "events"];
  const missingTop = requiredTop.filter((key) => !(key in snapshot));
  const runtime = snapshot.runtime || {};
  const requiredRuntime = [
    "visual_state",
    "status_label",
    "desired_mode",
    "effective_mode",
    "endpoint",
    "machine_error_code",
    "human_message",
    "last_error"
  ];
  const missingRuntime = requiredRuntime.filter((key) => !(key in runtime));
  return { ok: missingTop.length === 0 && missingRuntime.length === 0, missingTop, missingRuntime };
}

function snapshotNotice(snapshot) {
  if (snapshot.source === "live_readonly") {
    if (snapshot.status !== "ok") {
      return "Live read-only integration failure. Previous healthy data was not reused.";
    }
    if (snapshot.has_warnings) {
      return `Live read-only preview with warnings. ${warningSummary(snapshot.warnings || [])}`;
    }
    return "Live read-only preview. Runtime truth comes from strict command packets.";
  }
  return snapshot.fixture_notice || "Fixture preview only. No command execution, no runtime file reads.";
}

function warningSummary(warnings) {
  if (!warnings.length) {
    return "";
  }
  return warnings
    .slice(0, 2)
    .map((warning) => `${warning.label || warning.role}: ${warning.human_message}`)
    .join(" · ");
}

function modeLabel(value) {
  const labels = {
    managed: "Управляемый",
    stable: "Стабильный",
    unknown: "Неизвестно"
  };
  return labels[value] || value || "Неизвестно";
}

function renderModeSegments(runtime) {
  const desired = runtime.desired_mode;
  const effective = runtime.effective_mode;
  const managed = document.getElementById("managedSegment");
  const stable = document.getElementById("stableSegment");
  managed.className = desired === "managed" ? "active" : "";
  stable.className = desired === "stable" ? "active" : "";
  if (desired !== effective && effective !== "unknown") {
    managed.classList.add("mismatch");
    stable.classList.add("mismatch");
  }
}

function renderEvents(events) {
  const list = document.getElementById("eventList");
  list.replaceChildren();
  for (const event of events.slice(0, 5)) {
    const row = document.createElement("div");
    row.className = "log-row";

    const icon = document.createElement("span");
    const level = event.level || "neutral";
    icon.className = `round-icon ${level}`;
    icon.textContent = EVENT_ICON[level] || EVENT_ICON.neutral;

    const message = document.createElement("span");
    message.textContent = event.message || "Fixture event";

    const time = document.createElement("time");
    time.textContent = event.observed_at || "fixture";

    row.append(icon, message, time);
    list.append(row);
  }
}

function setSourceCopy(source) {
  const screen = currentScreen();
  document.getElementById("sourceFooter").textContent = source === "live"
    ? (screen === "accounts" ? "Accounts live read-only" : "Live read-only · basic actions")
    : "UI preview · no live commands";
  document.getElementById("subtitleText").textContent = source === "live"
    ? (
      screen === "accounts"
        ? "Пул аккаунтов читается только из канонического accounts JSON packet. Lifecycle-действия идут через bounded action gate."
        : "Первый экран подключен к живым JSON-командам. Basic actions требуют live refresh после выполнения."
    )
    : (
      screen === "accounts"
        ? "Визуальный перенос экрана аккаунтов. Данные ниже являются fixtures, а не runtime truth."
        : "Визуальный перенос первого экрана. Данные ниже являются fixtures, а не runtime truth."
    );
}

function setActionPanel(payload) {
  const result = payload.result || {};
  text("actionUiAction", payload.ui_action || "unknown");
  text("actionRole", payload.action_role || "unknown");
  text("actionAccountId", payload.account_id || "-");
  text("actionStatus", result.status || payload.status || "unknown");
  text("actionMachineCode", result.machine_error_code || "-");
  text("actionMessage", result.human_message || "-");
  text("actionNextAction", result.next_action || "none");
  text("actionChangedFiles", JSON.stringify(result.changed_files || []));
  text(
    "actionRefreshStatus",
    payload.post_action_refresh_required ? "required after action" : "not required"
  );
}

function setActionsBusy(isBusy) {
  for (const button of document.querySelectorAll(".live-action, .account-action")) {
    const metadata = metadataFor(button.dataset.uiAction);
    const requiresLive = button.classList.contains("account-action");
    const isLiveSource = document.querySelector(".desktop").dataset.source === "live";
    const available = metadata.available !== false && (!requiresLive || isLiveSource);
    button.disabled = isBusy || !available;
  }
}

function maybeConfirmAndRun(uiAction, extraPayload = {}) {
  const metadata = metadataFor(uiAction);
  if (metadata.available === false) {
    setActionPanel({
      ui_action: uiAction,
      action_role: "blocked",
      account_id: extraPayload.account_id || "",
      post_action_refresh_required: false,
      result: {
        status: "integration_failure",
        machine_error_code: "UI_ACTION_UNAVAILABLE",
        human_message: metadata.unavailable_reason || "Action unavailable.",
        next_action: "user_action",
        changed_files: []
      }
    });
    return;
  }
  if (metadata.confirmation_required) {
    openConfirmation(uiAction, metadata, extraPayload);
    return;
  }
  runUiAction(uiAction, extraPayload);
}

function openConfirmation(uiAction, metadata, extraPayload = {}) {
  pendingConfirmedAction = { uiAction, extraPayload };
  text("confirmTitle", metadata.display_name || uiAction);
  text("confirmMeaning", metadata.human_meaning || "Confirm this action.");
  text("confirmUiAction", uiAction);
  text("confirmAccountId", extraPayload.account_id || "-");
  text("confirmMutation", metadata.mutates_runtime ? "true" : "false");
  text("confirmRefresh", metadata.post_action_refresh_required ? "required" : "not required");
  text("confirmScope", metadata.action_claim_scope || "unknown");
  document.getElementById("confirmOverlay").hidden = false;
  document.getElementById("confirmAction").focus();
}

function closeConfirmation() {
  pendingConfirmedAction = null;
  document.getElementById("confirmOverlay").hidden = true;
}

function confirmPendingAction() {
  const pending = pendingConfirmedAction;
  closeConfirmation();
  if (pending) {
    runUiAction(pending.uiAction, pending.extraPayload);
  }
}

function setScreen(screen, updateUrl = false) {
  const nextScreen = SCREENS.includes(screen) ? screen : "overview";
  const desktop = document.querySelector(".desktop");
  desktop.dataset.screen = nextScreen;

  for (const node of document.querySelectorAll(".screen")) {
    node.hidden = node.dataset.screen !== nextScreen;
  }
  for (const node of document.querySelectorAll(".overview-only")) {
    node.hidden = nextScreen !== "overview";
  }
  for (const node of document.querySelectorAll(".accounts-only")) {
    node.hidden = nextScreen !== "accounts";
  }
  for (const link of document.querySelectorAll("[data-screen-link]")) {
    const active = link.dataset.screenLink === nextScreen;
    link.classList.toggle("active", active);
    if (active) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  }

  text("mainTitle", nextScreen === "accounts" ? "Аккаунты" : "Обзор");
  setSourceCopy(document.getElementById("sourcePicker").value);

  if (updateUrl) {
    const url = new URL(window.location.href);
    url.searchParams.set("screen", nextScreen);
    window.history.replaceState({}, "", url);
  }
}

function accountsFixtureFromOverview(fixture) {
  const stateId = fixture.state_id || "unknown";
  const pool = fixture.pool_summary || {};
  const problemState = stateId === "healthy" ? "red" : "amber";
  const accounts = [
    accountFixture("acct-active-01", "codex-primary@example.com", "active", "healthy", "green", "", "Сегодня, 12:42"),
    accountFixture("acct-reserve-01", "codex-reserve@example.com", "reserve", "healthy", "blue", "", "Сегодня, 11:50"),
    accountFixture("acct-hold-01", "codex-hold@example.com", "reserve", "healthy", "amber", "manual hold", "Сегодня, 10:48", true),
    accountFixture("acct-problem-01", "codex-auth@example.com", "retired", "down", problemState, "auth/session error", "Сегодня, 09:44")
  ];
  return {
    schema_version: 1,
    status: stateId === "integration_failure" ? "integration_failure" : "ok",
    source: "accounts_fixture",
    primary_truth_ok: false,
    privacy: {
      redacted: true,
      raw_command_packet_included: false,
      forbidden_fields_excluded: ["secret_references", "tokens", "raw_paths", "raw_logs"]
    },
    registry_identity: {
      status: stateId === "integration_failure" ? "unknown" : "fixture",
      machine_error_code: fixture.runtime?.machine_error_code || "fixture",
      next_action: "none"
    },
    summary: {
      active: pool.active ?? 0,
      reserve: pool.reserve ?? 0,
      retired: 1,
      hold: pool.hold ?? 0,
      problem: pool.problem ?? 0,
      healthy: stateId === "healthy" ? 3 : 1,
      degraded: stateId === "degraded" ? 2 : 0,
      down: stateId === "down" ? 2 : 1,
      capacity_target: 20,
      visible_count: accounts.length,
      human_message: fixture.fixture_notice || "Accounts fixture preview.",
      machine_error_code: fixture.runtime?.machine_error_code || "fixture",
      last_error: fixture.runtime?.last_error || ""
    },
    accounts
  };
}

function accountFixture(id, label, pool, status, visualState, lastError, lastSuccess, manualHold = false) {
  return {
    id,
    label: redactAccountLabel(label),
    pool,
    pool_label: manualHold ? "На удержании" : poolLabel(pool),
    status,
    status_label: manualHold ? "Удержание" : statusLabel(status),
    visual_state: visualState,
    manual_hold: manualHold,
    enabled: true,
    fail_count: lastError ? 2 : 0,
    success_count: lastError ? 0 : 8,
    last_success: lastSuccess,
    last_error_class: lastError ? "fixture" : "",
    last_error_summary: lastError,
    cooldown_until: "",
    notes_summary: "fixture"
  };
}

function validateAccountsSnapshot(snapshot) {
  const summary = snapshot.summary || {};
  const registry = snapshot.registry_identity || {};
  const missingTop = ["schema_version", "status", "source", "summary", "accounts"].filter((key) => !(key in snapshot));
  const missingSummary = ["active", "reserve", "retired", "hold", "problem", "visible_count", "human_message", "machine_error_code"].filter((key) => !(key in summary));
  const missingRegistry = ["status", "machine_error_code", "next_action"].filter((key) => !(key in registry));
  return {
    ok: missingTop.length === 0 && missingSummary.length === 0 && missingRegistry.length === 0 && Array.isArray(snapshot.accounts),
    missingTop,
    missingSummary,
    missingRegistry
  };
}

function renderAccountsSnapshot(snapshot) {
  const validation = validateAccountsSnapshot(snapshot);
  const safeSnapshot = validation.ok ? snapshot : {
    ...accountsFixtureFromOverview(FALLBACK_FIXTURE),
    status: "integration_failure",
    source: "accounts_fixture_invalid",
    summary: {
      ...accountsFixtureFromOverview(FALLBACK_FIXTURE).summary,
      machine_error_code: "UI_ACCOUNTS_SCHEMA_INVALID",
      last_error: `Accounts schema invalid: top [${validation.missingTop.join(", ")}], summary [${validation.missingSummary.join(", ")}], registry [${validation.missingRegistry.join(", ")}]`
    },
    accounts: []
  };

  const source = safeSnapshot.source === "accounts_readonly" ? "live" : "fixture";
  const visualState = safeSnapshot.status === "ok" ? "healthy" : "integration_failure";
  const desktop = document.querySelector(".desktop");
  desktop.dataset.fixtureState = visualState;
  desktop.dataset.source = source;
  document.getElementById("sourcePicker").value = source;
  document.getElementById("statePicker").disabled = source === "live";
  document.getElementById("brandCaption").textContent = source === "live"
    ? "accounts live read-only"
    : "accounts fixture preview";
  document.getElementById("refreshFixture").lastElementChild.textContent = source === "live"
    ? "Обновить live"
    : "Обновить fixture";
  setSourceCopy(source);

  const banner = document.getElementById("accountsBanner");
  setClassName(banner, "fixture-banner", visualState);
  banner.textContent = source === "live"
    ? "Accounts live mode. Truth comes only from the canonical accounts JSON packet; promote/demote/hold/release are bounded action requests."
    : "Accounts fixture preview only. Account actions are disabled.";

  const summary = safeSnapshot.summary;
  text("accountsActiveChip", `${summary.active} активных`);
  text("accountsReserveChip", `${summary.reserve} резерв`);
  text("accountsHoldChip", `${summary.hold} удержание`);
  text("accountsProblemChip", `${summary.problem} проблемных`);
  text(
    "accountsRegistryStatus",
    `registry identity: ${safeSnapshot.registry_identity.status} · ${safeSnapshot.registry_identity.machine_error_code}`
  );
  text("accountsVisibleCount", `Показано ${safeSnapshot.accounts.length} из ${summary.visible_count}`);
  text("accountsPagination", `Строки ${safeSnapshot.accounts.length ? 1 : 0}-${safeSnapshot.accounts.length} из ${summary.visible_count}`);
  renderAccountRows(safeSnapshot.accounts);

  const sidebarDot = document.getElementById("sidebarDot");
  setClassName(sidebarDot, "dot", visualState);
  text("sidebarStatus", summary.human_message || "Accounts read-only");
}

function renderAccountRows(accounts) {
  const body = document.getElementById("accountsTableBody");
  body.replaceChildren();
  for (const account of accounts.slice(0, 12)) {
    const row = document.createElement("tr");
    row.append(
      td("checkcell", checkbox()),
      td("", accountIdentity(account)),
      td("", account.pool_label || poolLabel(account.pool)),
      td("", statusChip(account)),
      td(account.last_error_summary ? "" : "dash", account.last_error_summary || "—"),
      td("right mono-value", account.last_success || account.cooldown_until || "—"),
      td("", accountActionButtons(account))
    );
    body.append(row);
  }
  applyActionAvailability();
}

function td(className, child) {
  const cell = document.createElement("td");
  if (className) {
    cell.className = className;
  }
  if (child instanceof Node) {
    cell.append(child);
  } else {
    cell.textContent = String(child);
  }
  return cell;
}

function checkbox() {
  const node = document.createElement("div");
  node.className = "checkbox";
  node.title = "Bulk lifecycle actions are deferred in this contour.";
  return node;
}

function accountIdentity(account) {
  const wrap = document.createElement("div");
  const main = document.createElement("div");
  main.className = "account-main";
  main.textContent = account.id || "unknown-account";
  const sub = document.createElement("div");
  sub.className = "account-sub";
  sub.textContent = redactAccountLabel(account.label || account.id || "redacted account");
  wrap.append(main, sub);
  return wrap;
}

function statusChip(account) {
  const chip = document.createElement("span");
  const visual = ACCOUNT_VISUAL_CLASS[account.visual_state] || "neutral";
  chip.className = `chip ${visual}`;
  const dot = document.createElement("span");
  dot.className = "dot";
  const label = document.createElement("span");
  label.textContent = account.status_label || statusLabel(account.status);
  chip.append(dot, label);
  return chip;
}

function accountActionButtons(account) {
  const group = document.createElement("div");
  group.className = "account-action-group";
  group.append(accountActionButton(account, "validate_account", "Проверить"));
  if (account.pool !== "retired") {
    if (account.manual_hold) {
      group.append(accountActionButton(account, "release_account", "Снять hold"));
    } else {
      if (account.pool === "reserve") {
        group.append(accountActionButton(account, "promote_account", "В актив"));
      }
      if (account.pool === "active") {
        group.append(accountActionButton(account, "demote_account", "В резерв"));
      }
      group.append(accountActionButton(account, "hold_account", "Удержать"));
    }
  }
  return group;
}

function accountActionButton(account, uiAction, label) {
  const button = document.createElement("button");
  button.className = "button small account-action";
  button.type = "button";
  button.dataset.uiAction = uiAction;
  button.dataset.accountId = account.id || "";
  button.textContent = label;
  button.title = "Run an allowlisted account action. Accounts list refresh remains truth.";
  button.addEventListener("click", () => {
    maybeConfirmAndRun(uiAction, { account_id: button.dataset.accountId });
  });
  return button;
}

function poolLabel(pool) {
  return {
    active: "Активные",
    reserve: "Резерв",
    retired: "Выведен"
  }[pool] || pool || "Неизвестно";
}

function statusLabel(status) {
  return {
    healthy: "Работает",
    degraded: "Деградация",
    down: "Недоступен",
    unknown: "Неизвестно"
  }[status] || status || "Неизвестно";
}

function redactAccountLabel(label) {
  const value = String(label || "");
  if (!value.includes("@")) {
    return value
      .replaceAll("/Users/", "[redacted]/")
      .replaceAll("/Volumes/", "[redacted]/")
      .replaceAll("/tmp/", "[redacted]/")
      .replaceAll(".cli" + "-proxy-api", "[redacted]")
      .replaceAll(".co" + "dex", "[redacted]");
  }
  const [left, domain] = value.split("@");
  const tail = (domain || "account").split(".").pop();
  return `${left.slice(0, 3)}***@***.${tail || "account"}`;
}

function renderSnapshot(snapshot) {
  const validation = validateSnapshot(snapshot);
  const safeSnapshot = validation.ok ? snapshot : {
    ...FALLBACK_FIXTURE,
    state_id: "integration_failure",
    fixture_notice: `Fixture schema invalid: missing top [${validation.missingTop.join(", ")}], runtime [${validation.missingRuntime.join(", ")}]`
  };

  const runtime = safeSnapshot.runtime;
  const visualState = runtime.visual_state || safeSnapshot.state_id || "unknown";
  const source = safeSnapshot.source === "live_readonly" ? "live" : "fixture";
  const desktop = document.querySelector(".desktop");
  desktop.dataset.fixtureState = safeSnapshot.state_id || safeSnapshot.ui_state || visualState;
  desktop.dataset.source = source;

  const picker = document.getElementById("statePicker");
  picker.value = canonicalState(safeSnapshot.state_id || safeSnapshot.ui_state);
  picker.disabled = source === "live";
  document.getElementById("sourcePicker").value = source;
  document.getElementById("brandCaption").textContent = source === "live"
    ? "live read-only web preview"
    : "fixture-backed web preview";
  setSourceCopy(source);
  document.getElementById("refreshFixture").lastElementChild.textContent = source === "live"
    ? "Обновить live"
    : "Обновить fixture";

  const runtimeChip = document.getElementById("runtimeChip");
  setClassName(runtimeChip, "chip", visualState);
  runtimeChip.lastElementChild.textContent = runtime.status_label;

  const sidebarDot = document.getElementById("sidebarDot");
  setClassName(sidebarDot, "dot", visualState);
  text("sidebarStatus", runtime.human_message);

  text("desiredMode", modeLabel(runtime.desired_mode));
  text("effectiveMode", modeLabel(runtime.effective_mode));
  text("endpoint", runtime.endpoint);
  text("lastError", runtime.last_error || "нет");
  document.getElementById("lastError").className = runtime.last_error ? "last-error problem" : "last-error ok";

  renderModeSegments(runtime);

  const pool = safeSnapshot.pool_summary;
  text("activeCount", pool.active);
  text("reserveCount", pool.reserve);
  text("holdCount", pool.hold);
  text("problemCount", pool.problem);
  text("activeNote", pool.active_note);
  text("reserveNote", pool.reserve_note);
  text("holdNote", pool.hold_note);
  text("problemNote", pool.problem_note);

  const banner = document.getElementById("fixtureBanner");
  const bannerState = safeSnapshot.has_warnings && visualState === "healthy" ? "degraded" : visualState;
  setClassName(banner, "fixture-banner", bannerState);
  banner.textContent = snapshotNotice(safeSnapshot);

  renderEvents(safeSnapshot.events || []);
}

async function setFixtureState(stateId, updateUrl = false) {
  setSourceCopy("fixture");
  const state = canonicalState(stateId);
  const fixture = await loadFixture(state);
  if (updateUrl) {
    const url = new URL(window.location.href);
    url.searchParams.set("state", state);
    url.searchParams.set("source", "fixture");
    window.history.replaceState({}, "", url);
  }
  if (currentScreen() === "accounts") {
    renderAccountsSnapshot(accountsFixtureFromOverview(fixture));
  } else {
    renderSnapshot(fixture);
  }
}

async function setLiveReadonly(updateUrl = false) {
  setSourceCopy("live");
  const snapshot = currentScreen() === "accounts"
    ? await loadAccountsReadonly()
    : await loadLiveReadonly();
  if (updateUrl) {
    const url = new URL(window.location.href);
    url.searchParams.set("source", "live");
    window.history.replaceState({}, "", url);
  }
  if (currentScreen() === "accounts") {
    renderAccountsSnapshot(snapshot);
  } else {
    renderSnapshot(snapshot);
  }
  setSourceCopy("live");
  return snapshot;
}

function refreshCurrentSource() {
  const source = document.getElementById("sourcePicker").value;
  if (source === "live") {
    return setLiveReadonly(false);
  }
  return setFixtureState(document.getElementById("statePicker").value, false);
}

document.addEventListener("DOMContentLoaded", async () => {
  const sourcePicker = document.getElementById("sourcePicker");
  const picker = document.getElementById("statePicker");
  const refresh = document.getElementById("refreshFixture");
  const initialState = stateFromLocation();
  const initialSource = sourceFromLocation();
  const initialScreen = screenFromLocation();
  await loadActionMetadata();
  applyActionAvailability();
  setScreen(initialScreen, false);
  sourcePicker.value = initialSource;
  picker.value = initialState;
  picker.addEventListener("change", () => setFixtureState(picker.value, true));
  for (const link of document.querySelectorAll("[data-screen-link]")) {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      setScreen(link.dataset.screenLink, true);
      refreshCurrentSource();
    });
  }
  for (const button of document.querySelectorAll(".live-action")) {
    button.addEventListener("click", () => maybeConfirmAndRun(button.dataset.uiAction));
  }
  document.getElementById("cancelAction").addEventListener("click", () => closeConfirmation());
  document.getElementById("confirmAction").addEventListener("click", () => confirmPendingAction());
  sourcePicker.addEventListener("change", () => {
    if (sourcePicker.value === "live") {
      setLiveReadonly(true);
    } else {
      setFixtureState(picker.value, true);
    }
  });
  refresh.addEventListener("click", () => refreshCurrentSource());
  if (initialSource === "live") {
    setLiveReadonly(false);
  } else {
    setFixtureState(initialState, false);
  }
});
