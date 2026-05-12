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

function fitPreviewToViewport() {
  const frameWidth = 1544;
  const frameHeight = 944;
  const margin = 56;
  const availableWidth = Math.max(320, window.innerWidth - margin);
  const availableHeight = Math.max(320, window.innerHeight - margin);
  const scale = Math.min(1, availableWidth / frameWidth, availableHeight / frameHeight);
  document.documentElement.style.setProperty("--preview-scale", scale.toFixed(4));
}

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

function validateFixture(fixture) {
  const requiredTop = ["schema_version", "state_id", "runtime", "pool_summary", "events"];
  const missingTop = requiredTop.filter((key) => !(key in fixture));
  const runtime = fixture.runtime || {};
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

function renderFixture(fixture) {
  const validation = validateFixture(fixture);
  const safeFixture = validation.ok ? fixture : {
    ...FALLBACK_FIXTURE,
    state_id: "integration_failure",
    fixture_notice: `Fixture schema invalid: missing top [${validation.missingTop.join(", ")}], runtime [${validation.missingRuntime.join(", ")}]`
  };

  const runtime = safeFixture.runtime;
  const visualState = runtime.visual_state || safeFixture.state_id || "unknown";
  document.querySelector(".desktop").dataset.fixtureState = safeFixture.state_id;

  const picker = document.getElementById("statePicker");
  picker.value = canonicalState(safeFixture.state_id);

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

  const pool = safeFixture.pool_summary;
  text("activeCount", pool.active);
  text("reserveCount", pool.reserve);
  text("holdCount", pool.hold);
  text("problemCount", pool.problem);
  text("activeNote", pool.active_note);
  text("reserveNote", pool.reserve_note);
  text("holdNote", pool.hold_note);
  text("problemNote", pool.problem_note);

  const banner = document.getElementById("fixtureBanner");
  setClassName(banner, "fixture-banner", visualState);
  banner.textContent = safeFixture.fixture_notice;

  renderEvents(safeFixture.events || []);
}

async function setFixtureState(stateId, updateUrl = false) {
  const state = canonicalState(stateId);
  const fixture = await loadFixture(state);
  if (updateUrl) {
    const url = new URL(window.location.href);
    url.searchParams.set("state", state);
    window.history.replaceState({}, "", url);
  }
  renderFixture(fixture);
}

document.addEventListener("DOMContentLoaded", () => {
  fitPreviewToViewport();
  const picker = document.getElementById("statePicker");
  const refresh = document.getElementById("refreshFixture");
  const initialState = stateFromLocation();
  picker.value = initialState;
  picker.addEventListener("change", () => setFixtureState(picker.value, true));
  refresh.addEventListener("click", () => setFixtureState(picker.value, false));
  window.addEventListener("resize", fitPreviewToViewport);
  setFixtureState(initialState, false);
});
