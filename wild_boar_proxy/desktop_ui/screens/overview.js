// SPDX-FileCopyrightText: 2026 Kirill Ponomarev
// SPDX-License-Identifier: AGPL-3.0-or-later

const FIXTURE_DIR = "./fixtures";
const DEFAULT_FIXTURE = "overview_healthy";
const DEFAULT_LIVE_SNAPSHOT = "./live/overview_live_snapshot.json";
const TRANSPORT_GATE = "ADMITTED_LOCAL_ONLY";
const TRANSPORT_ROUTE = "/overview-bridge";
const TRANSPORT_HOST = "127.0.0.1";
const SIMULATED_BRIDGE_SOURCE = "ui_desktop_html_overview_implantation_simulated";

const BRIDGE_ACTIONS = Object.freeze({
  "launch-client": "launch_client",
  smoke: "run_smoke",
  stable: "switch_stable",
  sync: "run_sync"
});

const FORBIDDEN_BRIDGE_FIELDS = Object.freeze([
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
  "cwd"
]);

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

function formatObservedAt(value) {
  if (!value) return "нет данных о времени";
  const observed = new Date(value);
  if (Number.isNaN(observed.getTime())) return value;
  return observed.toLocaleString("ru-RU", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
    second: "2-digit"
  });
}

function renderRefreshMeta(payload, prefix = "Обновлено") {
  setText("refresh-meta", `${prefix}: ${formatObservedAt(payload?.observed_at_utc)}`);
}

function renderTransportFailure(message, state = "transport_error") {
  setBridgeState(state);
  setText("truth-source", "transport error");
  setText("last-error", message);
  renderToast(message);
}

function setBridgeState(state) {
  document.querySelector(".window").dataset.bridgeState = state;
}

function renderIntegrationFailure(message) {
  renderChip("integration-failure");
  renderModes({ desired_mode: "-", effective_mode: "-" });
  renderCounts({ account_summary: {} });
  setText("endpoint", "-");
  setText("last-error", message);
  setText("truth-source", "integration-failure");
  setText("refresh-meta", "Обновление не удалось");
  setBridgeState("bridge_integration_failure");
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
  setBridgeState(payload.live_mode ? "live_idle" : "fixture");
  renderEvents(payload.events);
  renderRefreshMeta(payload, payload.live_mode ? "Обновлено из backend" : "Фикстура");
  renderToast(payload.notice || "");
}

function isAdmittedBridgeAction(action) {
  return action === "refresh" || Object.prototype.hasOwnProperty.call(BRIDGE_ACTIONS, action);
}

function setActionPolicy(mode, bridgeMode = "none") {
  document.querySelectorAll("[data-fixture-action]").forEach((node) => {
    const action = node.dataset.fixtureAction;
    const bridgeActive = bridgeMode === "simulated" || bridgeMode === "transport";
    const allowed = action === "refresh" || (mode === "live" && bridgeActive && isAdmittedBridgeAction(action));
    node.disabled = mode === "live" && !allowed;
    node.title = mode === "live" && !allowed ? "Deferred in overview implantation gate" : "";
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

function hasForbiddenBridgeFields(request) {
  return FORBIDDEN_BRIDGE_FIELDS.some((field) => Object.prototype.hasOwnProperty.call(request, field));
}

function buildBridgeRequest(action, confirmed = false) {
  if (action === "refresh") {
    return { operation_id: "refresh_overview" };
  }
  const actionId = BRIDGE_ACTIONS[action];
  if (!actionId) {
    return null;
  }
  return {
    operation_id: "run_overview_action",
    action_id: actionId,
    confirmed: confirmed === true
  };
}

function validateTransportEndpoint(candidate) {
  if (typeof candidate !== "string" || !candidate.trim()) {
    return { ok: false, error: "transport endpoint is not configured" };
  }
  let parsed;
  try {
    parsed = new URL(candidate, window.location.href);
  } catch (error) {
    return { ok: false, error: `transport endpoint is invalid: ${error.message}` };
  }
  if (parsed.protocol !== "http:") {
    return { ok: false, error: "transport endpoint protocol is not admitted" };
  }
  if (parsed.hostname !== TRANSPORT_HOST) {
    return { ok: false, error: "transport endpoint host is not admitted" };
  }
  if (parsed.pathname !== TRANSPORT_ROUTE) {
    return { ok: false, error: "transport endpoint route is not admitted" };
  }
  if (parsed.username || parsed.password || parsed.hash || parsed.search) {
    return { ok: false, error: "transport endpoint contains forbidden URL components" };
  }
  return { ok: true, endpoint: parsed.toString() };
}

function getConfiguredTransportEndpoint(params) {
  const injected = window.__WBP_OVERVIEW_TRANSPORT_ENDPOINT;
  if (typeof injected === "string" && injected.trim()) {
    return validateTransportEndpoint(injected);
  }
  if (params.get("bridge") === "transport" && params.has("transport")) {
    return validateTransportEndpoint(params.get("transport"));
  }
  return { ok: false, error: "transport endpoint is not configured" };
}

async function callTransportBridge(endpoint, request) {
  if (!request || typeof request !== "object") {
    throw new Error("bridge request is invalid");
  }
  if (hasForbiddenBridgeFields(request)) {
    throw new Error("bridge request contains forbidden fields");
  }
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    cache: "no-store"
  });
  let packet;
  try {
    packet = await response.json();
  } catch (error) {
    throw new Error(`transport response is not JSON: ${error.message}`);
  }
  if (!packet || typeof packet !== "object") {
    throw new Error("transport response is not a JSON object");
  }
  if (!response.ok || packet.status !== "ok") {
    const message = packet.human_message || packet.machine_error_code || "transport bridge request failed";
    const error = new Error(message);
    error.packet = packet;
    throw error;
  }
  return packet;
}

function simulatedBridgeResponse(request) {
  if (!request || typeof request !== "object") {
    return {
      source: SIMULATED_BRIDGE_SOURCE,
      status: "error",
      machine_error_code: "SIMULATED_BRIDGE_REQUEST_INVALID",
      human_message: "Simulated bridge request is invalid.",
      snapshot_written: false,
      action_result: null
    };
  }
  if (hasForbiddenBridgeFields(request)) {
    return {
      source: SIMULATED_BRIDGE_SOURCE,
      operation_id: request.operation_id || "",
      status: "error",
      machine_error_code: "SIMULATED_BRIDGE_FORBIDDEN_FIELD",
      human_message: "Simulated bridge request contains a forbidden field.",
      snapshot_written: false,
      action_result: null
    };
  }
  if (request.operation_id === "refresh_overview") {
    return {
      source: SIMULATED_BRIDGE_SOURCE,
      operation_id: "refresh_overview",
      status: "ok",
      machine_error_code: "SIMULATED_TRANSPORT_GATE_RED",
      human_message: "Transport gate is RED; refresh is simulated in browser lifecycle only.",
      snapshot_written: false,
      action_result: null
    };
  }
  if (request.operation_id === "run_overview_action" && !request.confirmed) {
    return {
      source: SIMULATED_BRIDGE_SOURCE,
      operation_id: "run_overview_action",
      status: "error",
      machine_error_code: "CONFIRMATION_REQUIRED",
      human_message: "Confirmation is required before this simulated action can proceed.",
      snapshot_written: false,
      action_result: null
    };
  }
  if (request.operation_id === "run_overview_action" && Object.values(BRIDGE_ACTIONS).includes(request.action_id)) {
    return {
      source: SIMULATED_BRIDGE_SOURCE,
      operation_id: "run_overview_action",
      status: "ok",
      machine_error_code: "SIMULATED_TRANSPORT_GATE_RED",
      human_message: "Transport gate is RED; action lifecycle is simulated and no backend action ran.",
      snapshot_written: false,
      action_result: {
        status: "ok",
        action_id: request.action_id,
        simulated: true
      }
    };
  }
  return {
    source: SIMULATED_BRIDGE_SOURCE,
    operation_id: request.operation_id || "",
    status: "error",
    machine_error_code: "SIMULATED_BRIDGE_OPERATION_FORBIDDEN",
    human_message: "Simulated bridge operation is not admitted.",
    snapshot_written: false,
    action_result: null
  };
}

async function runSimulatedBridgeAction(action) {
  setBridgeState("bridge_pending");
  const request = buildBridgeRequest(action, false);
  if (!request) {
    setBridgeState("deferred");
    renderToast(`Deferred in this contour: ${action}`);
    return;
  }
  if (request.operation_id === "run_overview_action") {
    const confirmed = window.confirm(`Simulate ${BRIDGE_ACTIONS[action]}? No backend command will run.`);
    request.confirmed = confirmed === true;
  }
  const response = simulatedBridgeResponse(request);
  if (response.status !== "ok") {
    setBridgeState(response.machine_error_code === "CONFIRMATION_REQUIRED" ? "confirmation_required" : "bridge_command_error");
    renderToast(response.human_message);
    return;
  }
  setBridgeState("bridge_success_refreshing");
  await setLiveSnapshot(new URLSearchParams(window.location.search).get("live") || DEFAULT_LIVE_SNAPSHOT);
  setBridgeState("transport_unavailable");
  renderToast(response.human_message);
}

async function runTransportBridgeAction(action) {
  setBridgeState("bridge_pending");
  setText("refresh-meta", "Обновляем данные...");
  const params = new URLSearchParams(window.location.search);
  const endpoint = getConfiguredTransportEndpoint(params);
  if (!endpoint.ok) {
    renderTransportFailure(endpoint.error);
    return;
  }
  const request = buildBridgeRequest(action, false);
  if (!request) {
    setBridgeState("deferred");
    renderToast(`Deferred in this contour: ${action}`);
    return;
  }
  if (request.operation_id === "run_overview_action") {
    const confirmed = window.confirm(`Run ${BRIDGE_ACTIONS[action]} through admitted local transport?`);
    request.confirmed = confirmed === true;
  }
  try {
    const response = await callTransportBridge(endpoint.endpoint, request);
    setBridgeState("bridge_success_refreshing");
    await setLiveSnapshot(params.get("live") || DEFAULT_LIVE_SNAPSHOT);
    setBridgeState("transport_live");
    renderToast(response.human_message || "Overview bridge request completed.");
  } catch (error) {
    const code = error.packet?.machine_error_code;
    renderTransportFailure(error.message, code === "CONFIRMATION_REQUIRED" ? "confirmation_required" : "bridge_command_error");
  }
}

async function loadLiveSnapshot(source) {
  const response = await fetch(source, { cache: "no-store" });
  if (!response.ok) throw new Error(`live snapshot load failed: ${source}`);
  return response.json();
}

async function setLiveSnapshot(source) {
  const bridgeMode = new URLSearchParams(window.location.search).get("bridge");
  setActionPolicy("live", bridgeMode);
  try {
    const payload = await loadLiveSnapshot(source);
    if (!payload || payload.source !== "ui_desktop_html_live_overview_snapshot" || payload.synthetic !== false) {
      throw new Error("live snapshot source is not admitted");
    }
    renderOverview(payload);
    if (bridgeMode === "simulated") {
      setText("truth-source", "live snapshot + simulated bridge");
      setBridgeState("transport_unavailable");
    } else if (bridgeMode === "transport") {
      setText("truth-source", "live snapshot + admitted transport");
      setBridgeState("transport_live");
    }
  } catch (error) {
    renderIntegrationFailure(error.message);
  }
}

document.querySelectorAll("[data-fixture-action]").forEach((node) => {
  node.addEventListener("click", () => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("mode") === "live" && params.get("bridge") === "simulated") {
      runSimulatedBridgeAction(node.dataset.fixtureAction);
      return;
    }
    if (params.get("mode") === "live" && params.get("bridge") === "transport") {
      runTransportBridgeAction(node.dataset.fixtureAction);
      return;
    }
    if (node.dataset.fixtureAction === "refresh") {
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
window.__overviewImplantationGate = Object.freeze({
  transportGate: TRANSPORT_GATE,
  admittedActions: Object.freeze({ ...BRIDGE_ACTIONS }),
  forbiddenFields: FORBIDDEN_BRIDGE_FIELDS,
  buildBridgeRequest,
  validateTransportEndpoint,
  getConfiguredTransportEndpoint,
  simulatedBridgeResponse
});

if (params.get("mode") === "live") {
  setLiveSnapshot(params.get("live") || DEFAULT_LIVE_SNAPSHOT);
} else {
  setFixture(queryFixture || DEFAULT_FIXTURE);
}
