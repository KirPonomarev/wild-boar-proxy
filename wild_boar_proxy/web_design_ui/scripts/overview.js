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
  running: "neutral",
  duplicate_blocked: "neutral",
  ok_refresh_pending: "amber",
  ok_refresh_complete: "green",
  ok_refresh_failed: "amber",
  refresh_mismatch: "amber",
  command_error: "red",
  integration_failure: "red",
  invalid_json: "red",
  timeout: "amber",
  partial_success: "amber",
  unsupported: "neutral",
  missing_surface: "neutral",
  needs_user_action: "amber",
  ok: "green",
  stale: "amber",
  degraded: "amber",
  down: "red",
  unknown: "neutral"
};

const SCREENS = ["quick-start", "overview", "accounts", "api-connections", "diagnostics", "settings", "setup", "select-client", "import-existing"];
const ACCOUNT_VISUAL_CLASS = {
  green: "green",
  blue: "blue",
  amber: "amber",
  red: "red",
  neutral: "neutral"
};
const ACTION_LEDGER_LIMIT = 5;
const BROWSER_ACTION_PAYLOAD_KEYS = ["account_id", "route_id"];
const SETTINGS_SECTIONS = ["hub", "runtime", "client", "accounts-policy", "diagnostics-privacy", "advanced", "data-layout"];
const UI_READONLY_LANE_NEXT_CONTOUR = "STOP_AND_DIAGNOSE_REPEATED_SELECTOR_LOCK_AND_RUNTIME_REGRESSION";
const UI_READONLY_LANE_BLOCKERS = [
  ["LOCK_HELD", "Повторный selector owner path не admitted до локализации lock contention."],
  ["claim_gate_blocked", "Runtime truth снова показывает blocked claim gate."],
  ["policy_drift_detected", "Runtime truth снова показывает detected policy drift."],
  ["selector_evidence_no_progress", "Нового selector progress packet нет."],
  ["exact_auth_source_not_singleton", "Exact auth-source admission не singleton-ready."],
  ["onboarding_not_admitted", "Onboarding и auth materialization остаются parked."],
  ["STAGE_PILOT_NOT_ADMITTED", "Stage admission claims запрещены до runtime diagnosis."]
];
const UI_READONLY_LANE_SAFE_SCOPE = [
  "Read-only truth display only.",
  "Disabled live-action reasons inspection.",
  "Snapshot command summary inspection."
];
const UI_READONLY_LANE_FORBIDDEN_SCOPE = [
  "runtime sync dispatch",
  "smoke dispatch",
  "stable repair apply",
  "onboarding admission",
  "auth source materialization",
  "selector retry loop",
  "route mutation",
  "stage proof admission"
];
const DATA_LAYOUT_FIXTURES = {
  healthy: {
    key: "initialized_healthy",
    visual: "green",
    mode: "fixture preview",
    packageStatus: "init preview",
    schemaVersion: "v1 preview",
    writable: "ok preview",
    snapshotAvailable: "yes preview",
    rollbackPoint: "available preview",
    lastChecked: "Сегодня, 12:45",
    directoryStatus: "available",
    directoryVisual: "green",
    directoryPath: "~/Library/Application Support/Wild Boar Proxy",
    structureVisual: "green",
    structure: {
      config: ["ok preview", "green"],
      accounts: ["ok preview", "green"],
      snapshots: ["ok preview", "green"],
      logs: ["human-open only", "neutral"],
      registry: ["readonly preview", "neutral"]
    },
    permissionsVisual: "green",
    permissions: {
      read: "ok preview",
      write: "ok preview",
      owner: "current user preview",
      mode: "bounded summary",
      secrets: "isolated by policy"
    },
    snapshotVisual: "green",
    snapshotLabel: "snapshot ready",
    snapshotCopy: "preview snapshot marker",
    rollbackCopy: "rollback point preview"
  },
  degraded: {
    key: "permissions_warning",
    visual: "amber",
    mode: "fixture preview",
    packageStatus: "init preview",
    schemaVersion: "v1 preview",
    writable: "missing_permission preview",
    snapshotAvailable: "yes preview",
    rollbackPoint: "available preview",
    lastChecked: "Сегодня, 12:38",
    directoryStatus: "missing permission",
    directoryVisual: "amber",
    directoryPath: "~/Library/Application Support/Wild Boar Proxy",
    structureVisual: "amber",
    structure: {
      config: ["ok preview", "green"],
      accounts: ["ok preview", "green"],
      snapshots: ["ok preview", "green"],
      logs: ["human-open only", "neutral"],
      registry: ["readonly preview", "neutral"]
    },
    permissionsVisual: "amber",
    permissions: {
      read: "ok preview",
      write: "not_proven preview",
      owner: "not proven",
      mode: "not proven",
      secrets: "values never shown"
    },
    snapshotVisual: "green",
    snapshotLabel: "snapshot ready",
    snapshotCopy: "preview snapshot marker",
    rollbackCopy: "rollback point preview"
  },
  unknown: {
    key: "no_data_dir_known",
    visual: "neutral",
    mode: "fixture preview",
    packageStatus: "unknown",
    schemaVersion: "unknown",
    writable: "unknown",
    snapshotAvailable: "unknown",
    rollbackPoint: "unknown",
    lastChecked: "—",
    directoryStatus: "not inspected",
    directoryVisual: "neutral",
    directoryPath: "Каталог не подтверждён",
    structureVisual: "neutral",
    structure: {
      config: ["not inspected", "neutral"],
      accounts: ["not inspected", "neutral"],
      snapshots: ["not inspected", "neutral"],
      logs: ["human-open only", "neutral"],
      registry: ["not inspected", "neutral"]
    },
    permissionsVisual: "neutral",
    permissions: {
      read: "Не проверено",
      write: "Не проверено",
      owner: "unknown",
      mode: "unknown",
      secrets: "values never shown"
    },
    snapshotVisual: "neutral",
    snapshotLabel: "no snapshot",
    snapshotCopy: "не подтверждён",
    rollbackCopy: "недоступен без rollback point"
  },
  down: {
    key: "rollback_required",
    visual: "amber",
    mode: "fixture preview",
    packageStatus: "pending preview",
    schemaVersion: "unknown",
    writable: "not_proven preview",
    snapshotAvailable: "no preview",
    rollbackPoint: "none preview",
    lastChecked: "Сегодня, 12:30",
    directoryStatus: "attention",
    directoryVisual: "amber",
    directoryPath: "~/Library/Application Support/Wild Boar Proxy",
    structureVisual: "amber",
    structure: {
      config: ["missing preview", "amber"],
      accounts: ["ok preview", "green"],
      snapshots: ["missing preview", "amber"],
      logs: ["human-open only", "neutral"],
      registry: ["readonly preview", "neutral"]
    },
    permissionsVisual: "amber",
    permissions: {
      read: "not_proven preview",
      write: "not_proven preview",
      owner: "unknown",
      mode: "unknown",
      secrets: "values never shown"
    },
    snapshotVisual: "amber",
    snapshotLabel: "rollback required",
    snapshotCopy: "snapshot missing preview",
    rollbackCopy: "rollback point не подтверждён"
  },
  stale: {
    key: "stale",
    visual: "amber",
    mode: "stale preview",
    packageStatus: "stale",
    schemaVersion: "unknown",
    writable: "stale",
    snapshotAvailable: "stale",
    rollbackPoint: "stale",
    lastChecked: "устарело",
    directoryStatus: "stale",
    directoryVisual: "amber",
    directoryPath: "Каталог не подтверждён",
    structureVisual: "amber",
    structure: {
      config: ["stale", "amber"],
      accounts: ["stale", "amber"],
      snapshots: ["stale", "amber"],
      logs: ["human-open only", "neutral"],
      registry: ["stale", "amber"]
    },
    permissionsVisual: "amber",
    permissions: {
      read: "stale",
      write: "stale",
      owner: "stale",
      mode: "stale",
      secrets: "values never shown"
    },
    snapshotVisual: "amber",
    snapshotLabel: "stale",
    snapshotCopy: "устаревший preview",
    rollbackCopy: "требуется обновление"
  },
  integration_failure: {
    key: "live_integration_failure",
    visual: "red",
    mode: "live unavailable",
    packageStatus: "unknown",
    schemaVersion: "unknown",
    writable: "unknown",
    snapshotAvailable: "unknown",
    rollbackPoint: "unknown",
    lastChecked: "live-readonly failed",
    directoryStatus: "unavailable",
    directoryVisual: "red",
    directoryPath: "Каталог не подтверждён",
    structureVisual: "neutral",
    structure: {
      config: ["not inspected", "neutral"],
      accounts: ["not inspected", "neutral"],
      snapshots: ["not inspected", "neutral"],
      logs: ["human-open only", "neutral"],
      registry: ["not inspected", "neutral"]
    },
    permissionsVisual: "neutral",
    permissions: {
      read: "Не проверено",
      write: "Не проверено",
      owner: "unknown",
      mode: "unknown",
      secrets: "values never shown"
    },
    snapshotVisual: "neutral",
    snapshotLabel: "no data",
    snapshotCopy: "не подтверждён",
    rollbackCopy: "недоступен без rollback point"
  }
};
const ACCOUNT_UI_ACTIONS = new Set([
  "validate_account",
  "promote_account",
  "demote_account",
  "hold_account",
  "release_account",
  "retire_account"
]);

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
    warning: "Удаляет только отключённую route registry запись после server preflight. Не меняет другие routes и не утверждает runtime readiness."
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
let currentApiConnectionsSnapshot = null;
let selectedAccountId = "";
let selectedAccountIds = new Set();
let actionLedger = [];
let actionLedgerFilter = "all";
let activeActionRequestKey = "";
let snapshotCommandLedgerState = {
  surface: "not loaded",
  status: "missing",
  source: "none",
  entries: [],
  hasWarnings: false
};

function text(id, value) {
  document.getElementById(id).textContent = String(value ?? "-");
}

function pathText(id, value) {
  const node = document.getElementById(id);
  if (!node) {
    return;
  }
  const fullValue = String(value ?? "-");
  node.textContent = middleTruncatePath(fullValue);
  node.title = fullValue;
}

function middleTruncatePath(value) {
  const path = String(value || "");
  if (path.length <= 34 || !path.includes("/")) {
    return path || "-";
  }
  const parts = path.split("/").filter(Boolean);
  const file = parts.at(-1) || path.slice(-18);
  const first = parts[0] ? `/${parts[0]}` : "";
  return `${first}/.../${file}`;
}

function setClassName(node, base, visualState) {
  node.className = `${base} ${VISUAL_CLASS[visualState] || "neutral"}`;
}

function setNodeAttribute(node, name, value) {
  if (typeof node.setAttribute === "function") {
    node.setAttribute(name, value);
  } else {
    node[name] = value;
  }
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

function settingsSectionFromLocation() {
  const params = new URLSearchParams(window.location.search);
  const section = params.get("section") || "hub";
  return SETTINGS_SECTIONS.includes(section) ? section : "hub";
}

function currentScreen() {
  return document.querySelector(".desktop").dataset.screen || "overview";
}

function currentSettingsSection() {
  return document.querySelector(".desktop").dataset.settingsSection || "hub";
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
    availability_state: "unknown_disabled",
    disabled_reason_code: "UI_ACTION_METADATA_UNAVAILABLE",
    disabled_reasons: ["unknown_disabled"],
    unavailable_reason: "Метаданные действия не удалось загрузить.",
    launch_preflight: {
      status: "denied",
      machine_error_code: "UI_ACTION_METADATA_UNAVAILABLE",
      reason: "Метаданные preflight не удалось загрузить.",
      target_kind: "unknown",
      target_exists: false,
      separate_profile: false,
      separate_data_dir: false,
      separate_port: false,
      process_confirmation_possible: false,
      current_session_untouched: false
    }
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
  let displayState = status || "unknown";
  if (status === "ok" && payload.post_action_refresh_required) {
    if (refreshState === "complete") {
      displayState = "ok_refresh_complete";
    } else if (refreshState === "failed") {
      displayState = "ok_refresh_failed";
    } else if (refreshState === "mismatch") {
      displayState = "refresh_mismatch";
    } else {
      displayState = "ok_refresh_pending";
    }
  } else if (status === "ok") {
    displayState = "ok_refresh_complete";
  }
  const visualClass = actionVisualClass(payload, displayState);
  return {
    status,
    displayState,
    visualClass,
    truthNote: actionTruthNote(payload, displayState, refreshState)
  };
}

function actionVisualClass(payload, displayState) {
  if (displayState === "ok_refresh_complete" && payload.action_role === "support_artifact") {
    return "blue";
  }
  return ACTION_STATUS_VISUAL_CLASS[displayState] || (
    displayState === "ok" ? "green" : "red"
  );
}

function actionTruthNote(payload, displayState, refreshState) {
  if (displayState === "running") {
    return "Запрос действия выполняется. UI не изменял подтверждённое состояние runtime.";
  }
  if (displayState === "duplicate_blocked") {
    return "Повторная отправка заблокирована в текущей UI-сессии. Второй command dispatch не выполнялся.";
  }
  if (displayState === "ok_refresh_pending") {
    return "Пакет действия сообщил ok; каноническое состояние runtime требует обновлённого JSON.";
  }
  if (displayState === "ok_refresh_failed" || refreshState === "failed") {
    return "Команда могла выполниться, но состояние не подтверждено: canonical refresh failed.";
  }
  if (displayState === "refresh_mismatch" || refreshState === "mismatch") {
    return "Команда могла выполниться, но обновлённый список всё ещё содержит target. Успех не подтверждён.";
  }
  if (displayState === "ok_refresh_complete" && payload.action_role === "support_artifact") {
    return "Пакет support artifact сообщил ok. Это не является отдельным источником runtime truth.";
  }
  if (displayState === "ok_refresh_complete") {
    return "Пакет действия сообщил ok. Этот журнал не является отдельным источником runtime truth.";
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

function actionDisplayLabel(displayState) {
  return {
    running: "выполняется",
    duplicate_blocked: "дубль заблокирован",
    ok_refresh_pending: "требует refresh",
    ok_refresh_complete: "подтверждено",
    ok_refresh_failed: "refresh failed",
    refresh_mismatch: "refresh mismatch",
    command_error: "ошибка команды",
    invalid_json: "invalid JSON",
    timeout: "timeout",
    integration_failure: "ошибка интеграции",
    created: "артефакт создан",
    redaction_unreported: "redaction не подтверждена",
    redaction_failed: "redaction failed",
    artifact_unavailable: "artifact unavailable",
    partial_success: "частично",
    unsupported: "недоступно",
    missing_surface: "missing surface",
    needs_user_action: "нужно действие"
  }[displayState] || displayState || "неизвестно";
}

function actionRefreshLabel(payload, refreshState) {
  if (refreshState === "complete") {
    return "canonical refresh complete";
  }
  if (refreshState === "failed") {
    return "canonical refresh failed";
  }
  if (refreshState === "mismatch") {
    return "canonical refresh mismatch";
  }
  return payload.post_action_refresh_required ? "canonical refresh pending" : "refresh not required";
}

async function runUiAction(uiAction, extraPayload = {}) {
  const requestPayload = boundedUiActionPayload(uiAction, extraPayload);
  const requestKey = actionRequestKey(requestPayload);
  if (activeActionRequestKey) {
    const sameRequest = activeActionRequestKey === requestKey;
    setActionPanel({
      status: "duplicate_blocked",
      ui_action: uiAction,
      action_role: "ui_session_guard",
      account_id: requestPayload.account_id || "",
      route_id: requestPayload.route_id || "",
      post_action_refresh_required: false,
      result: {
        status: "duplicate_blocked",
        machine_error_code: sameRequest ? "UI_DUPLICATE_SUBMIT_BLOCKED" : "UI_ACTION_IN_FLIGHT",
        human_message: sameRequest
          ? "Повторная отправка заблокирована в текущей UI-сессии."
          : "Другое действие уже выполняется в текущей UI-сессии.",
        next_action: "wait",
        changed_files: []
      }
    });
    return;
  }
  activeActionRequestKey = requestKey;
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
        const refreshState = apiRouteRemoveRefreshState(payload, refreshed);
        setActionPanel(payload, refreshState);
        setMiniPill(
          "onboardingResultRefreshChip",
          refreshState === "mismatch" ? "refresh mismatch" : "refresh complete",
          refreshState === "mismatch" ? "amber" : "green"
        );
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
    activeActionRequestKey = "";
    setActionsBusy(false);
  }
}

function actionRequestKey(payload) {
  return [
    payload.ui_action || "unknown",
    payload.account_id || payload.route_id || "-"
  ].join("|");
}

function apiRouteRemoveRefreshState(payload, refreshed) {
  if (payload.ui_action !== "api_route_remove") {
    return "complete";
  }
  return apiRoutePresentInSnapshot(refreshed, payload.route_id) ? "mismatch" : "complete";
}

function apiRoutePresentInSnapshot(snapshot, routeId) {
  if (!routeId) {
    return false;
  }
  const routes = Array.isArray(snapshot?.routes) ? snapshot.routes : [];
  return routes.some((route) => route?.route_id === routeId);
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

function isApiRouteActionDeferredInReadonlyRegistry(uiAction) {
  return [
    "api_route_allow",
    "api_route_disable",
    "api_route_check",
    "api_route_profile",
    "api_route_evidence_capture"
  ].includes(uiAction);
}

function actionAvailabilityForButton(button) {
  const metadata = metadataFor(button.dataset.uiAction);
  const metadataAllowsAction = metadata.available !== false;
  const requiresLive = (
    button.classList.contains("account-action")
    || button.classList.contains("onboard-action")
    || button.classList.contains("api-route-action")
  );
  const isLiveSource = document.querySelector(".desktop").dataset.source === "live";
  const routeEnabled = button.dataset.routeEnabled !== "false";
  const routeStateProven = button.dataset.routeStateProven === "true";
  const routeStateRequirement = button.dataset.routeStateRequirement || "any";
  const routeStateAllowed = routeStateRequirement === "disabled"
    ? (!routeEnabled && routeStateProven)
    : (routeStateRequirement === "enabled" ? (routeEnabled && routeStateProven) : true);
  const routeActionDeferred = button.classList.contains("api-route-action")
    && isApiRouteActionDeferredInReadonlyRegistry(button.dataset.uiAction);

  if (!routeStateAllowed) {
    return {
      available: false,
      availabilityState: "not_admitted",
      disabledReasonCode: routeStateProven ? "ROUTE_STATE_REQUIREMENT_NOT_MET" : "ROUTE_STATE_NOT_PROVEN",
      disabledReasons: routeStateProven ? ["route_state_requirement_not_met"] : ["route_state_not_proven"],
      title: routeStateRequirement === "disabled"
        ? (
          routeStateProven
            ? "Маршрут уже разрешён. Это действие доступно только для отключённых маршрутов."
            : "Состояние маршрута не доказано. Нужен readonly route packet."
        )
        : (
          routeStateProven
            ? "Маршрут отключён. Это действие доступно только для разрешённых маршрутов."
            : "Состояние маршрута не доказано. Нужен readonly route packet."
        )
    };
  }
  if (routeActionDeferred) {
    return {
      available: false,
      availabilityState: "disabled_live_action",
      disabledReasonCode: "READONLY_ROUTE_ACTION_DEFERRED",
      disabledReasons: ["readonly_registry_deferred"],
      title: "Это действие маршрута отложено в этом readonly registry contour."
    };
  }
  if (requiresLive && !isLiveSource) {
    return {
      available: false,
      availabilityState: "not_admitted",
      disabledReasonCode: "LIVE_SOURCE_REQUIRED",
      disabledReasons: ["live_source_required"],
      title: "Переключите экран на live-источник перед выполнением действий."
    };
  }
  if (!metadataAllowsAction) {
    return {
      available: false,
      availabilityState: metadata.availability_state || "unknown_disabled",
      disabledReasonCode: metadata.disabled_reason_code || "UI_ACTION_DISABLED",
      disabledReasons: metadata.disabled_reasons || [],
      title: metadata.unavailable_reason || "Действие недоступно"
    };
  }
  return {
    available: true,
    availabilityState: "displayable_readonly",
    disabledReasonCode: "",
    disabledReasons: [],
    title: ""
  };
}

function applyActionAvailability() {
  for (const button of document.querySelectorAll(".live-action, .account-action, .onboard-action, .api-route-action")) {
    const state = actionAvailabilityForButton(button);
    button.disabled = !state.available;
    button.dataset.available = state.available ? "true" : "false";
    button.dataset.availabilityState = state.availabilityState;
    button.dataset.disabledReasonCode = state.disabledReasonCode;
    button.dataset.disabledReasons = state.available ? "" : JSON.stringify(state.disabledReasons);
    button.title = state.title;
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
      return "Live-readonly недоступен. Предыдущие healthy-данные не используются.";
    }
    if (snapshot.has_warnings) {
      return `Live-readonly с предупреждениями. ${warningSummary(snapshot.warnings || [])}`;
    }
    return "Live-readonly. Экран открыт без команд на изменение.";
  }
  const state = canonicalState(snapshot.state_id || snapshot.ui_state || "healthy");
  if (state === "stale") {
    return "Данные устарели. Требуется обновление.";
  }
  if (state === "down") {
    return "Демо-режим. Недоступное состояние показано как ошибка, а не как успех.";
  }
  if (state === "degraded") {
    return "Демо-режим. Деградация выделена отдельно от рабочего состояния.";
  }
  if (state === "integration_failure") {
    return "Демо-режим. Ошибка интеграции не использует предыдущие healthy-данные.";
  }
  return "Демо-режим. Данные не являются runtime truth.";
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
  const settingsSection = currentSettingsSection();
  const setupLike = ["setup", "select-client", "import-existing"].includes(screen);
  const settingsFooterBySection = {
    runtime: "Настройки · runtime mode",
    client: "Настройки · client launch",
    "accounts-policy": "Настройки · accounts policy readonly",
    "diagnostics-privacy": "Настройки · diagnostics privacy",
    advanced: "Настройки · advanced boundaries",
    "data-layout": "Настройки · data layout preview",
    hub: "Настройки · hub разделов"
  };
  const settingsSubtitleBySection = {
    runtime: "Желаемый и фактический режим работы, подтверждённые только command packets.",
    client: "Клиент Codex, условия запуска и bounded dispatch без выбора файлов из браузера.",
    "accounts-policy": "Правила пулов, проверки и безопасного reserve-first поведения аккаунтов.",
    "diagnostics-privacy": "Правила экспорта диагностики, redaction и support bundle boundaries.",
    advanced: "Границы операторских действий, deferred gates и безопасные поверхности команд.",
    "data-layout": "Состояние каталога данных, разрешений и безопасных операций установки.",
    hub: "Конфигурация клиента, данных приложения и безопасных действий."
  };
  const settingsFooter = settingsFooterBySection[settingsSection] || settingsFooterBySection.hub;
  const settingsSubtitle = settingsSubtitleBySection[settingsSection] || settingsSubtitleBySection.hub;
  const footerByScreen = {
    "quick-start": "Quick Start · summary control panel",
    accounts: "Аккаунты · live только чтение",
    "api-connections": "API-подключения · список маршрутов",
    diagnostics: "Диагностика · detail screen",
    settings: settingsFooter,
    setup: "Setup · admission preview",
    "select-client": "Select Client · candidate preview",
    "import-existing": "Import · transaction preview"
  };
  const subtitleByScreen = {
    "quick-start": "Ежедневный пульт подключений: аккаунты Codex и один основной API.",
    accounts: "Пул аккаунтов, статусы проверки и распределение по режимам.",
    "api-connections": "Маршруты внешних моделей, статусы проверки и безопасные действия.",
    diagnostics: "Проверка цепочки подключения, аккаунтов и режима прокси.",
    settings: settingsSubtitle,
    setup: "Безопасная подготовка локального контура без изменения рабочих файлов Codex.",
    "select-client": "Выберите локальный клиент Codex из безопасно предоставленных кандидатов.",
    "import-existing": "Перенесите найденную конфигурацию без изменения рабочих файлов Codex."
  };
  const sourceFooter = source === "live"
    ? (footerByScreen[screen] || (setupLike ? "Экраны настройки · отложенный каркас" : "Состояние · live только чтение"))
    : "Предпросмотр UI · без live-команд";
  const subtitle = subtitleByScreen[screen] || (
    source === "live"
      ? "Операторская сводка подключена к live-ответам команд. После действий состояние обновляется заново."
      : "Операторская сводка: фактическое состояние, режим работы, пул аккаунтов и последние события."
  );
  document.getElementById("sourceFooter").textContent = sourceFooter;
  document.getElementById("subtitleText").textContent = subtitle;
  const sourcePill = document.getElementById("sourcePill");
  if (sourcePill) {
    sourcePill.textContent = source === "live" ? "Live" : "Demo";
    sourcePill.className = source === "live" ? "source-pill live" : "source-pill";
  }
  updateDiagnosticsDetailSource(source);
  updateSetupAdmissionCopy(source);
  updateSelectClientCopy(source);
  updateImportExistingCopy(source);
}

function liveBrandCaptionForScreen(screen) {
  return {
    "quick-start": "quick start · live readonly",
    accounts: "аккаунты · live только чтение",
    "api-connections": "API-подключения · список маршрутов",
    overview: "live только чтение"
  }[screen] || "live только чтение";
}

function setLiveReadonlyPendingUi() {
  const screen = currentScreen();
  const desktop = document.querySelector(".desktop");
  const sourcePicker = document.getElementById("sourcePicker");
  const statePicker = document.getElementById("statePicker");
  const brandCaption = document.getElementById("brandCaption");
  desktop.dataset.source = "live";
  if (sourcePicker) {
    sourcePicker.value = "live";
  }
  if (statePicker) {
    statePicker.disabled = true;
  }
  if (brandCaption) {
    brandCaption.textContent = liveBrandCaptionForScreen(screen);
  }
  setSourceCopy("live");
  setSnapshotCommandLedgerFromSnapshots(`${screen} live-readonly pending`, []);
  renderUiReadonlyLaneExitSummary();
}

function renderOverviewLivePendingState() {
  const runtimeChip = document.getElementById("runtimeChip");
  setClassName(runtimeChip, "chip", "neutral");
  runtimeChip.lastElementChild.textContent = "Загрузка";
  text("desiredMode", "—");
  text("effectiveMode", "—");
  text("endpoint", "—");
  text("lastError", "ожидание live-readonly");
  document.getElementById("lastError").className = "last-error";
  text("activeCount", "—");
  text("reserveCount", "—");
  text("holdCount", "—");
  text("problemCount", "—");
  text("activeNote", "загрузка");
  text("reserveNote", "загрузка");
  text("holdNote", "загрузка");
  text("problemNote", "загрузка");
  const banner = document.getElementById("fixtureBanner");
  setClassName(banner, "fixture-banner", "neutral");
  banner.textContent = "Загрузка live-readonly. Предыдущие fixture-данные не используются как truth.";
  const sidebarDot = document.getElementById("sidebarDot");
  setClassName(sidebarDot, "dot", "neutral");
  text("sidebarStatus", "Загрузка live-readonly…");
}

function updateSetupAdmissionCopy(source) {
  const banner = document.getElementById("setupBanner");
  if (!banner) {
    return;
  }
  const desktop = document.querySelector(".desktop");
  const fixtureState = desktop?.dataset?.fixtureState || "healthy";
  if (source === "live") {
    setClassName(banner, "fixture-banner", "integration_failure");
    banner.textContent = "Live-readonly setup недоступен. Предыдущие fixture-данные не используются.";
    return;
  }
  const stateClass = fixtureState === "stale"
    ? "stale"
    : (fixtureState === "down" || fixtureState === "integration_failure" ? "degraded" : "amber");
  setClassName(banner, "fixture-banner", stateClass);
  banner.textContent = fixtureState === "stale"
    ? "Демо-режим stale. Экран показывает setup preview, не результат настройки."
    : "Демо-режим. Экран показывает setup preview, не результат настройки.";
}

function updateSelectClientCopy(source) {
  const banner = document.getElementById("selectClientBanner");
  if (!banner) {
    return;
  }
  const desktop = document.querySelector(".desktop");
  const fixtureState = desktop?.dataset?.fixtureState || "healthy";
  if (source === "live") {
    setClassName(banner, "fixture-banner", "integration_failure");
    banner.textContent = "Список клиентов недоступен. Ручной выбор ожидает desktop/native flow.";
    return;
  }
  const stateClass = fixtureState === "stale"
    ? "stale"
    : (fixtureState === "down" || fixtureState === "integration_failure" ? "degraded" : "amber");
  setClassName(banner, "fixture-banner", stateClass);
  banner.textContent = fixtureState === "stale"
    ? "Демо-режим stale. Кандидаты показаны как fixture preview, не как найденные локальные приложения."
    : "Демо-режим. Кандидаты показаны как fixture preview, не как найденные локальные приложения.";
}

function updateImportExistingCopy(source) {
  const banner = document.getElementById("importExistingBanner");
  const screen = document.getElementById("importExistingScreen");
  if (!banner || !screen) {
    return;
  }
  const params = new URLSearchParams(window.location.search);
  const requestedVariant = params.get("import_state") || "";
  const desktop = document.querySelector(".desktop");
  const fixtureState = desktop?.dataset?.fixtureState || "healthy";
  const variant = source === "live"
    ? "live_failure"
    : canonicalImportVariant(requestedVariant || fixtureState);
  screen.dataset.importVariant = variant;

  const state = importVariantModel(variant);
  setImportVisualClass(banner, "fixture-banner", state.bannerVisual);
  banner.textContent = state.banner;
  text("importRailNote", state.railNote);
  setImportChip("importCandidateChip", state.candidateVisual, state.candidateChip);
  setImportChip("importPlanChip", state.planVisual, state.planChip);
  setImportChip("importSafetyChip", state.safetyVisual, state.safetyChip);
  setImportChip("importResultChip", state.resultVisual, state.resultChip);
  text("importCandidateClient", state.client);
  pathText("importCandidateSource", state.sourcePath);
  text("importCandidateData", state.dataStatus);
  text("importCandidateAccounts", state.accountsPreview);
  text("importCandidateStatus", state.candidateStatus);
  setImportRow("importPlanSnapshotRow", state.rows.snapshot.status, state.rows.snapshot.label);
  setImportRow("importPlanAccountsRow", state.rows.accounts.status, state.rows.accounts.label);
  setImportRow("importPlanPolicyRow", state.rows.policy.status, state.rows.policy.label);
  setImportRow("importPlanRollbackRow", state.rows.rollback.status, state.rows.rollback.label);
  text("importResultTitle", state.resultTitle);
  text("importResultText", state.resultText);
  setImportPhase("importPhaseCandidate", "1", state.phases.candidate);
  setImportPhase("importPhaseDryRun", "2", state.phases.dryRun);
  setImportPhase("importPhaseSnapshot", "3", state.phases.snapshot);
  setImportPhase("importPhaseApply", "4", state.phases.apply);
}

function canonicalImportVariant(value) {
  const normalized = String(value || "").replaceAll("-", "_");
  if (["preview_ready", "healthy"].includes(normalized)) {
    return "preview_ready";
  }
  if (["no_candidate", "unknown"].includes(normalized)) {
    return "no_candidate";
  }
  if (["dry_run_missing_snapshot", "degraded"].includes(normalized)) {
    return "dry_run_missing_snapshot";
  }
  if (["snapshot_ready"].includes(normalized)) {
    return "snapshot_ready";
  }
  if (["partial"].includes(normalized)) {
    return "partial";
  }
  if (["failed", "down", "integration_failure"].includes(normalized)) {
    return "failed";
  }
  if (["rollback", "rollback_available"].includes(normalized)) {
    return "rollback_available";
  }
  if (["stale"].includes(normalized)) {
    return "stale";
  }
  return "preview_ready";
}

function importVariantModel(variant) {
  const base = {
    bannerVisual: "amber",
    banner: "Демо-режим. План импорта показан как preview, не как найденные локальные файлы.",
    railNote: "Импорт требует command-owned discovery, dry-run, snapshot и rollback packet.",
    candidateVisual: "blue",
    candidateChip: "preview",
    planVisual: "amber",
    planChip: "dry-run required",
    safetyVisual: "neutral",
    safetyChip: "bounded",
    resultVisual: "amber",
    resultChip: "apply disabled",
    client: "Codex Custom",
    sourcePath: "/Applications/Codex Custom.app",
    dataStatus: "fixture candidate display",
    accountsPreview: "preview count · not confirmed",
    candidateStatus: "Ожидает command-owned discovery",
    rows: {
      snapshot: { status: "ready", label: "ready preview" },
      accounts: { status: "deferred", label: "deferred" },
      policy: { status: "pending", label: "pending" },
      rollback: { status: "blocked", label: "rollback not confirmed" }
    },
    resultTitle: "Apply отключён",
    resultText: "Требуется dry-run packet, snapshot packet и rollback point. Preview не является runtime truth.",
    phases: {
      candidate: "candidate preview",
      dryRun: "dry-run required",
      snapshot: "snapshot required",
      apply: "apply disabled"
    }
  };
  if (variant === "no_candidate") {
    return {
      ...base,
      bannerVisual: "neutral",
      banner: "Демо-режим. Кандидат импорта отсутствует; пустое состояние не является ошибкой.",
      candidateVisual: "neutral",
      candidateChip: "no candidate",
      planVisual: "neutral",
      planChip: "not inspected",
      client: "не подтверждён",
      sourcePath: "нет command-owned candidate packet",
      dataStatus: "нет packet",
      accountsPreview: "нет packet",
      candidateStatus: "Ожидает command-owned discovery",
      rows: {
        snapshot: { status: "pending", label: "pending" },
        accounts: { status: "pending", label: "pending" },
        policy: { status: "pending", label: "pending" },
        rollback: { status: "blocked", label: "rollback missing" }
      },
      phases: { candidate: "not inspected", dryRun: "not started", snapshot: "not started", apply: "disabled" }
    };
  }
  if (variant === "dry_run_missing_snapshot") {
    return {
      ...base,
      bannerVisual: "amber",
      banner: "Dry-run preview доступен только как fixture; snapshot не подтверждён.",
      candidateChip: "fixture preview",
      planChip: "dry-run preview",
      rows: {
        snapshot: { status: "blocked", label: "snapshot missing" },
        accounts: { status: "ready", label: "ready preview" },
        policy: { status: "ready", label: "ready preview" },
        rollback: { status: "blocked", label: "rollback missing" }
      },
      resultChip: "snapshot required",
      resultTitle: "Snapshot требуется",
      resultText: "Dry-run preview не разрешает apply без snapshot и rollback point.",
      phases: { candidate: "candidate preview", dryRun: "dry-run preview", snapshot: "snapshot missing", apply: "disabled" }
    };
  }
  if (variant === "snapshot_ready") {
    return {
      ...base,
      bannerVisual: "amber",
      banner: "Snapshot preview готов, но apply остаётся disabled без admitted command surface.",
      safetyVisual: "blue",
      safetyChip: "snapshot preview",
      resultChip: "apply disabled",
      rows: {
        snapshot: { status: "ready", label: "snapshot preview" },
        accounts: { status: "ready", label: "planned preview" },
        policy: { status: "ready", label: "planned preview" },
        rollback: { status: "ready", label: "rollback preview" }
      },
      resultTitle: "Apply всё ещё отключён",
      resultText: "Snapshot preview не является rollback proof до command-owned packet.",
      phases: { candidate: "candidate preview", dryRun: "dry-run preview", snapshot: "snapshot preview", apply: "disabled" }
    };
  }
  if (variant === "partial") {
    return {
      ...base,
      bannerVisual: "amber",
      banner: "Partial import требует проверки. Partial import не считается success.",
      resultVisual: "amber",
      resultChip: "partial",
      rows: {
        snapshot: { status: "ready", label: "snapshot preview" },
        accounts: { status: "failed", label: "partial" },
        policy: { status: "blocked", label: "needs review" },
        rollback: { status: "ready", label: "rollback preview" }
      },
      resultTitle: "Partial не является success",
      resultText: "Нужен command-owned result packet и операторская проверка перед любым следующим шагом.",
      phases: { candidate: "candidate preview", dryRun: "partial", snapshot: "rollback preview", apply: "needs review" }
    };
  }
  if (variant === "failed") {
    return {
      ...base,
      bannerVisual: "red",
      banner: "Import preview failed. Никакие fixture-данные не считаются применёнными.",
      candidateVisual: "neutral",
      candidateChip: "not trusted",
      planVisual: "red",
      planChip: "failed",
      resultVisual: "red",
      resultChip: "failed",
      rows: {
        snapshot: { status: "blocked", label: "not proven" },
        accounts: { status: "failed", label: "failed" },
        policy: { status: "blocked", label: "blocked" },
        rollback: { status: "blocked", label: "not available" }
      },
      resultTitle: "Import failed",
      resultText: "Failure не меняет runtime truth и не доказывает состояние файлов.",
      phases: { candidate: "not trusted", dryRun: "failed", snapshot: "not proven", apply: "not run" }
    };
  }
  if (variant === "rollback_available") {
    return {
      ...base,
      bannerVisual: "amber",
      banner: "Rollback preview доступен только как model state; apply остаётся disabled.",
      safetyVisual: "blue",
      safetyChip: "rollback preview",
      resultVisual: "amber",
      resultChip: "rollback available",
      rows: {
        snapshot: { status: "ready", label: "snapshot preview" },
        accounts: { status: "blocked", label: "apply not run" },
        policy: { status: "pending", label: "pending" },
        rollback: { status: "ready", label: "rollback preview" }
      },
      resultTitle: "Rollback point не подтверждён",
      resultText: "Rollback доступен только после command-owned rollback_id packet.",
      phases: { candidate: "candidate preview", dryRun: "dry-run preview", snapshot: "rollback preview", apply: "not run" }
    };
  }
  if (variant === "stale") {
    return {
      ...base,
      bannerVisual: "amber",
      banner: "Import preview устарел. Stale не является зелёным состоянием.",
      candidateVisual: "amber",
      candidateChip: "stale",
      planVisual: "amber",
      planChip: "stale",
      resultVisual: "amber",
      resultChip: "stale",
      resultTitle: "Preview устарел",
      resultText: "Требуется новый command-owned packet; fixture preview не используется как live truth.",
      phases: { candidate: "stale", dryRun: "stale", snapshot: "stale", apply: "disabled" }
    };
  }
  if (variant === "live_failure") {
    return {
      ...base,
      bannerVisual: "red",
      banner: "Import discovery недоступен. Предыдущие fixture-данные не используются.",
      candidateVisual: "neutral",
      candidateChip: "unavailable",
      planVisual: "neutral",
      planChip: "not inspected",
      safetyVisual: "neutral",
      safetyChip: "bounded",
      resultVisual: "red",
      resultChip: "integration failure",
      client: "не подтверждён",
      sourcePath: "live packet unavailable",
      dataStatus: "нет live packet",
      accountsPreview: "нет packet",
      candidateStatus: "Live discovery unavailable",
      rows: {
        snapshot: { status: "pending", label: "not started" },
        accounts: { status: "pending", label: "not inspected" },
        policy: { status: "pending", label: "not inspected" },
        rollback: { status: "blocked", label: "rollback missing" }
      },
      resultTitle: "Live discovery недоступен",
      resultText: "UI не переиспользует fixture path, fixture count или preview как live truth.",
      phases: { candidate: "unavailable", dryRun: "not started", snapshot: "not started", apply: "disabled" }
    };
  }
  return base;
}

function setImportChip(id, visual, label) {
  const chip = document.getElementById(id);
  if (!chip) {
    return;
  }
  chip.className = `chip ${ACCOUNT_VISUAL_CLASS[visual] || "neutral"}`;
  chip.lastElementChild.textContent = label;
}

function setImportVisualClass(node, base, visual) {
  node.className = `${base} ${ACCOUNT_VISUAL_CLASS[visual] || "neutral"}`;
}

function setImportRow(id, status, label) {
  const row = document.getElementById(id);
  if (!row) {
    return;
  }
  row.dataset.importStatus = status;
  const value = row.querySelector("strong");
  if (value) {
    value.textContent = label;
  }
}

function setImportPhase(id, number, label) {
  const phase = document.getElementById(id);
  if (!phase) {
    return;
  }
  phase.replaceChildren();
  const circle = document.createElement("span");
  circle.textContent = number;
  const textNode = document.createElement("strong");
  textNode.textContent = label;
  phase.append(circle, textNode);
}

function updateDiagnosticsDetailSource(source) {
  const fixtureOnly = source !== "live";
  const desktop = document.querySelector(".desktop");
  const fixtureState = desktop?.dataset?.fixtureState || "unknown";
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
  const banner = document.getElementById("diagnosticsBanner");
  if (banner) {
    const fixtureCopy = {
      healthy: ["blue", "Демо-режим диагностики. Сигналы и шкала являются bounded fixture view, не runtime truth."],
      degraded: ["amber", "Демо-режим диагностики показывает деградацию сигнала без claims о runtime truth."],
      down: ["red", "Демо-режим диагностики показывает недоступный сигнал без live-подтверждения."],
      stale: ["amber", "Данные диагностики устарели. Stale не считается healthy."],
      integration_failure: ["red", "Ошибка интеграции preview. Зелёная история не используется как fallback."],
      unknown: ["neutral", "Демо-режим диагностики. Источник сигнала не подтверждён."]
    };
    const [visual, copy] = fixtureOnly
      ? (fixtureCopy[fixtureState] || fixtureCopy.unknown)
      : ["red", "Live-readonly диагностика недоступна. Предыдущие healthy-данные не используются."];
    banner.className = `fixture-banner ${visual}`;
    banner.textContent = copy;
  }
}

function setActionPanel(payload, refreshState = "none") {
  const result = payload.result || {};
  const onboarding = result.onboarding || {};
  const onboardingModel = onboardingResultModel(onboarding, payload, refreshState);
  const changedFiles = Array.isArray(result.changed_files) ? result.changed_files : [];
  const display = actionDisplayState(payload, refreshState);
  const exportModel = payload.ui_action === "export_diagnostics"
    ? diagnosticsExportResultModel(payload)
    : null;
  const safeUiAction = safeLedgerText(payload.ui_action || "unknown", "unknown");
  const safeRole = safeLedgerText(payload.action_role || "unknown", "unknown");
  const safeTarget = safeLedgerText(payload.account_id || payload.route_id || "-", "-");
  const safeMachineCode = safeLedgerText(result.machine_error_code || "-", "-");
  const safeMessage = safeLedgerText(result.human_message || "-", "-");
  const safeNextAction = safeLedgerText(result.next_action || "none", "none");
  const safeSupportDetails = safeLedgerText(actionSupportDetails(payload), "-");
  const launchResultData = payload.ui_action === "launch_client_dispatch" ? (result.data || {}) : {};
  const launchPreflightState = payload.ui_action === "launch_client_dispatch"
    ? safeLedgerText(launchResultData.launch_preflight?.status || "not run", "not run")
    : "not run";
  const launchPhase = payload.ui_action === "launch_client_dispatch"
    ? safeLedgerText(launchResultData.launch_phase || "not run", "not run")
    : "not run";
  const panel = document.getElementById("actionPanel");
  const panelVisualClass = exportModel
    ? exportModel.visual
    : payload.ui_action === "onboard_account"
    ? actionPanelVisualForOnboarding(onboardingModel, display)
    : display.visualClass;
  const displayStateLabel = exportModel ? exportModel.state : display.displayState;
  const truthNote = exportModel ? exportModel.copy : display.truthNote;
  if (panel) {
    panel.className = `action-panel compact-action-panel ${panelVisualClass}`;
  }
  text("actionUiAction", safeUiAction);
  text("actionRole", safeRole);
  text("actionAccountId", safeTarget);
  text("actionStatus", display.status);
  text("actionDisplayState", displayStateLabel);
  text("actionMachineCode", safeMachineCode);
  text("actionMessage", safeMessage);
  text("actionNextAction", safeNextAction);
  text("actionChangedFiles", `${changedFiles.length} записей метаданных`);
  text("actionSupportDetails", safeSupportDetails);
  const refreshLabel = actionRefreshLabel(payload, refreshState);
  text("actionRefreshStatus", refreshLabel);
  text("actionTruthNote", truthNote);
  text("actionOnboardingOutcome", onboardingModel.finalOutcome || "-");
  text("actionOnboardingReserveProof", onboardingModel.reserveFirst);
  text("actionOnboardingBackend", safeLedgerText(onboardingModel.selectedBackendId, "-"));
  setStatusChip("actionDisplayChip", actionDisplayLabel(displayStateLabel), panelVisualClass);
  setRuntimeModeChip("runtimeActionChip", panelVisualClass, actionDisplayLabel(displayStateLabel));
  text("runtimeActionUiAction", safeUiAction || "нет");
  text("runtimeActionMachineCode", safeMachineCode);
  text("runtimeActionRefresh", refreshLabel);
  text("runtimeActionMessage", safeMessage || "Действия режима ещё не выполнялись.");
  text("runtimeRefreshState", refreshLabel);
  text("runtimeLastCommandScope", `${safeUiAction} · action packet only`);
  setClientLaunchChip("clientActionChip", panelVisualClass, actionDisplayLabel(displayStateLabel));
  text("clientActionUiAction", safeUiAction || "нет");
  text("clientActionMachineCode", safeMachineCode);
  text("clientActionRefresh", refreshLabel);
  text("clientActionPreflight", launchPreflightState);
  text("clientActionPhase", launchPhase);
  text("clientActionMessage", safeMessage || "Запуск клиента ещё не запрашивался.");
  setAccountsPolicyChip("accountsPolicyActionChip", panelVisualClass, actionDisplayLabel(displayStateLabel));
  text("accountsPolicyActionName", safeUiAction || "нет");
  text("accountsPolicyActionTarget", safeTarget);
  text("accountsPolicyActionRefresh", refreshLabel);
  renderDiagnosticsPrivacyAction(payload, refreshLabel, displayStateLabel, panelVisualClass);
  renderAdvancedAction(payload, refreshLabel, displayStateLabel, panelVisualClass);
  text("actionSummaryTitle", safeUiAction || "Действие не выбрано");
  text("actionSummaryMeta", `target ${safeTarget} · ${displayStateLabel}`);
  text("actionSummaryMessage", safeMessage || "Действия ещё не выполнялись.");
  text("actionSummaryTarget", safeTarget);
  text("actionSummaryRefresh", refreshLabel);
  renderOnboardingResultFlow(payload, onboarding, refreshState);
  recordActionLedgerEntry(payload, refreshState, display, changedFiles);
  if (payload.ui_action === "export_diagnostics") {
    renderDiagnosticsAction(payload);
  }
  renderAccountDetailDrawer();
}

function actionPanelVisualForOnboarding(onboardingModel, display) {
  if (["ok_refresh_pending", "ok_refresh_failed"].includes(display.displayState)) {
    return display.visualClass;
  }
  if (display.displayState === "ok_refresh_complete") {
    return onboardingModel.visual;
  }
  return display.visualClass;
}

function renderOnboardingResultFlow(payload, onboarding, refreshState = "none") {
  const flow = document.getElementById("onboardingResultFlow");
  if (!flow) {
    return;
  }
  const isOnboarding = payload.ui_action === "onboard_account";
  flow.hidden = !isOnboarding;
  const panel = document.getElementById("actionPanel");
  if (panel && panel.classList && typeof panel.classList.toggle === "function") {
    panel.classList.toggle("onboarding-result-expanded", isOnboarding);
  }
  if (!isOnboarding) {
    return;
  }

  const model = onboardingResultModel(onboarding, payload, refreshState);
  const chip = document.getElementById("onboardingResultModeChip");
  chip.className = `chip ${model.visual}`;
  chip.lastElementChild.textContent = model.modeLabel;
  text("onboardingResultTitle", model.title);
  text("onboardingResultSummary", model.summary);
  text("onboardingResultSummaryNote", model.summaryNote);
  const banner = document.getElementById("onboardingResultBanner");
  banner.className = `onboarding-result-banner ${model.visual}`;
  banner.textContent = model.banner;
  text("onboardingResultNewIds", model.newBackendIds);
  text("onboardingResultSelected", model.selectedBackendId);
  setMiniPill("onboardingResultSelectionChip", model.selectionStatus, model.selectionVisual);
  setMiniPill("onboardingResultPoolChip", model.poolLabel, model.poolVisual);
  setMiniPill("onboardingResultReserveChip", model.reserveFirst, model.reserveVisual);
  setMiniPill("onboardingResultValidateChip", model.validateOutcome, model.validateVisual);
  setMiniPill("onboardingResultSyncChip", model.syncOutcome, model.syncVisual);
  setMiniPill("onboardingResultStatusProofChip", model.statusProof, model.statusProofVisual);
  setMiniPill("onboardingResultRefreshChip", model.refreshState, model.refreshVisual);
  text("onboardingResultNextAction", model.nextAction);
}

function onboardingResultModel(onboarding, payload = {}, refreshState = "none") {
  const uiState = onboarding.ui_state || "unknown_outcome";
  const finalOutcome = onboarding.final_outcome || "unknown_outcome";
  const successfulOutcome = [
    "reserve_only_success",
    "explicit_auth_imported_to_reserve"
  ].includes(finalOutcome);
  const reserveFirst = onboarding.reserve_first_proven === true;
  const rawSelectedBackendId = onboarding.selected_backend_id || "";
  const poolAfter = onboarding.pool_after_onboarding || "";
  const poolOk = poolAfter === "reserve";
  const activeRoutingUnchanged = onboarding.active_routing_changed === false;
  const validateOk = onboarding.validate_outcome === "ok";
  const statusProofOk = onboardingStatusProofOk(onboarding);
  const success = uiState === "success"
    && successfulOutcome
    && reserveFirst
    && rawSelectedBackendId
    && poolOk
    && activeRoutingUnchanged
    && validateOk
    && statusProofOk;
  const selectedBackendId = success ? rawSelectedBackendId : "-";
  const integrationStatus = payload.status || payload.result?.status || "";
  const integrationVisual = integrationStatus === "timeout"
    ? "amber"
    : (["invalid_json", "integration_failure"].includes(integrationStatus) ? "red" : "");
  const newBackendIds = Array.isArray(onboarding.new_backend_ids) && onboarding.new_backend_ids.length
    ? `[${onboarding.new_backend_ids.join(", ")}]`
    : `[${selectedBackendId}]`;
  const visual = success
    ? "green"
    : (integrationVisual || (uiState === "needs_user_action" ? "amber" : (uiState === "command_error" ? "red" : "neutral")));
  const banner = success
    ? "Аккаунт добавлен в резерв. Активная маршрутизация не изменялась."
    : onboardingResultBanner(uiState, finalOutcome);
  const syncSkipped = String(onboarding.sync_outcome || "").includes("skipped");
  return {
    finalOutcome,
    visual,
    title: success ? "Аккаунт добавлен в резерв" : onboardingResultTitle(uiState, finalOutcome),
    summary: success ? "Reserve-first proof принят" : onboardingResultSummary(uiState, finalOutcome),
    summaryNote: success
      ? "Выбранный backend показан только из доказанного packet результата."
      : "UI не показывает selected backend и не достраивает success.",
    modeLabel: success ? "reserve-first proof" : uiStateLabel(uiState),
    banner,
    newBackendIds: success ? newBackendIds : "-",
    selectedBackendId,
    selectionStatus: onboarding.selection_status || "-",
    selectionVisual: success ? "green" : (uiState === "needs_user_action" ? "amber" : "neutral"),
    poolLabel: success ? "Резерв" : (poolAfter || "pool unknown"),
    poolVisual: success ? "green" : "neutral",
    reserveFirst: reserveFirst ? "доказано" : "не доказано",
    reserveVisual: reserveFirst ? "green" : "amber",
    validateOutcome: onboarding.validate_outcome || "-",
    validateVisual: onboarding.validate_outcome === "ok" ? "green" : (onboarding.validate_outcome ? "amber" : "neutral"),
    syncOutcome: onboarding.sync_outcome || "-",
    syncVisual: onboarding.sync_outcome === "ok" ? "green" : (onboarding.sync_outcome ? "blue" : "neutral"),
    statusProof: statusProofOk ? "confirmed" : "not confirmed",
    statusProofVisual: statusProofOk ? "green" : "amber",
    refreshState: onboardingRefreshLabel(payload, refreshState),
    refreshVisual: refreshState === "complete" ? "green" : (refreshState === "failed" ? "red" : (payload.post_action_refresh_required ? "amber" : "neutral")),
    nextAction: onboardingNextAction(uiState, finalOutcome, success, syncSkipped)
  };
}

function onboardingResultBanner(uiState, finalOutcome) {
  if (uiState === "needs_user_action") {
    if (finalOutcome === "no_new_auth_detected") {
      return "Новых auth-данных не найдено. Действие не добавило аккаунт.";
    }
    if (finalOutcome === "ambiguous_new_auth_detection") {
      return "Требуется действие оператора: найдено несколько возможных кандидатов.";
    }
    return `${finalOutcome}: подключение не считается успешным без действия оператора.`;
  }
  if (uiState === "command_error") {
    if (["validate_failed", "validation_failed"].includes(finalOutcome)) {
      return "Проверка не пройдена. Аккаунт не используется для маршрутизации.";
    }
    if (finalOutcome === "status_failed") {
      return "Статус не подтверждён. Результат onboarding не считается runtime truth.";
    }
    return `${finalOutcome}: команда не дала безопасный reserve-first успех.`;
  }
  return "Результат подключения недостаточен для зелёного вывода; UI не достраивает успех.";
}

function onboardingResultTitle(uiState, finalOutcome) {
  if (finalOutcome === "no_new_auth_detected") {
    return "Новых auth-данных не найдено";
  }
  if (finalOutcome === "ambiguous_new_auth_detection") {
    return "Требуется действие оператора";
  }
  if (["validate_failed", "validation_failed"].includes(finalOutcome)) {
    return "Проверка не пройдена";
  }
  if (finalOutcome === "status_failed") {
    return "Статус не подтверждён";
  }
  if (uiState === "command_error") {
    return "Onboarding не завершён";
  }
  return "Итог не подтверждён";
}

function onboardingResultSummary(uiState, finalOutcome) {
  if (finalOutcome === "no_new_auth_detected") {
    return "Новый backend не появился";
  }
  if (finalOutcome === "ambiguous_new_auth_detection") {
    return "Нужен выбор оператора";
  }
  if (["validate_failed", "validation_failed"].includes(finalOutcome)) {
    return "Validation proof отсутствует";
  }
  if (finalOutcome === "status_failed") {
    return "Status proof отсутствует";
  }
  if (uiState === "command_error") {
    return "Команда не дала admitted result";
  }
  return "Требуется новый packet truth";
}

function onboardingStatusProofOk(onboarding) {
  const observed = onboarding.status_observed;
  return Boolean(
    observed
    && typeof observed === "object"
    && observed.command_status === "ok"
  );
}

function onboardingRefreshLabel(payload, refreshState) {
  if (refreshState === "complete") {
    return "refresh complete";
  }
  if (refreshState === "failed") {
    return "refresh failed";
  }
  return payload.post_action_refresh_required ? "refresh pending" : "refresh not required";
}

function onboardingNextAction(uiState, finalOutcome, success, syncSkipped = false) {
  if (success) {
    if (syncSkipped) {
      return "Аккаунт находится в резерве. Следующее действие: запустить сверку отдельной командой.";
    }
    return "Аккаунт находится в резервном пуле. Проверка или продвижение возможны только отдельным действием оператора.";
  }
  if (uiState === "needs_user_action") {
    return "Нужно действие оператора: проверьте источник авторизации и повторите существующий flow без новых browser payload.";
  }
  if (uiState === "command_error") {
    return "Исправьте причину ошибки и повторите существующий onboard flow; active routing не менялся.";
  }
  return `Состояние ${finalOutcome} не admitted как успех; требуется новый packet truth или действие оператора.`;
}

function uiStateLabel(uiState) {
  return {
    success: "reserve-first",
    needs_user_action: "operator action",
    command_error: "failed",
    unknown_outcome: "unknown"
  }[uiState] || uiState;
}

function setMiniPill(id, label, visual) {
  const node = document.getElementById(id);
  if (!node) {
    return;
  }
  node.className = `mini-pill ${visual || "neutral"}`;
  node.textContent = label || "-";
}

function setStatusChip(id, label, visual) {
  const node = document.getElementById(id);
  if (!node) {
    return;
  }
  node.className = `chip ${visual || "neutral"}`;
  if (typeof node.replaceChildren !== "function") {
    node.textContent = label || "-";
    return;
  }
  node.replaceChildren();
  const dot = document.createElement("span");
  dot.className = "dot";
  const value = document.createElement("span");
  value.textContent = label || "-";
  node.append(dot, value);
}

function recordActionLedgerEntry(payload, refreshState, display, changedFiles) {
  const result = payload.result || {};
  const exportModel = payload.ui_action === "export_diagnostics"
    ? diagnosticsExportResultModel(payload)
    : null;
  const entry = {
    key: actionLedgerKey(payload, result),
    uiAction: payload.ui_action || "unknown",
    role: payload.action_role || metadataFor(payload.ui_action || "unknown").action_role || "unknown",
    target: safeLedgerText(payload.account_id || payload.route_id || "-", "-"),
    status: display.status,
    displayState: exportModel ? exportModel.state : display.displayState,
    visualClass: exportModel ? exportModel.visual : display.visualClass,
    machineCode: safeLedgerText(result.machine_error_code || "-", "-"),
    message: safeLedgerText(result.human_message || "-", "-"),
    nextAction: safeLedgerText(result.next_action || "none", "none"),
    changedFilesCount: changedFiles.length,
    refreshStatus: actionRefreshLabel(payload, refreshState),
    truthNote: exportModel ? exportModel.copy : display.truthNote,
    supportDetails: safeLedgerText(actionSupportDetails(payload), "-"),
    specialDetails: safeLedgerText(actionSpecialDetails(payload), "-"),
    timestamp: actionLedgerTimestamp()
  };
  if (["complete", "failed", "mismatch"].includes(refreshState) && actionLedger[0]?.key === entry.key) {
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
  const entries = actionLedger.filter(actionLedgerFilterPredicate);
  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "action-ledger-empty";
    empty.textContent = actionLedger.length
      ? "Нет записей для выбранного фильтра."
      : "Действия ещё не выполнялись в этой UI-сессии.";
    list.append(empty);
    return;
  }
  for (const entry of entries) {
    list.append(actionLedgerRow(entry));
  }
}

function actionLedgerFilterPredicate(entry) {
  if (actionLedgerFilter === "errors") {
    return ["red", "amber"].includes(entry.visualClass)
      && !["ok_refresh_pending", "running"].includes(entry.displayState);
  }
  if (actionLedgerFilter === "refresh") {
    return ["ok_refresh_pending", "ok_refresh_failed", "refresh_mismatch"].includes(entry.displayState)
      || entry.refreshStatus.includes("pending")
      || entry.refreshStatus.includes("failed")
      || entry.refreshStatus.includes("mismatch");
  }
  return true;
}

function actionLedgerRow(entry) {
  const row = document.createElement("details");
  row.className = `action-ledger-row ${entry.visualClass}`;
  row.open = false;

  const head = document.createElement("summary");
  head.className = "action-ledger-row-head";
  setNodeAttribute(head, "aria-label", `Раскрыть детали действия ${entry.uiAction}`);
  const titleWrap = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = `${entry.uiAction} · ${entry.target}`;
  const time = document.createElement("small");
  time.textContent = entry.timestamp;
  titleWrap.append(title, time);
  const chip = document.createElement("span");
  chip.className = `chip ${entry.visualClass}`;
  const dot = document.createElement("span");
  dot.className = "dot";
  const chipText = document.createElement("span");
  chipText.textContent = actionDisplayLabel(entry.displayState);
  chip.append(dot, chipText);
  head.append(titleWrap, chip);

  const meta = document.createElement("div");
  meta.className = "action-ledger-meta";
  meta.textContent = [
    `target ${entry.target}`,
    `machine ${entry.machineCode}`,
    `refresh ${entry.refreshStatus}`
  ].join(" · ");

  const message = document.createElement("p");
  message.textContent = entry.message;

  const truth = document.createElement("div");
  truth.className = "action-ledger-truth";
  truth.textContent = `command packet outcome only · ${entry.truthNote}`;

  row.append(head, meta, message, truth);
  const detailGrid = document.createElement("div");
  detailGrid.className = "action-ledger-detail-grid";
  for (const [label, value] of [
    ["machine", entry.machineCode],
    ["next", entry.nextAction],
    ["refresh", entry.refreshStatus],
    ["display", entry.displayState],
    ["claim scope", entry.role],
    ["changed files", `${entry.changedFilesCount} metadata entries`]
  ]) {
    const labelNode = document.createElement("span");
    labelNode.textContent = label;
    const valueNode = document.createElement("strong");
    valueNode.textContent = value;
    detailGrid.append(labelNode, valueNode);
  }
  row.append(detailGrid);
  if (entry.supportDetails && entry.supportDetails !== "-") {
    const support = document.createElement("div");
    support.className = "action-ledger-support";
    support.textContent = entry.supportDetails;
    row.append(support);
  }
  if (entry.specialDetails && entry.specialDetails !== "-") {
    const special = document.createElement("div");
    special.className = "action-ledger-support";
    special.textContent = entry.specialDetails;
    row.append(special);
  }
  return row;
}

function safeLedgerText(value, fallback = "-") {
  const textValue = String(value || "").trim();
  if (!textValue) {
    return fallback;
  }
  const rawDispatchPattern = new RegExp("\\b(argv|raw_json|stack_trace)\\s*[:=]\\s*[^ \\n\\t,;)]*", "gi");
  const browserCommandIdPattern = new RegExp("\\b(command" + "_id)\\s*[:=]\\s*[^ \\n\\t,;)]*", "gi");
  return redactUiSensitiveText(textValue)
    .replace(rawDispatchPattern, "$1=[redacted]")
    .replace(browserCommandIdPattern, "$1=[redacted]");
}

function actionLedgerTimestamp() {
  try {
    return new Date().toLocaleTimeString("ru-RU", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });
  } catch (_error) {
    return "UI-session";
  }
}

function actionSpecialDetails(payload) {
  const result = payload.result || {};
  const onboarding = result.onboarding || {};
  if (payload.ui_action === "onboard_account" && Object.keys(onboarding).length) {
    const newIds = Array.isArray(onboarding.new_backend_ids) ? onboarding.new_backend_ids.length : 0;
    return [
      `selected_backend_id=${onboarding.selected_backend_id || "-"}`,
      `new_backend_ids=${newIds}`,
      `reserve_first=${onboarding.reserve_first_proven === true ? "true" : "false"}`,
      `final_outcome=${onboarding.final_outcome || "-"}`
    ].join(" · ");
  }
  if (payload.ui_action === "export_diagnostics") {
    const data = result.data || {};
    const exportModel = diagnosticsExportResultModel(payload);
    return [
      `artifact_ref=${artifactReference(data.bundle_path)}`,
      `redaction=${exportModel.redactionStatus}`,
      `changed_files=${Array.isArray(result.changed_files) ? result.changed_files.length : 0}`,
      "claim_scope=support_artifact_only"
    ].join(" · ");
  }
  return "-";
}

function openActionLedgerPanel() {
  const overlay = document.getElementById("actionLedgerOverlay");
  if (!overlay) {
    return;
  }
  overlay.hidden = false;
  renderActionLedger();
}

function closeActionLedgerPanel() {
  const overlay = document.getElementById("actionLedgerOverlay");
  if (overlay) {
    overlay.hidden = true;
  }
}

function setActionLedgerFilter(filter) {
  actionLedgerFilter = ["all", "errors", "refresh"].includes(filter) ? filter : "all";
  for (const button of document.querySelectorAll("[data-ledger-filter]")) {
    button.classList.toggle("active", button.dataset.ledgerFilter === actionLedgerFilter);
  }
  renderActionLedger();
}

function clearActionLedger() {
  actionLedger = [];
  renderActionLedger();
}

function setSnapshotCommandLedgerFromSnapshots(surface, snapshots) {
  const snapshotList = Array.isArray(snapshots) ? snapshots : [snapshots];
  const entries = [];
  for (const snapshot of snapshotList) {
    if (!snapshot || typeof snapshot !== "object") {
      continue;
    }
    const commands = snapshot.commands && typeof snapshot.commands === "object" ? snapshot.commands : {};
    for (const [commandId, command] of Object.entries(commands)) {
      if (!command || typeof command !== "object") {
        continue;
      }
      entries.push(snapshotCommandLedgerEntry(commandId, command, snapshot));
    }
  }
  snapshotCommandLedgerState = {
    surface: safeLedgerText(surface || "read-only snapshot", "read-only snapshot"),
    status: snapshotList.some((snapshot) => snapshot?.status === "integration_failure")
      ? "integration_failure"
      : (entries.length ? "loaded" : "missing"),
    source: safeLedgerText(snapshotList.map((snapshot) => snapshot?.source).filter(Boolean).join(" + "), "unknown"),
    entries: entries.slice(0, 12),
    hasWarnings: snapshotList.some((snapshot) => snapshot?.has_warnings === true || snapshot?.status === "integration_failure")
  };
  renderSnapshotCommandLedger();
}

function snapshotCommandLedgerEntry(commandId, command, snapshot) {
  return {
    commandId: safeLedgerText(commandId, "unknown"),
    role: safeLedgerText(command.role || "unknown", "unknown"),
    status: safeLedgerText(command.status || "unknown", "unknown"),
    uiState: safeLedgerText(command.ui_state || "unknown", "unknown"),
    machineCode: safeLedgerText(command.machine_error_code || "-", "-"),
    exitCode: Number.isFinite(Number(command.exit_code)) ? String(command.exit_code) : "-",
    nextAction: safeLedgerText(command.next_action || "none", "none"),
    visualClass: snapshotCommandVisual(command, snapshot),
    source: safeLedgerText(snapshot?.source || "unknown", "unknown")
  };
}

function snapshotCommandVisual(command, snapshot) {
  const status = String(command.status || "unknown");
  const uiState = String(command.ui_state || "unknown");
  if (["command_error", "integration_failure", "invalid_json"].includes(status) || uiState === "integration_failure") {
    return "red";
  }
  if (status !== "ok" || ["degraded", "down", "unknown"].includes(uiState) || snapshot?.has_warnings === true) {
    return "amber";
  }
  return "blue";
}

function renderSnapshotCommandLedger() {
  const list = document.getElementById("snapshotCommandLedgerList");
  const surface = document.getElementById("snapshotCommandLedgerSurface");
  const scope = document.getElementById("snapshotCommandLedgerScope");
  if (surface) {
    surface.textContent = `${snapshotCommandLedgerState.surface} · ${snapshotCommandLedgerState.source} · command packet outcome only`;
  }
  if (scope) {
    const visual = snapshotCommandLedgerState.status === "integration_failure"
      ? "red"
      : (snapshotCommandLedgerState.hasWarnings ? "amber" : (snapshotCommandLedgerState.entries.length ? "blue" : "neutral"));
    scope.className = `chip ${visual}`;
    scope.lastElementChild.textContent = snapshotCommandLedgerState.entries.length
      ? `${snapshotCommandLedgerState.entries.length} summaries`
      : "нет summaries";
  }
  if (!list || typeof list.replaceChildren !== "function") {
    return;
  }
  list.replaceChildren();
  if (!snapshotCommandLedgerState.entries.length) {
    const empty = document.createElement("div");
    empty.className = "action-ledger-empty";
    empty.textContent = "Нет bounded command summaries в последнем read-only snapshot.";
    list.append(empty);
    return;
  }
  for (const entry of snapshotCommandLedgerState.entries) {
    list.append(snapshotCommandLedgerRow(entry));
  }
}

function snapshotCommandLedgerRow(entry) {
  const row = document.createElement("details");
  row.className = `action-ledger-row ${entry.visualClass}`;
  row.open = false;

  const head = document.createElement("summary");
  head.className = "action-ledger-row-head";
  setNodeAttribute(head, "aria-label", `Раскрыть read-only command summary ${entry.commandId}`);
  const titleWrap = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = `${entry.commandId} · ${entry.role}`;
  const source = document.createElement("small");
  source.textContent = entry.source;
  titleWrap.append(title, source);
  const chip = document.createElement("span");
  chip.className = `chip ${entry.visualClass}`;
  const dot = document.createElement("span");
  dot.className = "dot";
  const chipText = document.createElement("span");
  chipText.textContent = entry.status;
  chip.append(dot, chipText);
  head.append(titleWrap, chip);

  const truth = document.createElement("div");
  truth.className = "action-ledger-truth";
  truth.textContent = "command packet outcome only · not runtime health proof";

  const detailGrid = document.createElement("div");
  detailGrid.className = "action-ledger-detail-grid";
  for (const [label, value] of [
    ["command", entry.commandId],
    ["role", entry.role],
    ["status", entry.status],
    ["ui_state", entry.uiState],
    ["machine", entry.machineCode],
    ["exit", entry.exitCode],
    ["next", entry.nextAction]
  ]) {
    const labelNode = document.createElement("span");
    labelNode.textContent = label;
    const valueNode = document.createElement("strong");
    valueNode.textContent = value;
    detailGrid.append(labelNode, valueNode);
  }
  row.append(head, truth, detailGrid);
  return row;
}

function renderUiReadonlyLaneExitSummary() {
  const summary = document.getElementById("uiLaneExitSummary");
  if (!summary) {
    return;
  }
  const chip = document.getElementById("uiLaneExitChip");
  const model = uiReadonlyLaneExitSummaryModel();
  if (chip) {
    chip.className = `chip ${model.visual}`;
    chip.lastElementChild.textContent = model.chipLabel;
  }
  text("uiLaneExitSource", model.sourceLabel);
  text("uiLaneExitTruthNote", model.truthNote);
  text("uiLaneExitCurrentSource", model.currentSource);
  text("uiLaneExitSnapshotState", model.snapshotState);
  text("uiLaneExitLiveChain", model.liveChain);
  text("uiLaneExitMetadataStatus", model.metadataStatus);
  text("uiLaneExitSafeSummary", model.safeSummary);
  text("uiLaneExitNextContour", UI_READONLY_LANE_NEXT_CONTOUR);
  renderUiReadonlyLaneExitList("uiLaneExitBlockedList", model.blockedNow, "amber");
  renderUiReadonlyLaneExitList("uiLaneExitSafeList", model.safeNow, "blue");
  renderUiReadonlyLaneExitList("uiLaneExitForbiddenList", model.forbiddenNow, "red");
}

function uiReadonlyLaneExitSummaryModel() {
  const desktop = document.querySelector(".desktop");
  const source = desktop?.dataset?.source === "live" ? "live-readonly" : "fixture preview";
  const screen = currentScreen();
  const snapshotState = snapshotCommandLedgerState.entries.length
    ? `${snapshotCommandLedgerState.entries.length} bounded summaries · ${snapshotCommandLedgerState.status}`
    : (snapshotCommandLedgerState.status === "integration_failure"
      ? "snapshot unavailable"
      : "no bounded summaries loaded");
  const parkedCount = Object.values(actionMetadata).filter((metadata) => (
    metadata?.disabled_reason_code === "RUNTIME_LIVE_ACTION_CHAIN_PARKED"
    || metadata?.availability_state === "disabled_live_action"
  )).length;
  const metadataStatus = parkedCount
    ? `${parkedCount} live actions blocked in current metadata`
    : "metadata loaded without parked-action count";
  const visual = snapshotCommandLedgerState.status === "integration_failure" ? "red" : "amber";
  return {
    visual,
    chipLabel: snapshotCommandLedgerState.status === "integration_failure" ? "blocked truth" : "parked handoff",
    sourceLabel: `${screen} · ${source} · no new commands`,
    truthNote: snapshotCommandLedgerState.status === "integration_failure"
      ? "Runtime/live-action chain remains parked. Read-only UI lane is sufficient for now, but current live snapshot truth is degraded and the next contour must return to runtime diagnosis."
      : "Runtime/live-action chain remains parked. Read-only UI lane is sufficient for now and should stop here; the next contour must return to runtime diagnosis instead of another UI panel.",
    currentSource: source,
    snapshotState,
    liveChain: "parked by canon-backed runtime blockers",
    metadataStatus,
    safeSummary: "read-only truth, disabled reasons, snapshot command summaries",
    blockedNow: UI_READONLY_LANE_BLOCKERS,
    safeNow: UI_READONLY_LANE_SAFE_SCOPE.map((entry) => [entry, "No dispatch, no mutation, no new runtime truth claim."]),
    forbiddenNow: UI_READONLY_LANE_FORBIDDEN_SCOPE.map((entry) => [entry, "Blocked until runtime diagnosis closes the parked chain."])
  };
}

function renderUiReadonlyLaneExitList(containerId, entries, visual) {
  const container = document.getElementById(containerId);
  if (!container || typeof container.replaceChildren !== "function") {
    return;
  }
  container.replaceChildren();
  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "action-ledger-empty";
    empty.textContent = "Нет данных для этой сводки.";
    container.append(empty);
    return;
  }
  for (const entry of entries) {
    const row = document.createElement("div");
    row.className = `action-ledger-row ${visual}`;
    const title = document.createElement("strong");
    title.textContent = safeLedgerText(entry[0], "-");
    const note = document.createElement("div");
    note.className = "action-ledger-meta";
    note.textContent = safeLedgerText(entry[1], "-");
    row.append(title, note);
    container.append(row);
  }
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
  if (payload.ui_action === "export_diagnostics") {
    const exportModel = diagnosticsExportResultModel(payload);
    return `support artifact · ${artifactReference(data.bundle_path)} · redaction=${exportModel.redactionStatus}`;
  }
  return "-";
}

function renderDiagnosticsAction(payload) {
  const result = payload.result || {};
  const data = result.data || {};
  const exportModel = diagnosticsExportResultModel(payload);
  const changedFiles = Array.isArray(result.changed_files) ? result.changed_files : [];
  const chip = document.getElementById("diagnosticsStatusChip");
  if (!chip) {
    return;
  }
  chip.className = `chip ${exportModel.visual}`;
  chip.lastElementChild.textContent = exportModel.label;
  text("diagnosticsMessage", safeLedgerText(result.human_message || "Команда диагностики не вернула сообщение."));
  text("diagnosticsPacketStatus", exportModel.state);
  text("diagnosticsExitCode", result.exit_code ?? "-");
  text("diagnosticsMachineCode", safeLedgerText(result.machine_error_code || "-"));
  text("diagnosticsNextAction", safeLedgerText(result.next_action || "none", "none"));
  text("diagnosticsChangedFiles", `${changedFiles.length}`);
  text("diagnosticsBundleRef", artifactReference(data.bundle_path));

  const banner = document.getElementById("diagnosticsBanner");
  banner.className = `fixture-banner ${exportModel.visual}`;
  banner.textContent = exportModel.copy;
}

function diagnosticsExportResultModel(payload) {
  const result = payload.result || {};
  const data = result.data || {};
  const status = String(result.status || payload.status || "unknown");
  const redactionStatus = normalizeDiagnosticsRedactionStatus(data.redaction_status);
  const artifactRef = artifactReference(data.bundle_path);
  const hasArtifact = artifactRef !== "не предоставлено";
  if (status === "ok" && redactionStatus === "failed") {
    return {
      state: "redaction_failed",
      label: "Redaction failed",
      visual: "red",
      redactionStatus,
      copy: "Экспорт вернул redaction failure. Artifact не считается безопасным, UI не читает bundle и не меняет runtime truth."
    };
  }
  if (status === "ok" && !hasArtifact) {
    return {
      state: "artifact_unavailable",
      label: "Artifact unavailable",
      visual: "amber",
      redactionStatus,
      copy: "Команда не вернула reference артефакта. Это не runtime health truth; повторите export или откройте журнал действий."
    };
  }
  if (status === "ok" && redactionStatus === "unreported") {
    return {
      state: "redaction_unreported",
      label: "Redaction not reported",
      visual: "amber",
      redactionStatus,
      copy: "Артефакт диагностики создан, но redaction не подтверждена packet-ом. Это support artifact, не runtime health truth."
    };
  }
  if (status === "ok") {
    return {
      state: "created",
      label: "Артефакт создан",
      visual: "blue",
      redactionStatus,
      copy: "Артефакт диагностики создан. Пути и секреты скрыты; это support artifact, не runtime health truth."
    };
  }
  if (status === "timeout") {
    return {
      state: "timeout",
      label: "Timeout",
      visual: "amber",
      redactionStatus,
      copy: "Экспорт диагностики истёк по времени. Успех не выводится; можно повторить команду."
    };
  }
  if (status === "invalid_json") {
    return {
      state: "invalid_json",
      label: "Invalid JSON",
      visual: "red",
      redactionStatus,
      copy: "Экспорт вернул invalid JSON. Это ошибка интеграции, а не результат диагностики."
    };
  }
  if (status === "running") {
    return {
      state: "running",
      label: "Выполняется",
      visual: "amber",
      redactionStatus,
      copy: "Экспорт диагностики выполняется. UI не меняет runtime truth и не читает bundle."
    };
  }
  return {
    state: status === "command_error" ? "command_error" : (status === "integration_failure" ? "integration_failure" : "command_error"),
    label: status === "integration_failure" ? "Ошибка интеграции" : "Ошибка команды",
    visual: "red",
    redactionStatus,
    copy: "Команда диагностики не создала успешный support artifact. Истина о здоровье runtime не изменялась."
  };
}

function normalizeDiagnosticsRedactionStatus(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (["enabled", "passed", "enforced", "ok", "true"].includes(normalized)) {
    return "enabled";
  }
  if (["failed", "failure", "error", "redaction_failed", "false"].includes(normalized)) {
    return "failed";
  }
  return "unreported";
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
    const copy = {
      healthy: "Демо-режим настроек. Значения показывают admitted layout, не runtime config truth.",
      degraded: "Настройки доступны только для чтения. Деградация не открывает config mutation.",
      down: "Настройки доступны только для чтения. Runtime недоступен, изменения не принимаются.",
      stale: "Данные настроек устарели. Требуется обновление перед изменениями.",
      integration_failure: "Live-readonly настройки недоступны. Предыдущие fixture-значения не используются как saved state.",
      unknown: "Настройки доступны только для чтения. Источник состояния не подтверждён."
    };
    banner.textContent = copy[visualState] || copy.unknown;
  }
  renderDataLayoutSnapshot(snapshot);
  renderRuntimeModeSnapshot(snapshot);
  renderClientLaunchSnapshot(snapshot);
  renderAccountsPolicySnapshot(snapshot);
  renderDiagnosticsPrivacySnapshot(snapshot);
  renderAdvancedSettingsSnapshot(snapshot);
}

function updateSettingsActionMetadata() {
  const launch = metadataFor("launch_client_dispatch");
  const target = document.getElementById("settingsLaunchAvailability");
  if (!target) {
    return;
  }
  const preflight = launchPreflightSummary(launch);
  target.textContent = launch.available === false
    ? `${preflight.statusLabel} · ${preflight.reason}`
    : `${preflight.statusLabel} · isolated copy admitted`;
}

function setClientLaunchChip(id, visual, label) {
  const chip = document.getElementById(id);
  if (!chip) {
    return;
  }
  chip.className = `chip ${ACCOUNT_VISUAL_CLASS[visual] || VISUAL_CLASS[visual] || "neutral"}`;
  const labelNode = chip.lastElementChild;
  if (labelNode) {
    labelNode.textContent = label;
  }
}

function launchPreflightSummary(metadata) {
  const raw = metadata?.launch_preflight || {};
  const admitted = raw.status === "admitted";
  return {
    admitted,
    status: raw.status || "denied",
    reason: raw.reason || (metadata?.unavailable_reason || "preflight не подтверждён"),
    targetKind: raw.target_kind || "unknown",
    separateProfile: raw.separate_profile === true,
    separateDataDir: raw.separate_data_dir === true,
    separatePort: raw.separate_port === true,
    processConfirmationPossible: raw.process_confirmation_possible === true,
    currentSessionUntouched: raw.current_session_untouched === true,
    statusLabel: admitted ? "preflight admitted" : "preflight blocked"
  };
}

function clientLaunchModelFromSnapshot(snapshot) {
  const runtime = snapshot?.runtime || {};
  const source = snapshot?.source === "live_readonly" ? "live" : "fixture";
  const state = snapshot?.state_id || snapshot?.ui_state || runtime.visual_state || "unknown";
  const liveFailure = source === "live" && snapshot?.status === "integration_failure";
  const launch = metadataFor("launch_client_dispatch");
  const launchPreflight = launchPreflightSummary(launch);
  const launchAdmitted = launch.available !== false;
  const runtimeDown = state === "down" || liveFailure;
  const stale = state === "stale";
  const degraded = state === "degraded";
  const visual = liveFailure || runtimeDown
    ? "red"
    : (stale || degraded ? "amber" : (state === "healthy" ? "green" : "neutral"));
  const candidateVisual = liveFailure
    ? "red"
    : (stale ? "amber" : (state === "healthy" || degraded ? "green" : "neutral"));
  const selectedName = liveFailure ? "unknown" : "Codex Custom";
  const selectedStatus = liveFailure
    ? "unavailable"
    : (stale ? "stale" : (degraded ? "requires verification" : (state === "healthy" ? "available" : "unknown")));
  const inertPath = liveFailure
    ? "Каталог не подтверждён"
    : "~/Applications/Codex Custom.app · inert display only";
  const runtimeReachable = runtimeDown ? "down" : (stale ? "stale" : (state === "healthy" || degraded ? "OK" : "unknown"));
  const modeCompatible = runtime.desired_mode && runtime.effective_mode && runtime.desired_mode !== runtime.effective_mode
    ? "mismatch"
    : (runtimeDown ? "unknown" : (stale ? "stale" : "OK"));
  const accountsAvailable = state === "healthy" ? "OK" : (runtimeDown ? "unknown" : (stale || degraded ? "warning" : "unknown"));
  const dispatch = launchAdmitted ? "dispatch admitted" : `disabled · ${launch.unavailable_reason || "server-owned target missing"}`;
  const processProof = launchPreflight.processConfirmationPossible ? "possible after packet proof" : "not admitted";
  return {
    source,
    visual,
    candidateVisual,
    launchAdmitted,
    launchPreflight,
    panelLabel: liveFailure ? "unavailable" : (stale ? "stale" : (degraded ? "requires check" : "ready preview")),
    bannerCopy: liveFailure
      ? "Client status недоступен. Предыдущие fixture-данные не используются."
      : (stale
        ? "Client status устарел. Требуется refresh из bounded packet."
        : (launchPreflight.admitted
          ? "Демо-режим. Изолированная копия admitted только через server-owned preflight."
          : "Демо-режим. Изолированная копия не admitted без server-owned preflight.")),
    selectedName,
    selectedStatus,
    selectedSource: source === "live" ? "command-owned packet" : "fixture preview",
    inertPath,
    lastChecked: liveFailure ? "—" : (runtime.observed_at_utc || "Сегодня, 12:45"),
    readinessVisual: visual,
    readinessLabel: runtimeDown ? "blocked" : (stale || degraded ? "warning" : "ready"),
    candidateStatus: liveFailure ? "unavailable" : (degraded ? "requires verification" : (stale ? "stale" : "OK")),
    runtimeReachable,
    modeCompatible,
    accountsAvailable,
    preflight: launchPreflight.statusLabel,
    dispatch,
    processProof
  };
}

function renderClientLaunchSnapshot(snapshot) {
  const model = clientLaunchModelFromSnapshot(snapshot || {});
  setClientLaunchChip("clientLaunchPanelChip", model.visual, model.panelLabel);
  setClientLaunchChip("clientSelectedChip", model.candidateVisual, model.selectedStatus);
  setClientLaunchChip("clientReadinessChip", model.readinessVisual, model.readinessLabel);
  setClientLaunchChip("clientDispatchChip", model.launchAdmitted ? "blue" : "amber", model.launchAdmitted ? "dispatch admitted" : "dispatch disabled");

  text("clientSelectedName", model.selectedName);
  text("clientSelectedStatus", model.selectedStatus);
  text("clientSelectedSource", model.selectedSource);
  text("clientSelectedPath", model.inertPath);
  const pathNode = document.getElementById("clientSelectedPath");
  if (pathNode) {
    pathNode.title = model.inertPath;
  }
  text("clientSelectedChecked", model.lastChecked);
  text("clientReadyCandidate", model.candidateStatus);
  text("clientReadyRuntime", model.runtimeReachable);
  text("clientReadyMode", model.modeCompatible);
  text("clientReadyAccounts", model.accountsAvailable);
  text("clientReadyPreflight", model.preflight);
  text("clientReadyDispatch", model.dispatch);
  text("clientReadyProcess", model.processProof);

  const banner = document.getElementById("settingsBanner");
  if (banner && currentScreen() === "settings" && currentSettingsSection() === "client") {
    banner.className = `fixture-banner ${ACCOUNT_VISUAL_CLASS[model.visual] || VISUAL_CLASS[model.visual] || "neutral"}`;
    banner.textContent = model.bannerCopy;
  }
}

function setAccountsPolicyChip(id, visual, label) {
  const chip = document.getElementById(id);
  if (!chip) {
    return;
  }
  chip.className = `chip ${ACCOUNT_VISUAL_CLASS[visual] || VISUAL_CLASS[visual] || "neutral"}`;
  const labelNode = chip.lastElementChild;
  if (labelNode) {
    labelNode.textContent = label;
  }
}

function accountsPolicyModelFromSnapshot(snapshot) {
  const runtime = snapshot?.runtime || {};
  const pool = snapshot?.pool_summary || {};
  const source = snapshot?.source === "live_readonly" ? "live" : "fixture";
  const state = snapshot?.state_id || snapshot?.ui_state || runtime.visual_state || "unknown";
  const liveFailure = source === "live" && snapshot?.status === "integration_failure";
  const stale = state === "stale" || runtime.visual_state === "stale";
  const down = state === "down" || runtime.visual_state === "down" || liveFailure;
  const degraded = state === "degraded" || runtime.visual_state === "degraded";
  const noAccounts = Number(pool.active || 0) + Number(pool.reserve || 0) + Number(pool.hold || 0) + Number(pool.problem || 0) + Number(pool.retired || 0) === 0;
  const snapshotVisual = liveFailure
    ? "red"
    : (stale || degraded ? "amber" : (state === "healthy" && !noAccounts ? "green" : "neutral"));
  const panelVisual = liveFailure || down
    ? "red"
    : (stale || degraded ? "amber" : (state === "healthy" ? "green" : "neutral"));
  const snapshotLabel = liveFailure
    ? "unavailable"
    : (stale ? "stale" : (noAccounts ? "no accounts" : "observed"));
  const counts = liveFailure
    ? { active: "unknown", reserve: "unknown", hold: "unknown", problem: "unknown", retired: "unknown" }
    : {
      active: String(pool.active ?? "unknown"),
      reserve: String(pool.reserve ?? "unknown"),
      hold: String(pool.hold ?? "unknown"),
      problem: String(pool.problem ?? "unknown"),
      retired: String(pool.retired ?? "unknown")
    };
  return {
    source,
    panelVisual,
    panelLabel: liveFailure ? "unavailable" : (stale ? "stale" : "readonly"),
    snapshotVisual,
    snapshotLabel,
    targetVisual: source === "live" ? "neutral" : "blue",
    targetLabel: source === "live" ? "future packet" : "design preview",
    counts,
    capacityTarget: source === "live" ? "unknown" : "design target preview",
    reserveTarget: source === "live" ? "unknown" : "design target preview",
    validationStart: "unknown / display only",
    validationSource: "accounts list readonly snapshot",
    snapshotCopy: liveFailure
      ? "Observed pool snapshot недоступен. Предыдущие fixture counts не используются как policy truth."
      : "Snapshot показывает наблюдаемое состояние пула, не сохранённую policy config.",
    footerCopy: "Accounts Policy объясняет правила и observed counts; lifecycle actions остаются в Accounts / Detail.",
    bannerCopy: liveFailure
      ? "Accounts policy недоступна. Предыдущие fixture-данные не используются."
      : (stale
        ? "Accounts policy snapshot устарел. Stale counts не являются зелёным состоянием."
        : "Демо-режим. Политика аккаунтов показана как preview, не как config truth.")
  };
}

function renderAccountsPolicySnapshot(snapshot) {
  const model = accountsPolicyModelFromSnapshot(snapshot || {});
  setAccountsPolicyChip("accountsPolicyPanelChip", model.panelVisual, model.panelLabel);
  setAccountsPolicyChip("accountsPolicyTargetChip", model.targetVisual, model.targetLabel);
  setAccountsPolicyChip("accountsPolicySnapshotChip", model.snapshotVisual, model.snapshotLabel);
  setAccountsPolicyChip("accountsPolicyInvariantChip", "blue", "canon");

  text("accountsPolicyReserveFirst", "enforced by canon / preview");
  text("accountsPolicyAutoPromote", "not admitted");
  text("accountsPolicySource", "future policy packet");
  text("accountsPolicyCapacityTarget", model.capacityTarget);
  text("accountsPolicyReserveTarget", model.reserveTarget);
  text("accountsPolicyValidationStart", model.validationStart);
  text("accountsPolicyValidationSource", model.validationSource);
  text("accountsPolicyActiveCount", model.counts.active);
  text("accountsPolicyReserveCount", model.counts.reserve);
  text("accountsPolicyHeldCount", model.counts.hold);
  text("accountsPolicyProblemCount", model.counts.problem);
  text("accountsPolicyRetiredCount", model.counts.retired);
  text("accountsPolicySnapshotCopy", model.snapshotCopy);
  text("accountsPolicyFooter", model.footerCopy);

  const banner = document.getElementById("settingsBanner");
  if (banner && currentScreen() === "settings" && currentSettingsSection() === "accounts-policy") {
    banner.className = `fixture-banner ${ACCOUNT_VISUAL_CLASS[model.panelVisual] || VISUAL_CLASS[model.panelVisual] || "neutral"}`;
    banner.textContent = model.bannerCopy;
  }
}

function setDiagnosticsPrivacyChip(id, visual, label) {
  const chip = document.getElementById(id);
  if (!chip) {
    return;
  }
  chip.className = `chip ${ACCOUNT_VISUAL_CLASS[visual] || VISUAL_CLASS[visual] || "neutral"}`;
  const labelNode = chip.lastElementChild;
  if (labelNode) {
    labelNode.textContent = label;
  }
}

function diagnosticsPrivacyModelFromSnapshot(snapshot) {
  const runtime = snapshot?.runtime || {};
  const source = snapshot?.source === "live_readonly" ? "live" : "fixture";
  const state = snapshot?.state_id || snapshot?.ui_state || runtime.visual_state || "unknown";
  const liveFailure = source === "live" && snapshot?.status === "integration_failure";
  const stale = state === "stale" || runtime.visual_state === "stale";
  const degraded = state === "degraded" || runtime.visual_state === "degraded";
  const down = state === "down" || liveFailure;
  const visual = down
    ? "red"
    : (stale || degraded ? "amber" : (state === "healthy" ? "blue" : "neutral"));
  return {
    visual,
    panelLabel: liveFailure ? "unavailable" : (stale ? "stale" : (state === "healthy" ? "preview" : "not inspected")),
    exportVisual: liveFailure ? "red" : "blue",
    exportLabel: liveFailure ? "unavailable" : "support artifact",
    redactionVisual: liveFailure ? "neutral" : "amber",
    redactionLabel: liveFailure ? "unknown" : "required",
    footerCopy: liveFailure
      ? "Diagnostics privacy status unavailable. Previous fixture data is not used."
      : "Export creates support artifact metadata only; runtime health color is never derived from diagnostics export result.",
    bannerCopy: liveFailure
      ? "Diagnostics privacy status недоступен. Предыдущие fixture-данные не используются."
      : (stale
        ? "Diagnostics privacy status устарел. Redaction proof требует свежий packet."
        : "Демо-режим. Правила диагностики показаны как preview, не как содержимое bundle.")
  };
}

function renderDiagnosticsPrivacySnapshot(snapshot) {
  const model = diagnosticsPrivacyModelFromSnapshot(snapshot || {});
  setDiagnosticsPrivacyChip("diagnosticsPrivacyPanelChip", model.visual, model.panelLabel);
  setDiagnosticsPrivacyChip("diagnosticsPrivacyExportChip", model.exportVisual, model.exportLabel);
  setDiagnosticsPrivacyChip("diagnosticsPrivacyRedactionChip", model.redactionVisual, model.redactionLabel);
  text("diagnosticsPrivacyFooter", model.footerCopy);

  const banner = document.getElementById("settingsBanner");
  if (banner && currentScreen() === "settings" && currentSettingsSection() === "diagnostics-privacy") {
    banner.className = `fixture-banner ${ACCOUNT_VISUAL_CLASS[model.visual] || VISUAL_CLASS[model.visual] || "neutral"}`;
    banner.textContent = model.bannerCopy;
  }
}

function renderDiagnosticsPrivacyAction(payload, refreshLabel, displayStateLabel, panelVisualClass) {
  const safeUiAction = safeLedgerText(payload.ui_action || "unknown", "unknown");
  const result = payload.result || {};
  const data = result.data || {};
  const changedFiles = Array.isArray(result.changed_files) ? result.changed_files : [];
  const exportModel = payload.ui_action === "export_diagnostics"
    ? diagnosticsExportResultModel(payload)
    : null;
  const visual = exportModel ? exportModel.visual : panelVisualClass;
  const label = exportModel ? exportModel.state : displayStateLabel;
  const message = exportModel
    ? exportModel.copy
    : safeLedgerText(result.human_message || "Действие не относится к diagnostics export.", "-");
  const redactionStatus = exportModel
    ? exportModel.redactionStatus
    : normalizeDiagnosticsRedactionStatus(data.redaction_status);

  setDiagnosticsPrivacyChip("diagnosticsPrivacyActionChip", visual, actionDisplayLabel(label));
  text("diagnosticsPrivacyActionName", safeUiAction || "нет");
  text("diagnosticsPrivacyActionTarget", payload.ui_action === "export_diagnostics" ? "support artifact" : safeLedgerText(payload.account_id || payload.route_id || "—", "—"));
  text("diagnosticsPrivacyActionRefresh", refreshLabel || "not applicable");

  if (payload.ui_action !== "export_diagnostics") {
    return;
  }

  setDiagnosticsPrivacyChip("diagnosticsPrivacyResultChip", visual, exportModel.label);
  setDiagnosticsPrivacyChip("diagnosticsPrivacyRedactionChip", redactionStatus === "enabled" ? "green" : (redactionStatus === "failed" ? "red" : "amber"), redactionStatus);
  text("diagnosticsPrivacyResultStatus", exportModel.state);
  text("diagnosticsPrivacyMachineCode", safeLedgerText(result.machine_error_code || "-", "-"));
  text("diagnosticsPrivacyArtifactRef", artifactReference(data.bundle_path));
  text("diagnosticsPrivacyRedactionStatus", redactionStatus);
  text("diagnosticsPrivacyChangedFiles", `${changedFiles.length} metadata markers`);
  text("diagnosticsPrivacyNextAction", safeLedgerText(result.next_action || "none", "none"));
  text("diagnosticsPrivacyTimestamp", "текущая UI-сессия");
  text("diagnosticsPrivacyResultMessage", message);
}

function setAdvancedChip(id, visual, label) {
  const chip = document.getElementById(id);
  if (!chip) {
    return;
  }
  chip.className = `chip ${ACCOUNT_VISUAL_CLASS[visual] || VISUAL_CLASS[visual] || "neutral"}`;
  const labelNode = chip.lastElementChild;
  if (labelNode) {
    labelNode.textContent = label;
  }
}

function advancedModelFromSnapshot(snapshot) {
  const runtime = snapshot?.runtime || {};
  const source = snapshot?.source === "live_readonly" ? "live" : "fixture";
  const state = snapshot?.state_id || snapshot?.ui_state || runtime.visual_state || "unknown";
  const liveFailure = source === "live" && snapshot?.status === "integration_failure";
  const stale = state === "stale" || runtime.visual_state === "stale";
  const degraded = state === "degraded" || runtime.visual_state === "degraded";
  const visual = liveFailure
    ? "red"
    : (stale || degraded ? "amber" : (state === "healthy" ? "blue" : "neutral"));
  return {
    visual,
    panelLabel: liveFailure ? "unavailable" : (stale ? "stale" : (state === "healthy" ? "preview" : "readonly")),
    operatorLabel: source === "live" ? "standard" : "preview",
    ownerLabel: "required",
    uiMode: source === "live" ? "standard operator mode" : "standard operator preview",
    footerCopy: liveFailure
      ? "Advanced status unavailable. Previous fixture data is not used."
      : "Advanced is a boundary/reference surface: safe links only, no hidden admin console.",
    bannerCopy: liveFailure
      ? "Advanced status недоступен. Предыдущие fixture-данные не используются."
      : (stale
        ? "Advanced status устарел. Deferred gates не становятся зелёным состоянием."
        : "Демо-режим. Advanced показывает policy preview, не активные системные переключатели.")
  };
}

function renderAdvancedSettingsSnapshot(snapshot) {
  const model = advancedModelFromSnapshot(snapshot || {});
  setAdvancedChip("advancedSettingsPanelChip", model.visual, model.panelLabel);
  setAdvancedChip("advancedOperatorChip", model.visual === "red" ? "neutral" : "blue", model.operatorLabel);
  setAdvancedChip("advancedOwnerGateChip", "amber", model.ownerLabel);
  text("advancedUiMode", model.uiMode);
  text("advancedSettingsFooter", model.footerCopy);

  const banner = document.getElementById("settingsBanner");
  if (banner && currentScreen() === "settings" && currentSettingsSection() === "advanced") {
    banner.className = `fixture-banner ${ACCOUNT_VISUAL_CLASS[model.visual] || VISUAL_CLASS[model.visual] || "neutral"}`;
    banner.textContent = model.bannerCopy;
  }
}

function renderAdvancedAction(payload, refreshLabel, displayStateLabel, panelVisualClass) {
  const result = payload.result || {};
  setAdvancedChip("advancedActionChip", panelVisualClass, actionDisplayLabel(displayStateLabel));
  text("advancedActionName", safeLedgerText(payload.ui_action || "нет", "нет"));
  text("advancedActionStatus", actionDisplayLabel(displayStateLabel));
  text("advancedActionRefresh", refreshLabel || "не запрашивалось");
  text("advancedActionNext", safeLedgerText(result.next_action || "none", "none"));
  text(
    "advancedActionMessage",
    safeLedgerText(result.human_message || "Action result is a UI-session summary, not runtime truth.", "not runtime truth")
  );
}

function runtimeModeModelFromSnapshot(snapshot) {
  const runtime = snapshot?.runtime || {};
  const source = snapshot?.source === "live_readonly" ? "live" : "fixture";
  const visualState = runtime.visual_state || snapshot?.state_id || "unknown";
  const desired = runtime.desired_mode || "unknown";
  const effective = runtime.effective_mode || "unknown";
  const knownModes = desired !== "unknown" && effective !== "unknown";
  const mismatch = knownModes && desired !== effective;
  let visual = ACCOUNT_VISUAL_CLASS[VISUAL_CLASS[visualState]] ? VISUAL_CLASS[visualState] : (VISUAL_CLASS[visualState] || "neutral");
  if (mismatch) {
    visual = "amber";
  }
  if (visualState === "healthy" && !mismatch) {
    visual = "green";
  }
  if (source === "live" && snapshot?.status === "integration_failure") {
    visual = "red";
  }
  const freshness = visualState === "stale"
    ? "stale"
    : (visualState === "healthy" && !mismatch ? "fresh" : (source === "live" && snapshot?.status === "integration_failure" ? "unavailable" : "not confirmed"));
  const stateLabel = mismatch
    ? "mismatch"
    : (visualState === "healthy" ? "consistent" : (visualState === "stale" ? "stale" : runtime.status_label || "unknown"));
  const modeSource = source === "live" ? "mode JSON packet / status JSON packet" : "fixture preview";
  const observed = freshness === "fresh"
    ? (runtime.observed_at_utc || "packet timestamp")
    : (freshness === "stale" ? "stale" : "—");
  return {
    source,
    visual,
    stateLabel,
    desired,
    effective,
    mismatch,
    freshness,
    observed,
    modeSource,
    lastError: runtime.last_error || "—",
    machineCode: runtime.machine_error_code || "—",
    statusLabel: runtime.status_label || "Неизвестно",
    bannerCopy: source === "live" && snapshot?.status === "integration_failure"
      ? "Runtime mode недоступен. Предыдущие fixture-данные не используются."
      : (
        visualState === "stale"
          ? "Данные режима устарели. Требуется обновление из canonical source."
          : "Демо-режим. Значения режима показаны как preview, не как runtime truth."
      )
  };
}

function setRuntimeModeChip(id, visual, label) {
  const chip = document.getElementById(id);
  if (!chip) {
    return;
  }
  chip.className = `chip ${ACCOUNT_VISUAL_CLASS[visual] || VISUAL_CLASS[visual] || "neutral"}`;
  const labelNode = chip.lastElementChild;
  if (labelNode) {
    labelNode.textContent = label;
  }
}

function renderRuntimeModeSnapshot(snapshot) {
  const model = runtimeModeModelFromSnapshot(snapshot || {});
  setRuntimeModeChip("runtimeModePanelChip", model.visual, model.stateLabel);
  setRuntimeModeChip("runtimeModeStateChip", model.visual, model.stateLabel);
  setRuntimeModeChip("runtimeModeRequestChip", model.mismatch ? "amber" : "neutral", model.mismatch ? "mismatch" : "request only");
  setRuntimeModeChip("runtimeModeTruthChip", model.visual, model.source === "live" ? "live packet" : "fixture preview");

  text("runtimeModeDesired", modeLabel(model.desired));
  text("runtimeModeEffective", modeLabel(model.effective));
  text("runtimeModeSource", model.modeSource);
  text("runtimeModeFreshness", model.observed);
  text("runtimeModeLastError", model.lastError || "—");
  text("runtimeDesiredSource", model.source === "live" ? "mode JSON packet" : "fixture preview");
  text("runtimeEffectiveSource", model.source === "live" ? "status JSON packet" : "fixture preview");
  text("runtimePacketFreshness", model.freshness);
  text("runtimeLastCommandScope", "last command не является runtime truth");
  text("runtimeModeFooter", "Режим запрошен ≠ режим применён ≠ здоровье runtime.");

  const managed = document.getElementById("runtimeManagedPreview");
  const stable = document.getElementById("runtimeStablePreview");
  if (managed && stable) {
    managed.classList.toggle("active", model.desired === "managed");
    stable.classList.toggle("active", model.desired === "stable");
  }

  const banner = document.getElementById("settingsBanner");
  if (banner && currentScreen() === "settings" && currentSettingsSection() === "runtime") {
    banner.className = `fixture-banner ${ACCOUNT_VISUAL_CLASS[model.visual] || VISUAL_CLASS[model.visual] || "neutral"}`;
    banner.textContent = model.bannerCopy;
  }
}

function setSettingsSection(section) {
  const normalized = SETTINGS_SECTIONS.includes(section) ? section : "hub";
  const desktop = document.querySelector(".desktop");
  desktop.dataset.settingsSection = normalized;
  const hub = document.getElementById("settingsHub");
  const runtimePanel = document.getElementById("runtimeModePanel");
  const clientPanel = document.getElementById("clientLaunchPanel");
  const accountsPolicyPanel = document.getElementById("accountsPolicyPanel");
  const diagnosticsPrivacyPanel = document.getElementById("diagnosticsPrivacyPanel");
  const advancedPanel = document.getElementById("advancedSettingsPanel");
  const panel = document.getElementById("dataLayoutPanel");
  const finder = document.getElementById("dataLayoutOpenFinderAction");
  const isRuntime = normalized === "runtime" && currentScreen() === "settings";
  const isClient = normalized === "client" && currentScreen() === "settings";
  const isAccountsPolicy = normalized === "accounts-policy" && currentScreen() === "settings";
  const isDiagnosticsPrivacy = normalized === "diagnostics-privacy" && currentScreen() === "settings";
  const isAdvanced = normalized === "advanced" && currentScreen() === "settings";
  const isDataLayout = normalized === "data-layout" && currentScreen() === "settings";
  if (hub) {
    hub.hidden = isRuntime || isClient || isAccountsPolicy || isDiagnosticsPrivacy || isAdvanced || isDataLayout;
  }
  if (runtimePanel) {
    runtimePanel.hidden = !isRuntime;
  }
  if (clientPanel) {
    clientPanel.hidden = !isClient;
  }
  if (accountsPolicyPanel) {
    accountsPolicyPanel.hidden = !isAccountsPolicy;
  }
  if (diagnosticsPrivacyPanel) {
    diagnosticsPrivacyPanel.hidden = !isDiagnosticsPrivacy;
  }
  if (advancedPanel) {
    advancedPanel.hidden = !isAdvanced;
  }
  if (panel) {
    panel.hidden = !isDataLayout;
  }
  if (finder) {
    finder.hidden = !isDataLayout;
    finder.disabled = true;
    finder.title = "Показать в Finder доступно только через desktop/native или admitted human-open surface.";
  }
}

function dataLayoutModelFromSnapshot(snapshot) {
  const visualState = snapshot?.runtime?.visual_state || snapshot?.state_id || snapshot?.ui_state || "unknown";
  const key = snapshot?.source === "live_readonly" && snapshot?.status === "integration_failure"
    ? "integration_failure"
    : canonicalState(visualState);
  return DATA_LAYOUT_FIXTURES[key] || DATA_LAYOUT_FIXTURES.unknown;
}

function setDataLayoutChip(id, visual, label) {
  const chip = document.getElementById(id);
  if (!chip) {
    return;
  }
  chip.className = `chip ${ACCOUNT_VISUAL_CLASS[visual] || VISUAL_CLASS[visual] || "neutral"}`;
  const labelNode = chip.lastElementChild;
  if (labelNode) {
    labelNode.textContent = label;
  }
}

function renderDataLayoutSnapshot(snapshot) {
  const model = dataLayoutModelFromSnapshot(snapshot || {});
  const source = snapshot?.source === "live_readonly" ? "live" : "fixture";
  setDataLayoutChip("dataLayoutModeChip", model.visual, model.mode);
  setDataLayoutChip("dataLayoutPackageChip", model.visual, model.packageStatus);
  setDataLayoutChip("dataLayoutDirectoryChip", model.directoryVisual, model.directoryStatus);
  setDataLayoutChip("dataLayoutStructureChip", model.structureVisual, model.structureVisual === "green" ? "summary preview" : "not confirmed");
  setDataLayoutChip("dataLayoutPermissionsChip", model.permissionsVisual, model.permissionsVisual === "green" ? "preview ok" : model.permissions.read);
  setDataLayoutChip("dataLayoutSnapshotChip", model.snapshotVisual, model.snapshotLabel);

  text("dataLayoutPackageStatus", model.packageStatus);
  text("dataLayoutSchemaVersion", model.schemaVersion);
  text("dataLayoutWritable", model.writable);
  text("dataLayoutSnapshotAvailable", model.snapshotAvailable);
  text("dataLayoutRollbackPoint", model.rollbackPoint);
  text("dataLayoutLastChecked", model.lastChecked);
  text("dataLayoutPath", model.directoryPath);
  const pathNode = document.getElementById("dataLayoutPath");
  if (pathNode) {
    pathNode.title = model.directoryPath;
  }

  setDataLayoutChip("dataLayoutConfigStatus", model.structure.config[1], model.structure.config[0]);
  setDataLayoutChip("dataLayoutAccountsStatus", model.structure.accounts[1], model.structure.accounts[0]);
  setDataLayoutChip("dataLayoutSnapshotsStatus", model.structure.snapshots[1], model.structure.snapshots[0]);
  setDataLayoutChip("dataLayoutLogsStatus", model.structure.logs[1], model.structure.logs[0]);
  setDataLayoutChip("dataLayoutRegistryStatus", model.structure.registry[1], model.structure.registry[0]);

  text("dataLayoutReadAccess", model.permissions.read);
  text("dataLayoutWriteAccess", model.permissions.write);
  text("dataLayoutOwner", model.permissions.owner);
  text("dataLayoutMode", model.permissions.mode);
  text("dataLayoutSecretsIsolation", model.permissions.secrets);
  text("dataLayoutSnapshotCopy", model.snapshotCopy);
  text("dataLayoutRollbackCopy", model.rollbackCopy);
  text(
    "dataLayoutFooter",
    source === "live" && model.key === "live_integration_failure"
      ? "Последняя проверка: live-readonly failed · Предыдущие fixture-данные не используются."
      : `Последняя проверка: ${model.lastChecked} · Все значения являются preview/deferred summary, не прямым чтением файлов.`
  );

  const banner = document.getElementById("settingsBanner");
  if (banner && currentScreen() === "settings" && currentSettingsSection() === "data-layout") {
    banner.className = `fixture-banner ${ACCOUNT_VISUAL_CLASS[model.visual] || VISUAL_CLASS[model.visual] || "neutral"}`;
    banner.textContent = source === "live"
      ? "Live-readonly статус данных недоступен. Предыдущие fixture-данные не используются."
      : (
        model.key === "stale"
          ? "Данные layout устарели. Stale preview не является зелёным состоянием."
          : "Демо-режим. Layout данных показан как preview, не как состояние файловой системы."
      );
  }
}

function setActionsBusy(isBusy) {
  for (const button of document.querySelectorAll(".live-action, .account-action, .onboard-action, .api-route-action")) {
    const state = actionAvailabilityForButton(button);
    button.disabled = isBusy || !state.available;
    button.dataset.available = state.available ? "true" : "false";
    button.dataset.availabilityState = state.availabilityState;
    button.dataset.disabledReasonCode = state.disabledReasonCode;
    button.dataset.disabledReasons = state.available ? "" : JSON.stringify(state.disabledReasons);
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
  renderAccountActionPreflight(uiAction, extraPayload, metadata);
  renderLaunchClientPreflight(uiAction, metadata);
  renderApiRouteRemovePreflight(uiAction, extraPayload);
  const confirmButton = document.getElementById("confirmAction");
  if (confirmButton) {
    confirmButton.dataset.readyLabel = confirmationReadyLabel(uiAction);
  }
  setConfirmationInFlight(false);
  document.getElementById("confirmOverlay").hidden = false;
  document.getElementById("confirmAction").focus();
}

function confirmationReadyLabel(uiAction) {
  if (uiAction === "api_route_remove") {
    return "Удалить route";
  }
  if (uiAction === "retire_account") {
    return "Вывести из пула";
  }
  if (uiAction === "launch_client_dispatch") {
    return "Запустить копию";
  }
  return "Подтвердить";
}

function renderAccountActionPreflight(uiAction, extraPayload = {}, metadata = {}) {
  const block = document.getElementById("accountActionPreflight");
  if (!block) {
    return;
  }
  const isAccountAction = ACCOUNT_UI_ACTIONS.has(uiAction);
  block.hidden = !isAccountAction;
  if (!isAccountAction) {
    return;
  }
  const accountId = extraPayload.account_id || "";
  const account = findAccountById(accountId);
  text("accountActionPreflightId", accountId || "-");
  text(
    "accountActionPreflightPool",
    account ? `${account.pool_label || poolLabel(account.pool)} · ${accountLifecycleLabel(account)}` : "account_missing_after_refresh"
  );
  text("accountActionPreflightAction", metadata.display_name || uiAction);
  text("accountActionPreflightRefresh", metadata.post_action_refresh_required ? "required" : "not required");
}

function renderLaunchClientPreflight(uiAction, metadata = {}) {
  const block = document.getElementById("launchClientPreflight");
  if (!block) {
    return;
  }
  if (uiAction !== "launch_client_dispatch") {
    block.hidden = true;
    return;
  }
  const preflight = launchPreflightSummary(metadata);
  block.hidden = false;
  text("launchClientPreflightTarget", preflight.targetKind);
  text("launchClientPreflightProfile", preflight.separateProfile ? "separate" : "not proven");
  text("launchClientPreflightDataDir", preflight.separateDataDir ? "separate" : "not proven");
  text("launchClientPreflightPort", preflight.separatePort ? "separate" : "not proven");
  text("launchClientPreflightProcess", preflight.processConfirmationPossible ? "packet-confirmable" : "not confirmable");
  text("launchClientPreflightNote", preflight.reason);
}

function renderApiRouteRemovePreflight(uiAction, extraPayload = {}) {
  const block = document.getElementById("apiRouteRemovePreflight");
  if (!block) {
    return;
  }
  const isRouteRemove = uiAction === "api_route_remove";
  block.hidden = !isRouteRemove;
  if (!isRouteRemove) {
    return;
  }
  const routeId = extraPayload.route_id || "";
  const route = findApiRouteById(routeId);
  const exists = route ? "yes" : "no";
  const status = route?.enabled === false
    ? "disabled"
    : (route?.enabled === true ? "enabled · blocked" : "unproven · blocked");
  text("apiRouteRemovePreflightExists", exists);
  text("apiRouteRemovePreflightStatus", status);
  text("apiRouteRemovePreflightMutation", "remove registry route");
  text("apiRouteRemovePreflightWrite", "command-owned");
  text("apiRouteRemovePreflightRefresh", "required");
}

function findAccountById(accountId) {
  const accounts = Array.isArray(currentAccountsSnapshot?.accounts)
    ? currentAccountsSnapshot.accounts
    : [];
  return accounts.find((account) => account?.id === accountId) || null;
}

function findApiRouteById(routeId) {
  const routes = Array.isArray(currentApiConnectionsSnapshot?.routes)
    ? currentApiConnectionsSnapshot.routes
    : [];
  return routes.find((route) => route?.route_id === routeId) || null;
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
    confirmButton.textContent = isInFlight ? "Выполняется..." : (confirmButton.dataset.readyLabel || "Подтвердить");
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
  document.getElementById("runOnboardAction").focus({ preventScroll: true });
}

function closeOnboardModal() {
  document.getElementById("onboardOverlay").hidden = true;
}

function runOnboardFromModal() {
  closeOnboardModal();
  maybeConfirmAndRun("onboard_account");
}

function setScreen(screen, updateUrl = false, settingsSection = null) {
  const nextScreen = SCREENS.includes(screen) ? screen : "overview";
  const nextSettingsSection = nextScreen === "settings"
    ? (settingsSection || (updateUrl ? "hub" : settingsSectionFromLocation()))
    : "hub";
  const desktop = document.querySelector(".desktop");
  desktop.dataset.screen = nextScreen;
  desktop.dataset.settingsSection = nextSettingsSection;
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
  for (const node of document.querySelectorAll(".quick-start-only")) {
    node.hidden = nextScreen !== "quick-start";
  }
  setSettingsSection(nextSettingsSection);
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
        nextScreen === "quick-start"
          ? "Быстрый старт"
          : (
        nextScreen === "api-connections"
          ? "API-подключения"
          : (
        nextScreen === "diagnostics"
          ? "Диагностика"
          : (
            nextScreen === "settings"
              ? (
                nextSettingsSection === "runtime"
                  ? "Runtime / Mode"
                  : (
                    nextSettingsSection === "client"
                      ? "Client / Launch"
                      : (
                        nextSettingsSection === "accounts-policy"
                          ? "Accounts Policy"
                          : (
                            nextSettingsSection === "diagnostics-privacy"
                              ? "Diagnostics / Privacy"
                              : (
                                nextSettingsSection === "advanced"
                                  ? "Advanced"
                                  : (nextSettingsSection === "data-layout" ? "Данные приложения" : "Настройки")
                              )
                          )
                      )
                  )
              )
              : (
                nextScreen === "setup"
                  ? "Настройка Wild Boar Proxy"
                  : (
                    nextScreen === "select-client"
                      ? "Выбор клиента"
                      : (nextScreen === "import-existing" ? "Импорт существующей настройки" : "Обзор")
                  )
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
    if (nextScreen === "settings" && nextSettingsSection !== "hub") {
      url.searchParams.set("section", nextSettingsSection);
    } else {
      const params = new URLSearchParams();
      for (const [key, value] of url.searchParams.entries()) {
        if (key !== "section") {
          params.append(key, value);
        }
      }
      url.search = params.toString();
    }
    window.history.replaceState({}, "", url);
  }
}

function quickStartAccountState(account, snapshotStatus) {
  if (snapshotStatus === "stale") {
    return { key: "stale", label: "Устарело", visual: "amber", order: 1 };
  }
  if (snapshotStatus === "integration_failure") {
    return { key: "stale", label: "Устарело", visual: "amber", order: 1 };
  }
  if (account.manual_hold === true) {
    return { key: "hold_pause", label: "Пауза", visual: "amber", order: 4 };
  }
  if (account.last_error_summary || account.visual_state === "red" || account.status === "down") {
    return { key: "problem", label: "Проверить", visual: "red", order: 0 };
  }
  if (account.visual_state === "amber" || account.status === "degraded") {
    return { key: "stale", label: "Устарело", visual: "amber", order: 2 };
  }
  if (account.pool === "reserve") {
    return { key: "reserve", label: "Резерв", visual: "green", order: 5 };
  }
  if (account.status === "healthy" || account.visual_state === "green" || account.visual_state === "blue") {
    return { key: "ok", label: account.pool === "active" ? "Работает" : "Готов", visual: "green", order: 6 };
  }
  return { key: "checking", label: "Проверка", visual: "blue", order: 3 };
}

function renderQuickStartAccountRows(snapshot) {
  const list = document.getElementById("quickStartAccountList");
  list.replaceChildren();
  const accounts = Array.isArray(snapshot.accounts) ? snapshot.accounts : [];
  if (!accounts.length) {
    const empty = document.createElement("div");
    empty.className = "quick-start-empty-state neutral";
    empty.innerHTML = '<strong>Аккаунты не подключены</strong><span>Первый запуск: пустое состояние не является ошибкой.</span>';
    list.append(empty);
    return;
  }
  const rows = accounts
    .map((account) => ({ account, state: quickStartAccountState(account, snapshot.status) }))
    .sort((a, b) => a.state.order - b.state.order)
    .slice(0, 4);
  rows.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = `quick-start-account-row ${item.state.visual}`;
    row.dataset.accountId = item.account.id || "";

    const indexNode = document.createElement("span");
    indexNode.className = `quick-start-account-index ${item.state.visual}`;
    indexNode.textContent = String(index + 1).padStart(2, "0");

    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = item.account.id || "unknown-account";
    const meta = document.createElement("span");
    const pool = item.account.pool_label || poolLabel(item.account.pool);
    const check = item.account.last_success || item.account.cooldown_until || "нет данных";
    meta.textContent = `${pool} · last check ${check}`;
    copy.append(title, meta);

    const chip = document.createElement("span");
    chip.className = `chip ${item.state.visual}`;
    const dot = document.createElement("span");
    dot.className = "dot";
    const label = document.createElement("span");
    label.textContent = item.state.label;
    chip.append(dot, label);
    row.append(indexNode, copy, chip);
    list.append(row);
  });

  if (accounts.length > rows.length) {
    const more = document.createElement("a");
    more.className = "quick-start-more-row";
    more.href = "?screen=accounts";
    more.dataset.screenLink = "accounts";
    more.textContent = `+${accounts.length - rows.length} ещё · открыть аккаунты`;
    more.addEventListener("click", (event) => {
      event.preventDefault();
      setScreen("accounts", true);
      refreshCurrentSource();
    });
    list.append(more);
  }
}

function quickStartApiModel(snapshot, source) {
  const routes = Array.isArray(snapshot.routes) ? snapshot.routes : [];
  if (snapshot.status === "stale") {
    const primary = routes.find((route) => route.role_label === "main route" || route.role_label === "primary" || route.is_primary === true || route.primary === true) || routes[0];
    return {
      state: "stale",
      visual: "amber",
      title: "Устарело",
      provider: primary?.provider || "Не настроено",
      model: primary ? `${primary.upstream_model || "model unknown"} · ${primary.role_label || "registry entry"}` : "Основной route не подтверждён",
      routeId: primary?.route_id || "",
      secretRef: primary?.secret_ref || "—",
      secretState: primary?.secret_status_label || "unknown",
      validationState: "stale",
      lastCheck: "нет данных",
      routeCount: routes.length,
      confirmed: false
    };
  }
  if (snapshot.status !== "ok" || (source === "live" && snapshot.source !== "api_connections_readonly")) {
    return {
      state: "failed",
      visual: "red",
      title: "Данные недоступны",
      provider: "Не настроено",
      model: "Live-readonly route snapshot недоступен",
      routeId: "",
      secretRef: "—",
      secretState: "unknown",
      validationState: "unknown",
      lastCheck: "нет данных",
      routeCount: routes.length,
      confirmed: false
    };
  }
  if (!routes.length) {
    return {
      state: "not_configured",
      visual: "neutral",
      title: "Не настроено",
      provider: "Не настроено",
      model: "Основной route не подтверждён",
      routeId: "",
      secretRef: "—",
      secretState: "unknown",
      validationState: "unknown",
      lastCheck: "нет данных",
      routeCount: 0,
      confirmed: false
    };
  }
  const primary = source === "live"
    ? routes.find((route) => route.role_label === "main route" || route.role_label === "primary" || route.is_primary === true || route.primary === true)
    : routes.find((route) => route.enabled === true) || routes[0];
  if (!primary) {
    return {
      state: "not_configured",
      visual: "neutral",
      title: "Основной route не подтверждён",
      provider: "Не настроено",
      model: "Live snapshot не содержит confirmed main route",
      routeId: "",
      secretRef: "—",
      secretState: "unknown",
      validationState: "unknown",
      lastCheck: "нет данных",
      routeCount: routes.length,
      confirmed: false
    };
  }
  const missingSecret = primary.status_code === "missing_secret" || primary.secret_visual_state === "amber" || primary.secret_status_label === "missing";
  const failed = primary.visual_state === "red" || primary.validation_visual_state === "red";
  const stale = snapshot.status === "stale" || primary.status_code === "stale";
  const visual = missingSecret || stale ? "amber" : (failed ? "red" : (primary.enabled === true ? "green" : "neutral"));
  const title = missingSecret
    ? "Нужен secret_ref"
    : (failed ? "Ошибка" : (stale ? "Устарело" : (primary.enabled === true ? "Работает" : "Deferred")));
  return {
    state: missingSecret ? "missing_secret_ref" : (failed ? "failed" : (stale ? "stale" : (primary.enabled === true ? "ok" : "unsupported_provider"))),
    visual,
    title,
    provider: primary.provider || "Не настроено",
    model: `${primary.upstream_model || "model unknown"} · ${primary.role_label || "registry entry"}`,
    routeId: primary.route_id || "",
    secretRef: primary.secret_ref || "—",
    secretState: missingSecret ? "missing" : (primary.secret_status_label || "unknown"),
    validationState: primary.validation_label || primary.status_label || "not checked",
    lastCheck: primary.last_checked || "нет данных",
    routeCount: routes.length,
    confirmed: source !== "live" || primary.role_label === "main route" || primary.role_label === "primary" || primary.is_primary === true || primary.primary === true
  };
}

function renderQuickStart(accountsSnapshot, apiSnapshot, source, fixtureState = "unknown") {
  const accountsValidation = validateAccountsSnapshot(accountsSnapshot);
  const safeAccounts = accountsValidation.ok ? accountsSnapshot : {
    ...accountsFixtureFromOverview(FALLBACK_FIXTURE),
    status: "integration_failure",
    accounts: []
  };
  const apiValidation = validateApiConnectionsSnapshot(apiSnapshot);
  const safeApi = apiValidation.ok ? apiSnapshot : {
    ...apiConnectionsFixtureFromOverview(FALLBACK_FIXTURE),
    status: "integration_failure",
    routes: []
  };
  currentAccountsSnapshot = safeAccounts;
  currentApiConnectionsSnapshot = safeApi;
  setSnapshotCommandLedgerFromSnapshots("quick-start snapshot", [safeAccounts, safeApi]);
  renderUiReadonlyLaneExitSummary();

  const desktop = document.querySelector(".desktop");
  desktop.dataset.fixtureState = fixtureState;
  desktop.dataset.source = source;
  document.getElementById("sourcePicker").value = source;
  document.getElementById("statePicker").disabled = source === "live";
  document.getElementById("brandCaption").textContent = source === "live"
    ? "quick start · live readonly"
    : "quick start · v0.2.0";
  document.getElementById("refreshFixture").lastElementChild.textContent = "Обновить";
  setSourceCopy(source);

  const accounts = safeAccounts.accounts || [];
  const noAccounts = accounts.length === 0;
  const accountProblemCount = accounts.filter((account) => quickStartAccountState(account, safeAccounts.status).visual === "red").length;
  const accountStaleCount = accounts.filter((account) => quickStartAccountState(account, safeAccounts.status).key === "stale").length;
  const workingCount = accounts.filter((account) => ["green", "blue"].includes(account.visual_state) && !account.last_error_summary && !account.manual_hold).length;
  const accountVisual = safeAccounts.status !== "ok" ? "amber" : (accountProblemCount ? "red" : (accountStaleCount ? "amber" : (noAccounts ? "neutral" : "green")));
  const accountLabel = safeAccounts.status === "integration_failure"
    ? "нет данных"
    : (safeAccounts.status !== "ok"
      ? "устарело"
      : (accountProblemCount ? "проверить" : (noAccounts ? "пусто" : "готово")));

  const accountChip = document.getElementById("quickStartAccountsChip");
  accountChip.className = `chip ${accountVisual}`;
  accountChip.lastElementChild.textContent = accountLabel;
  text("quickStartAccountsConnected", noAccounts ? 0 : accounts.length);
  text("quickStartAccountsWorking", workingCount);
  text("quickStartAccountsToCheck", accountProblemCount + accountStaleCount);
  renderQuickStartAccountRows(safeAccounts);

  const apiModel = quickStartApiModel(safeApi, source);
  const apiChip = document.getElementById("quickStartApiChip");
  apiChip.className = `chip ${apiModel.visual}`;
  apiChip.lastElementChild.textContent = apiModel.title;
  text("quickStartApiProvider", apiModel.provider);
  text("quickStartApiModel", apiModel.model);
  text("quickStartApiSecret", `secret_ref: ${apiModel.secretRef}`);
  const routeHint = document.getElementById("quickStartApiRouteHint");
  const hiddenRouteCount = Math.max(0, apiModel.routeCount - 1);
  routeHint.hidden = hiddenRouteCount <= 0;
  routeHint.textContent = `+${hiddenRouteCount} route · открыть API-подключения`;
  const statusCard = document.getElementById("quickStartApiStatusCard");
  statusCard.className = `quick-start-api-status ${apiModel.visual}`;
  document.getElementById("quickStartApiStatusDot").className = `quick-start-status-dot ${apiModel.visual}`;
  text("quickStartApiStatusTitle", apiModel.title);
  text(
    "quickStartApiStatusText",
    apiModel.state === "missing_secret_ref"
      ? "Основной route выбран, но secret_ref не подтверждён bounded packet. Это не runtime failure."
      : (apiModel.state === "ok"
        ? "Provider, secret_ref и route представлены как bounded summary. Runtime readiness подтверждается отдельно."
        : (apiModel.state === "stale"
          ? "Основной route показан из устаревшего bounded snapshot. Требуется обновление."
          : "Основной route не подтверждён bounded snapshot."))
  );

  setQuickStartChecklistChip("quickStartApiProviderChip", apiModel.provider === "Не настроено" ? "neutral" : "green", apiModel.provider === "Не настроено" ? "unknown" : "OK");
  setQuickStartChecklistChip("quickStartApiSecretChip", apiModel.state === "missing_secret_ref" ? "amber" : (apiModel.secretState === "available" ? "green" : "neutral"), apiModel.state === "missing_secret_ref" ? "missing" : apiModel.secretState);
  setQuickStartChecklistChip("quickStartApiRouteChip", apiModel.state === "ok" ? "green" : (apiModel.state === "missing_secret_ref" ? "amber" : "neutral"), apiModel.validationState);

  const apiAction = document.getElementById("quickStartCheckApiAction");
  apiAction.dataset.routeId = apiModel.routeId || "";
  apiAction.dataset.routeEnabled = apiModel.state === "ok" ? "true" : "false";
  apiAction.dataset.routeStateProven = apiModel.confirmed && apiModel.routeId ? "true" : "false";
  apiAction.disabled = true;
  apiAction.title = apiModel.confirmed && apiModel.routeId
    ? "Проверка API остаётся disabled в Quick Start до отдельного admitted action mapping."
    : "Нужен confirmed main route из bounded snapshot.";

  const banner = document.getElementById("quickStartBanner");
  const firstRun = noAccounts && safeApi.routes.length === 0;
  const liveFailure = source === "live" && (safeAccounts.status !== "ok" || safeApi.status !== "ok");
  const stale = fixtureState === "stale";
  const bannerVisual = liveFailure ? "red" : (firstRun ? "neutral" : (stale ? "amber" : (apiModel.visual === "red" || accountVisual === "red" ? "amber" : "blue")));
  setVisualClass(banner, "fixture-banner", bannerVisual);
  banner.textContent = liveFailure
    ? "Live-readonly данные недоступны. Предыдущие fixture-данные не используются."
    : (firstRun
      ? "Первый запуск: пустые состояния не являются ошибкой."
      : (stale
        ? "Упрощённый режим показывает устаревший bounded snapshot; stale не является зелёным состоянием."
        : "Упрощённый режим показывает только итоговые статусы и безопасные действия."));

  const latest = apiModel.lastCheck !== "нет данных" ? apiModel.lastCheck : "нет данных";
  text("quickStartFooter", `Последняя общая проверка: ${latest} · Детальные расследования остаются в экспертных разделах.`);
  const sidebarDot = document.getElementById("sidebarDot");
  setVisualClass(sidebarDot, "dot", bannerVisual);
  text("sidebarStatus", firstRun ? "Quick Start: first run" : "Quick Start: summary state");
  applyActionAvailability();
}

function setQuickStartChecklistChip(id, visual, label) {
  const chip = document.getElementById(id);
  chip.className = `chip ${ACCOUNT_VISUAL_CLASS[visual] || "neutral"}`;
  chip.lastElementChild.textContent = label || "unknown";
}

function setVisualClass(node, base, visual) {
  node.className = `${base} ${ACCOUNT_VISUAL_CLASS[visual] || VISUAL_CLASS[visual] || "neutral"}`;
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

function quickStartAccountsFixtureFromOverview(fixture) {
  const snapshot = accountsFixtureFromOverview(fixture);
  const stateId = fixture.state_id || "unknown";
  if (stateId === "unknown") {
    return {
      ...snapshot,
      summary: {
        ...snapshot.summary,
        active: 0,
        reserve: 0,
        hold: 0,
        problem: 0,
        healthy: 0,
        degraded: 0,
        down: 0,
        visible_count: 0
      },
      accounts: []
    };
  }
  if (stateId === "healthy") {
    const accounts = [
      accountFixture("acct-primary-01", "codex-primary@example.com", "active", "healthy", "green", "", "Сегодня, 12:45"),
      accountFixture("acct-reserve-01", "codex-reserve@example.com", "reserve", "healthy", "green", "", "Сегодня, 12:40"),
      accountFixture("acct-backup-01", "codex-backup@example.com", "reserve", "healthy", "green", "", "Сегодня, 12:32"),
      accountFixture("acct-hold-01", "codex-hold@example.com", "reserve", "healthy", "amber", "", "Сегодня, 11:58", true)
    ];
    return {
      ...snapshot,
      summary: {
        ...snapshot.summary,
        active: 1,
        reserve: 3,
        hold: 1,
        problem: 0,
        healthy: 3,
        degraded: 0,
        down: 0,
        visible_count: accounts.length
      },
      accounts
    };
  }
  if (stateId === "stale") {
    return {
      ...snapshot,
      status: "stale",
      accounts: snapshot.accounts.map((account) => ({
        ...account,
        visual_state: account.manual_hold ? "amber" : "amber",
        status_label: account.manual_hold ? "Пауза" : "Устарело"
      }))
    };
  }
  return snapshot;
}

function apiConnectionsFixtureFromOverview(fixture) {
  const integrationFailure = fixture.state_id === "integration_failure";
  const degraded = fixture.state_id === "degraded";
  const routes = integrationFailure ? [] : [
    {
      route_id: "wbp-openrouter-primary",
      display_name: "OpenRouter registry entry",
      provider: "openrouter",
      upstream_model: "deepseek/deepseek-chat",
      enabled: true,
      status_code: degraded ? "missing_secret" : "enabled",
      status_label: degraded ? "missing secret" : "enabled",
      visual_state: degraded ? "amber" : "blue",
      role_label: "registry entry",
      validation_label: degraded ? "blocked by secret" : "not checked",
      validation_visual_state: degraded ? "amber" : "neutral",
      secret_ref: "OPENROUTER_PRIMARY",
      secret_status_label: degraded ? "missing" : "available",
      secret_visual_state: degraded ? "amber" : "green",
      last_checked: degraded ? "" : "12:44",
      note: degraded
        ? "Демо-предупреждение: secret ref не подтверждён, отдельная проверка маршрута не выполнялась."
        : "Демо-представление registry-пакета без отдельной проверки маршрута."
    },
    {
      route_id: "wbp-openrouter-reserve",
      display_name: "OpenRouter disabled entry",
      provider: "openrouter",
      upstream_model: "deepseek/deepseek-chat",
      enabled: false,
      status_code: "disabled",
      status_label: "disabled",
      visual_state: "neutral",
      role_label: "registry entry",
      validation_label: "not checked",
      validation_visual_state: "neutral",
      secret_ref: "OPENROUTER_RESERVE",
      secret_status_label: "unknown",
      secret_visual_state: "neutral",
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
      latest_check: degraded || integrationFailure ? "" : "12:44",
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

function quickStartApiFixtureFromOverview(fixture) {
  const snapshot = apiConnectionsFixtureFromOverview(fixture);
  const stateId = fixture.state_id || "unknown";
  if (stateId === "unknown") {
    return {
      ...snapshot,
      summary: {
        ...snapshot.summary,
        routes_count: 0,
        enabled_count: 0,
        attention_count: 0,
        latest_check: ""
      },
      routes: []
    };
  }
  if (stateId === "healthy" && snapshot.routes[0]) {
    return {
      ...snapshot,
      routes: [
        {
          ...snapshot.routes[0],
          provider: "openai",
          upstream_model: "gpt-4.1-mini",
          role_label: "main route",
          secret_ref: "WBP_OPENAI_API_KEY",
          secret_status_label: "available",
          secret_visual_state: "green",
          validation_label: "OK",
          validation_visual_state: "green",
          status_label: "OK",
          visual_state: "green",
          last_checked: "12:45"
        },
        ...snapshot.routes.slice(1)
      ]
    };
  }
  if (stateId === "degraded" && snapshot.routes[0]) {
    return {
      ...snapshot,
      routes: [
        {
          ...snapshot.routes[0],
          provider: "anthropic",
          upstream_model: "claude-3-5-sonnet",
          role_label: "main route",
          secret_ref: "ANTHROPIC_API_KEY",
          status_code: "missing_secret",
          status_label: "missing secret",
          visual_state: "amber",
          secret_status_label: "missing",
          secret_visual_state: "amber",
          validation_label: "pending",
          validation_visual_state: "amber",
          last_checked: ""
        },
        ...snapshot.routes.slice(1)
      ]
    };
  }
  if (stateId === "stale") {
    return {
      ...snapshot,
      status: "stale",
      routes: snapshot.routes.map((route) => ({
        ...route,
        status_code: "stale",
        status_label: "stale",
        visual_state: "amber",
        validation_label: "stale",
        validation_visual_state: "amber"
      }))
    };
  }
  return snapshot;
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
  document.getElementById("refreshFixture").lastElementChild.textContent = "Обновить";
  setSourceCopy(source);

  const banner = document.getElementById("accountsBanner");
  setClassName(banner, "fixture-banner", visualState);
  banner.textContent = source === "live"
    ? (
      safeSnapshot.status === "ok"
        ? "Live-readonly аккаунтов. Действия остаются bounded requests и подтверждаются обновлённым списком."
        : "Live-readonly аккаунтов недоступен. Предыдущие healthy-данные не используются."
    )
    : "Демо-режим аккаунтов. Данные не являются runtime truth.";

  const summary = safeSnapshot.summary;
  const noData = source === "live" && safeSnapshot.status !== "ok";
  text("accountsActiveChip", noData ? "нет данных" : `${summary.active} активных`);
  text("accountsReserveChip", noData ? "нет данных" : `${summary.reserve} резерв`);
  text("accountsHoldChip", noData ? "нет данных" : `${summary.hold} удержание`);
  text("accountsProblemChip", noData ? "нет данных" : `${summary.problem} проблемных`);
  text(
    "accountsRegistryStatus",
    `Идентичность registry: ${safeSnapshot.registry_identity.status} · ${safeSnapshot.registry_identity.machine_error_code}`
  );
  text("accountsVisibleCount", `Показано ${safeSnapshot.accounts.length} из ${summary.visible_count}`);
  text(
    "accountsPagination",
    safeSnapshot.accounts.length
      ? `Строки 1-${safeSnapshot.accounts.length} из ${summary.visible_count}`
      : (noData ? "Нет данных для таблицы" : "Строки 0-0 из 0")
  );
  currentAccountsSnapshot = safeSnapshot;
  setSnapshotCommandLedgerFromSnapshots("accounts snapshot", safeSnapshot);
  renderUiReadonlyLaneExitSummary();
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
  document.getElementById("refreshFixture").lastElementChild.textContent = "Обновить";
  setSourceCopy(source);

  const banner = document.getElementById("apiConnectionsBanner");
  setClassName(banner, "fixture-banner", visualState);
  banner.textContent = source === "live"
    ? (
      safeSnapshot.status === "ok"
        ? "Live-readonly маршрутов. Удаление доступно только для disabled route после server preflight."
        : "Live-readonly маршруты недоступны. Предыдущие данные не используются."
    )
    : "Демо-режим. Маршруты показаны как bounded fixture view, не runtime config truth.";

  const summary = safeSnapshot.summary;
  const noData = source === "live" && safeSnapshot.status !== "ok";
  const latestCheck = summary.latest_check || "Нет данных";
  text("apiConnectionsRoutesCount", noData ? "—" : summary.routes_count);
  text("apiConnectionsEnabledCount", noData ? "—" : summary.enabled_count);
  text("apiConnectionsAttentionCount", noData ? "—" : summary.attention_count);
  text("apiConnectionsLatestCheck", noData ? "—" : latestCheck);
  text("apiConnectionsRoutesNote", noData ? "нет данных" : (source === "live" ? "из пакета команд" : "bounded fixture"));
  text("apiConnectionsEnabledNote", noData ? "нет данных" : "только registry state");
  text("apiConnectionsAttentionNote", noData ? "нет данных" : "missing/invalid/disabled");
  text("apiConnectionsLatestCheckNote", noData ? "нет данных" : (latestCheck === "Нет данных" ? "проверка маршрута ещё не запускалась" : "время последней проверки"));
  text(
    "apiConnectionsRegistryStatus",
    noData
      ? `Недоступно · ${summary.machine_error_code}`
      : `Контур: ${safeSnapshot.adapter.foundation_phase} · models source: ${safeSnapshot.adapter.models_source}`
  );
  text("apiConnectionsVisibleCount", noData ? "Нет данных" : `Показано ${safeSnapshot.routes.length} из ${summary.routes_count}`);
  text("apiConnectionsPagination", noData ? "Нет данных для таблицы" : `Строки ${safeSnapshot.routes.length ? 1 : 0}-${safeSnapshot.routes.length} из ${summary.routes_count}`);
  currentApiConnectionsSnapshot = safeSnapshot;
  setSnapshotCommandLedgerFromSnapshots("api-connections snapshot", safeSnapshot);
  renderUiReadonlyLaneExitSummary();
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
    cell.textContent = "Маршруты недоступны. Создание и изменение маршрутов остаются deferred до отдельного server-side builder.";
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
      td("", routeValidationChip(route)),
      td("", routeSecretRef(route)),
      td("right mono-value", route.last_checked || "—"),
      td("", routeActionButtons(route))
    );
    body.append(row);
  }
  applyActionAvailability();
}

function routeIdentity(route) {
  const wrap = document.createElement("div");
  const main = document.createElement("div");
  main.className = "account-main mono-value api-route-id";
  main.textContent = route.route_id || "unknown-route";
  const sub = document.createElement("div");
  sub.className = "account-sub";
  const subtitle = routeSubtitle(route);
  sub.textContent = subtitle;
  sub.title = subtitle;
  wrap.append(main, sub);
  return wrap;
}

function routeSubtitle(route) {
  const parts = [];
  const displayName = String(route.display_name || "").trim();
  const roleLabel = String(route.role_label || "").trim();
  if (displayName) {
    parts.push(displayName.replace(/\s*registry entry\s*$/i, "").trim() || displayName);
  }
  if (roleLabel && roleLabel.toLowerCase() !== "registry entry") {
    parts.push(roleLabel);
  }
  return parts.filter(Boolean).join(" · ") || "registry entry";
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

function routeValidationChip(route) {
  const chip = document.createElement("span");
  const fallbackVisual = route.status_code === "missing_secret" ? "amber" : "neutral";
  const visual = ACCOUNT_VISUAL_CLASS[route.validation_visual_state] || ACCOUNT_VISUAL_CLASS[fallbackVisual] || "neutral";
  chip.className = `chip ${visual}`;
  const dot = document.createElement("span");
  dot.className = "dot";
  const label = document.createElement("span");
  label.textContent = route.validation_label || route.validation_status_label || (route.status_code === "missing_secret" ? "blocked by secret" : "not checked");
  chip.append(dot, label);
  return chip;
}

function routeSecretRef(route) {
  const wrap = document.createElement("div");
  wrap.className = "api-secret-ref";
  const ref = document.createElement("div");
  ref.className = "mono-value";
  ref.textContent = route.secret_ref || "unknown";
  const chip = document.createElement("span");
  const visual = ACCOUNT_VISUAL_CLASS[route.secret_visual_state] || "neutral";
  chip.className = `chip ${visual}`;
  const dot = document.createElement("span");
  dot.className = "dot";
  const label = document.createElement("span");
  label.textContent = route.secret_status_label || "unknown";
  chip.append(dot, label);
  wrap.append(ref, chip);
  return wrap;
}

function routeActionButtons(route) {
  const menu = document.createElement("details");
  menu.className = "account-action-menu api-route-action-menu";

  const summary = document.createElement("summary");
  summary.className = "account-action-menu-trigger";
  setNodeAttribute(summary, "aria-label", `Действия для маршрута ${route.route_id || "unknown"}`);
  const icon = document.createElement("img");
  icon.className = "ui-icon button-icon";
  icon.src = "assets/icons/phosphor/dots-three.png";
  icon.alt = "";
  setNodeAttribute(icon, "aria-hidden", "true");
  summary.append(icon);

  const list = document.createElement("div");
  list.className = "account-action-menu-list api-route-action-menu-list";
  list.append(routeActionButton(route, "api_route_validate", "Проверить маршрут", { menuItem: true }));
  list.append(routeDisabledMenuButton("Детали", "Readonly route details are deferred to a separate surface."));
  const divider = document.createElement("div");
  divider.className = "account-action-menu-divider";
  list.append(divider);
  if (route.enabled === false) {
    list.append(routeActionButton(route, "api_route_remove", "Удалить route", { menuItem: true, danger: true }));
  } else {
    list.append(routeDisabledMenuButton("Удалить route", apiRouteRemoveDisabledReason(route), true));
  }

  menu.append(summary, list);
  return menu;
}

function routeActionButton(route, uiAction, label, options = {}) {
  const button = document.createElement("button");
  const classes = ["button", "small", "api-route-action"];
  if (options.menuItem) {
    classes.push("account-menu-item");
  }
  if (options.danger) {
    classes.push("danger", "api-route-destructive-action");
  }
  button.className = classes.join(" ");
  button.type = "button";
  button.dataset.uiAction = uiAction;
  button.dataset.routeId = route.route_id || "";
  button.dataset.routeEnabled = route.enabled === true ? "true" : "false";
  button.dataset.routeStateProven = route.enabled === true || route.enabled === false ? "true" : "false";
  button.dataset.routeStateRequirement = apiRouteStateRequirement(uiAction);
  button.textContent = label;
  const routeActionTitles = {
    api_route_allow: "Разрешить выбранный маршрут. Это не утверждение состояния runtime.",
    api_route_disable: "Отключить выбранный маршрут. Это не утверждение состояния runtime.",
    api_route_check: "Проверочный запрос к провайдеру для выбранного маршрута. Это не утверждение состояния runtime.",
    api_route_validate: "Проверка доступности модели у провайдера для выбранного маршрута. Это не утверждение состояния runtime.",
    api_route_profile: "Пакет профиля поддержки без настройки Codex config и без утверждения состояния runtime.",
    api_route_evidence_capture: "Свидетельство маршрута: собрать локальный support artifact. UI не читает evidence file.",
    api_route_remove: "Удалить только отключённую route registry запись после server preflight. Не меняет другие routes и не утверждает runtime readiness."
  };
  button.title = routeActionTitles[uiAction] || "Действие с маршрутом через серверный command surface.";
  button.addEventListener("click", () => {
    maybeConfirmAndRun(uiAction, { route_id: button.dataset.routeId });
  });
  return button;
}

function apiRouteRemoveDisabledReason(route) {
  if (route.enabled === true) {
    return "Удаление доступно только для disabled route после server preflight.";
  }
  return "Удаление недоступно: disabled-state не доказан readonly route packet.";
}

function routeDisabledMenuButton(label, title, danger = false) {
  const button = document.createElement("button");
  button.className = `button small account-menu-item disabled${danger ? " danger" : ""}`;
  button.type = "button";
  button.disabled = true;
  button.textContent = label;
  button.title = title;
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
  const validIds = new Set(accounts.map((account) => account.id).filter(Boolean));
  selectedAccountIds = new Set([...selectedAccountIds].filter((id) => validIds.has(id)));
  for (const account of accounts) {
    const row = document.createElement("tr");
    const accountId = account.id || "";
    const errorCell = td(account.last_error_summary ? "account-error-cell" : "dash account-error-cell", account.last_error_summary || "—");
    errorCell.title = account.last_error_summary || "";
    row.append(
      td("checkcell", checkbox(account)),
      td("", accountIdentity(account)),
      td("", account.pool_label || poolLabel(account.pool)),
      td("", statusChip(account)),
      errorCell,
      td("right mono-value", account.last_success || account.cooldown_until || "—"),
      td("account-actions-cell", accountActionButtons(account, { rowMenu: true }))
    );
    row.dataset.accountId = accountId;
    row.tabIndex = 0;
    row.title = "Открыть детали аккаунта. Это UI-only действие без command dispatch.";
    row.addEventListener("click", (event) => {
      if (isInteractiveAccountRowTarget(event.target)) {
        return;
      }
      openAccountDrawer(accountId);
    });
    row.addEventListener("keydown", (event) => {
      if ((event.key === "Enter" || event.key === " ") && !isInteractiveAccountRowTarget(event.target)) {
        event.preventDefault();
        openAccountDrawer(accountId);
      }
    });
    row.classList.toggle("selected", selectedAccountIds.has(accountId));
    body.append(row);
  }
  updateAccountsSelectionUi();
  applyActionAvailability();
}

function isInteractiveAccountRowTarget(target) {
  let node = target;
  while (node) {
    if (["BUTTON", "A", "SUMMARY", "DETAILS", "INPUT", "SELECT", "TEXTAREA"].includes(node.tagName)) {
      return true;
    }
    if (node.classList?.contains("account-action-menu")) {
      return true;
    }
    node = node.parentNode;
  }
  return false;
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

function checkbox(account) {
  const accountId = account.id || "";
  const node = document.createElement("button");
  node.className = "checkbox account-row-select";
  node.type = "button";
  node.dataset.accountId = accountId;
  setNodeAttribute(node, "aria-label", `Выбрать ${accountId || "аккаунт"}`);
  setNodeAttribute(node, "aria-pressed", selectedAccountIds.has(accountId) ? "true" : "false");
  node.title = "Массовые lifecycle-действия отложены; выбор строк не запускает команды.";
  node.addEventListener("click", () => toggleAccountSelection(accountId));
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
  const visual = account.manual_hold ? "amber" : (ACCOUNT_VISUAL_CLASS[account.visual_state] || "neutral");
  chip.className = `chip ${visual}`;
  const dot = document.createElement("span");
  dot.className = "dot";
  const label = document.createElement("span");
  label.textContent = account.manual_hold ? "Удержан" : (account.status_label || statusLabel(account.status));
  chip.append(dot, label);
  return chip;
}

function accountActionButtons(account, options = {}) {
  if (options.rowMenu) {
    return accountActionMenu(account);
  }
  const group = document.createElement("div");
  group.className = "account-action-group";
  group.append(accountDetailButton(account));
  for (const spec of accountActionEligibility(account).filter((item) => item.enabled)) {
    group.append(accountActionButton(account, spec.uiAction, compactAccountActionLabel(spec), { danger: spec.danger }));
  }
  return group;
}

function accountActionMenu(account) {
  const menu = document.createElement("details");
  menu.className = "account-action-menu";

  const summary = document.createElement("summary");
  summary.className = "account-action-menu-trigger";
  setNodeAttribute(summary, "aria-label", `Действия для ${account.id || "аккаунта"}`);
  const icon = document.createElement("img");
  icon.className = "ui-icon button-icon";
  icon.src = "assets/icons/phosphor/dots-three.png";
  icon.alt = "";
  setNodeAttribute(icon, "aria-hidden", "true");
  summary.append(icon);

  const list = document.createElement("div");
  list.className = "account-action-menu-list";
  list.append(accountDetailButton(account, { menuItem: true }));

  const availableSpecs = accountActionEligibility(account).filter((item) => item.enabled);
  for (const spec of availableSpecs.filter((item) => !item.danger)) {
    list.append(accountActionButton(account, spec.uiAction, spec.label, { menuItem: true }));
  }
  const dangerSpecs = availableSpecs.filter((item) => item.danger);
  if (dangerSpecs.length) {
    const divider = document.createElement("div");
    divider.className = "account-action-menu-divider";
    list.append(divider);
    for (const spec of dangerSpecs) {
      list.append(accountActionButton(account, spec.uiAction, spec.label, { menuItem: true, danger: true }));
    }
  }

  menu.append(summary, list);
  return menu;
}

function compactAccountActionLabel(spec) {
  return {
    validate_account: "Проверить",
    release_account: "Снять паузу",
    hold_account: "Удержать",
    promote_account: "В актив",
    demote_account: "В резерв",
    retire_account: "Вывести"
  }[spec.uiAction] || spec.label;
}

function accountDetailButton(account, options = {}) {
  const button = document.createElement("button");
  button.className = options.menuItem
    ? "button small account-detail-trigger account-menu-item"
    : "button small account-detail-trigger";
  button.type = "button";
  button.dataset.accountId = account.id || "";
  button.textContent = "Открыть детали";
  button.title = "Открыть drawer. Данные берутся только из текущего accounts JSON.";
  button.addEventListener("click", () => {
    openAccountDrawer(button.dataset.accountId);
  });
  return button;
}

function accountActionButton(account, uiAction, label, options = {}) {
  const button = document.createElement("button");
  button.className = options.menuItem
    ? `button small account-action account-menu-item${options.danger ? " danger" : ""}`
    : `button small account-action${options.danger ? " danger" : ""}`;
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

function toggleAccountSelection(accountId) {
  if (!accountId) {
    return;
  }
  if (selectedAccountIds.has(accountId)) {
    selectedAccountIds = new Set([...selectedAccountIds].filter((id) => id !== accountId));
  } else {
    selectedAccountIds.add(accountId);
  }
  updateAccountsSelectionUi();
}

function clearAccountSelection() {
  selectedAccountIds.clear();
  updateAccountsSelectionUi();
}

function updateAccountsSelectionUi() {
  const count = selectedAccountIds.size;
  const bulkBar = document.getElementById("accountsBulkBar");
  if (bulkBar) {
    bulkBar.hidden = count === 0;
  }
  const selectedCount = document.getElementById("accountsSelectedCount");
  if (selectedCount) {
    selectedCount.textContent = `Выбрано: ${count}`;
  }

  const validateButton = document.getElementById("accountValidateSelectedAction");
  if (validateButton) {
    validateButton.disabled = true;
    validateButton.title = count === 0
      ? "Выберите аккаунты в таблице."
      : "Массовая проверка будет добавлена отдельным контуром.";
  }

  const bulkValidate = document.getElementById("accountsBulkValidateAction");
  if (bulkValidate) {
    bulkValidate.disabled = true;
    bulkValidate.title = count === 0
      ? "Выберите аккаунты в таблице."
      : "Массовая проверка будет добавлена отдельным контуром.";
  }

  for (const row of document.querySelectorAll("#accountsTableBody tr")) {
    const selected = selectedAccountIds.has(row.dataset.accountId || "");
    row.classList.toggle("selected", selected);
    const selector = row.querySelector(".account-row-select");
    if (selector) {
      setNodeAttribute(selector, "aria-pressed", selected ? "true" : "false");
    }
  }
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
  text("accountDetailPoolValue", account.pool_label || poolLabel(account.pool));
  text("accountDetailLifecycle", accountLifecycleLabel(account));
  text("accountDetailHoldValue", account.manual_hold ? "yes" : "no");
  text("accountDetailEnabled", account.enabled === true ? "да" : (account.enabled === false ? "нет" : "не указано"));
  text("accountDetailLastSuccess", safeAccountDetailText(account.last_success, "—"));
  text("accountDetailError", safeAccountDetailText(account.last_error_summary, "—"));
  text("accountDetailChecks24h", accountChecksLabel(account));
  text("accountDetailFail", boundedNumberLabel(account.fail_count));
  text("accountDetailLatency", account.last_latency_ms ? `${account.last_latency_ms} ms` : "нет данных");
  text("accountDetailRecovery", boundedNumberLabel(account.recovery_attempts));
  text(
    "accountDetailCounterNote",
    account.checks_24h !== undefined || account.success_count !== undefined || account.fail_count !== undefined
      ? "Счётчики взяты из bounded accounts packet и не расширяются UI-слоем."
      : "Счётчики недоступны: нужен bounded account telemetry packet."
  );

  const status = document.getElementById("accountDetailStatusChip");
  status.className = `chip ${ACCOUNT_VISUAL_CLASS[account.visual_state] || "neutral"}`;
  status.lastElementChild.textContent = account.status_label || statusLabel(account.status);

  const pool = document.getElementById("accountDetailPoolChip");
  pool.className = account.pool === "active" ? "chip green" : (account.pool === "reserve" ? "chip blue" : "chip neutral");
  pool.lastElementChild.textContent = account.pool_label || poolLabel(account.pool);

  const hold = document.getElementById("accountDetailHoldChip");
  hold.className = account.manual_hold ? "chip amber" : "chip neutral";
  hold.lastElementChild.textContent = account.manual_hold ? "На удержании" : "Без удержания";

  setMiniPill(
    "accountDetailTruthChip",
    currentAccountsSnapshot?.source === "accounts_readonly" ? "accounts readonly" : "bounded fixture",
    currentAccountsSnapshot?.source === "accounts_readonly" ? "blue" : "neutral"
  );
  renderAccountDetailTimeline(account);
  renderAccountDetailActions(account);
  renderAccountDetailLastCommand();
  applyActionAvailability();
}

function renderMissingAccountDrawer() {
  document.getElementById("accountDetailMissing").hidden = false;
  text("accountDetailTitle", selectedAccountId || "Аккаунт отсутствует");
  text("accountDetailSubtitle", "Выбранный аккаунт не найден после обновления accounts JSON.");
  text("accountDetailId", selectedAccountId || "-");
  text("accountDetailLabel", "account_missing_after_refresh");
  text("accountDetailPoolValue", "нет данных");
  text("accountDetailLifecycle", "account_missing_after_refresh");
  text("accountDetailHoldValue", "нет данных");
  text("accountDetailEnabled", "-");
  text("accountDetailChecks24h", "нет данных");
  text("accountDetailFail", "-");
  text("accountDetailLatency", "нет данных");
  text("accountDetailRecovery", "нет данных");
  text("accountDetailLastSuccess", "-");
  text("accountDetailError", "Действия отключены до выбора существующего аккаунта.");
  text("accountDetailCounterNote", "Счётчики недоступны: выбранного аккаунта нет в обновлённом accounts JSON.");

  for (const chipId of ["accountDetailStatusChip", "accountDetailPoolChip", "accountDetailHoldChip"]) {
    const chip = document.getElementById(chipId);
    chip.className = "chip amber";
    chip.lastElementChild.textContent = "не подтверждено";
  }

  const actions = document.getElementById("accountDetailActions");
  actions.replaceChildren();
  actions.append(disabledAccountActionButton("Действия отключены", "account_missing_after_refresh"));
  document.getElementById("accountDetailDangerActions").replaceChildren(
    disabledAccountActionButton("Вывести из пула", "account_missing_after_refresh")
  );
  setMiniPill("accountDetailTruthChip", "missing", "amber");
  renderAccountDetailTimeline(null);
  renderAccountDetailLastCommand();
}

function accountLifecycleLabel(account) {
  if (!account) {
    return "unknown";
  }
  if (account.pool === "retired") {
    return "retired";
  }
  if (account.manual_hold) {
    return "held";
  }
  if (account.enabled === false) {
    return "disabled";
  }
  if (account.last_error_summary || ["down", "degraded"].includes(account.status)) {
    return "blocked";
  }
  if (account.pool === "active" || account.pool === "reserve") {
    return "available";
  }
  return "unknown";
}

function boundedNumberLabel(value) {
  return Number.isFinite(Number(value)) ? String(value) : "нет данных";
}

function accountChecksLabel(account) {
  if (Number.isFinite(Number(account?.checks_24h))) {
    return String(account.checks_24h);
  }
  if (Number.isFinite(Number(account?.success_count)) || Number.isFinite(Number(account?.fail_count))) {
    return String(Number(account.success_count || 0) + Number(account.fail_count || 0));
  }
  return "нет данных";
}

function renderAccountDetailTimeline(account) {
  const list = document.getElementById("accountDetailTimeline");
  if (!list || typeof list.replaceChildren !== "function") {
    return;
  }
  list.replaceChildren();
  const rows = boundedAccountTimeline(account);
  if (!rows.length) {
    list.append(accountTimelineEmpty());
    return;
  }
  for (const row of rows.slice(0, 4)) {
    const item = document.createElement("div");
    item.className = `account-detail-timeline-row ${row.visual || "neutral"}`;
    const icon = document.createElement("span");
    icon.className = `round-icon ${row.visual || "neutral"}`;
    const img = document.createElement("img");
    img.className = "ui-icon";
    img.src = row.icon || "assets/icons/phosphor/info.png";
    img.alt = "";
    setNodeAttribute(img, "aria-hidden", "true");
    icon.append(img);
    const body = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = row.message;
    const meta = document.createElement("small");
    meta.textContent = row.at || "bounded packet";
    body.append(title, meta);
    item.append(icon, body);
    list.append(item);
  }
}

function boundedAccountTimeline(account) {
  if (!account) {
    return [];
  }
  if (Array.isArray(account.timeline)) {
    return account.timeline.map((row) => ({
      at: safeAccountDetailText(row.at || row.observed_at, "bounded packet"),
      message: safeAccountDetailText(row.message || row.event, "Событие аккаунта"),
      visual: ACCOUNT_VISUAL_CLASS[row.visual_state] || row.visual || "neutral",
      icon: row.icon || "assets/icons/phosphor/info.png"
    }));
  }
  const rows = [];
  if (account.last_error_summary) {
    rows.push({
      at: safeAccountDetailText(account.last_success, "нет времени"),
      message: safeAccountDetailText(account.last_error_summary, "Ошибка аккаунта"),
      visual: "red",
      icon: "assets/icons/phosphor/x-circle.png"
    });
  } else if (account.last_success) {
    rows.push({
      at: safeAccountDetailText(account.last_success, "bounded packet"),
      message: "Последняя проверка OK",
      visual: "green",
      icon: "assets/icons/phosphor/check-circle.png"
    });
  }
  if (account.manual_hold) {
    rows.push({
      at: "bounded accounts packet",
      message: "Аккаунт удержан оператором",
      visual: "amber",
      icon: "assets/icons/phosphor/pause-circle.png"
    });
  }
  if (currentAccountsSnapshot?.source === "accounts_readonly" && rows.length <= 1) {
    return rows;
  }
  if (currentAccountsSnapshot?.source !== "accounts_readonly") {
    rows.push({
      at: "fixture summary",
      message: `${poolLabel(account.pool)} · ${accountLifecycleLabel(account)}`,
      visual: ACCOUNT_VISUAL_CLASS[account.visual_state] || "neutral",
      icon: "assets/icons/phosphor/info.png"
    });
  }
  return rows;
}

function safeAccountDetailText(value, fallback = "нет данных") {
  const textValue = String(value || "").trim();
  if (!textValue) {
    return fallback;
  }
  return redactUiSensitiveText(textValue);
}

function redactUiSensitiveText(value) {
  return String(value || "")
    .replace(/\/Users\/[^ \n\t,;:)]*/g, "[redacted-path]")
    .replace(/\/Volumes\/[^ \n\t,;:)]*/g, "[redacted-path]")
    .replace(/\/private\/tmp\/[^ \n\t,;:)]*/g, "[redacted-path]")
    .replace(/\/tmp\/[^ \n\t,;:)]*/g, "[redacted-path]")
    .replace(/\b(token|secret|password|auth[_-]?token)\s*[:=]\s*[^ \n\t,;)]*/gi, "$1=[redacted]");
}

function accountTimelineEmpty() {
  const empty = document.createElement("div");
  empty.className = "account-detail-empty";
  empty.textContent = "История недоступна. Нужен bounded history packet.";
  return empty;
}

function renderAccountDetailActions(account) {
  const routine = document.getElementById("accountDetailActions");
  const danger = document.getElementById("accountDetailDangerActions");
  routine.replaceChildren();
  danger.replaceChildren();
  for (const spec of accountActionEligibility(account).filter((item) => !item.danger)) {
    routine.append(accountDetailEligibilityButton(account, spec));
  }
  for (const spec of accountActionEligibility(account).filter((item) => item.danger)) {
    danger.append(accountDetailEligibilityButton(account, spec));
  }
}

function accountActionEligibility(account) {
  const retired = account.pool === "retired";
  const held = account.manual_hold === true;
  return [
    { uiAction: "validate_account", label: "Проверить", enabled: !retired, reason: retired ? "аккаунт выведен из пула" : "", icon: "assets/icons/phosphor/shield-check.png" },
    { uiAction: "release_account", label: "Снять удержание", enabled: held && !retired, reason: held ? "" : "аккаунт не на удержании", icon: "assets/icons/phosphor/play.png" },
    { uiAction: "hold_account", label: "Удержать", enabled: !held && !retired, reason: held ? "аккаунт уже удержан" : (retired ? "аккаунт выведен из пула" : ""), icon: "assets/icons/phosphor/pause-circle.png" },
    { uiAction: "promote_account", label: "Перевести в активные", enabled: account.pool === "reserve" && !held, reason: account.pool === "active" ? "аккаунт уже активен" : (held ? "сначала снимите удержание" : "доступно только из резерва"), icon: "assets/icons/phosphor/play.png" },
    { uiAction: "demote_account", label: "Перевести в резерв", enabled: account.pool === "active" && !held, reason: account.pool === "reserve" ? "аккаунт уже в резерве" : (held ? "сначала снимите удержание" : "доступно только из active"), icon: "assets/icons/phosphor/arrows-clockwise.png" },
    { uiAction: "retire_account", label: "Вывести из пула", enabled: !retired, reason: retired ? "аккаунт уже выведен" : "", icon: "assets/icons/phosphor/trash.png", danger: true }
  ];
}

function accountDetailEligibilityButton(account, spec) {
  if (!spec.enabled) {
    return disabledAccountActionButton(spec.label, spec.reason, spec.danger);
  }
  const button = accountActionButton(account, spec.uiAction, spec.label, { danger: spec.danger });
  button.classList.add("account-detail-action");
  prependNode(button, actionIcon(spec.icon));
  return button;
}

function disabledAccountActionButton(label, reason, danger = false) {
  const button = document.createElement("button");
  button.className = `button small account-detail-disabled-action${danger ? " danger" : ""}`;
  button.type = "button";
  button.disabled = true;
  button.title = reason || "Действие недоступно.";
  button.append(actionIcon("assets/icons/phosphor/info.png"));
  const textNode = document.createElement("span");
  textNode.textContent = label;
  const reasonNode = document.createElement("small");
  reasonNode.textContent = reason || "недоступно";
  button.append(textNode, reasonNode);
  return button;
}

function actionIcon(src) {
  const img = document.createElement("img");
  img.className = "ui-icon button-icon";
  img.src = src;
  img.alt = "";
  setNodeAttribute(img, "aria-hidden", "true");
  return img;
}

function prependNode(parent, child) {
  if (typeof parent.prepend === "function") {
    parent.prepend(child);
  } else if (typeof parent.append === "function") {
    parent.append(child);
  }
}

function renderAccountDetailLastCommand() {
  const entry = actionLedger.find((item) => item.target === selectedAccountId) || null;
  const drawer = document.getElementById("accountDetailDrawer");
  const section = document.getElementById("accountDetailLastCommandSection");
  const chip = document.getElementById("accountDetailLastCommandChip");
  if (!entry) {
    if (drawer) {
      if (drawer.classList && typeof drawer.classList.remove === "function") {
        drawer.classList.remove("last-command-visible");
      } else {
        drawer.className = String(drawer.className || "").replace(/\blast-command-visible\b/g, "").trim();
      }
    }
    if (section) {
      section.hidden = true;
    }
    chip.className = "chip neutral";
    chip.lastElementChild.textContent = "нет";
    text("accountDetailLastCommandAction", "нет");
    text("accountDetailLastCommandCode", "-");
    text("accountDetailLastCommandNext", "-");
    text("accountDetailLastCommandRefresh", "нет данных");
    return;
  }
  if (drawer) {
    if (drawer.classList && typeof drawer.classList.add === "function") {
      drawer.classList.add("last-command-visible");
    } else if (!String(drawer.className || "").includes("last-command-visible")) {
      drawer.className = `${drawer.className || ""} last-command-visible`.trim();
    }
  }
  if (section) {
    section.hidden = false;
  }
  chip.className = `chip ${entry.visualClass || "neutral"}`;
  chip.lastElementChild.textContent = entry.displayState || entry.status || "unknown";
  text("accountDetailLastCommandAction", entry.uiAction);
  text("accountDetailLastCommandCode", entry.machineCode);
  text("accountDetailLastCommandNext", entry.nextAction);
  text("accountDetailLastCommandRefresh", entry.refreshStatus);
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
  setSnapshotCommandLedgerFromSnapshots("overview snapshot", safeSnapshot);
  renderUiReadonlyLaneExitSummary();

  const picker = document.getElementById("statePicker");
  picker.value = canonicalState(safeSnapshot.state_id || safeSnapshot.ui_state);
  picker.disabled = source === "live";
  document.getElementById("sourcePicker").value = source;
  document.getElementById("brandCaption").textContent = source === "live"
    ? "live только чтение"
    : "демо-просмотр UI";
  setSourceCopy(source);
  document.getElementById("refreshFixture").lastElementChild.textContent = "Обновить";

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
  } else if (currentScreen() === "quick-start") {
    renderQuickStart(quickStartAccountsFixtureFromOverview(fixture), quickStartApiFixtureFromOverview(fixture), "fixture", fixture.state_id || state);
  } else {
    renderSnapshot(fixture);
  }
}

async function setLiveReadonly(updateUrl = false) {
  setLiveReadonlyPendingUi();
  if (currentScreen() === "overview") {
    renderOverviewLivePendingState();
  }
  const snapshot = currentScreen() === "quick-start"
    ? {
      accounts: await loadAccountsReadonly(),
      apiConnections: await loadApiConnectionsReadonly()
    }
    : (currentScreen() === "accounts"
      ? await loadAccountsReadonly()
      : (currentScreen() === "api-connections" ? await loadApiConnectionsReadonly() : await loadLiveReadonly()));
  if (updateUrl) {
    const url = new URL(window.location.href);
    url.searchParams.set("source", "live");
    window.history.replaceState({}, "", url);
  }
  if (currentScreen() === "accounts") {
    renderAccountsSnapshot(snapshot);
  } else if (currentScreen() === "api-connections") {
    renderApiConnectionsSnapshot(snapshot);
  } else if (currentScreen() === "quick-start") {
    renderQuickStart(snapshot.accounts, snapshot.apiConnections, "live", "integration_failure");
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
  for (const link of document.querySelectorAll("[data-settings-section-link]")) {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      setScreen("settings", true, link.dataset.settingsSectionLink);
      refreshCurrentSource();
    });
  }
  document.getElementById("dataLayoutBackAction")?.addEventListener("click", () => {
    setScreen("settings", true, "hub");
    refreshCurrentSource();
  });
  document.getElementById("runtimeModeBackAction")?.addEventListener("click", () => {
    setScreen("settings", true, "hub");
    refreshCurrentSource();
  });
  document.getElementById("clientLaunchBackAction")?.addEventListener("click", () => {
    setScreen("settings", true, "hub");
    refreshCurrentSource();
  });
  document.getElementById("accountsPolicyBackAction")?.addEventListener("click", () => {
    setScreen("settings", true, "hub");
    refreshCurrentSource();
  });
  document.getElementById("accountsPolicyOpenLedgerAction")?.addEventListener("click", () => openActionLedgerPanel());
  document.getElementById("diagnosticsPrivacyBackAction")?.addEventListener("click", () => {
    setScreen("settings", true, "hub");
    refreshCurrentSource();
  });
  document.getElementById("diagnosticsPrivacyOpenLedgerAction")?.addEventListener("click", () => openActionLedgerPanel());
  document.getElementById("advancedSettingsBackAction")?.addEventListener("click", () => {
    setScreen("settings", true, "hub");
    refreshCurrentSource();
  });
  document.getElementById("advancedOpenLedgerAction")?.addEventListener("click", () => openActionLedgerPanel());
  for (const button of document.querySelectorAll(".live-action")) {
    button.addEventListener("click", () => maybeConfirmAndRun(button.dataset.uiAction));
  }
  document.getElementById("accountAddAction").addEventListener("click", () => openOnboardModal());
  document.getElementById("quickStartAddAccountAction")?.addEventListener("click", () => openOnboardModal());
  document.getElementById("accountsClearSelectionAction")?.addEventListener("click", () => clearAccountSelection());
  document.getElementById("accountDetailClose").addEventListener("click", () => closeAccountDrawer());
  document.getElementById("accountDetailBackdrop").addEventListener("click", () => closeAccountDrawer());
  document.getElementById("actionOpenLedgerAction")?.addEventListener("click", () => openActionLedgerPanel());
  document.getElementById("actionLedgerClose")?.addEventListener("click", () => closeActionLedgerPanel());
  document.getElementById("actionLedgerBackdrop")?.addEventListener("click", () => closeActionLedgerPanel());
  document.getElementById("actionLedgerClear")?.addEventListener("click", () => clearActionLedger());
  for (const button of document.querySelectorAll("[data-ledger-filter]")) {
    button.addEventListener("click", () => setActionLedgerFilter(button.dataset.ledgerFilter));
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeAccountDrawer();
      closeActionLedgerPanel();
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
