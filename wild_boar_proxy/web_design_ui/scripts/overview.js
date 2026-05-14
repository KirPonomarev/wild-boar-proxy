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
  fixture_notice: "Встроенное резервное демо-состояние. Это не подтверждённое состояние runtime.",
  runtime: {
    visual_state: "unknown",
    status_label: "Неизвестно",
    desired_mode: "managed",
    effective_mode: "unknown",
    endpoint: "unknown",
    machine_error_code: "fixture_fallback",
    human_message: "Файл демо-состояния не удалось загрузить.",
    last_error: "загрузка демо-состояния не удалась",
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
      message: "Загружено резервное демо-состояние; live-команды не выполнялись.",
      observed_at: "демо"
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

const ACTION_STATUS_VISUAL_CLASS = {
  ok: "green",
  running: "amber",
  command_error: "red",
  integration_failure: "red",
  invalid_json: "red",
  timeout: "amber",
  stale: "amber",
  degraded: "amber",
  down: "red",
  unknown: "neutral"
};

const SCREENS = ["overview", "accounts", "api-connections", "diagnostics", "settings", "setup", "select-client", "import-existing"];
const ACCOUNT_VISUAL_CLASS = {
  green: "green",
  blue: "blue",
  amber: "amber",
  red: "red",
  neutral: "neutral"
};
const ACTION_LEDGER_LIMIT = 5;
const BROWSER_ACTION_PAYLOAD_KEYS = ["account_id", "route_id"];

const CONFIRMATION_POLICY = {
  sync_runtime: {
    severity: "medium",
    policy: "operator-request",
    warning: "Это запрашивает ограниченную синхронизацию. Подтверждением остаётся обновлённый JSON-пакет."
  },
  set_mode_stable: {
    severity: "medium",
    policy: "mode-request",
    warning: "Это запрашивает желаемый stable mode. Фактический режим должен быть подтверждён обновлённым JSON."
  },
  set_mode_managed: {
    severity: "medium",
    policy: "mode-request",
    warning: "Это запрашивает желаемый managed mode. Фактический режим должен быть подтверждён обновлённым JSON."
  },
  launch_client_dispatch: {
    severity: "high",
    policy: "bounded-dispatch",
    warning: "Это запрашивает только server-owned запуск приложения. Это не доказывает старт приложения или здоровье runtime."
  },
  onboard_account: {
    severity: "high",
    policy: "account-admission",
    warning: "Это может запустить внешнюю авторизацию. Успех с размещением сначала в резерв требует доказательства в пакете команды."
  },
  validate_account: {
    severity: "medium",
    policy: "account-verification",
    warning: "Это проверяет один аккаунт. Подтверждением пула остаётся обновлённый accounts JSON."
  },
  promote_account: {
    severity: "high",
    policy: "account-placement",
    warning: "Это запрашивает перевод в active. Это не доказательство ёмкости и не evidence готовности."
  },
  demote_account: {
    severity: "medium",
    policy: "account-placement",
    warning: "Это запрашивает перевод в reserve. Подтверждением остаётся обновлённый accounts JSON."
  },
  hold_account: {
    severity: "medium",
    policy: "account-hold",
    warning: "Это запрашивает ручную паузу. Подтверждением остаётся обновлённый accounts JSON."
  },
  release_account: {
    severity: "medium",
    policy: "account-hold",
    warning: "Это запрашивает снятие ручной паузы. Подтверждением остаётся обновлённый accounts JSON."
  },
  retire_account: {
    severity: "critical",
    policy: "terminal-account-lifecycle",
    warning: "Это запрашивает терминальный вывод аккаунта из lifecycle. Это не удаление и не путь возврата."
  },
  api_route_validate: {
    severity: "medium",
    policy: "api-route-validate",
    warning: "Это проверяет маршрут у провайдера. Это не утверждение состояния runtime."
  },
  api_route_check: {
    severity: "high",
    policy: "api-route-check",
    warning: "Это отправляет проверочный запрос через маршрут. Это не утверждение состояния runtime."
  },
  api_route_allow: {
    severity: "high",
    policy: "api-route-allow",
    warning: "Это запрашивает разрешение маршрута. Подтверждением остаётся ответ сервера плюс обновлённый JSON."
  },
  api_route_disable: {
    severity: "high",
    policy: "api-route-disable",
    warning: "Это запрашивает отключение маршрута. Подтверждением остаётся ответ сервера плюс обновлённый JSON."
  },
  api_route_remove: {
    severity: "critical",
    policy: "api-route-registry-cleanup",
    warning: "Удаляет только отключённую route registry запись после server preflight. Не меняет traffic, primary route, failover или runtime readiness."
  },
  api_route_profile: {
    severity: "medium",
    policy: "api-route-profile-packet",
    warning: "Это показывает профильный пакет поддержки. Это не настройка Codex, не готовность listener и не готовность runtime."
  },
  api_route_evidence_capture: {
    severity: "high",
    policy: "api-route-local-evidence",
    warning: "Это создаёт локальный support artifact. UI показывает только метаданные пакета команды и не читает evidence file."
  }
};

const CONSERVATIVE_CONFIRMATION_POLICY = {
  severity: "critical",
  policy: "metadata-fallback",
  warning: "Метаданные действия неполные. Считайте действие рискованным и опирайтесь только на ответ сервера плюс обновлённый JSON."
};

let actionMetadata = {};
let pendingConfirmedAction = null;
let confirmationInFlight = false;
let currentAccountsSnapshot = null;
let selectedAccountId = "";
let actionLedger = [];

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
      fixture_notice: `Live-запрос только для чтения не удался: ${error.message}`,
      runtime: {
        ...FALLBACK_FIXTURE.runtime,
        visual_state: "integration_failure",
        status_label: "Ошибка интеграции",
        machine_error_code: "UI_LIVE_READONLY_FETCH_FAILED",
        human_message: "Live-запрос только для чтения не удался.",
        last_error: error.message,
        observed_at_utc: "live-readonly"
      },
      events: [
        {
          level: "red",
          message: "Live-запрос только для чтения не удался.",
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
        human_message: "Запрос аккаунтов только для чтения не удался.",
        machine_error_code: "UI_ACCOUNTS_READONLY_FETCH_FAILED",
        last_error: error.message
      },
      accounts: []
    };
  }
}

async function loadApiConnectionsReadonly() {
  try {
    const response = await fetch("api/api-connections-readonly", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`api-connections http ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    return {
      schema_version: 1,
      status: "integration_failure",
      source: "api_connections_readonly",
      primary_truth_ok: false,
      privacy: {
        redacted: true,
        raw_command_packet_included: false,
        forbidden_fields_excluded: ["secret_references", "tokens", "raw_paths", "raw_logs"]
      },
      summary: {
        routes_count: 0,
        enabled_count: 0,
        attention_count: 0,
        latest_check: "",
        human_message: "Не удалось загрузить API-подключения только для чтения.",
        machine_error_code: "UI_API_CONNECTIONS_FETCH_FAILED",
        last_error: error.message
      },
      adapter: {
        foundation_phase: "unknown",
        adapter_runtime_available: false,
        lifecycle_mode: "unknown",
        adapter_state: "unknown",
        listener_proven: false,
        runtime_claim_blocked: true,
        profile_ready: false,
        local_token_present: false,
        observed_routes_count: 0,
        models_source: "integration_failure"
      },
      routes: []
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
    human_meaning: "Метаданные действия не удалось загрузить.",
    action_role: "unknown",
    mutates_runtime: true,
    confirmation_required: true,
    post_action_refresh_required: true,
    action_claim_scope: "unknown",
    available: false,
    unavailable_reason: "Метаданные действия не удалось загрузить."
  };
}

function confirmationPolicyFor(uiAction, metadata) {
  const policy = CONFIRMATION_POLICY[uiAction];
  if (!policy || metadata.available === false || metadata.confirmation_required !== true) {
    return {
      ...CONSERVATIVE_CONFIRMATION_POLICY,
      warning: policy?.warning || CONSERVATIVE_CONFIRMATION_POLICY.warning
    };
  }
  return policy;
}

function actionDisplayState(payload, refreshState = "none") {
  const result = payload.result || {};
  const status = String(payload.status || result.status || "unknown");
  let displayState = status;
  if (refreshState === "failed" && status === "ok" && payload.post_action_refresh_required) {
    displayState = "stale";
  }
  const visualClass = ACTION_STATUS_VISUAL_CLASS[displayState] || (
    displayState === "ok" ? "green" : "red"
  );
  return {
    status,
    displayState,
    visualClass,
    truthNote: actionTruthNote(payload, displayState, refreshState)
  };
}

function actionTruthNote(payload, displayState, refreshState) {
  if (displayState === "running") {
    return "Запрос действия выполняется. UI не изменял подтверждённое состояние runtime.";
  }
  if (displayState === "ok" && payload.post_action_refresh_required) {
    return "Пакет действия сообщил ok; каноническое состояние runtime требует обновлённого JSON.";
  }
  if (displayState === "ok") {
    return "Пакет действия сообщил ok. Этот журнал не является отдельным источником runtime truth.";
  }
  if (displayState === "stale" || refreshState === "failed") {
    return "Обновление после действия не удалось или устарело. Не считайте прежнее состояние UI зелёным runtime truth.";
  }
  if (displayState === "timeout") {
    return "Запрос истёк по времени. Это recoverable ошибка интеграции, а не успех.";
  }
  if (displayState === "invalid_json") {
    return "Endpoint вернул invalid JSON. Это жёсткая ошибка интеграции, а не успех.";
  }
  if (displayState === "command_error") {
    return "Строгий JSON-пакет сообщил command_error. UI не должен показывать это как успех.";
  }
  if (displayState === "integration_failure") {
    return "Ошибка интеграции UI/server. Успех команды не выводится по предположению.";
  }
  if (displayState === "degraded" || displayState === "down" || displayState === "unknown") {
    return `Журнал действия в состоянии ${displayState}; это не healthy runtime truth.`;
  }
  return "Состояние действия не ok. UI не должен выводить успех по предположению.";
}

async function runUiAction(uiAction, extraPayload = {}) {
  const requestPayload = boundedUiActionPayload(uiAction, extraPayload);
  setActionsBusy(true);
  setActionPanel({
    ui_action: uiAction,
    action_role: "running",
    account_id: requestPayload.account_id || "",
    route_id: requestPayload.route_id || "",
    post_action_refresh_required: false,
    result: {
      status: "running",
      machine_error_code: "RUNNING",
      human_message: "Действие выполняется.",
      next_action: "wait",
      changed_files: []
    }
  });
  try {
    const response = await fetch("api/action", {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestPayload)
    });
    if (!response.ok) {
      throw new Error(`action http ${response.status}`);
    }
    const payload = await response.json();
    setActionPanel(payload);
    if (payload.post_action_refresh_required) {
      const refreshTarget = currentScreen() === "accounts"
        ? "accounts"
        : (
          currentScreen() === "api-connections"
            ? "api-connections"
            : (currentScreen() === "settings" ? "settings" : "overview")
        );
      text("actionRefreshStatus", `обновление live ${refreshTarget}`);
      const refreshed = await setLiveReadonly(false);
      if (refreshed.status === "ok") {
        text("actionRefreshStatus", "live-обновление выполнено");
      } else {
        setActionPanel(payload, "failed");
      }
    }
  } catch (error) {
    const timeoutFailure = error.name === "AbortError" || String(error.message || "").toLowerCase().includes("timeout");
    const failureStatus = error instanceof SyntaxError ? "invalid_json" : (timeoutFailure ? "timeout" : "integration_failure");
    const machineCode = error instanceof SyntaxError
      ? "UI_ACTION_INVALID_JSON"
      : (timeoutFailure ? "UI_ACTION_TIMEOUT" : "UI_ACTION_FETCH_FAILED");
    setActionPanel({
      ui_action: uiAction,
      action_role: "integration_failure",
      account_id: requestPayload.account_id || "",
      route_id: requestPayload.route_id || "",
      post_action_refresh_required: false,
      result: {
        status: failureStatus,
        machine_error_code: machineCode,
        human_message: error.message,
        next_action: "retry",
        changed_files: []
      }
    });
  } finally {
    setActionsBusy(false);
  }
}

function boundedUiActionPayload(uiAction, extraPayload = {}) {
  const payload = { ui_action: uiAction };
  for (const key of BROWSER_ACTION_PAYLOAD_KEYS) {
    if (Object.prototype.hasOwnProperty.call(extraPayload, key) && typeof extraPayload[key] === "string") {
      payload[key] = extraPayload[key];
    }
  }
  return payload;
}

function applyActionAvailability() {
  for (const button of document.querySelectorAll(".live-action, .account-action, .onboard-action, .api-route-action")) {
    const metadata = metadataFor(button.dataset.uiAction);
    const requiresLive = (
      button.classList.contains("account-action")
      || button.classList.contains("onboard-action")
      || button.classList.contains("api-route-action")
    );
    const isLiveSource = document.querySelector(".desktop").dataset.source === "live";
    const routeEnabled = button.dataset.routeEnabled !== "false";
    const routeStateRequirement = button.dataset.routeStateRequirement || "any";
    const routeStateAllowed = routeStateRequirement === "disabled"
      ? !routeEnabled
      : (routeStateRequirement === "enabled" ? routeEnabled : true);
    const available = metadata.available !== false && (!requiresLive || isLiveSource) && routeStateAllowed;
    button.disabled = !available;
    button.dataset.available = available ? "true" : "false";
    button.title = available
      ? ""
      : (
        !routeStateAllowed
          ? (
            routeStateRequirement === "disabled"
              ? "Маршрут уже разрешён. Это действие доступно только для отключённых маршрутов."
              : "Маршрут отключён. Это действие доступно только для разрешённых маршрутов."
          )
          : (
            requiresLive && !isLiveSource
              ? "Переключите экран на live-источник перед выполнением действий."
              : (metadata.unavailable_reason || "Действие недоступно")
          )
      );
  }
  updateSettingsActionMetadata();
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
      return "Ошибка интеграции live only-read. Предыдущие healthy-данные не переиспользуются.";
    }
    if (snapshot.has_warnings) {
      return `Live-просмотр только для чтения с предупреждениями. ${warningSummary(snapshot.warnings || [])}`;
    }
    return "Live-просмотр только для чтения. Истина runtime приходит из строгих пакетов команд.";
  }
  return snapshot.fixture_notice || "Только демо-просмотр. Команды не выполняются, runtime-файлы не читаются.";
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
  if (!events.length) {
    const empty = document.createElement("div");
    empty.className = "log-empty";
    empty.textContent = "События не предоставлены текущим JSON-пакетом.";
    list.append(empty);
    return;
  }
  for (const event of events.slice(0, 2)) {
    const row = document.createElement("div");
    row.className = "log-row";

    const icon = document.createElement("span");
    const level = event.level || "neutral";
    icon.className = `round-icon ${level}`;
    icon.textContent = EVENT_ICON[level] || EVENT_ICON.neutral;

    const message = document.createElement("span");
    message.textContent = event.message || "Событие демо-состояния";

    const time = document.createElement("time");
    time.textContent = event.observed_at || "fixture";

    row.append(icon, message, time);
    list.append(row);
  }
}

function setSourceCopy(source) {
  const screen = currentScreen();
  const setupLike = ["setup", "select-client", "import-existing"].includes(screen);
  const sourceFooter = source === "live"
    ? (
      screen === "accounts"
        ? "Аккаунты · live только чтение"
        : (
          screen === "api-connections"
            ? "API-подключения · список маршрутов"
            : (
          screen === "diagnostics"
            ? "Диагностика · пакет поддержки"
            : (
              screen === "settings"
                ? "Настройки · через пакеты команд"
                : (setupLike ? "Экраны настройки · отложенный каркас" : "Состояние · live только чтение")
            )
            )
        )
    )
    : "Предпросмотр UI · без live-команд";
  const subtitle = source === "live"
    ? (
      screen === "accounts"
        ? "Пул аккаунтов отображается из подтверждённого ответа команды. Действия доступны только после проверки допустимости."
        : (
          screen === "api-connections"
            ? "Маршруты API-подключений отображаются из пакетов команд. Разрешены только безопасные проверки маршрутов без мутации конфигурации."
            : (
          screen === "diagnostics"
            ? "Диагностика показывает сведения пакета поддержки. Фактическое здоровье системы проверяется отдельными командами."
            : (
              screen === "settings"
                ? "Настройки показывают наблюдаемую конфигурацию только для чтения. Доступные действия являются запросами, а не сохранением параметров."
                : (
                  setupLike
                    ? "Экраны настройки, выбора и импорта инертны в этом контуре. Они не запускают обнаружение, выбор или команды импорта."
                    : "Операторская сводка подключена к live-ответам команд. После действий состояние обновляется заново."
                )
            )
            )
        )
    )
    : (
      screen === "accounts"
        ? "Демо-просмотр экрана аккаунтов. Данные не являются фактическим состоянием системы."
        : (
          screen === "api-connections"
            ? "Демо-просмотр API-подключений. Кнопки проверок доступны только в live-режиме."
            : (
          screen === "diagnostics"
            ? "Демо-просмотр диагностики. Экспорт создаёт пакет поддержки, но не доказывает здоровье системы."
            : (
              screen === "settings"
                ? "Демо-просмотр настроек. Элементы либо только для чтения, либо отложены без безопасного действия."
                : (
                  setupLike
                    ? "Визуальный перенос каркаса настройки, выбора и импорта. Все рискованные элементы отключены; simulated truth нет."
                    : "Операторская сводка: фактическое состояние, режим работы, пул аккаунтов и последние события."
                )
            )
            )
        )
    );
  document.getElementById("sourceFooter").textContent = sourceFooter;
  document.getElementById("subtitleText").textContent = subtitle;
  updateDiagnosticsDetailSource(source);
}

function updateDiagnosticsDetailSource(source) {
  const fixtureOnly = source !== "live";
  const fixtureNodes = [
    document.getElementById("diagnosticsFixtureChart"),
    document.getElementById("diagnosticsFixtureRecords")
  ].filter(Boolean);
  const deferredNodes = [
    document.getElementById("diagnosticsHistoryDeferred"),
    document.getElementById("diagnosticsRecordsDeferred")
  ].filter(Boolean);
  for (const node of fixtureNodes) {
    node.hidden = !fixtureOnly;
  }
  for (const node of deferredNodes) {
    node.hidden = fixtureOnly;
  }
  const historyChip = document.getElementById("diagnosticsHistoryModeChip");
  const recordsChip = document.getElementById("diagnosticsRecordsModeChip");
  for (const chip of [historyChip, recordsChip]) {
    if (!chip) {
      continue;
    }
    chip.className = fixtureOnly ? "chip blue" : "chip amber";
    chip.lastElementChild.textContent = fixtureOnly ? "fixture/demo" : "deferred";
  }
}

function setActionPanel(payload, refreshState = "none") {
  const result = payload.result || {};
  const onboarding = result.onboarding || {};
  const changedFiles = Array.isArray(result.changed_files) ? result.changed_files : [];
  const display = actionDisplayState(payload, refreshState);
  const panel = document.getElementById("actionPanel");
  panel.className = `action-panel compact-action-panel ${display.visualClass}`;
  text("actionUiAction", payload.ui_action || "unknown");
  text("actionRole", payload.action_role || "unknown");
  text("actionAccountId", payload.account_id || payload.route_id || "-");
  text("actionStatus", display.status);
  text("actionDisplayState", display.displayState);
  text("actionMachineCode", result.machine_error_code || "-");
  text("actionMessage", result.human_message || "-");
  text("actionNextAction", result.next_action || "none");
  text("actionChangedFiles", `${changedFiles.length} записей метаданных`);
  text("actionSupportDetails", actionSupportDetails(payload));
  text(
    "actionRefreshStatus",
    refreshState === "failed"
      ? "live-обновление не удалось; состояние устарело"
      : (payload.post_action_refresh_required ? "требуется после действия" : "не требуется")
  );
  text("actionTruthNote", display.truthNote);
  text("actionOnboardingOutcome", onboarding.final_outcome || "-");
  text("actionOnboardingReserveProof", onboarding.reserve_first_proven === true ? "доказано" : (onboarding.ui_state || "-"));
  text("actionOnboardingBackend", onboarding.selected_backend_id || "-");
  recordActionLedgerEntry(payload, refreshState, display, changedFiles);
  if (payload.ui_action === "export_diagnostics") {
    renderDiagnosticsAction(payload);
  }
}

function recordActionLedgerEntry(payload, refreshState, display, changedFiles) {
  if (display.status === "running") {
    renderActionLedger();
    return;
  }
  const result = payload.result || {};
  const entry = {
    key: actionLedgerKey(payload, result),
    uiAction: payload.ui_action || "unknown",
    role: payload.action_role || metadataFor(payload.ui_action || "unknown").action_role || "unknown",
    target: payload.account_id || payload.route_id || "-",
    status: display.status,
    displayState: display.displayState,
    visualClass: display.visualClass,
    machineCode: result.machine_error_code || "-",
    message: result.human_message || "-",
    nextAction: result.next_action || "none",
    changedFilesCount: changedFiles.length,
    refreshStatus: refreshState === "failed"
      ? "canonical refresh failed"
      : (payload.post_action_refresh_required ? "canonical refresh required" : "refresh not required"),
    truthNote: display.truthNote,
    supportDetails: actionSupportDetails(payload)
  };
  if (refreshState === "failed" && actionLedger[0]?.key === entry.key) {
    actionLedger[0] = entry;
  } else {
    actionLedger = [entry, ...actionLedger.filter((item) => item.key !== entry.key)]
      .slice(0, ACTION_LEDGER_LIMIT);
  }
  renderActionLedger();
}

function actionLedgerKey(payload, result) {
  return [
    payload.ui_action || "unknown",
    payload.account_id || payload.route_id || "-",
    result.machine_error_code || "-",
    result.human_message || "-"
  ].join("|");
}

function renderActionLedger() {
  const list = document.getElementById("actionLedgerList");
  if (!list || typeof list.replaceChildren !== "function") {
    return;
  }
  list.replaceChildren();
  if (!actionLedger.length) {
    const empty = document.createElement("div");
    empty.className = "action-ledger-empty";
    empty.textContent = "Действия ещё не выполнялись в этой UI-сессии.";
    list.append(empty);
    return;
  }
  for (const entry of actionLedger) {
    list.append(actionLedgerRow(entry));
  }
}

function actionLedgerRow(entry) {
  const row = document.createElement("article");
  row.className = `action-ledger-row ${entry.visualClass}`;

  const head = document.createElement("div");
  head.className = "action-ledger-row-head";
  const title = document.createElement("strong");
  title.textContent = entry.uiAction;
  const chip = document.createElement("span");
  chip.className = `chip ${entry.visualClass}`;
  const dot = document.createElement("span");
  dot.className = "dot";
  const chipText = document.createElement("span");
  chipText.textContent = entry.displayState;
  chip.append(dot, chipText);
  head.append(title, chip);

  const meta = document.createElement("div");
  meta.className = "action-ledger-meta";
  meta.textContent = [
    `role=${entry.role}`,
    `target=${entry.target}`,
    `code=${entry.machineCode}`,
    `changed_files=${entry.changedFilesCount}`,
    entry.refreshStatus
  ].join(" · ");

  const message = document.createElement("p");
  message.textContent = entry.message;

  const truth = document.createElement("div");
  truth.className = "action-ledger-truth";
  truth.textContent = `command packet outcome only · ${entry.truthNote}`;

  row.append(head, meta, message, truth);
  if (entry.supportDetails && entry.supportDetails !== "-") {
    const support = document.createElement("div");
    support.className = "action-ledger-support";
    support.textContent = entry.supportDetails;
    row.append(support);
  }
  return row;
}

function actionSupportDetails(payload) {
  const result = payload.result || {};
  const data = result.data || {};
  if (payload.ui_action === "api_route_profile") {
    return [
      `writes_external_config=${data.writes_external_config === true ? "true" : "false"}`,
      `profile_ready=${data.profile_ready === true ? "true" : "false"}`,
      `listener_proven=${data.listener_proven === true ? "true" : "false"}`,
      `runtime_claim_blocked=${data.runtime_claim_blocked === false ? "false" : "true"}`
    ].join(" · ");
  }
  if (payload.ui_action === "api_route_evidence_capture") {
    return `локальный artifact · ${artifactReference(data.evidence_path)}`;
  }
  return "-";
}

function renderDiagnosticsAction(payload) {
  const result = payload.result || {};
  const packet = result.packet || {};
  const data = packet.data || {};
  const status = result.status || payload.status || "unknown";
  const changedFiles = Array.isArray(result.changed_files) ? result.changed_files : [];
  const visual = status === "ok" ? "blue" : (status === "running" ? "amber" : "red");
  const chip = document.getElementById("diagnosticsStatusChip");
  if (!chip) {
    return;
  }
  chip.className = `chip ${visual}`;
  chip.lastElementChild.textContent = diagnosticsStatusLabel(status);
  text("diagnosticsMessage", result.human_message || "Команда диагностики не вернула сообщение.");
  text("diagnosticsPacketStatus", status);
  text("diagnosticsExitCode", result.exit_code ?? "-");
  text("diagnosticsMachineCode", result.machine_error_code || "-");
  text("diagnosticsNextAction", result.next_action || "none");
  text("diagnosticsChangedFiles", `${changedFiles.length}`);
  text("diagnosticsBundleRef", artifactReference(data.bundle_path));

  const banner = document.getElementById("diagnosticsBanner");
  setClassName(banner, "fixture-banner", status === "ok" ? "healthy" : (status === "running" ? "stale" : "integration_failure"));
  banner.textContent = status === "ok"
    ? "Диагностический пакет поддержки экспортирован. Истина о здоровье runtime не изменялась."
    : "Команда диагностики не создала успешный пакет поддержки. Истина о здоровье runtime не изменялась.";
}

function diagnosticsStatusLabel(status) {
  return {
    ok: "Артефакт экспортирован",
    running: "Выполняется",
    command_error: "Ошибка команды",
    integration_failure: "Ошибка интеграции"
  }[status] || "Неизвестно";
}

function artifactReference(value) {
  if (typeof value !== "string" || !value) {
    return "не предоставлено";
  }
  const basename = value.split(/[\\/]/).filter(Boolean).pop() || "artifact";
  return `только метаданные: ${basename}`;
}

function renderSettingsSnapshot(snapshot) {
  const runtime = snapshot.runtime || {};
  const statusLabel = runtime.status_label || "Неизвестно";
  text("settingsDesiredMode", modeLabel(runtime.desired_mode));
  text("settingsEffectiveMode", modeLabel(runtime.effective_mode));
  text("settingsEndpoint", runtime.endpoint || "не предоставлен пакетом команды");
  text("settingsRuntimeStatus", `${statusLabel} · наблюдается, не редактируется`);
  text("settingsMachineCode", runtime.machine_error_code || "не предоставлен пакетом команды");
  updateSettingsActionMetadata();

  const banner = document.getElementById("settingsBanner");
  if (banner) {
    const visualState = runtime.visual_state || snapshot.state_id || "unknown";
    setClassName(banner, "fixture-banner", visualState);
    banner.textContent = "Настройки в этом контуре доступны только для чтения. Безопасные действия являются запросами, а не сохранёнными preferences.";
  }
}

function updateSettingsActionMetadata() {
  const launch = metadataFor("launch_client_dispatch");
  const target = document.getElementById("settingsLaunchAvailability");
  if (!target) {
    return;
  }
  target.textContent = launch.available === false
    ? `недоступно · ${launch.unavailable_reason || "server-owned path не предоставлен"}`
    : "доступно · server-owned bounded dispatch";
}

function setActionsBusy(isBusy) {
  for (const button of document.querySelectorAll(".live-action, .account-action, .onboard-action, .api-route-action")) {
    const metadata = metadataFor(button.dataset.uiAction);
    const requiresLive = (
      button.classList.contains("account-action")
      || button.classList.contains("onboard-action")
      || button.classList.contains("api-route-action")
    );
    const isLiveSource = document.querySelector(".desktop").dataset.source === "live";
    const routeEnabled = button.dataset.routeEnabled !== "false";
    const routeStateRequirement = button.dataset.routeStateRequirement || "any";
    const routeStateAllowed = routeStateRequirement === "disabled"
      ? !routeEnabled
      : (routeStateRequirement === "enabled" ? routeEnabled : true);
    const available = metadata.available !== false && (!requiresLive || isLiveSource) && routeStateAllowed;
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
      route_id: extraPayload.route_id || "",
      post_action_refresh_required: false,
      result: {
        status: "integration_failure",
        machine_error_code: "UI_ACTION_UNAVAILABLE",
        human_message: metadata.unavailable_reason || "Действие недоступно.",
        next_action: "user_action",
        changed_files: []
      }
    });
    return;
  }
  if (metadata.confirmation_required) {
    openConfirmation(uiAction, metadata, confirmationPolicyFor(uiAction, metadata), extraPayload);
    return;
  }
  runUiAction(uiAction, extraPayload);
}

function openConfirmation(uiAction, metadata, policy, extraPayload = {}) {
  confirmationInFlight = false;
  pendingConfirmedAction = { uiAction, extraPayload };
  const confirmModal = document.getElementById("confirmModal");
  if (confirmModal) {
    confirmModal.dataset.confirmSeverity = policy.severity || "critical";
  }
  text("confirmTitle", metadata.display_name || uiAction);
  text("confirmMeaning", metadata.human_meaning || "Подтвердите это действие.");
  text("confirmUiAction", uiAction);
  text("confirmAccountId", extraPayload.account_id || extraPayload.route_id || "-");
  text("confirmSeverity", policy.severity || "critical");
  text("confirmPolicy", policy.policy || "metadata-fallback");
  text("confirmMutation", metadata.mutates_runtime ? "да" : "нет");
  text("confirmRefresh", metadata.post_action_refresh_required ? "требуется" : "не требуется");
  text("confirmScope", metadata.action_claim_scope || "unknown");
  text("confirmTruthWarning", policy.warning || CONSERVATIVE_CONFIRMATION_POLICY.warning);
  setConfirmationInFlight(false);
  document.getElementById("confirmOverlay").hidden = false;
  document.getElementById("confirmAction").focus();
}

function closeConfirmation() {
  if (confirmationInFlight) {
    return;
  }
  pendingConfirmedAction = null;
  setConfirmationInFlight(false);
  document.getElementById("confirmOverlay").hidden = true;
}

function setConfirmationInFlight(isInFlight) {
  confirmationInFlight = isInFlight;
  const confirmButton = document.getElementById("confirmAction");
  const cancelButton = document.getElementById("cancelAction");
  if (confirmButton) {
    confirmButton.disabled = isInFlight;
    confirmButton.textContent = isInFlight ? "Выполняется..." : "Подтвердить";
  }
  if (cancelButton) {
    cancelButton.disabled = isInFlight;
  }
  text("confirmDispatchState", isInFlight ? "однократная отправка" : "ожидание");
}

async function confirmPendingAction() {
  if (confirmationInFlight) {
    return;
  }
  const pending = pendingConfirmedAction;
  if (!pending) {
    return;
  }
  pendingConfirmedAction = null;
  setConfirmationInFlight(true);
  try {
    await runUiAction(pending.uiAction, pending.extraPayload);
  } finally {
    setConfirmationInFlight(false);
    document.getElementById("confirmOverlay").hidden = true;
  }
}

function openOnboardModal() {
  document.getElementById("onboardOverlay").hidden = false;
  document.getElementById("runOnboardAction").focus();
}

function closeOnboardModal() {
  document.getElementById("onboardOverlay").hidden = true;
}

function runOnboardFromModal() {
  closeOnboardModal();
  maybeConfirmAndRun("onboard_account");
}

function setScreen(screen, updateUrl = false) {
  const nextScreen = SCREENS.includes(screen) ? screen : "overview";
  const desktop = document.querySelector(".desktop");
  desktop.dataset.screen = nextScreen;
  if (nextScreen !== "accounts") {
    closeAccountDrawer();
  }

  for (const node of document.querySelectorAll(".screen")) {
    node.hidden = node.dataset.screen !== nextScreen;
  }
  for (const node of document.querySelectorAll(".overview-only")) {
    node.hidden = nextScreen !== "overview";
  }
  for (const node of document.querySelectorAll(".accounts-only")) {
    node.hidden = nextScreen !== "accounts";
  }
  for (const node of document.querySelectorAll(".diagnostics-only")) {
    node.hidden = nextScreen !== "diagnostics";
  }
  for (const node of document.querySelectorAll(".settings-only")) {
    node.hidden = nextScreen !== "settings";
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

  text(
    "mainTitle",
    nextScreen === "accounts"
      ? "Аккаунты"
      : (
        nextScreen === "api-connections"
          ? "API-подключения"
          : (
        nextScreen === "diagnostics"
          ? "Диагностика"
          : (
            nextScreen === "settings"
              ? "Настройки"
              : (
                nextScreen === "setup"
                  ? "Настройка"
                  : (
                    nextScreen === "select-client"
                      ? "Выбор клиента"
                      : (nextScreen === "import-existing" ? "Импорт" : "Обзор")
                  )
              )
          )
          )
      )
  );
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
    accountFixture("acct-hold-01", "codex-hold@example.com", "reserve", "healthy", "amber", "ручная пауза", "Сегодня, 10:48", true),
    accountFixture("acct-problem-01", "codex-auth@example.com", "retired", "down", problemState, "ошибка auth/session", "Сегодня, 09:44")
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
      human_message: fixture.fixture_notice || "Демо-просмотр аккаунтов.",
      machine_error_code: fixture.runtime?.machine_error_code || "fixture",
      last_error: fixture.runtime?.last_error || ""
    },
    accounts
  };
}

function apiConnectionsFixtureFromOverview(fixture) {
  const integrationFailure = fixture.state_id === "integration_failure";
  const degraded = fixture.state_id === "degraded";
  const routes = integrationFailure ? [] : [
    {
      route_id: "wbp-openrouter-primary",
      display_name: "OpenRouter рабочий маршрут",
      provider: "openrouter",
      upstream_model: "deepseek/deepseek-chat",
      enabled: true,
      status_code: degraded ? "missing_secret" : "enabled",
      status_label: degraded ? "Требует ключ" : "Разрешён",
      visual_state: degraded ? "amber" : "blue",
      role_label: "Кандидат",
      last_checked: "",
      note: degraded
        ? "Демо-предупреждение: ключ не подтверждён, отдельная проверка маршрута не выполнялась."
        : "Демо-представление registry-пакета без отдельной проверки маршрута."
    },
    {
      route_id: "wbp-openrouter-reserve",
      display_name: "OpenRouter резервный маршрут",
      provider: "openrouter",
      upstream_model: "deepseek/deepseek-chat",
      enabled: false,
      status_code: "disabled",
      status_label: "Отключён",
      visual_state: "neutral",
      role_label: "Допустим для резерва",
      last_checked: "",
      note: "Демо-представление отключённого маршрута. Резервное использование не подтверждено."
    }
  ];
  return {
    schema_version: 1,
    status: integrationFailure ? "integration_failure" : "ok",
    source: "api_connections_fixture",
    primary_truth_ok: false,
    privacy: {
      redacted: true,
      raw_command_packet_included: false,
      forbidden_fields_excluded: ["secret_references", "tokens", "raw_paths", "raw_logs"]
    },
    summary: {
      routes_count: routes.length,
      enabled_count: routes.filter((route) => route.enabled).length,
      attention_count: routes.filter((route) => route.status_code === "missing_secret").length,
      latest_check: "",
      human_message: integrationFailure
        ? "Демо API-подключений не удалось собрать."
        : "Демо-представление API-подключений без live-команд.",
      machine_error_code: integrationFailure ? "UI_API_CONNECTIONS_FIXTURE_INVALID" : "fixture",
      last_error: integrationFailure ? "демо-состояние не прошло проверку" : ""
    },
    adapter: {
      foundation_phase: "fixture",
      adapter_runtime_available: false,
      lifecycle_mode: "synthetic",
      adapter_state: "stopped",
      listener_proven: false,
      runtime_claim_blocked: true,
      profile_ready: false,
      local_token_present: !degraded,
      observed_routes_count: 0,
      models_source: "fixture"
    },
    routes
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
      last_error_class: lastError ? "демо" : "",
    last_error_summary: lastError,
    cooldown_until: "",
      notes_summary: "демо"
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

function validateApiConnectionsSnapshot(snapshot) {
  const summary = snapshot.summary || {};
  const adapter = snapshot.adapter || {};
  const missingTop = ["schema_version", "status", "source", "summary", "routes"].filter((key) => !(key in snapshot));
  const missingSummary = [
    "routes_count",
    "enabled_count",
    "attention_count",
    "latest_check",
    "human_message",
    "machine_error_code"
  ].filter((key) => !(key in summary));
  const missingAdapter = [
    "foundation_phase",
    "adapter_runtime_available",
    "lifecycle_mode",
    "adapter_state",
    "listener_proven",
    "runtime_claim_blocked",
    "profile_ready",
    "local_token_present",
    "observed_routes_count",
    "models_source"
  ].filter((key) => !(key in adapter));
  return {
    ok: missingTop.length === 0 && missingSummary.length === 0 && missingAdapter.length === 0 && Array.isArray(snapshot.routes),
    missingTop,
    missingSummary,
    missingAdapter
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
      last_error: `Схема accounts недействительна: top [${validation.missingTop.join(", ")}], summary [${validation.missingSummary.join(", ")}], registry [${validation.missingRegistry.join(", ")}]`
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
    ? "аккаунты · live только чтение"
    : "аккаунты · демо-просмотр";
  document.getElementById("refreshFixture").lastElementChild.textContent = source === "live"
    ? "Обновить live"
    : "Обновить демо";
  setSourceCopy(source);

  const banner = document.getElementById("accountsBanner");
  setClassName(banner, "fixture-banner", visualState);
  banner.textContent = source === "live"
    ? "Live-режим аккаунтов. Подтверждение приходит только из канонического accounts JSON packet; lifecycle controls являются bounded action requests."
    : "Только демо-просмотр аккаунтов. Действия с аккаунтами отключены.";

  const summary = safeSnapshot.summary;
  text("accountsActiveChip", `${summary.active} активных`);
  text("accountsReserveChip", `${summary.reserve} резерв`);
  text("accountsHoldChip", `${summary.hold} удержание`);
  text("accountsProblemChip", `${summary.problem} проблемных`);
  text(
    "accountsRegistryStatus",
    `Идентичность registry: ${safeSnapshot.registry_identity.status} · ${safeSnapshot.registry_identity.machine_error_code}`
  );
  text("accountsVisibleCount", `Показано ${safeSnapshot.accounts.length} из ${summary.visible_count}`);
  text("accountsPagination", `Строки ${safeSnapshot.accounts.length ? 1 : 0}-${safeSnapshot.accounts.length} из ${summary.visible_count}`);
  currentAccountsSnapshot = safeSnapshot;
  renderAccountRows(safeSnapshot.accounts);
  renderAccountDetailDrawer();

  const sidebarDot = document.getElementById("sidebarDot");
  setClassName(sidebarDot, "dot", visualState);
  text("sidebarStatus", summary.human_message || "Accounts read-only");
}

function renderApiConnectionsSnapshot(snapshot) {
  const validation = validateApiConnectionsSnapshot(snapshot);
  const safeSnapshot = validation.ok ? snapshot : {
    ...apiConnectionsFixtureFromOverview(FALLBACK_FIXTURE),
    status: "integration_failure",
    source: "api_connections_fixture_invalid",
    summary: {
      ...apiConnectionsFixtureFromOverview(FALLBACK_FIXTURE).summary,
      machine_error_code: "UI_API_CONNECTIONS_SCHEMA_INVALID",
      human_message: "Схема API-подключений недействительна.",
      last_error: `Схема API-подключений недействительна: top [${validation.missingTop.join(", ")}], summary [${validation.missingSummary.join(", ")}], adapter [${validation.missingAdapter.join(", ")}]`
    },
    routes: []
  };

  const source = safeSnapshot.source === "api_connections_readonly" ? "live" : "fixture";
  const visualState = safeSnapshot.status === "ok" ? "healthy" : "integration_failure";
  const desktop = document.querySelector(".desktop");
  desktop.dataset.fixtureState = visualState;
  desktop.dataset.source = source;
  document.getElementById("sourcePicker").value = source;
  document.getElementById("statePicker").disabled = source === "live";
  document.getElementById("brandCaption").textContent = source === "live"
    ? "API-подключения · список маршрутов"
    : "API-подключения · демо";
  document.getElementById("refreshFixture").lastElementChild.textContent = source === "live"
    ? "Обновить live"
    : "Обновить демо";
  setSourceCopy(source);

  const banner = document.getElementById("apiConnectionsBanner");
  setClassName(banner, "fixture-banner", visualState);
  banner.textContent = source === "live"
    ? "API-подключения показываются из пакетов команд. Доступны только безопасные проверки маршрутов; мутации маршрутов отложены."
    : "Демо-представление API-подключений. Кнопки проверок отключены, пока не включён live-источник.";

  const summary = safeSnapshot.summary;
  const latestCheck = summary.latest_check || "Нет данных";
  text("apiConnectionsRoutesCount", summary.routes_count);
  text("apiConnectionsEnabledCount", summary.enabled_count);
  text("apiConnectionsAttentionCount", summary.attention_count);
  text("apiConnectionsLatestCheck", latestCheck);
  text("apiConnectionsRoutesNote", source === "live" ? "список собран из пакетов команд" : "демо");
  text("apiConnectionsEnabledNote", "только признак разрешения");
  text("apiConnectionsAttentionNote", "только внимание по маршрутам");
  text("apiConnectionsLatestCheckNote", latestCheck === "Нет данных" ? "проверка маршрута ещё не запускалась" : "время последней отдельной проверки");
  text(
    "apiConnectionsRegistryStatus",
    `Контур: ${safeSnapshot.adapter.foundation_phase} · models source: ${safeSnapshot.adapter.models_source}`
  );
  text("apiConnectionsVisibleCount", `Показано ${safeSnapshot.routes.length} из ${summary.routes_count}`);
  text("apiConnectionsPagination", `Строки ${safeSnapshot.routes.length ? 1 : 0}-${safeSnapshot.routes.length} из ${summary.routes_count}`);
  renderApiConnectionRows(safeSnapshot.routes);

  const sidebarDot = document.getElementById("sidebarDot");
  setClassName(sidebarDot, "dot", visualState);
  text("sidebarStatus", summary.human_message || "API-подключения только для чтения");
}

function renderApiConnectionRows(routes) {
  const body = document.getElementById("apiConnectionsTableBody");
  body.replaceChildren();
  if (!routes.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 8;
    cell.className = "dash";
    cell.textContent = "API-подключения пока не настроены. Добавление маршрутов будет подключено отдельным безопасным контуром.";
    row.append(cell);
    body.append(row);
    return;
  }
  for (const route of routes.slice(0, 12)) {
    const row = document.createElement("tr");
    row.append(
      td("", routeIdentity(route)),
      td("", route.provider || "—"),
      td("", route.upstream_model || "—"),
      td("", routeStatusChip(route)),
      td("", route.role_label || "Нет данных"),
      td("right mono-value", route.last_checked || "—"),
      td("", route.note || "—"),
      td("", routeActionButtons(route))
    );
    body.append(row);
  }
  applyActionAvailability();
}

function routeIdentity(route) {
  const wrap = document.createElement("div");
  const main = document.createElement("div");
  main.className = "account-main";
  main.textContent = route.display_name || route.route_id || "unknown-route";
  const sub = document.createElement("div");
  sub.className = "account-sub";
  sub.textContent = route.route_id || "route-id unavailable";
  wrap.append(main, sub);
  return wrap;
}

function routeStatusChip(route) {
  const chip = document.createElement("span");
  const visual = ACCOUNT_VISUAL_CLASS[route.visual_state] || "neutral";
  chip.className = `chip ${visual}`;
  const dot = document.createElement("span");
  dot.className = "dot";
  const label = document.createElement("span");
  label.textContent = route.status_label || "Нет данных";
  chip.append(dot, label);
  return chip;
}

function routeActionButtons(route) {
  const group = document.createElement("div");
  group.className = "account-action-group api-route-action-group";
  group.append(
    routeActionButton(route, "api_route_allow", "Разрешить"),
    routeActionButton(route, "api_route_disable", "Отключить"),
    routeActionButton(route, "api_route_validate", "Проверить"),
    routeActionButton(route, "api_route_check", "Запрос"),
    routeActionButton(route, "api_route_profile", "Профиль"),
    routeActionButton(route, "api_route_evidence_capture", "Свид-во"),
    routeActionButton(route, "api_route_remove", "Удалить")
  );
  return group;
}

function routeActionButton(route, uiAction, label) {
  const button = document.createElement("button");
  button.className = uiAction === "api_route_remove"
    ? "button small api-route-action api-route-destructive-action"
    : "button small api-route-action";
  button.type = "button";
  button.dataset.uiAction = uiAction;
  button.dataset.routeId = route.route_id || "";
  button.dataset.routeEnabled = route.enabled === true ? "true" : "false";
  button.dataset.routeStateRequirement = apiRouteStateRequirement(uiAction);
  button.textContent = label;
  const routeActionTitles = {
    api_route_allow: "Разрешить выбранный маршрут. Это не утверждение состояния runtime.",
    api_route_disable: "Отключить выбранный маршрут. Это не утверждение состояния runtime.",
    api_route_check: "Проверочный запрос к провайдеру для выбранного маршрута. Это не утверждение состояния runtime.",
    api_route_validate: "Проверка доступности модели у провайдера для выбранного маршрута. Это не утверждение состояния runtime.",
    api_route_profile: "Пакет профиля поддержки без настройки Codex config и без утверждения состояния runtime.",
    api_route_evidence_capture: "Свидетельство маршрута: собрать локальный support artifact. UI не читает evidence file.",
    api_route_remove: "Удалить только отключённую route registry запись после server preflight. Не меняет traffic, primary route, failover или runtime readiness."
  };
  button.title = routeActionTitles[uiAction] || "Действие с маршрутом через серверный JSON command surface.";
  button.addEventListener("click", () => {
    maybeConfirmAndRun(uiAction, { route_id: button.dataset.routeId });
  });
  return button;
}

function apiRouteStateRequirement(uiAction) {
  if (uiAction === "api_route_allow" || uiAction === "api_route_remove") {
    return "disabled";
  }
  if (uiAction === "api_route_profile" || uiAction === "api_route_evidence_capture") {
    return "any";
  }
  return "enabled";
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
    row.dataset.accountId = account.id || "";
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
  node.title = "Массовые lifecycle-действия отложены в этом контуре.";
  return node;
}

function accountIdentity(account) {
  const wrap = document.createElement("div");
  const main = document.createElement("div");
  main.className = "account-main";
  main.textContent = account.id || "unknown-account";
  const sub = document.createElement("div");
  sub.className = "account-sub";
  sub.textContent = redactAccountLabel(account.label || account.id || "редактированный аккаунт");
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
  group.append(accountDetailButton(account));
  group.append(accountActionButton(account, "validate_account", "Проверить"));
  if (account.pool !== "retired") {
    if (account.manual_hold) {
        group.append(accountActionButton(account, "release_account", "Снять паузу"));
    } else {
      if (account.pool === "reserve") {
        group.append(accountActionButton(account, "promote_account", "В актив"));
      }
      if (account.pool === "active") {
        group.append(accountActionButton(account, "demote_account", "В резерв"));
      }
      group.append(accountActionButton(account, "hold_account", "Удержать"));
    }
    group.append(accountActionButton(account, "retire_account", "Вывести"));
  }
  return group;
}

function accountDetailButton(account) {
  const button = document.createElement("button");
  button.className = "button small account-detail-trigger";
  button.type = "button";
  button.dataset.accountId = account.id || "";
  button.textContent = "Детали";
  button.title = "Открыть drawer. Данные берутся только из текущего accounts JSON.";
  button.addEventListener("click", () => {
    openAccountDrawer(button.dataset.accountId);
  });
  return button;
}

function accountActionButton(account, uiAction, label) {
  const button = document.createElement("button");
  button.className = "button small account-action";
  button.type = "button";
  button.dataset.uiAction = uiAction;
  button.dataset.accountId = account.id || "";
  button.textContent = label;
  button.title = uiAction === "retire_account"
    ? "Запросить терминальный вывод из lifecycle. Подтверждением остаётся обновлённый список аккаунтов."
    : "Выполнить allowlisted действие с аккаунтом. Подтверждением остаётся обновлённый список аккаунтов.";
  button.addEventListener("click", () => {
    maybeConfirmAndRun(uiAction, { account_id: button.dataset.accountId });
  });
  return button;
}

function openAccountDrawer(accountId) {
  selectedAccountId = String(accountId || "");
  const overlay = document.getElementById("accountDetailOverlay");
  overlay.hidden = false;
  renderAccountDetailDrawer();
  document.getElementById("accountDetailClose").focus();
}

function closeAccountDrawer() {
  const overlay = document.getElementById("accountDetailOverlay");
  if (overlay) {
    overlay.hidden = true;
  }
}

function selectedAccountFromSnapshot() {
  const accounts = currentAccountsSnapshot?.accounts || [];
  return accounts.find((account) => account.id === selectedAccountId) || null;
}

function renderAccountDetailDrawer() {
  const overlay = document.getElementById("accountDetailOverlay");
  if (!overlay || overlay.hidden || !selectedAccountId) {
    return;
  }
  const account = selectedAccountFromSnapshot();
  if (!account) {
    renderMissingAccountDrawer();
    return;
  }

  document.getElementById("accountDetailMissing").hidden = true;
  text("accountDetailTitle", account.id || "unknown-account");
  text("accountDetailSubtitle", redactAccountLabel(account.label || account.id || "редактированный аккаунт"));
  text("accountDetailId", account.id || "unknown-account");
  text("accountDetailLabel", redactAccountLabel(account.label || account.id || "редактированный аккаунт"));
  text("accountDetailEnabled", account.enabled === true ? "да" : (account.enabled === false ? "нет" : "не указано"));
  text("accountDetailSuccess", account.success_count ?? 0);
  text("accountDetailFail", account.fail_count ?? 0);
  text("accountDetailLastSuccess", account.last_success || "—");
  text("accountDetailCooldown", account.cooldown_until || "—");
  text("accountDetailError", account.last_error_summary || "—");
  text("accountDetailNotes", account.notes_summary || "—");

  const status = document.getElementById("accountDetailStatusChip");
  status.className = `chip ${ACCOUNT_VISUAL_CLASS[account.visual_state] || "neutral"}`;
  status.lastElementChild.textContent = account.status_label || statusLabel(account.status);

  const pool = document.getElementById("accountDetailPoolChip");
  pool.className = account.pool === "active" ? "chip green" : (account.pool === "reserve" ? "chip blue" : "chip neutral");
  pool.lastElementChild.textContent = account.pool_label || poolLabel(account.pool);

  const hold = document.getElementById("accountDetailHoldChip");
  hold.className = account.manual_hold ? "chip amber" : "chip neutral";
  hold.lastElementChild.textContent = account.manual_hold ? "На удержании" : "Без удержания";

  const actions = document.getElementById("accountDetailActions");
  actions.replaceChildren();
  const group = accountActionButtons(account);
  group.querySelector(".account-detail-trigger")?.remove();
  actions.append(...Array.from(group.children));
  applyActionAvailability();
}

function renderMissingAccountDrawer() {
  document.getElementById("accountDetailMissing").hidden = false;
  text("accountDetailTitle", selectedAccountId || "Аккаунт отсутствует");
  text("accountDetailSubtitle", "Выбранный аккаунт не найден после обновления accounts JSON.");
  text("accountDetailId", selectedAccountId || "-");
  text("accountDetailLabel", "account_missing_after_refresh");
  text("accountDetailEnabled", "-");
  text("accountDetailSuccess", "-");
  text("accountDetailFail", "-");
  text("accountDetailLastSuccess", "-");
  text("accountDetailCooldown", "-");
  text("accountDetailError", "Действия отключены до выбора существующего аккаунта.");
  text("accountDetailNotes", "-");

  for (const chipId of ["accountDetailStatusChip", "accountDetailPoolChip", "accountDetailHoldChip"]) {
    const chip = document.getElementById(chipId);
    chip.className = "chip amber";
    chip.lastElementChild.textContent = "не подтверждено";
  }

  const actions = document.getElementById("accountDetailActions");
  actions.replaceChildren();
  const disabled = document.createElement("button");
  disabled.className = "button small account-detail-disabled-action";
  disabled.type = "button";
  disabled.disabled = true;
  disabled.textContent = "Действия отключены";
  actions.append(disabled);
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
    fixture_notice: `Схема демо-состояния недействительна: отсутствует top [${validation.missingTop.join(", ")}], runtime [${validation.missingRuntime.join(", ")}]`
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
    ? "live только чтение"
    : "демо-просмотр UI";
  setSourceCopy(source);
  document.getElementById("refreshFixture").lastElementChild.textContent = source === "live"
    ? "Обновить live"
    : "Обновить демо";

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
  renderSettingsSnapshot(safeSnapshot);

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
  } else if (currentScreen() === "api-connections") {
    renderApiConnectionsSnapshot(apiConnectionsFixtureFromOverview(fixture));
  } else {
    renderSnapshot(fixture);
  }
}

async function setLiveReadonly(updateUrl = false) {
  setSourceCopy("live");
  const snapshot = currentScreen() === "accounts"
    ? await loadAccountsReadonly()
    : (currentScreen() === "api-connections" ? await loadApiConnectionsReadonly() : await loadLiveReadonly());
  if (updateUrl) {
    const url = new URL(window.location.href);
    url.searchParams.set("source", "live");
    window.history.replaceState({}, "", url);
  }
  if (currentScreen() === "accounts") {
    renderAccountsSnapshot(snapshot);
  } else if (currentScreen() === "api-connections") {
    renderApiConnectionsSnapshot(snapshot);
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
  document.getElementById("accountAddAction").addEventListener("click", () => openOnboardModal());
  document.getElementById("accountDetailClose").addEventListener("click", () => closeAccountDrawer());
  document.getElementById("accountDetailBackdrop").addEventListener("click", () => closeAccountDrawer());
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeAccountDrawer();
    }
  });
  document.getElementById("cancelOnboardAction").addEventListener("click", () => closeOnboardModal());
  document.getElementById("runOnboardAction").addEventListener("click", () => runOnboardFromModal());
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
