// SPDX-FileCopyrightText: 2026 Kirill Ponomarev
// SPDX-License-Identifier: AGPL-3.0-or-later

const FIXTURE_DIR = "./fixtures";
const DEFAULT_FIXTURE = "overview_healthy";
const DEFAULT_LIVE_SNAPSHOT = "./live/overview_live_snapshot.json";

const statusView = {
  healthy: { label: "Работает", sidebar: "Все системы работают нормально", chip: "green" },
  degraded: { label: "Деградация", sidebar: "Требуется внимание", chip: "amber" },
  down: { label: "Недоступно", sidebar: "Система недоступна", chip: "red" },
  stale: { label: "Устарело", sidebar: "Данные устарели", chip: "amber" },
  unknown: { label: "Неизвестно", sidebar: "Состояние неизвестно", chip: "neutral" },
  "integration-failure": { label: "Ошибка интеграции", sidebar: "Ошибка данных интерфейса", chip: "red" },
  error: { label: "Ошибка команды", sidebar: "Команда вернула ошибку", chip: "red" }
};

const modeLabels = {
  managed: "Управляемый",
  stable: "Стабильный"
};

const $ = (selector) => document.querySelector(selector);

function setText(selector, value) {
  const node = $(`[data-field="${selector}"]`);
  if (node) node.textContent = value ?? "-";
}

function normalizePacket(packet) {
  if (!packet || typeof packet !== "object") return null;
  if (packet.status === "ok" && packet.machine_error_code === "OK") return packet;
  return packet;
}

async function loadFixture(name) {
  const response = await fetch(`${FIXTURE_DIR}/${name}.json`, { cache: "no-store" });
  if (!response.ok) throw new Error(`fixture load failed: ${name}`);
  return response.json();
}

function renderChip(state) {
  const view = statusView[state] || statusView.unknown;
  const chip = $('[data-field="status-chip"]');
  chip.className = `chip ${view.chip}`;
  chip.innerHTML = `<span class="dot"></span><span>${view.label}</span>`;
  document.querySelector(".window").dataset.runtimeState = state;
  setText("runtime-label", view.label);
  setText("sidebar-status", view.sidebar);
}

function renderModes(modePacket) {
  const desired = modePacket?.desired_mode || "-";
  const effective = modePacket?.effective_mode || "-";
  setText("desired-mode", modeLabels[desired] || desired);
  setText("effective-mode", modeLabels[effective] || effective);
  document.querySelectorAll("[data-mode-option]").forEach((node) => {
    node.classList.toggle("active", node.dataset.modeOption === desired);
  });
}

function renderCounts(accountsPacket) {
  const summary = accountsPacket?.account_summary || {};
  setText("active-count", summary.active_count ?? 0);
  setText("reserve-count", summary.reserve_count ?? 0);
  setText("hold-count", summary.hold_count ?? 0);
  setText("problem-count", summary.problem_count ?? 0);
  setText("active-note", summary.active_note || "-");
  setText("reserve-note", summary.reserve_note || "-");
  setText("hold-note", summary.hold_note || "-");
  setText("problem-note", summary.problem_note || "-");
}

function renderEvents(events) {
  const list = $('[data-field="events"]');
  list.replaceChildren();
  for (const event of events || []) {
    const row = document.createElement("div");
    row.className = "log-row";
    row.innerHTML = `
      <span class="round-icon ${event.tone || "neutral"}">${event.icon || "•"}</span>
      <span>${event.message}</span>
      <time>${event.time}</time>
    `;
    list.appendChild(row);
  }
}

function renderToast(text) {
  const toast = $('[data-field="toast"]');
  if (!text) {
    toast.hidden = true;
    return;
  }
  toast.textContent = text;
  toast.hidden = false;
}

function renderIntegrationFailure(message) {
  renderChip("integration-failure");
  renderModes({ desired_mode: "-", effective_mode: "-" });
  renderCounts({ account_summary: {} });
  setText("endpoint", "-");
  setText("last-error", message);
  setText("truth-source", "integration-failure");
  renderEvents([{ tone: "red", icon: "!", message: "Overview integration failure", time: "local preview" }]);
  renderToast(message);
}

function renderOverview(payload) {
  const statusPacket = normalizePacket(payload.status_packet);
  const modePacket = normalizePacket(payload.mode_packet);
  const accountsPacket = normalizePacket(payload.accounts_packet);

  if (!statusPacket || !modePacket || !accountsPacket) {
    renderIntegrationFailure("missing fixture packet");
    return;
  }

  const state = payload.fixture_state || statusPacket.liveness || "unknown";
  renderChip(state);
  renderModes(modePacket);
  renderCounts(accountsPacket);
  setText("endpoint", statusPacket.endpoint || "-");
  setText("last-error", statusPacket.last_error || "нет");
  setText("truth-source", payload.live_mode ? "live snapshot" : "fixture-only");
  renderEvents(payload.events);
  renderToast(payload.notice || "");
}

function setActionPolicy(mode) {
  document.querySelectorAll("[data-fixture-action]").forEach((node) => {
    const action = node.dataset.fixtureAction;
    const allowed = action === "refresh";
    node.disabled = mode === "live" && !allowed;
    node.title = mode === "live" && !allowed ? "Deferred in live read contour" : "";
  });
}

async function setFixture(name) {
  setActionPolicy("fixture");
  try {
    const payload = await loadFixture(name);
    renderOverview(payload);
  } catch (error) {
    renderIntegrationFailure(error.message);
  }
}

async function loadLiveSnapshot(source) {
  const response = await fetch(source, { cache: "no-store" });
  if (!response.ok) throw new Error(`live snapshot load failed: ${source}`);
  return response.json();
}

async function setLiveSnapshot(source) {
  setActionPolicy("live");
  try {
    const payload = await loadLiveSnapshot(source);
    if (!payload || payload.source !== "ui_desktop_html_live_overview_snapshot" || payload.synthetic !== false) {
      throw new Error("live snapshot source is not admitted");
    }
    renderOverview(payload);
  } catch (error) {
    renderIntegrationFailure(error.message);
  }
}

document.querySelectorAll("[data-fixture-action]").forEach((node) => {
  node.addEventListener("click", () => {
    if (node.dataset.fixtureAction === "refresh") {
      const params = new URLSearchParams(window.location.search);
      if (params.get("mode") === "live") {
        setLiveSnapshot(params.get("live") || DEFAULT_LIVE_SNAPSHOT);
      } else {
        setFixture(params.get("fixture") || DEFAULT_FIXTURE);
      }
      return;
    }
    renderToast(`Deferred in this contour: ${node.dataset.fixtureAction}`);
  });
});

const params = new URLSearchParams(window.location.search);
const queryFixture = params.get("fixture");
window.setOverviewFixture = setFixture;
window.setOverviewLiveSnapshot = setLiveSnapshot;

if (params.get("mode") === "live") {
  setLiveSnapshot(params.get("live") || DEFAULT_LIVE_SNAPSHOT);
} else {
  setFixture(queryFixture || DEFAULT_FIXTURE);
}
