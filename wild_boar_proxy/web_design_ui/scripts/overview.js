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

async function runUiAction(uiAction) {
  setActionPanel({
    ui_action: uiAction,
    action_role: "running",
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
      body: JSON.stringify({ ui_action: uiAction })
    });
    if (!response.ok) {
      throw new Error(`action http ${response.status}`);
    }
    const payload = await response.json();
    setActionPanel(payload);
  } catch (error) {
    setActionPanel({
      ui_action: uiAction,
      action_role: "integration_failure",
      result: {
        status: "integration_failure",
        machine_error_code: "UI_ACTION_FETCH_FAILED",
        human_message: error.message,
        next_action: "retry",
        changed_files: []
      }
    });
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
  document.getElementById("sourceFooter").textContent = source === "live"
    ? "Live read-only · safe actions"
    : "UI preview · no live commands";
  document.getElementById("subtitleText").textContent = source === "live"
    ? "Первый экран подключен к живым read-only JSON-командам. Ниже доступны только безопасные действия."
    : "Визуальный перенос первого экрана. Данные ниже являются fixtures, а не runtime truth.";
}

function setActionPanel(payload) {
  const result = payload.result || {};
  text("actionUiAction", payload.ui_action || "unknown");
  text("actionRole", payload.action_role || "unknown");
  text("actionStatus", result.status || payload.status || "unknown");
  text("actionMachineCode", result.machine_error_code || "-");
  text("actionMessage", result.human_message || "-");
  text("actionNextAction", result.next_action || "none");
  text("actionChangedFiles", JSON.stringify(result.changed_files || []));
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
  renderSnapshot(fixture);
}

async function setLiveReadonly(updateUrl = false) {
  setSourceCopy("live");
  const snapshot = await loadLiveReadonly();
  if (updateUrl) {
    const url = new URL(window.location.href);
    url.searchParams.set("source", "live");
    window.history.replaceState({}, "", url);
  }
  renderSnapshot(snapshot);
  setSourceCopy("live");
}

function refreshCurrentSource() {
  const source = document.getElementById("sourcePicker").value;
  if (source === "live") {
    return setLiveReadonly(false);
  }
  return setFixtureState(document.getElementById("statePicker").value, false);
}

document.addEventListener("DOMContentLoaded", () => {
  const sourcePicker = document.getElementById("sourcePicker");
  const picker = document.getElementById("statePicker");
  const refresh = document.getElementById("refreshFixture");
  const initialState = stateFromLocation();
  const initialSource = sourceFromLocation();
  sourcePicker.value = initialSource;
  picker.value = initialState;
  picker.addEventListener("change", () => setFixtureState(picker.value, true));
  for (const button of document.querySelectorAll(".live-action")) {
    button.addEventListener("click", () => runUiAction(button.dataset.uiAction));
  }
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
