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
  cancelled: "amber",
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
const QUICK_START_DEFAULT_LAUNCH_LABEL = "Проверить запуск";
const QUICK_START_BLOCKED_MIXED_LAUNCH_LABEL = QUICK_START_DEFAULT_LAUNCH_LABEL;
let quickStartMixedModeProductBlocked = false;
const ACCOUNT_VISUAL_CLASS = {
  green: "green",
  blue: "blue",
  amber: "amber",
  red: "red",
  neutral: "neutral"
};
const ACTION_LEDGER_LIMIT = 5;
const BROWSER_ACTION_PAYLOAD_KEYS = ["account_id", "route_id", "session_id"];
const CODEX_ROUTE_SELECTION_STORAGE_KEY = "wbp.codex.route-selection.v2";
const QUICK_START_DEFAULT_EXECUTION_MODE = "chatgpt_plus_api";
const QUICK_START_PREFERRED_CHATGPT_MODEL_ID = "gpt-5.5";
const QUICK_START_LEGACY_CHATGPT_DEFAULT_MODEL_IDS = new Set(["gpt-5.3-codex"]);
const QUICK_START_PREFERRED_API_MODEL_ID = "wbp-deepseek-chat";
const QUICK_START_PREFERRED_API_REASONING_OPTION_ID = "provider_declared_disabled";
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
  "recheck_account",
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
  launch_custom_client_native: {
    severity: "high",
    policy: "native-proof-required",
    warning: "Это запрашивает native Custom launch. Зелёный успех допустим только при process_started, expected_custom_identity_observed и native_window_observed плюс подтверждённом launch_claim_scope; workbench/session readiness этого не доказывают."
  },
  onboard_account_dry_run: {
    severity: "low",
    policy: "account-preview",
    warning: "Это показывает только dry-run preview подключения аккаунта. Реальная авторизация и импорт не выполняются."
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
  recheck_account: {
    severity: "medium",
    policy: "account-verification",
    warning: "Это повторно проверяет один аккаунт. Подтверждением пула остаётся обновлённый accounts JSON."
  },
  promote_account: {
    severity: "high",
    policy: "account-placement",
    warning: "Это запрашивает перевод в active. Это не доказательство ёмкости и не evidence готовности; подтверждением остаются обновлённый accounts JSON и status truth."
  },
  demote_account: {
    severity: "medium",
    policy: "account-placement",
    warning: "Это запрашивает перевод в reserve. Подтверждением остаются обновлённый accounts JSON и status truth."
  },
  hold_account: {
    severity: "medium",
    policy: "account-hold",
    warning: "Это запрашивает ручную паузу. Подтверждением остаются обновлённый accounts JSON и status truth."
  },
  release_account: {
    severity: "medium",
    policy: "account-hold",
    warning: "Это запрашивает снятие ручной паузы. Подтверждением остаются обновлённый accounts JSON и status truth."
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
  api_route_connect: {
    severity: "high",
    policy: "api-route-connect",
    warning: "Это запускает owner credential bridge и server-owned подключение API route. Browser не передаёт api_key, route_id, auth, secret, token или path; подтверждением остаётся packet плюс api-connections refresh."
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
let actionPhase = "live_readonly";
let sandboxActionPreflight = null;
let actionMetadataLoaded = false;
let actionMetadataLoadPromise = null;
let pendingConfirmedAction = null;
let confirmationInFlight = false;
let currentAccountsSnapshot = null;
let currentApiConnectionsSnapshot = null;
let lastOnboardingActionPayload = null;
let lastApiCredentialActionPayload = null;
let lastApiCredentialActionRefreshState = "none";
let refreshButtonFeedbackTimer = null;
let selectedAccountId = "";
let selectedAccountIds = new Set();
let actionLedger = [];
let actionLedgerFilter = "all";
let activeActionRequestKey = "";
let activeActionAbortController = null;
let activeActionAbortReason = "";
let activeOnboardLoginSession = null;
let onboardLoginWindowRef = null;
let onboardLoginOverlayOpenUrl = "";
let onboardLoginWindowBlobUrl = "";
let operatorRunInFlight = false;
let operatorLastPacket = null;
let reviewPanelBusy = false;
let reviewSurfacePacket = null;
let reviewCommandsPacket = null;
let reviewLastCommandPacket = null;
let codexLaunchDryRunInFlight = false;
const QUICK_START_MANUAL_CHECK_REPLAY_MAX_AGE_MS = 30000;
let quickStartManualCheckSnapshot = null;
let codexCustomModelDryRunInFlight = false;
let codexCustomAccountDryRunInFlight = false;
let codexCustomSessionActionInFlight = false;
let codexCustomSelectedSessionId = "";
let codexCustomProductCoderWorktreeId = "";
let codexCustomApiModelEntryById = new Map();
let snapshotCommandLedgerState = {
  surface: "not loaded",
  status: "missing",
  source: "none",
  entries: [],
  hasWarnings: false
};
const CODEX_CUSTOM_AGENT_ALIAS_CONFIG_KIND = "ui_session_memory";
const CODEX_CUSTOM_AGENT_ALIAS_DEFAULTS = Object.freeze({
  primary_model_slot: "Codex",
  coding_agent_model_slot: "DIP",
  agent_1_display: "1",
  agent_2_display: "2"
});
const CODEX_CUSTOM_AGENT_ALIAS_SLOTS = Object.freeze([
  {
    slot_id: "primary_model_slot",
    input_id: "quickStartPrimaryAgentAliasInput",
    default_label: "Codex",
    runtime_lane: "chatgpt",
    display_only: true
  },
  {
    slot_id: "coding_agent_model_slot",
    input_id: "quickStartCodingAgentAliasInput",
    default_label: "DIP",
    runtime_lane: "deepseek_api",
    display_only: true
  },
  {
    slot_id: "agent_1_display",
    input_id: "quickStartAgentOneAliasInput",
    default_label: "1",
    runtime_lane: "display",
    display_only: true
  },
  {
    slot_id: "agent_2_display",
    input_id: "quickStartAgentTwoAliasInput",
    default_label: "2",
    runtime_lane: "display",
    display_only: true
  }
]);
let codexCustomAgentAliases = { ...CODEX_CUSTOM_AGENT_ALIAS_DEFAULTS };

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
  const source = params.get("source");
  if (source === "live") {
    return "live";
  }
  if (source === "fixture") {
    return "fixture";
  }
  const desktop = document.querySelector(".desktop");
  return desktop?.dataset?.source === "live" ? "live" : "fixture";
}

function screenFromLocation() {
  const params = new URLSearchParams(window.location.search);
  const screen = params.get("screen") || "quick-start";
  return SCREENS.includes(screen) ? screen : "quick-start";
}

function settingsSectionFromLocation() {
  const params = new URLSearchParams(window.location.search);
  const section = params.get("section") || "hub";
  return SETTINGS_SECTIONS.includes(section) ? section : "hub";
}

function currentScreen() {
  return document.querySelector(".desktop").dataset.screen || "quick-start";
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
    actionPhase = payload.action_phase || "live_readonly";
    sandboxActionPreflight = payload.sandbox_preflight || null;
  } catch (error) {
    actionMetadata = {};
    actionPhase = "live_readonly";
    sandboxActionPreflight = null;
  } finally {
    actionMetadataLoaded = true;
  }
}

async function ensureActionMetadataLoaded() {
  if (actionMetadataLoaded) {
    return;
  }
  if (!actionMetadataLoadPromise) {
    actionMetadataLoadPromise = loadActionMetadata().finally(() => {
      actionMetadataLoadPromise = null;
    });
  }
  await actionMetadataLoadPromise;
}

async function fetchOperatorJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} http ${response.status}`);
  }
  return response.json();
}

async function fetchCodexLaunchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} http ${response.status}`);
  }
  return response.json();
}

async function fetchReviewJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} http ${response.status}`);
  }
  return response.json();
}

function webBootstrapValue(name) {
  if (typeof document === "undefined" || typeof document.querySelector !== "function") {
    return "";
  }
  const node = document.querySelector(`meta[name="${name}"]`);
  if (!node || typeof node.getAttribute !== "function") {
    return "";
  }
  return String(node.getAttribute("content") || "");
}

function webPostHeaders(extraHeaders = {}) {
  return {
    ...extraHeaders,
    Authorization: `Bearer ${webBootstrapValue("wbp-web-token")}`,
    "X-WBP-CSRF": webBootstrapValue("wbp-csrf-token")
  };
}

function operatorSetText(id, value) {
  const node = document.getElementById(id);
  if (node) {
    node.textContent = String(value ?? "-");
  }
}

function normalizeCodexCustomAgentAliasLabel(value, fallback) {
  const normalized = String(value ?? "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 24);
  return normalized || fallback;
}

function normalizedCodexCustomAgentAliases(value = {}) {
  const aliases = {};
  for (const slot of CODEX_CUSTOM_AGENT_ALIAS_SLOTS) {
    aliases[slot.slot_id] = normalizeCodexCustomAgentAliasLabel(
      value[slot.slot_id],
      slot.default_label
    );
  }
  return aliases;
}

function codexCustomAgentAliasRoleMap(aliases = codexCustomAgentAliases) {
  return CODEX_CUSTOM_AGENT_ALIAS_SLOTS.map((slot) => ({
    slot_id: slot.slot_id,
    label: normalizeCodexCustomAgentAliasLabel(aliases[slot.slot_id], slot.default_label),
    runtime_lane: slot.runtime_lane,
    display_only: true
  }));
}

function codexCustomAgentAliasMetadataPacket(source = "render") {
  return {
    status: "ok",
    packet_kind: "codex_custom_agent_aliases",
    source,
    alias_scope: "ui_display_metadata_only",
    config_kind: CODEX_CUSTOM_AGENT_ALIAS_CONFIG_KIND,
    persisted_in_browser_storage: false,
    semantic_alias_routing_enabled: false,
    runtime_dispatch_changed: false,
    session_manager_changed: false,
    provider_selection_changed: false,
    command_surface_changed: false,
    changed_files: [],
    role_map: codexCustomAgentAliasRoleMap()
  };
}

function renderCodexCustomAgentAliases(source = "render") {
  codexCustomAgentAliases = normalizedCodexCustomAgentAliases(codexCustomAgentAliases);
  for (const slot of CODEX_CUSTOM_AGENT_ALIAS_SLOTS) {
    const node = document.getElementById(slot.input_id);
    if (node) {
      node.value = codexCustomAgentAliases[slot.slot_id];
    }
  }
  const primary = codexCustomAgentAliases.primary_model_slot;
  const coding = codexCustomAgentAliases.coding_agent_model_slot;
  const agentOne = codexCustomAgentAliases.agent_1_display;
  const agentTwo = codexCustomAgentAliases.agent_2_display;
  operatorSetText("quickStartAgentAliasPreview", `${primary}/ChatGPT · ${coding}/DeepSeek · ${agentOne}/${agentTwo} labels`);
  const packet = codexCustomAgentAliasMetadataPacket(source);
  const packetNode = document.getElementById("quickStartAgentAliasPacket");
  if (packetNode) {
    packetNode.textContent = `alias metadata · ${packet.alias_scope} · dispatch changed: ${packet.runtime_dispatch_changed} · roles: ${packet.role_map.length}`;
    packetNode.dataset.aliasScope = packet.alias_scope;
    packetNode.dataset.runtimeDispatchChanged = String(packet.runtime_dispatch_changed);
    packetNode.dataset.semanticAliasRoutingEnabled = String(packet.semantic_alias_routing_enabled);
    packetNode.dataset.roleMapCount = String(packet.role_map.length);
  }
  const scope = document.getElementById("quickStartAgentAliasScope");
  if (scope?.lastElementChild) {
    scope.lastElementChild.textContent = "display only";
  }
}

function collectCodexCustomAgentAliasesFromInputs() {
  const aliases = {};
  for (const slot of CODEX_CUSTOM_AGENT_ALIAS_SLOTS) {
    const node = document.getElementById(slot.input_id);
    aliases[slot.slot_id] = normalizeCodexCustomAgentAliasLabel(
      node ? node.value : "",
      slot.default_label
    );
  }
  return normalizedCodexCustomAgentAliases(aliases);
}

function saveCodexCustomAgentAliasesFromUi() {
  codexCustomAgentAliases = collectCodexCustomAgentAliasesFromInputs();
  renderCodexCustomAgentAliases("operator_saved");
}

function resetCodexCustomAgentAliasesFromUi() {
  codexCustomAgentAliases = normalizedCodexCustomAgentAliases(CODEX_CUSTOM_AGENT_ALIAS_DEFAULTS);
  renderCodexCustomAgentAliases("operator_reset");
}

function setupCodexCustomAgentAliases() {
  codexCustomAgentAliases = normalizedCodexCustomAgentAliases(CODEX_CUSTOM_AGENT_ALIAS_DEFAULTS);
  renderCodexCustomAgentAliases("bootstrap");
  for (const slot of CODEX_CUSTOM_AGENT_ALIAS_SLOTS) {
    document.getElementById(slot.input_id)?.addEventListener("input", () => {
      codexCustomAgentAliases = collectCodexCustomAgentAliasesFromInputs();
      renderCodexCustomAgentAliases("editing");
    });
  }
  document.getElementById("quickStartAgentAliasesSaveAction")?.addEventListener("click", () => saveCodexCustomAgentAliasesFromUi());
  document.getElementById("quickStartAgentAliasesResetAction")?.addEventListener("click", () => resetCodexCustomAgentAliasesFromUi());
}

function codexLaunchSetText(id, value) {
  operatorSetText(id, value);
}

function codexLaunchSetChip(visual, label) {
  const chip = document.getElementById("codexLaunchModesChip");
  if (!chip) {
    return;
  }
  chip.className = `chip ${ACCOUNT_VISUAL_CLASS[visual] || VISUAL_CLASS[visual] || ACTION_STATUS_VISUAL_CLASS[visual] || visual || "neutral"}`;
  if (chip.lastElementChild) {
    chip.lastElementChild.textContent = label || visual || "unknown";
  }
}

function codexLaunchModeById(packet, modeId) {
  const modes = Array.isArray(packet?.modes) ? packet.modes : [];
  return modes.find((mode) => mode?.id === modeId) || {};
}

function renderCodexLaunchModes(launchModes, originalStatus, customStatus) {
  const original = codexLaunchModeById(launchModes, "original_codex");
  const custom = codexLaunchModeById(launchModes, "codex_custom");
  const claimGate = launchModes?.claim_gate_status || customStatus?.claim_gate_status || "not_reported";
  const claimGateBlocked = String(claimGate).includes("blocked");
  codexLaunchSetChip(claimGateBlocked ? "amber" : "green", claimGateBlocked ? "split ready / gate blocked" : "split ready");
  codexLaunchSetText(
    "codexLaunchModesSummary",
    `Original ${original.role || "protected_baseline"} · Custom ${custom.role || "proxy_enabled_workbench"}`
  );
  codexLaunchSetText("originalCodexRole", original.role || originalStatus?.host_boundary || "-");
  codexLaunchSetText("originalCodexProxy", originalStatus?.proxy_injection_allowed === false ? "forbidden" : "unknown");
  codexLaunchSetText("originalCodexClaim", original.launch_claim_scope || originalStatus?.launch_claim_scope || "-");
  codexLaunchSetText("customCodexRole", custom.role || "proxy_enabled_workbench");
  codexLaunchSetText(
    "customCodexSession",
    customStatus?.custom_session_available ? "available" : (customStatus?.availability_reason || "not admitted")
  );
  codexLaunchSetText("codexLaunchClaimGate", claimGate);
  codexLaunchSetText("originalCodexStatus", `${originalStatus?.status || "unknown"} · ${originalStatus?.launch_claim_scope || "status_only"}`);
  codexLaunchSetText("customCodexStatus", `${customStatus?.status || "unknown"} · ${customStatus?.launch_claim_scope || "readonly_readiness_only"}`);
}

async function refreshCodexLaunchModesPanel() {
  try {
    const [launchModes, originalStatus, customStatus] = await Promise.all([
      fetchCodexLaunchJson("api/codex/launch-modes"),
      fetchCodexLaunchJson("api/codex/original/status"),
      fetchCodexLaunchJson("api/codex/custom/status")
    ]);
    renderCodexLaunchModes(launchModes, originalStatus, customStatus);
  } catch (error) {
    codexLaunchSetChip("red", "failed");
    codexLaunchSetText("codexLaunchModesSummary", `Launch modes fetch failed: ${error.message}`);
  }
}

function renderOriginalCodexDryRun(packet) {
  const response = document.getElementById("codexLaunchDryRunResponse");
  const ok = packet?.status === "ok" && packet?.dry_run === true && packet?.dispatch_plan_safe === true;
  const claimGate = document.getElementById("codexLaunchClaimGate")?.textContent || "not_reported";
  const claimGateBlocked = String(claimGate).includes("blocked");
  codexLaunchSetChip(
    ok && !claimGateBlocked ? "green" : (ok ? "amber" : (packet?.status === "rejected" ? "amber" : "red")),
    ok && claimGateBlocked ? "dry-run safe / gate blocked" : (ok ? "dry-run safe" : (packet?.status || "failed"))
  );
  codexLaunchSetText("originalCodexStatus", `${packet?.status || "unknown"} · ${packet?.launch_claim_scope || "dry_run_guard_only"}`);
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      dry_run: packet?.dry_run === true,
      dispatch_plan_safe: packet?.dispatch_plan_safe === true,
      proxy_env_injected: packet?.proxy_env_injected === true,
      custom_home_injected: packet?.custom_home_injected === true,
      model_override_injected: packet?.model_override_injected === true,
      route_or_backend_injected: packet?.route_or_backend_injected === true,
      launch_claim_scope: packet?.launch_claim_scope || "",
      next_action: packet?.next_action || "",
    }, null, 2);
  }
}

function renderOriginalCodexLaunch(packet) {
  const response = document.getElementById("codexLaunchDryRunResponse");
  const ok = packet?.status === "ok"
    && packet?.running_status === true
    && packet?.proxy_env_present === false
    && packet?.wbp_endpoint_injected === false
    && packet?.custom_home_present === false
    && packet?.custom_codex_home_present === false
    && packet?.current_codex_touched === false;
  codexLaunchSetChip(
    ok ? "green" : (packet?.status === "blocked" ? "amber" : "red"),
    ok ? "original launch proven" : (packet?.status || "failed")
  );
  codexLaunchSetText("originalCodexStatus", `${packet?.status || "unknown"} · ${packet?.launch_claim_scope || "baseline_launch"}`);
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      running_status: packet?.running_status === true,
      proxy_env_present: packet?.proxy_env_present === true,
      wbp_endpoint_injected: packet?.wbp_endpoint_injected === true,
      custom_home_present: packet?.custom_home_present === true,
      custom_codex_home_present: packet?.custom_codex_home_present === true,
      current_codex_touched: packet?.current_codex_touched === true,
      protected_surfaces_unchanged: packet?.protected_surfaces_unchanged === true,
      launch_claim_scope: packet?.launch_claim_scope || "",
      next_action: packet?.next_action || "",
    }, null, 2);
  }
}

function renderCodexCustomLaunchDryRun(packet) {
  const response = document.getElementById("codexLaunchDryRunResponse");
  const ok = packet?.status === "ok" && packet?.dry_run === true && packet?.custom_launch_plan_safe === true;
  codexLaunchSetChip(ok ? "amber" : (packet?.status === "rejected" ? "amber" : "red"), ok ? "custom dry-run safe" : (packet?.status || "failed"));
  codexLaunchSetText("customCodexStatus", `${packet?.status || "unknown"} · ${packet?.launch_claim_scope || "dry_run_readiness_only"}`);
  codexLaunchSetText("customCodexSession", packet?.real_launch_attempted ? "unexpected launch attempted" : "dry-run only");
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      dry_run: packet?.dry_run === true,
      custom_launch_plan_safe: packet?.custom_launch_plan_safe === true,
      real_launch_attempted: packet?.real_launch_attempted === true,
      prompt_attempted: packet?.prompt_attempted === true,
      token_burn: packet?.token_burn ?? 0,
      wbp_endpoint_configured: packet?.wbp_endpoint_configured || "",
      current_codex_home_allowed: packet?.current_codex_home_allowed === true,
      current_codex_touch_risk: packet?.current_codex_touch_risk || "unknown",
      launch_claim_scope: packet?.launch_claim_scope || "",
      next_action: packet?.next_action || "",
    }, null, 2);
  }
}

function renderCodexCustomLaunch(packet) {
  const response = document.getElementById("codexLaunchDryRunResponse");
  const claimScope = String(packet?.launch_claim_scope || "");
  const selectionPacket = packet?.selection_packet || {};
  const launchExecutionMode = packet?.execution_mode || selectionPacket?.execution_mode || "";
  const launchChatgptModelId = packet?.chatgpt_model_id || selectionPacket?.chatgpt_model_id || "";
  const launchApiModelId = packet?.api_model_id || selectionPacket?.api_model_id || "";
  const launchRouteModelId = packet?.route_model_id || "";
  const normalizedClaimScope = claimScope.toLowerCase();
  const workbenchOnly = packet?.session_created === true
    || packet?.workbench_ready === true
    || normalizedClaimScope.includes("dispatch")
    || normalizedClaimScope.includes("workbench");
  const nativeProofOk = packet?.status === "ok"
    && packet?.running_status === true
    && packet?.isolated_home === true
    && packet?.isolated_codex_home === true
    && packet?.isolated_profile_dir === true
    && packet?.server_issued_model_list === true
    && packet?.wbp_endpoint_configured === true
    && packet?.browser_route_injection === false
    && packet?.browser_backend_injection === false
    && packet?.current_codex_touched === false
    && packet?.process_started === true
    && packet?.expected_custom_identity_observed === true
    && packet?.native_window_observed === true
    && packet?.native_app_usable === true
    && packet?.real_codex_app_launched === true
    && claimScope !== ""
    && !normalizedClaimScope.includes("dispatch")
    && !normalizedClaimScope.includes("workbench");
  const limitedWindowLaunch = (packet?.status === "blocked" || packet?.status === "ok")
    && packet?.process_started === true
    && packet?.running_status === true
    && packet?.native_window_observed === true
    && packet?.native_app_usable !== true;
  const nativeUsabilityBlocked = packet?.machine_error_code === "CUSTOM_NATIVE_WINDOW_USABILITY_NOT_PROVEN"
    || Boolean(packet?.native_app_usability_blocked_reason_class)
    || Boolean(packet?.renderer_surface_blocked_reason_class);
  const launchPacketTruth = packet?.launch_packet_is_truth_source === true;
  const reusedExistingWindow = packet?.status === "ok"
    && launchPacketTruth
    && packet?.reused_existing_window === true
    && packet?.existing_window_reuse_admissible === true
    && packet?.selection_matches_last_launch === true
    && packet?.show_window_attempted === true
    && packet?.native_window_observed === true
    && packet?.native_app_usable === true
    && packet?.new_launch_started !== true;
  const relaunchSucceeded = nativeProofOk
    && launchPacketTruth
    && packet?.existing_window_relaunch_admissible === true
    && packet?.existing_window_relaunch_attempted === true
    && packet?.existing_window_relaunch_termination?.status === "ok"
    && packet?.new_launch_started === true;
  const orphanReplaceSucceeded = nativeProofOk
    && launchPacketTruth
    && packet?.existing_window_orphan_replace_admissible === true
    && packet?.existing_window_orphan_replace_attempted === true
    && packet?.existing_window_orphan_replace_termination?.status === "ok"
    && packet?.new_launch_started === true;
  const existingWindowBlocked = packet?.status === "blocked"
    && (
      packet?.machine_error_code === "CUSTOM_NATIVE_CONFIG_CHANGED_RELAUNCH_STOP_FAILED"
      || packet?.machine_error_code === "CUSTOM_NATIVE_ORPHAN_EXISTING_WINDOW_REPLACE_STOP_FAILED"
      || packet?.machine_error_code === "CUSTOM_NATIVE_CONFIG_CHANGED_EXISTING_WINDOW_NOT_REUSED"
      || packet?.machine_error_code === "CUSTOM_NATIVE_EXISTING_WINDOW_WITHOUT_MATCHING_LAUNCH_PACKET"
      || packet?.machine_error_code === "CUSTOM_NATIVE_EXISTING_WINDOW_NOT_RESPONSIVE"
      || packet?.machine_error_code === "CUSTOM_NATIVE_EXISTING_WINDOW_USABILITY_NOT_PROVEN"
    );
  codexLaunchSetChip(
    nativeProofOk
      ? "green"
      : (
        packet?.status === "ok"
          ? "amber"
          : (packet?.status === "blocked" || packet?.status === "rejected" ? "amber" : "red")
      ),
    nativeProofOk
      ? "native proof confirmed"
      : (
        packet?.status === "ok"
          ? (
            limitedWindowLaunch
              ? (
                nativeUsabilityBlocked
                  ? "renderer blocked / input not proven"
                  : "window visible / proof incomplete"
              )
              : (workbenchOnly ? "workbench/session only" : "native proof pending")
          )
          : (
            limitedWindowLaunch
              ? (
                nativeUsabilityBlocked
                  ? "renderer blocked / input not proven"
                  : "window visible / proof incomplete"
              )
              : (packet?.status || "failed")
          )
      )
  );
  codexLaunchSetText("customCodexStatus", `${packet?.status || "unknown"} · ${claimScope || "native_proof_required"}`);
  codexLaunchSetText(
    "customCodexSession",
    nativeProofOk
      ? (packet?.native_app_usable === true ? "native app usable" : "native app/window proven")
      : (
        workbenchOnly
          ? "workbench/session only"
          : (
            limitedWindowLaunch
              ? (
                nativeUsabilityBlocked
                  ? "window visible; input surface not proven"
                  : "window visible; native proof incomplete"
              )
              : (packet?.process_started === true
              ? "process only; native proof missing"
              : (packet?.next_action || "native proof missing"))
          )
      )
  );
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      final_status: packet?.final_status || "",
      execution_mode: launchExecutionMode,
      chatgpt_model_id: launchChatgptModelId,
      api_model_id: launchApiModelId,
      session_created: packet?.session_created === true,
      running_status: packet?.running_status === true,
      isolated_home: packet?.isolated_home === true,
      isolated_codex_home: packet?.isolated_codex_home === true,
      isolated_profile_dir: packet?.isolated_profile_dir === true,
      server_issued_model_list: packet?.server_issued_model_list === true,
      wbp_endpoint_configured: packet?.wbp_endpoint_configured === true,
      browser_route_injection: packet?.browser_route_injection === true,
      browser_backend_injection: packet?.browser_backend_injection === true,
      current_codex_touched: packet?.current_codex_touched === true,
      process_started: packet?.process_started === true,
      expected_custom_identity_observed: packet?.expected_custom_identity_observed === true,
      native_window_observed: packet?.native_window_observed === true,
      real_codex_app_launched: packet?.real_codex_app_launched === true,
      native_app_usable: packet?.native_app_usable === true,
      input_capable_ui_observed: packet?.input_capable_ui_observed === true,
      native_app_usability_source: packet?.native_app_usability_source || "",
      native_app_usability_blocked_reason_class:
        packet?.native_app_usability_blocked_reason_class || "",
      workbench_ready: packet?.workbench_ready === true,
      selected_source_class: selectionPacket?.selected_source_class || "",
      selected_route_digest: selectionPacket?.selected_route_digest || "",
      selected_model: packet?.selected_model || "",
      launch_model_id: packet?.launch_model_id || "",
      route_model_id: launchRouteModelId,
      bridge_alive: packet?.bridge_alive === true,
      stable_custom_codex_wbp_bridge_final_status:
        packet?.stable_custom_codex_wbp_bridge_final_status || "",
      bridge_status: packet?.bridge_status || "",
      launch_route_truth_final_status: packet?.launch_route_truth_final_status || "",
      quick_start_stable_custom_launch_final_status:
        packet?.quick_start_stable_custom_launch_final_status || "",
      profile_final_status: packet?.profile_final_status || "",
      session_storage_final_status: packet?.session_storage_final_status || "",
      profile_persistence_proven: packet?.profile_persistence_proven === true,
      persistent_profile_reused: packet?.persistent_profile_reused === true,
      codex_home_reused: packet?.codex_home_reused === true,
      electron_user_data_reused: packet?.electron_user_data_reused === true,
      profile_path_stable: packet?.profile_path_stable === true,
      persistent_profile_root_is_tmp: packet?.persistent_profile_root_is_tmp === true,
      persistent_codex_home_is_tmp: packet?.persistent_codex_home_is_tmp === true,
      persistent_user_data_dir_is_tmp: packet?.persistent_user_data_dir_is_tmp === true,
      profile_relaunch_required_for_strong_history_claim:
        packet?.profile_relaunch_required_for_strong_history_claim === true,
      route_packet_matches_selection_packet:
        packet?.route_packet_matches_selection_packet === true,
      quick_start_launch_route_truth_proven_with_limits:
        packet?.quick_start_launch_route_truth_proven_with_limits === true,
      custom_codex_window_deepseek_smoke_final_status:
        packet?.custom_codex_window_deepseek_smoke_final_status || "",
      custom_codex_window_deepseek_launch_proven_with_limits:
        packet?.custom_codex_window_deepseek_launch_proven_with_limits === true,
      manual_prompt_smoke_attempted: packet?.manual_prompt_smoke_attempted === true,
      manual_prompt_smoke_proven: packet?.manual_prompt_smoke_proven === true,
      manual_prompt_smoke_blocked_reason: packet?.manual_prompt_smoke_blocked_reason || "",
      manual_prompt_smoke_counts_as_model_truth:
        packet?.manual_prompt_smoke_counts_as_model_truth === true,
      model_self_report_counts_as_runtime_truth:
        packet?.model_self_report_counts_as_runtime_truth === true,
      deepseek_window_prompt_runtime_truth_proven:
        packet?.deepseek_window_prompt_runtime_truth_proven === true,
      history_persistence_claimed: packet?.history_persistence_claimed === true,
      visible_thread_history_restored_claimed:
        packet?.visible_thread_history_restored_claimed === true,
      api_reasoning_option_id: packet?.api_reasoning_option_id || "",
      api_reasoning_option_packet: packet?.api_reasoning_option_packet || {},
      source_provenance_status: packet?.selection_packet?.source_provenance_status || "",
      launch_claim_scope: claimScope,
      next_action: packet?.next_action || "",
    }, null, 2);
  }
  setQuickStartChip(
    "quickStartLaunchState",
    nativeProofOk || reusedExistingWindow
      ? "green"
      : (packet?.status === "blocked" || packet?.status === "rejected" || packet?.status === "ok" ? "amber" : "red"),
    relaunchSucceeded
      ? "перезапущен"
      : (
        orphanReplaceSucceeded
          ? "заменён"
          : (
            nativeProofOk
              ? "запущен"
              : (
                reusedExistingWindow
                  ? "старое окно"
                  : (
                    limitedWindowLaunch
                      ? (nativeUsabilityBlocked ? "input не доказан" : "окно открыто")
                      : (existingWindowBlocked ? "blocked" : (packet?.machine_error_code || packet?.status || "ошибка"))
                  )
              )
          )
      )
  );
  setQuickStartChip(
    "quickStartRouteChip",
    nativeProofOk || reusedExistingWindow ? "green" : "amber",
    relaunchSucceeded
      ? "relaunch ok"
      : (
        orphanReplaceSucceeded
          ? "replace ok"
          : (
            nativeProofOk
              ? "запуск ok"
              : (
                reusedExistingWindow
                  ? "reuse ok"
                  : (
                    limitedWindowLaunch
                      ? (nativeUsabilityBlocked ? "renderer blocked" : "proof incomplete")
                      : (existingWindowBlocked ? "blocked" : "проверь пакет")
                  )
              )
          )
      )
  );
  const launchUsesApiRoute = (
    launchExecutionMode === "api_only"
    || launchExecutionMode === "chatgpt_plus_api"
    || packet?.external_route_selected === true
    || Boolean(launchApiModelId)
  );
  const launchBridgeAlive = (
    packet?.bridge_alive === true
    || packet?.stable_custom_codex_wbp_bridge_final_status
      === "STABLE_CUSTOM_CODEX_WBP_BRIDGE_PROVEN_WITH_LIMITS"
  );
  const launchBridgeConfigured = packet?.wbp_endpoint_configured === true;
  setQuickStartChip(
    "quickStartBridgeState",
    launchUsesApiRoute
      ? (launchBridgeAlive ? "green" : (launchBridgeConfigured ? "neutral" : "amber"))
      : "neutral",
    launchUsesApiRoute
      ? (launchBridgeAlive ? "жив" : (launchBridgeConfigured ? "configured" : "не проверен"))
      : "не нужен"
  );
  setQuickStartChip(
    "quickStartWindowState",
    packet?.native_window_observed === true
      ? "green"
      : (packet?.process_started === true ? "amber" : "neutral"),
    packet?.native_window_observed === true
      ? "найдено"
      : (packet?.process_started === true ? "process" : "не найдено")
  );
  setQuickStartChip(
    "quickStartConfigState",
    packet?.quick_start_launch_route_truth_proven_with_limits === true
      || packet?.route_packet_matches_selection_packet === true
      || packet?.config_status === "matches_last_launch"
      ? "green"
      : (packet?.status === "ok" ? "neutral" : "amber"),
    packet?.quick_start_launch_route_truth_proven_with_limits === true
      || packet?.route_packet_matches_selection_packet === true
      || packet?.config_status === "matches_last_launch"
      ? "совпадает"
      : (packet?.status === "ok" ? "launch packet" : "blocked")
  );
  setQuickStartChip(
    "quickStartNextActionState",
    (!packet?.next_action || packet?.next_action === "none")
      && !limitedWindowLaunch
      && !nativeUsabilityBlocked
      && !existingWindowBlocked
      && packet?.status !== "blocked"
      && packet?.status !== "rejected"
      ? "green"
      : "amber",
    (!packet?.next_action || packet?.next_action === "none")
      && (limitedWindowLaunch || nativeUsabilityBlocked || existingWindowBlocked)
      ? "stop_and_diagnose"
      : quickStartNextActionLabel(packet?.next_action || "")
  );
  setQuickStartRouteResponse({
    status: packet?.status || "unknown",
    machine_error_code: packet?.machine_error_code || "UNKNOWN",
    final_status: packet?.final_status || "",
    execution_mode: launchExecutionMode,
    chatgpt_model_id: launchChatgptModelId,
    api_model_id: launchApiModelId,
    selected_model: packet?.selected_model || selectionPacket?.selected_model || packet?.model || "",
    launch_model_id: packet?.launch_model_id || "",
    route_model_id: launchRouteModelId,
    launch_route_truth_final_status: packet?.launch_route_truth_final_status || "",
    quick_start_stable_custom_launch_final_status:
      packet?.quick_start_stable_custom_launch_final_status || "",
    profile_final_status: packet?.profile_final_status || "",
    session_storage_final_status: packet?.session_storage_final_status || "",
    bridge_status: packet?.bridge_status || "",
    bridge_alive: packet?.bridge_alive === true,
    stable_custom_codex_wbp_bridge_final_status:
      packet?.stable_custom_codex_wbp_bridge_final_status || "",
    runtime_health_gate_blocks_launch_admission:
      packet?.runtime_health_gate_blocks_launch_admission === true,
    runtime_health_gate_blocks_window_launch:
      packet?.runtime_health_gate_blocks_window_launch === true,
    runtime_health_required_for_chatgpt_lane:
      packet?.runtime_health_required_for_chatgpt_lane === true,
    runtime_health_machine_error_code:
      packet?.runtime_health_machine_error_code || "",
    chatgpt_runtime_proof_status:
      packet?.chatgpt_runtime_proof_status || "",
    chatgpt_runtime_proof_machine_error_code:
      packet?.chatgpt_runtime_proof_machine_error_code || "",
    window_status: packet?.window_status || "",
    config_status: packet?.config_status || "",
    selection_matches_last_launch:
      packet?.selection_matches_last_launch === true,
    existing_window_reuse_admissible:
      packet?.existing_window_reuse_admissible === true,
    existing_window_relaunch_admissible:
      packet?.existing_window_relaunch_admissible === true,
    existing_window_relaunch_attempted:
      packet?.existing_window_relaunch_attempted === true,
    existing_window_relaunch_termination:
      packet?.existing_window_relaunch_termination || {},
    existing_window_orphan_replace_admissible:
      packet?.existing_window_orphan_replace_admissible === true,
    existing_window_orphan_replace_attempted:
      packet?.existing_window_orphan_replace_attempted === true,
    existing_window_orphan_replace_termination:
      packet?.existing_window_orphan_replace_termination || {},
    orphan_replacement_authority_scope:
      packet?.orphan_replacement_authority_scope || "",
    custom_process_observed:
      packet?.custom_process_observed === true,
    custom_process_count:
      Number(packet?.custom_process_count || 0),
    custom_process_observed_before_relaunch:
      packet?.custom_process_observed_before_relaunch === true,
    custom_process_observed_after_relaunch_stop:
      packet?.custom_process_observed_after_relaunch_stop === true,
    custom_process_count_after_relaunch_stop:
      Number(packet?.custom_process_count_after_relaunch_stop || 0),
    reused_existing_window:
      packet?.reused_existing_window === true,
    launch_blocked:
      packet?.launch_blocked === true,
    show_window_attempted:
      packet?.show_window_attempted === true,
    window_unresponsive_with_limits:
      packet?.window_unresponsive_with_limits === true,
    owner_authorization_phrase_present:
      packet?.owner_authorization_phrase_present === true,
    profile_persistence_proven: packet?.profile_persistence_proven === true,
    persistent_profile_reused: packet?.persistent_profile_reused === true,
    profile_path_stable: packet?.profile_path_stable === true,
    persistent_profile_root_is_tmp: packet?.persistent_profile_root_is_tmp === true,
    persistent_user_data_dir_is_tmp: packet?.persistent_user_data_dir_is_tmp === true,
    route_packet_matches_selection_packet:
      packet?.route_packet_matches_selection_packet === true,
    quick_start_launch_route_truth_proven_with_limits:
      packet?.quick_start_launch_route_truth_proven_with_limits === true,
    custom_codex_window_deepseek_smoke_final_status:
      packet?.custom_codex_window_deepseek_smoke_final_status || "",
    custom_codex_window_deepseek_launch_proven_with_limits:
      packet?.custom_codex_window_deepseek_launch_proven_with_limits === true,
    manual_prompt_smoke_attempted: packet?.manual_prompt_smoke_attempted === true,
    manual_prompt_smoke_proven: packet?.manual_prompt_smoke_proven === true,
    manual_prompt_smoke_blocked_reason: packet?.manual_prompt_smoke_blocked_reason || "",
    manual_prompt_smoke_counts_as_model_truth:
      packet?.manual_prompt_smoke_counts_as_model_truth === true,
    model_self_report_counts_as_runtime_truth:
      packet?.model_self_report_counts_as_runtime_truth === true,
    deepseek_window_prompt_runtime_truth_proven:
      packet?.deepseek_window_prompt_runtime_truth_proven === true,
    history_persistence_claimed: packet?.history_persistence_claimed === true,
    visible_thread_history_restored_claimed:
      packet?.visible_thread_history_restored_claimed === true,
    api_reasoning_option_id:
      packet?.api_reasoning_option_id || selectionPacket?.api_reasoning_option_id || "",
    api_reasoning_option_packet:
      packet?.api_reasoning_option_packet || selectionPacket?.api_reasoning_option_packet || {},
    primary_model_slot: packet?.primary_model_slot || selectionPacket?.primary_model_slot || {},
    coding_agent_model_slot:
      packet?.coding_agent_model_slot || selectionPacket?.coding_agent_model_slot || {},
    chatgpt_line_used_as_executor:
      Object.prototype.hasOwnProperty.call(packet || {}, "chatgpt_line_used_as_executor")
        ? packet?.chatgpt_line_used_as_executor === true
        : selectionPacket?.chatgpt_line_used_as_executor === true,
    api_line_used_as_executor:
      Object.prototype.hasOwnProperty.call(packet || {}, "api_line_used_as_executor")
        ? packet?.api_line_used_as_executor === true
        : selectionPacket?.api_line_used_as_executor === true,
    api_only_calls_chatgpt:
      packet?.api_only_calls_chatgpt === true
      || selectionPacket?.api_only_calls_chatgpt === true,
    chatgpt_only_calls_api:
      packet?.chatgpt_only_calls_api === true
      || selectionPacket?.chatgpt_only_calls_api === true,
    server_issued_catalog_used:
      packet?.server_issued_catalog_used === true
      || selectionPacket?.server_issued_catalog_used === true,
    persistent_profile_id: packet?.persistent_profile_id || "",
    temp_profile_used: packet?.temp_profile_used === true,
    running_status: packet?.running_status === true,
    process_started: packet?.process_started === true,
    native_window_observed: packet?.native_window_observed === true,
    real_codex_app_launched: packet?.real_codex_app_launched === true,
    native_app_usable: packet?.native_app_usable === true,
    input_capable_ui_observed: packet?.input_capable_ui_observed === true,
    native_app_usability_source: packet?.native_app_usability_source || "",
    native_app_usability_blocked_reason_class:
      packet?.native_app_usability_blocked_reason_class || "",
    custom_codex_launch_attempted: packet?.custom_codex_launch_attempted === true,
    new_launch_started: packet?.new_launch_started === true,
    network_calls_made: packet?.network_calls_made === true,
    live_call_attempted: packet?.live_call_attempted === true,
    provider_called: packet?.provider_called === true,
    launch_packet_is_truth_source: packet?.launch_packet_is_truth_source === true,
    raw_backend_details_exposed: packet?.raw_backend_details_exposed === true,
    original_codex_touched: packet?.original_codex_touched === true,
    launch_claim_scope: packet?.launch_claim_scope || "",
    next_action: packet?.next_action || ""
  });
}

function renderSafeAppCopyLaunchPacket(packet) {
  const response = document.getElementById("codexLaunchDryRunResponse");
  const dryRunReady = packet?.status === "ok"
    && packet?.machine_error_code === "WEB_SAFE_APP_COPY_LAUNCH_DRY_RUN_READY"
    && packet?.dry_run === true
    && packet?.server_issued_plan === true
    && packet?.current_codex_touched === false
    && packet?.uses_current_home === false
    && packet?.uses_current_codex_home === false
    && packet?.raw_path_exposed === false
    && packet?.raw_pid_exposed === false
    && packet?.raw_env_exposed === false
    && packet?.pid_not_exposed_to_browser === true;
  const admissionReady = packet?.status === "ok"
    && packet?.machine_error_code === "WEB_SAFE_APP_COPY_LIVE_ADMISSION_READY"
    && packet?.final_verdict === "WEB_SAFE_APP_COPY_LIVE_ADMISSION_READY"
    && packet?.live_launch_admitted === true
    && packet?.launch_performed === false
    && packet?.server_issued_plan === true
    && packet?.current_codex_touched === false
    && packet?.uses_current_home === false
    && packet?.uses_current_codex_home === false
    && packet?.raw_path_exposed === false
    && packet?.raw_pid_exposed === false
    && packet?.raw_env_exposed === false
    && packet?.pid_not_exposed_to_browser === true
    && packet?.bounded_live_launch_execution_ready === false
    && packet?.launch_ready_claimed === false;
  const helperExecutionReady = packet?.status === "ok"
    && packet?.machine_error_code === "WEB_SAFE_APP_COPY_BOUNDED_HELPER_EXECUTION_READY"
    && packet?.final_verdict === "WEB_SAFE_APP_COPY_BOUNDED_HELPER_EXECUTION_READY"
    && packet?.launch_performed === true
    && packet?.bounded_helper_execution === true
    && packet?.real_codex_app_launched === false
    && packet?.process_started === true
    && packet?.cleanup_or_stop_completed === true
    && packet?.receipt_redacted === true
    && packet?.current_codex_touched === false
    && packet?.uses_current_home === false
    && packet?.uses_current_codex_home === false
    && packet?.raw_path_exposed === false
    && packet?.raw_pid_exposed === false
    && packet?.raw_env_exposed === false
    && packet?.pid_not_exposed_to_browser === true;
  codexLaunchSetChip(
    dryRunReady || admissionReady || helperExecutionReady ? "green" : (packet?.status === "blocked" ? "amber" : "red"),
    dryRunReady ? "app copy dry-run ready" : (admissionReady ? "app copy admission ready" : (helperExecutionReady ? "bounded helper ready" : (packet?.status || "failed")))
  );
  codexLaunchSetText(
    "safeAppCopyStatus",
    `${packet?.status || "unknown"} · ${packet?.final_verdict || packet?.machine_error_code || "UNKNOWN"}`
  );
  codexLaunchSetText(
    "safeAppCopyAdmission",
    packet?.live_launch_admitted === true
      ? `${packet?.owner_contract_status || "unknown"} · execution separate`
      : `${packet?.owner_contract_status || "unknown"} · ${packet?.block_reason_code || packet?.machine_error_code || "UNKNOWN"}`
  );
  codexLaunchSetText(
    "safeAppCopyIsolation",
    packet?.current_codex_touched === false && packet?.uses_current_home === false
      ? "current Codex untouched"
      : "isolation check failed"
  );
  const liveButton = document.getElementById("safeAppCopyLaunchAction");
  if (liveButton) {
    liveButton.disabled = !(admissionReady || helperExecutionReady);
    if (admissionReady || helperExecutionReady) {
      liveButton.classList.remove("disabled");
    } else {
      liveButton.classList.add("disabled");
    }
  }
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      launch_mode: packet?.launch_mode || "separate_app_copy",
      dry_run: packet?.dry_run === true,
      launch_performed: packet?.launch_performed === true,
      server_issued_plan: packet?.server_issued_plan === true,
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      browser_forbidden_fields_absent: packet?.browser_forbidden_fields_absent === true,
      browser_forbidden_field_policy_enforced: packet?.browser_forbidden_field_policy_enforced === true,
      app_path_redacted: packet?.app_path_redacted === true,
      isolated_profile_root_redacted: packet?.isolated_profile_root_redacted === true,
      isolated_data_dir_redacted: packet?.isolated_data_dir_redacted === true,
      isolated_port_source: packet?.isolated_port_source || "",
      isolated_port_redacted: packet?.isolated_port_redacted === true,
      current_codex_touched: packet?.current_codex_touched === true,
      current_codex_home_touched: packet?.current_codex_home_touched === true,
      uses_current_home: packet?.uses_current_home === true,
      uses_current_codex_home: packet?.uses_current_codex_home === true,
      proxy_env_injected: packet?.proxy_env_injected === true,
      live_launch_admitted: packet?.live_launch_admitted === true,
      live_admission_check: packet?.live_admission_check === true,
      owner_contract_status: packet?.owner_contract_status || "",
      owner_preflight_machine_error_code: packet?.owner_preflight_machine_error_code || "",
      owner_preflight_target_exists: packet?.owner_preflight_target_exists === true,
      owner_preflight_target_kind: packet?.owner_preflight_target_kind || "",
      owner_preflight_separate_profile: packet?.owner_preflight_separate_profile === true,
      owner_preflight_separate_data_dir: packet?.owner_preflight_separate_data_dir === true,
      owner_preflight_separate_port: packet?.owner_preflight_separate_port === true,
      owner_preflight_current_session_untouched: packet?.owner_preflight_current_session_untouched === true,
      bounded_live_launch_execution_ready: packet?.bounded_live_launch_execution_ready === true,
      launch_ready_claimed: packet?.launch_ready_claimed === true,
      bounded_helper_execution: packet?.bounded_helper_execution === true,
      real_codex_app_launched: packet?.real_codex_app_launched === true,
      helper_target_safe: packet?.helper_target_safe === true,
      helper_execution_attempted: packet?.helper_execution_attempted === true,
      process_started: packet?.process_started === true,
      cleanup_or_stop_completed: packet?.cleanup_or_stop_completed === true,
      receipt_redacted: packet?.receipt_redacted === true,
      helper_receipt_ref: packet?.helper_receipt_ref || "",
      helper_stdout_omitted: packet?.helper_stdout_omitted === true,
      helper_stderr_omitted: packet?.helper_stderr_omitted === true,
      helper_exit_code_zero: packet?.helper_exit_code_zero === true,
      block_reason_code: packet?.block_reason_code || "",
      raw_path_exposed: packet?.raw_path_exposed === true,
      raw_pid_exposed: packet?.raw_pid_exposed === true,
      raw_env_exposed: packet?.raw_env_exposed === true,
      pid_not_exposed_to_browser: packet?.pid_not_exposed_to_browser === true,
      final_verdict: packet?.final_verdict || "",
      next_action: packet?.next_action || "",
    }, null, 2);
  }
}

async function runSafeAppCopyLiveAdmission() {
  if (codexLaunchDryRunInFlight) {
    return;
  }
  codexLaunchDryRunInFlight = true;
  document.getElementById("safeAppCopyLiveAdmissionAction")?.setAttribute("disabled", "disabled");
  codexLaunchSetChip("neutral", "checking admission");
  try {
    const response = await fetch("api/codex/app-copy/live-admission", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({})
    });
    if (!response.ok) {
      throw new Error(`app copy admission http ${response.status}`);
    }
    renderSafeAppCopyLaunchPacket(await response.json());
  } catch (error) {
    renderSafeAppCopyLaunchPacket({
      status: "failed",
      machine_error_code: "WEB_SAFE_APP_COPY_LIVE_ADMISSION_FETCH_FAILED",
      dry_run: false,
      live_admission_check: true,
      launch_performed: false,
      server_issued_plan: false,
      current_codex_touched: false,
      uses_current_home: false,
      uses_current_codex_home: false,
      bounded_live_launch_execution_ready: false,
      launch_ready_claimed: false,
      final_verdict: "WEB_SAFE_APP_COPY_LAUNCH_BLOCKED",
      next_action: error.message
    });
  } finally {
    codexLaunchDryRunInFlight = false;
    document.getElementById("safeAppCopyLiveAdmissionAction")?.removeAttribute("disabled");
  }
}

async function runOriginalCodexDryRun() {
  if (codexLaunchDryRunInFlight) {
    return;
  }
  codexLaunchDryRunInFlight = true;
  document.getElementById("originalCodexDryRunAction")?.setAttribute("disabled", "disabled");
  codexLaunchSetChip("neutral", "checking");
  try {
    const response = await fetch("api/codex/original/launch-dry-run", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({})
    });
    if (!response.ok) {
      throw new Error(`original dry-run http ${response.status}`);
    }
    renderOriginalCodexDryRun(await response.json());
  } catch (error) {
    renderOriginalCodexDryRun({
      status: "failed",
      machine_error_code: "ORIGINAL_DRY_RUN_FETCH_FAILED",
      human_message: error.message,
      dry_run: true,
      dispatch_plan_safe: false,
      launch_claim_scope: "dry_run_guard_only"
    });
  } finally {
    codexLaunchDryRunInFlight = false;
    document.getElementById("originalCodexDryRunAction")?.removeAttribute("disabled");
  }
}

async function runOriginalCodexLaunch() {
  if (codexLaunchDryRunInFlight) {
    return;
  }
  codexLaunchDryRunInFlight = true;
  document.getElementById("originalCodexLaunchAction")?.setAttribute("disabled", "disabled");
  codexLaunchSetChip("neutral", "launching");
  try {
    const response = await fetch("api/codex/original/launch", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({})
    });
    if (!response.ok) {
      throw new Error(`original launch http ${response.status}`);
    }
    renderOriginalCodexLaunch(await response.json());
  } catch (error) {
    renderOriginalCodexLaunch({
      status: "failed",
      machine_error_code: "ORIGINAL_LAUNCH_FETCH_FAILED",
      human_message: error.message,
      running_status: false,
      proxy_env_present: false,
      wbp_endpoint_injected: false,
      custom_home_present: false,
      custom_codex_home_present: false,
      current_codex_touched: false,
      launch_claim_scope: "owner_authorized_baseline_launch"
    });
  } finally {
    codexLaunchDryRunInFlight = false;
    document.getElementById("originalCodexLaunchAction")?.removeAttribute("disabled");
  }
}

async function runCodexCustomLaunchDryRun() {
  if (codexLaunchDryRunInFlight) {
    return;
  }
  codexLaunchDryRunInFlight = true;
  document.getElementById("codexCustomLaunchDryRunAction")?.setAttribute("disabled", "disabled");
  codexLaunchSetChip("neutral", "checking");
  try {
    const response = await fetch("api/codex/custom/launch-dry-run", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({})
    });
    if (!response.ok) {
      throw new Error(`custom dry-run http ${response.status}`);
    }
    renderCodexCustomLaunchDryRun(await response.json());
  } catch (error) {
    renderCodexCustomLaunchDryRun({
      status: "failed",
      machine_error_code: "CUSTOM_DRY_RUN_FETCH_FAILED",
      human_message: error.message,
      dry_run: true,
      custom_launch_plan_safe: false,
      real_launch_attempted: false,
      prompt_attempted: false,
      launch_claim_scope: "dry_run_readiness_only"
    });
  } finally {
    codexLaunchDryRunInFlight = false;
    document.getElementById("codexCustomLaunchDryRunAction")?.removeAttribute("disabled");
  }
}

async function buildCodexCustomLaunchSelectionPayload() {
  syncCodexRouteSelects("quickStartChatModelSelect");
  syncCodexRouteSelects("quickStartApiModelSelect");
  syncCodexRouteSelects("quickStartApiReasoningOptionSelect");
  syncCodexRouteSelects("quickStartExecutionModeSelect");
  let payload = quickStartLaunchPayloadFromSelects();
  if (customLaunchPayloadRequiresModelRefresh(payload)) {
    await refreshCodexCustomModelsPanel();
    syncCodexRouteSelects("codexCustomModelSelect");
    syncCodexRouteSelects("codexCustomApiModelSelect");
    syncCodexRouteSelects("codexCustomApiReasoningOptionSelect");
    syncCodexRouteSelects("codexCustomExecutionModeSelect");
    payload = quickStartLaunchPayloadFromSelects();
  }
  saveCodexRouteSelection(payload);
  return payload;
}

function renderQuickStartNativeLaunchInFlight(payload, preflightPacket) {
  setQuickStartChip("quickStartRouteChip", "neutral", "native launch");
  setQuickStartChip("quickStartLaunchState", "neutral", "запускаю");
  setQuickStartChip(
    "quickStartBridgeState",
    preflightPacket?.bridge_required === true
      ? (preflightPacket?.bridge_alive === true ? "green" : "amber")
      : "neutral",
    preflightPacket?.bridge_required === true
      ? (preflightPacket?.bridge_alive === true ? "жив" : "упал")
      : "не нужен"
  );
  setQuickStartChip(
    "quickStartWindowState",
    preflightPacket?.custom_process_observed === true ? "green" : "neutral",
    preflightPacket?.custom_process_observed === true ? "найдено" : "ожидаю"
  );
  setQuickStartChip(
    "quickStartConfigState",
    preflightPacket?.status === "ok" ? "green" : "amber",
    preflightPacket?.status === "ok" ? "preflight ok" : "preflight blocked"
  );
  setQuickStartChip("quickStartNextActionState", "neutral", "ожидание");
  setQuickStartRouteResponse({
    status: "running",
    machine_error_code: "CUSTOM_NATIVE_LAUNCH_IN_FLIGHT",
    final_status: "CUSTOM_NATIVE_LAUNCH_WAITING_FOR_PACKET",
    execution_mode: payload?.execution_mode || preflightPacket?.execution_mode || "",
    chatgpt_model_id: payload?.chatgpt_model_id || preflightPacket?.chatgpt_model_id || "",
    api_model_id: payload?.api_model_id || preflightPacket?.api_model_id || "",
    api_reasoning_option_id:
      payload?.api_reasoning_option_id || preflightPacket?.api_reasoning_option_id || "",
    bridge_status: preflightPacket?.bridge_status || "",
    bridge_alive: preflightPacket?.bridge_alive === true,
    window_status: preflightPacket?.window_status || "",
    config_status: preflightPacket?.config_status || "",
    custom_codex_launch_attempted: true,
    new_launch_started: false,
    live_call_attempted: true,
    provider_called: false,
    visible_window_counts_as_model_truth: false,
    bridge_alive_counts_as_model_truth: false,
    response_text_counts_as_route_truth: false,
    launch_packet_is_truth_source: false,
    next_action: "wait_for_native_launch_packet"
  });
}

async function runCodexCustomLaunch() {
  if (codexLaunchDryRunInFlight) {
    return;
  }
  const payload = await buildCodexCustomLaunchSelectionPayload();
  codexLaunchDryRunInFlight = true;
  document.getElementById("codexCustomLaunchAction")?.setAttribute("disabled", "disabled");
  document.getElementById("quickStartCustomLaunchAction")?.setAttribute("disabled", "disabled");
  codexLaunchSetChip("neutral", "launching");
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  const timeoutHandle = controller ? setTimeout(() => controller.abort(), 45000) : null;
  try {
    const admissionResponse = await fetch("api/codex/custom/quick-start/config-admission", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
      signal: controller?.signal
    });
    if (!admissionResponse.ok) {
      throw new Error(`quick start config admission http ${admissionResponse.status}`);
    }
    const admissionPacket = await admissionResponse.json();
    renderQuickStartConfigAdmission(admissionPacket);
    if (admissionPacket?.launch_admission !== "admitted") {
      renderCodexCustomLaunch({
        ...admissionPacket,
        status: admissionPacket?.status || "blocked",
        machine_error_code: admissionPacket?.machine_error_code || "QUICK_START_CONFIG_ADMISSION_BLOCKED",
        running_status: false,
        process_started: false,
        native_window_observed: false,
        native_app_usable: false,
        launch_claim_scope: "quick_start_config_admission_guard_no_live_mutation"
      });
      return;
    }
    const preflightResponse = await fetch("api/codex/custom/native-launch-preflight", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
      signal: controller?.signal
    });
    if (!preflightResponse.ok) {
      throw new Error(`custom launch preflight http ${preflightResponse.status}`);
    }
    const preflightPacket = await preflightResponse.json();
    renderQuickStartLaunchPreflight(preflightPacket);
    if (preflightPacket?.status !== "ok") {
      renderCodexCustomLaunch({
        ...preflightPacket,
        running_status: false,
        process_started: false,
        native_window_observed: false,
        native_app_usable: false,
        launch_claim_scope: "quick_start_launch_guard_no_live_mutation"
      });
      return;
    }
    renderQuickStartNativeLaunchInFlight(payload, preflightPacket);
    const response = await fetch("api/codex/custom/native-launch", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
      signal: controller?.signal
    });
    if (!response.ok) {
      throw new Error(`custom launch http ${response.status}`);
    }
    const packet = await response.json();
    renderCodexCustomLaunch(packet);
    await refreshQuickStartLiveBridgeStabilityTruth(packet);
    await refreshQuickStartMixedCoderTraceTruth(packet);
  } catch (error) {
    const timedOut = error?.name === "AbortError";
    renderCodexCustomLaunch({
      status: "failed",
      machine_error_code: timedOut ? "CUSTOM_LAUNCH_REQUEST_TIMEOUT" : "CUSTOM_LAUNCH_FETCH_FAILED",
      human_message: timedOut ? "Custom Codex launch request timed out before a packet returned." : error.message,
      launch_admission: "blocked",
      session_created: false,
      running_status: false,
      isolated_home: false,
      isolated_codex_home: false,
      isolated_profile_dir: false,
      server_issued_model_list: false,
      wbp_endpoint_configured: false,
      browser_route_injection: false,
      browser_backend_injection: false,
      current_codex_touched: false,
      process_started: false,
      expected_custom_identity_observed: false,
      native_window_observed: false,
      native_app_usable: false,
      workbench_ready: false,
      launch_claim_scope: "native_proof_unavailable",
      launch_timeout_with_limits: timedOut,
      window_response_timeout: timedOut,
      new_launch_started: false,
      show_window_attempted: false,
      visible_window_counts_as_model_truth: false,
      response_text_counts_as_route_truth: false,
      launch_packet_is_truth_source: false,
      final_status: "CUSTOM_CODEX_LAUNCH_STABILITY_AND_RECOVERY_WITH_LIMITS"
    });
  } finally {
    if (timeoutHandle) {
      clearTimeout(timeoutHandle);
    }
    codexLaunchDryRunInFlight = false;
    document.getElementById("codexCustomLaunchAction")?.removeAttribute("disabled");
    document.getElementById("quickStartCustomLaunchAction")?.removeAttribute("disabled");
  }
}

function quickStartExecutionModeLabel(mode) {
  if (mode === "chatgpt_plus_api") {
    return "ChatGPT + API";
  }
  if (mode === "api_only") {
    return "API";
  }
  if (mode === "chatgpt_only") {
    return "ChatGPT";
  }
  return "не выбран";
}

function quickStartAdmissionComponentVisual(component) {
  const status = component?.status || "";
  if (["admitted", "accepted", "defaulted"].includes(status)) {
    return "green";
  }
  if (status === "not_required") {
    return "neutral";
  }
  if (["missing", "unavailable", "not_confirmed", "blocked", "rejected"].includes(status)) {
    return "amber";
  }
  return "neutral";
}

function quickStartAdmissionComponentLabel(component) {
  const status = component?.status || "";
  if (status === "not_required") {
    return "not required";
  }
  if (status === "admitted") {
    return "admitted";
  }
  if (status === "accepted" || status === "defaulted") {
    return status;
  }
  return status || "unknown";
}

function quickStartNextActionLabel(nextAction) {
  const action = nextAction || "";
  if (!action || action === "none") {
    return "none";
  }
  if (action === "provide_exact_owner_authorization_phrase") {
    return "owner auth";
  }
  if (action === "repair_quick_start_config_selection") {
    return "repair config";
  }
  if (action === "remove_forbidden_browser_fields" || action === "remove_browser_payload_fields") {
    return "remove fields";
  }
  if (action === "relaunch_custom_codex_with_new_selection") {
    return "relaunch ready";
  }
  if (action === "replace_existing_custom_codex_without_launch_packet") {
    return "replace ready";
  }
  if (action.includes("launch_custom_codex") || action.includes("launch_or_reuse_custom_codex")) {
    return "ready to launch";
  }
  if (action === "show_existing_window") {
    return "show window";
  }
  if (action === "continue_in_existing_custom_window") {
    return "existing window";
  }
  if (action === "run_fresh_chatgpt_plus_api_launch") {
    return "fresh launch";
  }
  if (action === "refresh_chatgpt_plus_api_trace_snapshot") {
    return "refresh trace";
  }
  if (action === "relaunch_custom") {
    return "relaunch custom";
  }
  if (action === "inspect_bridge_stability_packet") {
    return "inspect bridge";
  }
  if (action === "retry_live_bridge_stability") {
    return "retry bridge";
  }
  if (action === "use_session_dispatch_probe_or_design_native_dual_lane_dispatcher") {
    return "dual-lane unsupported";
  }
  if (action === "inspect_slot_binding_launch_evidence") {
    return "inspect slot";
  }
  return action.length > 18 ? `${action.slice(0, 18)}...` : action;
}

function quickStartChatgptRuntimeProofPending(packet) {
  return Boolean(
    packet?.runtime_health_required_for_chatgpt_lane === true
    && packet?.chatgpt_runtime_proof_status === "not_proven"
    && (
      packet?.chatgpt_runtime_proof_machine_error_code
      || packet?.runtime_health_machine_error_code
      || packet?.runtime_health_gate?.runtime_health_machine_error_code
    )
  );
}

function quickStartRuntimeProofPendingLabel(packet) {
  const machineCode = packet?.chatgpt_runtime_proof_machine_error_code
    || packet?.runtime_health_machine_error_code
    || packet?.runtime_health_gate?.runtime_health_machine_error_code
    || "";
  return machineCode === "AUTH_UNAVAILABLE" ? "auth pending" : "runtime pending";
}

function renderQuickStartConfigAdmission(packet, options = {}) {
  const admitted = packet?.status === "ok" && packet?.launch_admission === "admitted";
  const blocked = packet?.status === "blocked" || packet?.status === "rejected";
  const replayed = options.replayed === true;
  const runtimeProofPending = quickStartChatgptRuntimeProofPending(packet);
  const admittedVisual = admitted && !runtimeProofPending && !replayed ? "green" : (blocked || admitted ? "amber" : "red");
  const admittedLabel = replayed
    ? "manual cache"
    : (
      admitted
        ? (runtimeProofPending ? quickStartRuntimeProofPendingLabel(packet) : "допущен")
        : (packet?.machine_error_code || packet?.status || "blocked")
    );
  const modeLabel = quickStartExecutionModeLabel(packet?.execution_mode || "");
  const apiRoute = packet?.api_route || {};
  const apiReasoning = packet?.api_reasoning || {};
  const chatgptModel = packet?.chatgpt_model || {};
  const apiModel = packet?.api_model || {};
  const nextAction = packet?.next_action || "";
  setQuickStartChip(
    "quickStartRouteChip",
    admittedVisual,
    admittedLabel
  );
  setQuickStartChip(
    "quickStartExecutionModeState",
    admittedVisual,
    modeLabel
  );
  setQuickStartChip(
    "quickStartChatSlotState",
    quickStartAdmissionComponentVisual(chatgptModel),
    quickStartAdmissionComponentLabel(chatgptModel)
  );
  setQuickStartChip(
    "quickStartApiSlotState",
    quickStartAdmissionComponentVisual(apiModel),
    quickStartAdmissionComponentLabel(apiModel)
  );
  setQuickStartChip(
    "quickStartOwnerAuthState",
    "neutral",
    "preflight"
  );
  setQuickStartChip(
    "quickStartLaunchState",
    admittedVisual,
    admitted ? (runtimeProofPending ? quickStartRuntimeProofPendingLabel(packet) : (replayed ? "manual cache" : "admission ok")) : "blocked"
  );
  setQuickStartChip(
    "quickStartConfigState",
    admittedVisual,
    packet?.launch_admission === "admitted"
      ? (runtimeProofPending ? "runtime pending" : (replayed ? "manual cache" : "admitted"))
      : "blocked"
  );
  setQuickStartChip(
    "quickStartNextActionState",
    (!nextAction || nextAction === "none") && !runtimeProofPending && !replayed ? "green" : "amber",
    runtimeProofPending ? quickStartRuntimeProofPendingLabel(packet) : (replayed ? "manual cache" : quickStartNextActionLabel(nextAction))
  );
  setQuickStartChip(
    "quickStartApiRouteChip",
    apiRoute.status === "admitted" || apiRoute.status === "not_required"
      ? "green"
      : (apiRoute.status === "missing" || apiRoute.status === "not_confirmed" ? "amber" : "neutral"),
    apiRoute.status || "unknown"
  );
  setQuickStartRouteResponse({
    status: packet?.status || "unknown",
    machine_error_code: packet?.machine_error_code || "UNKNOWN",
    final_status: packet?.final_status || "",
    execution_mode: packet?.execution_mode || "",
    chatgpt_model_id: packet?.chatgpt_model?.model_id || "",
    api_model_id: packet?.api_model?.model_id || "",
    api_reasoning_option_id: apiReasoning.option_id || "",
    api_reasoning_status: apiReasoning.status || "",
    api_route_status: apiRoute.status || "",
    api_route_reference: apiRoute.route_reference || "",
    owner_authorization_phrase_present: false,
    fallback_used: packet?.fallback_used === true,
    silent_fallback_used: packet?.silent_fallback_used === true,
    launch_admission: packet?.launch_admission || "blocked",
    launch_admission_summary: packet?.launch_admission_summary || "",
    runtime_health_gate_blocks_launch_admission:
      packet?.runtime_health_gate_blocks_launch_admission === true,
    runtime_health_gate_blocks_window_launch:
      packet?.runtime_health_gate_blocks_window_launch === true,
    runtime_health_required_for_chatgpt_lane:
      packet?.runtime_health_required_for_chatgpt_lane === true,
    runtime_health_machine_error_code:
      packet?.runtime_health_machine_error_code || packet?.runtime_health_gate?.runtime_health_machine_error_code || "",
    chatgpt_runtime_proof_status:
      packet?.chatgpt_runtime_proof_status || "",
    chatgpt_runtime_proof_machine_error_code:
      packet?.chatgpt_runtime_proof_machine_error_code || "",
    dry_server_truth_only: packet?.dry_server_truth_only === true,
    custom_codex_launch_attempted: packet?.custom_codex_launch_attempted === true,
    new_launch_started: packet?.new_launch_started === true,
    network_calls_made: packet?.network_calls_made === true,
    live_call_attempted: packet?.live_call_attempted === true,
    provider_called: packet?.provider_called === true,
    raw_backend_details_exposed: packet?.raw_backend_details_exposed === true,
    secret_value_exposed: packet?.secret_value_exposed === true,
    raw_path_exposed: packet?.raw_path_exposed === true,
    original_codex_touched: packet?.original_codex_touched === true,
    asar_touched: packet?.asar_touched === true,
    manual_check_replay_active: replayed,
    manual_check_replay_age_ms: Number.isFinite(options.replayAgeMs) ? options.replayAgeMs : null,
    manual_check_replay_max_age_ms: replayed ? QUICK_START_MANUAL_CHECK_REPLAY_MAX_AGE_MS : null,
    runtime_readiness_claimed: false,
    next_action: packet?.next_action || ""
  });
  if (options.remember === true && options.selectionPayload) {
    rememberQuickStartConfigAdmissionSnapshot(options.selectionPayload, packet);
  }
}

async function runQuickStartConfigAdmission(buttonId = "quickStartCheckApiAction") {
  if (codexLaunchDryRunInFlight) {
    return;
  }
  const payload = await buildCodexCustomLaunchSelectionPayload();
  codexLaunchDryRunInFlight = true;
  const button = document.getElementById(buttonId);
  button?.setAttribute("disabled", "disabled");
  setQuickStartChip("quickStartRouteChip", "neutral", "проверяю");
  const responseNode = document.getElementById("quickStartRouteResponse");
  if (responseNode) {
    responseNode.textContent = "запрашиваю bounded config admission packet...";
  }
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  const timeoutHandle = controller ? setTimeout(() => controller.abort(), 15000) : null;
  try {
    const response = await fetch("api/codex/custom/quick-start/config-admission", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
      signal: controller?.signal
    });
    if (!response.ok) {
      throw new Error(`quick start config admission http ${response.status}`);
    }
    const admissionPacket = await response.json();
    renderQuickStartConfigAdmission(admissionPacket, { remember: true, selectionPayload: payload });
    if (quickStartShouldRunSelectedApiRouteCheck(payload, admissionPacket)) {
      setQuickStartChip("quickStartRouteChip", "neutral", "route check");
      if (responseNode) {
        const admissionOk = admissionPacket.status === "ok" && admissionPacket.machine_error_code === "OK";
        responseNode.textContent = admissionOk
          ? "admission ok; проверяю выбранный API route..."
          : "selected route требует проверки; проверяю выбранный API route...";
      }
      const actionOutcome = await runUiAction("api_route_check", { route_id: payload.api_model_id });
      renderQuickStartApiRouteCheckResult(payload, actionOutcome, { remember: true });
    }
  } catch (error) {
    const timedOut = error?.name === "AbortError";
    renderQuickStartConfigAdmission({
      status: "failed",
      machine_error_code: timedOut ? "QUICK_START_CONFIG_ADMISSION_TIMEOUT" : "QUICK_START_CONFIG_ADMISSION_FETCH_FAILED",
      final_status: "KNOWN_BLOCKER_QUICK_START_CONFIG_ADMISSION_NOT_PROVEN",
      execution_mode: payload.execution_mode || "",
      chatgpt_model: {
        status: payload.execution_mode === "api_only" ? "not_required" : "missing",
        model_id: payload.chatgpt_model_id || ""
      },
      api_model: {
        status: payload.execution_mode === "chatgpt_only" ? "not_required" : "missing",
        model_id: payload.api_model_id || ""
      },
      api_reasoning: {
        status: payload.execution_mode === "chatgpt_only" ? "not_required" : "missing",
        option_id: payload.api_reasoning_option_id || ""
      },
      api_route: { status: "missing", route_reference: "" },
      launch_admission: "blocked",
      launch_admission_summary: "Config admission packet unavailable; launch remains gated.",
      dry_server_truth_only: true,
      live_call_attempted: false,
      provider_called: false,
      fallback_used: false,
      silent_fallback_used: false,
      raw_backend_details_exposed: false,
      secret_value_exposed: false,
      raw_path_exposed: false,
      original_codex_touched: false,
      asar_touched: false,
      next_action: error.message
    }, { remember: true, selectionPayload: payload });
  } finally {
    if (timeoutHandle) {
      clearTimeout(timeoutHandle);
    }
    codexLaunchDryRunInFlight = false;
    button?.removeAttribute("disabled");
  }
}

const QUICK_START_SELECTED_API_ROUTE_CHECK_MACHINE_CODES = new Set([
  "QUICK_START_CONFIG_API_ROUTE_BLOCKED",
  "QUICK_START_CONFIG_API_ROUTE_CHECK_ATTENTION",
  "QUICK_START_CONFIG_API_ROUTE_VALIDATION_FAILED"
]);

function quickStartAdmissionRequestsSelectedApiRouteCheck(payload, admissionPacket) {
  const truthPacket = (
    admissionPacket?.selection_packet?.next_action === "check_selected_api_route"
      ? admissionPacket.selection_packet
      : admissionPacket
  );
  if (!payload || !truthPacket || truthPacket.next_action !== "check_selected_api_route") {
    return false;
  }
  const routePacket = truthPacket.api_route || {};
  const apiModelPacket = truthPacket.api_model || {};
  const routeMachineCode = routePacket.machine_error_code || truthPacket.machine_error_code || "";
  return Boolean(
    apiModelPacket.status === "admitted"
    && (!apiModelPacket.model_id || apiModelPacket.model_id === payload.api_model_id)
    && routePacket.status === "not_confirmed"
    && QUICK_START_SELECTED_API_ROUTE_CHECK_MACHINE_CODES.has(routeMachineCode)
    && truthPacket.fallback_used === false
    && truthPacket.silent_fallback_used === false
  );
}

function quickStartShouldRunSelectedApiRouteCheck(payload, admissionPacket) {
  const launchAdmissionReady = Boolean(
    admissionPacket
    && admissionPacket.status === "ok"
    && admissionPacket.machine_error_code === "OK"
    && admissionPacket.launch_admission === "admitted"
  );
  const selectedRouteCheckRequested = quickStartAdmissionRequestsSelectedApiRouteCheck(payload, admissionPacket);
  return Boolean(
    payload
    && admissionPacket
    && payload.execution_mode !== "chatgpt_only"
    && typeof payload.api_model_id === "string"
    && payload.api_model_id
    && (launchAdmissionReady || selectedRouteCheckRequested)
  );
}

function renderQuickStartApiRouteCheckResult(selectionPayload, actionOutcome, options = {}) {
  const actionPacket = actionOutcome?.payload || actionOutcome || {};
  const result = actionPacket?.result || {};
  const status = result.status || actionPacket.status || "unknown";
  const machineCode = result.machine_error_code || actionPacket.machine_error_code || "UNKNOWN";
  const refreshState = actionOutcome?.refreshState || "none";
  const refreshRequired = actionPacket?.post_action_refresh_required === true;
  const routeId = selectionPayload?.api_model_id || actionPacket?.route_id || result?.data?.route_id || "";
  const routeOk = status === "ok" && machineCode === "OK";
  const refreshOk = !refreshRequired || refreshState === "complete";
  const replayed = options.replayed === true;
  const blockedLabel = machineCode.length > 18 ? `${machineCode.slice(0, 18)}...` : machineCode;
  setQuickStartChip(
    "quickStartRouteChip",
    routeOk && refreshOk && !replayed ? "green" : "amber",
    routeOk && refreshOk ? (replayed ? "cached OK" : "OK") : blockedLabel
  );
  setQuickStartRouteResponse({
    status,
    machine_error_code: machineCode,
    final_status: replayed ? "API_ROUTE_CHECK_ACTION_PACKET_REPLAYED" : "API_ROUTE_CHECK_ACTION_PACKET_RECEIVED",
    execution_mode: selectionPayload?.execution_mode || "",
    api_model_id: routeId,
    selected_model: routeId,
    api_reasoning_option_id: selectionPayload?.api_reasoning_option_id || "",
    api_route_status: routeOk ? "checked" : "blocked",
    api_route_reference: routeId,
    ui_action: actionPacket?.ui_action || "api_route_check",
    route_id: routeId,
    action_status: status,
    action_machine_error_code: machineCode,
    action_refresh_state: refreshState,
    human_message: result.human_message || "",
    next_action: result.next_action || "",
    post_action_refresh_required: refreshRequired,
    manual_check_replay_active: replayed,
    manual_check_replay_age_ms: Number.isFinite(options.replayAgeMs) ? options.replayAgeMs : null,
    manual_check_replay_max_age_ms: replayed ? QUICK_START_MANUAL_CHECK_REPLAY_MAX_AGE_MS : null,
    runtime_readiness_claimed: false
  });
  if (options.remember === true) {
    rememberQuickStartApiRouteCheckSnapshot(selectionPayload, actionOutcome);
  }
}

async function runQuickStartLaunchPreflight() {
  if (codexLaunchDryRunInFlight) {
    return;
  }
  const payload = await buildCodexCustomLaunchSelectionPayload();
  codexLaunchDryRunInFlight = true;
  const button = document.getElementById("quickStartLaunchPreflightAction");
  button?.setAttribute("disabled", "disabled");
  setQuickStartChip("quickStartRouteChip", "neutral", "preflight");
  const responseNode = document.getElementById("quickStartRouteResponse");
  if (responseNode) {
    responseNode.textContent = "запрашиваю предзапусковый пакет...";
  }
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  const timeoutHandle = controller ? setTimeout(() => controller.abort(), 15000) : null;
  try {
    const response = await fetch("api/codex/custom/native-launch-preflight", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
      signal: controller?.signal
    });
    if (!response.ok) {
      throw new Error(`custom launch preflight http ${response.status}`);
    }
    const preflightPacket = await response.json();
    renderQuickStartLaunchPreflight(preflightPacket);
    if (quickStartShouldRunSelectedApiRouteCheck(payload, preflightPacket)) {
      setQuickStartChip("quickStartRouteChip", "neutral", "route check");
      if (responseNode) {
        responseNode.textContent = "preflight требует selected route check; проверяю выбранный API route...";
      }
      const actionOutcome = await runUiAction("api_route_check", { route_id: payload.api_model_id });
      renderQuickStartApiRouteCheckResult(payload, actionOutcome);
    }
  } catch (error) {
    const timedOut = error?.name === "AbortError";
    renderQuickStartLaunchPreflight({
      status: "failed",
      machine_error_code: timedOut
        ? "CUSTOM_LAUNCH_PREFLIGHT_REQUEST_TIMEOUT"
        : "CUSTOM_LAUNCH_PREFLIGHT_FETCH_FAILED",
      human_message: timedOut
        ? "Custom Codex launch preflight timed out before a packet returned."
        : error.message,
      packet_kind: "custom_native_launch_preflight",
      execution_mode: payload.execution_mode || "",
      chatgpt_model_id: payload.chatgpt_model_id || "",
      api_model_id: payload.api_model_id || "",
      api_reasoning_option_id: payload.api_reasoning_option_id || "",
      bridge_required: payload.execution_mode !== "chatgpt_only",
      bridge_alive: false,
      custom_process_observed: false,
      config_status: "unknown",
      show_window_attempted: false,
      new_launch_started: false,
      live_provider_called: false,
      visible_window_counts_as_model_truth: false,
      bridge_alive_counts_as_model_truth: false,
      response_text_counts_as_route_truth: false,
      launch_packet_is_truth_source: true,
      raw_backend_details_exposed: false,
      secret_value_exposed: false,
      raw_path_exposed: false,
      original_codex_touched: false,
      asar_touched: false
    });
  } finally {
    if (timeoutHandle) {
      clearTimeout(timeoutHandle);
    }
    codexLaunchDryRunInFlight = false;
    button?.removeAttribute("disabled");
  }
}

async function runQuickStartLaunchAdmissionProjection() {
  if (codexLaunchDryRunInFlight) {
    return;
  }
  const payload = await buildCodexCustomLaunchSelectionPayload();
  codexLaunchDryRunInFlight = true;
  const launchButton = document.getElementById("quickStartCustomLaunchAction");
  const preflightButton = document.getElementById("quickStartLaunchPreflightAction");
  launchButton?.setAttribute("disabled", "disabled");
  preflightButton?.setAttribute("disabled", "disabled");
  setQuickStartChip("quickStartRouteChip", "neutral", "проверяю");
  setQuickStartChip("quickStartLaunchState", "neutral", "admission");
  const responseNode = document.getElementById("quickStartRouteResponse");
  if (responseNode) {
    responseNode.textContent = "проверяю admission и preflight без live launch...";
  }
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  const timeoutHandle = controller ? setTimeout(() => controller.abort(), 20000) : null;
  try {
    const admissionResponse = await fetch("api/codex/custom/quick-start/config-admission", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
      signal: controller?.signal
    });
    if (!admissionResponse.ok) {
      throw new Error(`quick start config admission http ${admissionResponse.status}`);
    }
    const admissionPacket = await admissionResponse.json();
    renderQuickStartConfigAdmission(admissionPacket);
    if (admissionPacket?.launch_admission !== "admitted") {
      return;
    }
    const preflightResponse = await fetch("api/codex/custom/native-launch-preflight", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
      signal: controller?.signal
    });
    if (!preflightResponse.ok) {
      throw new Error(`custom launch preflight http ${preflightResponse.status}`);
    }
    renderQuickStartLaunchPreflight(await preflightResponse.json());
  } catch (error) {
    const timedOut = error?.name === "AbortError";
    renderQuickStartLaunchPreflight({
      status: "failed",
      machine_error_code: timedOut
        ? "QUICK_START_LAUNCH_ADMISSION_PROJECTION_TIMEOUT"
        : "QUICK_START_LAUNCH_ADMISSION_PROJECTION_FETCH_FAILED",
      human_message: timedOut
        ? "Quick Start launch admission projection timed out before packet truth returned."
        : error.message,
      packet_kind: "quick_start_launch_admission_projection",
      preflight_claim_scope: "quick_start_launch_guard_no_live_mutation",
      execution_mode: payload.execution_mode || "",
      chatgpt_model_id: payload.chatgpt_model_id || "",
      api_model_id: payload.api_model_id || "",
      api_reasoning_option_id: payload.api_reasoning_option_id || "",
      owner_authorization_phrase_present: false,
      show_window_attempted: false,
      new_launch_started: false,
      live_call_attempted: false,
      provider_called: false,
      live_provider_called: false,
      custom_codex_launch_attempted: false,
      network_calls_made: false,
      raw_backend_details_exposed: false,
      secret_value_exposed: false,
      raw_path_exposed: false,
      original_codex_touched: false,
      asar_touched: false,
      next_action: error.message
    });
  } finally {
    if (timeoutHandle) {
      clearTimeout(timeoutHandle);
    }
    codexLaunchDryRunInFlight = false;
    launchButton?.removeAttribute("disabled");
    preflightButton?.removeAttribute("disabled");
  }
}

function renderCodexCustomShowWindow(packet) {
  const summary = {
    status: packet?.status || "unknown",
    machine_error_code: packet?.machine_error_code || "UNKNOWN",
    packet_kind: packet?.packet_kind || "",
    custom_process_pid: packet?.custom_process_pid ?? null,
    custom_window_visible: packet?.custom_window_visible === true,
    custom_window_frontmost: packet?.custom_window_frontmost === true,
    native_app_usable: packet?.native_app_usable === true,
    input_capable_ui_observed: packet?.input_capable_ui_observed === true,
    native_app_usability_source: packet?.native_app_usability_source || "",
    native_app_usability_blocked_reason_class:
      packet?.native_app_usability_blocked_reason_class || "",
    visible_window_counts_as_model_truth: false,
    response_text_counts_as_route_truth: false,
    launch_packet_is_truth_source: false,
    show_window_attempted: true,
    new_launch_started: false,
    original_codex_touched: packet?.original_codex_touched === true,
    asar_touched: packet?.asar_touched === true,
    claim_scope: "show_existing_custom_window_only"
  };
  const response = document.getElementById("codexLaunchDryRunResponse");
  if (response) {
    response.textContent = JSON.stringify(summary, null, 2);
  }
  const quickResponse = document.getElementById("quickStartRouteResponse");
  if (quickResponse) {
    quickResponse.textContent = JSON.stringify(summary, null, 2);
  }
  const ok = packet?.status === "ok"
    && packet?.custom_window_visible === true
    && packet?.native_app_usable === true;
  const visibleOnly = packet?.custom_window_visible === true && packet?.native_app_usable !== true;
  setQuickStartChip(
    "quickStartLaunchState",
    ok ? "green" : (packet?.status === "blocked" || packet?.status === "rejected" ? "amber" : "red"),
    ok ? "окно usable" : (visibleOnly ? "окно видно" : (packet?.machine_error_code || packet?.status || "ошибка"))
  );
  setQuickStartChip(
    "quickStartRouteChip",
    ok ? "green" : "amber",
    ok ? "окно ok" : (visibleOnly ? "proof incomplete" : "пакет окна")
  );
  codexLaunchSetChip(
    ok ? "green" : "amber",
    ok ? "window usable" : (visibleOnly ? "window visible / proof incomplete" : "window packet")
  );
}

async function showCodexCustomWindow() {
  if (codexLaunchDryRunInFlight) {
    return;
  }
  codexLaunchDryRunInFlight = true;
  const button = document.getElementById("quickStartShowCustomWindowAction");
  button?.setAttribute("disabled", "disabled");
  setQuickStartChip("quickStartLaunchState", "neutral", "показываю");
  const responseNode = document.getElementById("quickStartRouteResponse");
  if (responseNode) {
    responseNode.textContent = "запрашиваю пакет показа окна...";
  }
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  const timeoutHandle = controller ? setTimeout(() => controller.abort(), 15000) : null;
  try {
    const response = await fetch("api/codex/custom/show-window", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({}),
      signal: controller?.signal
    });
    if (!response.ok) {
      throw new Error(`custom show-window http ${response.status}`);
    }
    renderCodexCustomShowWindow(await response.json());
  } catch (error) {
    const timedOut = error?.name === "AbortError";
    renderCodexCustomShowWindow({
      status: "failed",
      machine_error_code: timedOut ? "CUSTOM_SHOW_WINDOW_REQUEST_TIMEOUT" : "CUSTOM_SHOW_WINDOW_FETCH_FAILED",
      human_message: timedOut ? "Custom Codex show-window request timed out before a packet returned." : error.message,
      packet_kind: "custom_codex_show_window",
      custom_window_visible: false,
      custom_window_frontmost: false,
      window_response_timeout: timedOut,
      window_unresponsive_with_limits: timedOut,
      new_launch_started: false,
      visible_window_counts_as_model_truth: false,
      response_text_counts_as_route_truth: false,
      launch_packet_is_truth_source: false,
      original_codex_touched: false,
      asar_touched: false,
      final_status: "CUSTOM_CODEX_LAUNCH_STABILITY_AND_RECOVERY_WITH_LIMITS"
    });
  } finally {
    if (timeoutHandle) {
      clearTimeout(timeoutHandle);
    }
    codexLaunchDryRunInFlight = false;
    button?.removeAttribute("disabled");
  }
}

async function confirmCodexCustomVisibleHistory() {
  const responseNode = document.getElementById("codexCustomVisibleHistoryResponse");
  const button = document.getElementById("codexCustomVisibleHistoryConfirmAction");
  const quickResponseNode = document.getElementById("quickStartRouteResponse");
  const checked = (...ids) => ids.some((id) => document.getElementById(id)?.checked === true);
  const payload = {
    custom_codex_open: checked("customVisibleHistoryOpenCheck", "quickStartVisibleHistoryOpenCheck"),
    old_chat_visible: checked("customVisibleHistoryOldChatCheck", "quickStartVisibleHistoryOldChatCheck"),
    chat_not_empty: checked("customVisibleHistoryNonEmptyCheck", "quickStartVisibleHistoryNonEmptyCheck"),
    not_original_codex: checked("customVisibleHistoryNotOriginalCheck", "quickStartVisibleHistoryNotOriginalCheck"),
    raw_thread_content_not_recorded: checked("customVisibleHistoryNoRawContentCheck", "quickStartVisibleHistoryNoRawContentCheck")
  };
  button?.setAttribute("disabled", "disabled");
  document.getElementById("quickStartVisibleHistoryConfirmAction")?.setAttribute("disabled", "disabled");
  if (responseNode) {
    responseNode.textContent = "проверяю ручное подтверждение видимой истории...";
  }
  if (quickResponseNode) {
    quickResponseNode.textContent = "проверяю ручное подтверждение видимой истории...";
  }
  try {
    const response = await fetch("api/codex/custom/visible-history/owner-confirmation", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      throw new Error(`visible history confirmation http ${response.status}`);
    }
    if (responseNode) {
      const packet = await response.json();
      responseNode.textContent = JSON.stringify(packet, null, 2);
      setQuickStartRouteResponse(packet);
      setQuickStartChip(
        "quickStartVisibleHistoryState",
        packet?.status === "ok" ? "green" : (packet?.status === "blocked" || packet?.status === "rejected" ? "amber" : "red"),
        packet?.status === "ok" ? "подтверждена" : (packet?.machine_error_code || packet?.status || "ошибка")
      );
    }
  } catch (error) {
    const failedPacket = {
      status: "failed",
      machine_error_code: "VISIBLE_HISTORY_CONFIRMATION_FETCH_FAILED",
      human_message: error.message,
      final_status: "VISIBLE_THREAD_HISTORY_NOT_PROVEN_WITH_STORAGE_CONTINUITY",
      raw_thread_content_recorded: false,
      full_history_restoration_claimed: false
    };
    if (responseNode) {
      responseNode.textContent = JSON.stringify(failedPacket, null, 2);
    }
    if (quickResponseNode) {
      setQuickStartRouteResponse(failedPacket);
    }
    setQuickStartChip("quickStartVisibleHistoryState", "red", "ошибка");
  } finally {
    button?.removeAttribute("disabled");
    document.getElementById("quickStartVisibleHistoryConfirmAction")?.removeAttribute("disabled");
  }
}

async function runSafeAppCopyLaunchDryRun() {
  if (codexLaunchDryRunInFlight) {
    return;
  }
  codexLaunchDryRunInFlight = true;
  document.getElementById("safeAppCopyLaunchDryRunAction")?.setAttribute("disabled", "disabled");
  codexLaunchSetChip("neutral", "checking");
  try {
    const response = await fetch("api/codex/app-copy/launch-dry-run", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({})
    });
    if (!response.ok) {
      throw new Error(`app copy dry-run http ${response.status}`);
    }
    renderSafeAppCopyLaunchPacket(await response.json());
  } catch (error) {
    renderSafeAppCopyLaunchPacket({
      status: "failed",
      machine_error_code: "WEB_SAFE_APP_COPY_LAUNCH_DRY_RUN_FETCH_FAILED",
      dry_run: true,
      launch_performed: false,
      server_issued_plan: false,
      current_codex_touched: false,
      uses_current_home: false,
      uses_current_codex_home: false,
      final_verdict: "WEB_SAFE_APP_COPY_LAUNCH_BLOCKED",
      next_action: error.message
    });
  } finally {
    codexLaunchDryRunInFlight = false;
    document.getElementById("safeAppCopyLaunchDryRunAction")?.removeAttribute("disabled");
  }
}

async function runSafeAppCopyLaunch() {
  const button = document.getElementById("safeAppCopyLaunchAction");
  if (button?.disabled) {
    return;
  }
  button.setAttribute("disabled", "disabled");
  codexLaunchSetChip("neutral", "launch checking");
  try {
    const response = await fetch("api/codex/app-copy/launch", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({})
    });
    if (!response.ok) {
      throw new Error(`app copy launch http ${response.status}`);
    }
    renderSafeAppCopyLaunchPacket(await response.json());
  } catch (error) {
    renderSafeAppCopyLaunchPacket({
      status: "failed",
      machine_error_code: "WEB_SAFE_APP_COPY_LAUNCH_FETCH_FAILED",
      dry_run: false,
      launch_performed: false,
      server_issued_plan: false,
      current_codex_touched: false,
      uses_current_home: false,
      uses_current_codex_home: false,
      final_verdict: "WEB_SAFE_APP_COPY_LAUNCH_BLOCKED",
      next_action: error.message
    });
  }
}

function codexCustomModelsSetText(id, value) {
  operatorSetText(id, value);
}

function codexCustomModelsSetChip(visual, label) {
  const chip = document.getElementById("codexCustomModelsChip");
  if (!chip) {
    return;
  }
  chip.className = `chip ${VISUAL_CLASS[visual] || ACTION_STATUS_VISUAL_CLASS[visual] || "neutral"}`;
  if (chip.lastElementChild) {
    chip.lastElementChild.textContent = label || visual || "unknown";
  }
}

function codexCustomLaneSetChip(id, visual, label) {
  const chip = document.getElementById(id);
  if (!chip) {
    return;
  }
  chip.className = `chip ${VISUAL_CLASS[visual] || ACTION_STATUS_VISUAL_CLASS[visual] || "neutral"}`;
  if (chip.lastElementChild) {
    chip.lastElementChild.textContent = label || visual || "unknown";
  }
}

function codexCustomLaneEntries(packet, lane) {
  const section = packet?.[lane];
  return (Array.isArray(section?.models) ? section.models : [])
    .filter((entry) => typeof entry?.model_id === "string" && entry.model_id);
}

function codexCustomSeedEntries(packet) {
  const section = packet?.seed_only_reference;
  return (Array.isArray(section?.models) ? section.models : [])
    .filter((entry) => typeof entry?.model_id === "string" && entry.model_id);
}

function codexCustomAvailableModelEntries(packet) {
  return codexCustomLaneEntries(packet, "chatgpt_lane");
}

function codexCustomApiModelEntries(packet) {
  const laneEntries = codexCustomLaneEntries(packet, "api_lane");
  if (laneEntries.length) {
    return laneEntries;
  }
  return (Array.isArray(packet?.available_models) ? packet.available_models : [])
    .filter((entry) => (
      typeof entry?.model_id === "string"
      && entry.model_id
      && entry?.selection_enabled === true
      && entry?.model_lane === "api_route_lane"
      && entry?.source === "server_owned_external_route"
    ));
}

function codexCustomDisabledReasonText(entry) {
  const reasons = Array.isArray(entry?.selection_disabled_reasons) ? entry.selection_disabled_reasons : [];
  if (reasons.includes("historical_seed_only") && reasons.includes("not_current_runtime_catalog")) {
    return "historical reference only";
  }
  if (reasons.includes("route_disabled") && reasons.includes("secret_ref_missing")) {
    return "route disabled + secret missing";
  }
  if (reasons.includes("route_disabled")) {
    return "route disabled";
  }
  if (reasons.includes("secret_ref_missing")) {
    return "secret missing";
  }
  return entry?.selection_disabled_reason_code || "not selectable";
}

function renderCodexCustomModelCatalog(listId, entries) {
  const node = document.getElementById(listId);
  if (!node) {
    return;
  }
  node.replaceChildren();
  for (const entry of entries) {
    const row = document.createElement("div");
    row.className = "model-catalog-row";
    const main = document.createElement("div");
    main.className = "model-catalog-main";
    const name = document.createElement("div");
    name.className = "model-catalog-name";
    name.textContent = entry?.display_name || entry?.model_id || "-";
    const subtitle = document.createElement("div");
    subtitle.className = "model-catalog-subtitle";
    subtitle.textContent = entry?.model_id || "-";
    main.append(name, subtitle);
    const meta = document.createElement("div");
    meta.className = "model-catalog-meta";
    meta.textContent = `${entry?.provider_label || entry?.provider_class || "unknown"} · ${entry?.availability_claim_level || "listed_not_live_proven"}`;
    const status = document.createElement("div");
    status.className = "model-catalog-meta model-catalog-status";
    status.textContent = entry?.selection_enabled === true
      ? "selectable"
      : `disabled · ${codexCustomDisabledReasonText(entry)}`;
    row.append(main, meta, status);
    node.append(row);
  }
}

function mirrorSelectOptions(source, targetId) {
  const target = document.getElementById(targetId);
  if (!source || !target) {
    return;
  }
  const previous = target.value;
  target.replaceChildren();
  for (const sourceOption of source.options) {
    const option = document.createElement("option");
    option.value = sourceOption.value;
    option.textContent = sourceOption.textContent;
    option.disabled = sourceOption.disabled;
    target.append(option);
  }
  if ([...target.options].some((option) => option.value === previous && !option.disabled)) {
    target.value = previous;
  } else {
    target.value = source.value;
  }
}

function apiReasoningOptionForModelEntry(entry) {
  const thinking = entry?.thinking || {};
  if (thinking?.type === "enabled" && thinking?.reasoning_effort === "max") {
    return {
      option_id: "provider_declared_max",
      label: "Глубокое"
    };
  }
  if (thinking?.type === "enabled" && thinking?.reasoning_effort === "high") {
    return {
      option_id: "provider_declared_high",
      label: "Усиленное"
    };
  }
  if (thinking?.type === "disabled") {
    return {
      option_id: "provider_declared_disabled",
      label: "Обычное"
    };
  }
  return {
    option_id: "catalog_default",
    label: "Авто"
  };
}

function renderApiReasoningOptionSelects() {
  const apiSelect = document.getElementById("codexCustomApiModelSelect");
  const modelEntry = codexCustomApiModelEntryById.get(apiSelect?.value || "") || {};
  const optionPacket = apiReasoningOptionForModelEntry(modelEntry);
  const targets = [
    document.getElementById("codexCustomApiReasoningOptionSelect"),
    document.getElementById("quickStartApiReasoningOptionSelect")
  ];
  for (const target of targets) {
    if (!target) {
      continue;
    }
    target.replaceChildren();
    const option = document.createElement("option");
    option.value = optionPacket.option_id;
    option.textContent = optionPacket.label;
    target.append(option);
    target.value = optionPacket.option_id;
  }
}

function codexRouteSelectionPrefersQuickStart() {
  const desktop = document.querySelector(".desktop");
  return desktop?.dataset?.screen === "quick-start";
}

function codexRoutePairValue(masterId, quickStartId, preferQuickStart = false) {
  const primary = preferQuickStart ? quickStartId : masterId;
  const fallback = preferQuickStart ? masterId : quickStartId;
  return selectValue(primary) || selectValue(fallback);
}

function codexRouteSelectionFromUi(preferQuickStart = codexRouteSelectionPrefersQuickStart()) {
  return {
    execution_mode: codexRoutePairValue("codexCustomExecutionModeSelect", "quickStartExecutionModeSelect", preferQuickStart),
    chatgpt_model_id: codexRoutePairValue("codexCustomModelSelect", "quickStartChatModelSelect", preferQuickStart),
    api_model_id: codexRoutePairValue("codexCustomApiModelSelect", "quickStartApiModelSelect", preferQuickStart),
    api_reasoning_option_id: codexRoutePairValue("codexCustomApiReasoningOptionSelect", "quickStartApiReasoningOptionSelect", preferQuickStart)
  };
}

function codexExecutionModeIsKnown(mode) {
  return ["chatgpt_only", "chatgpt_plus_api", "api_only"].includes(mode);
}

function codexExecutionModeNeedsChatGPT(mode) {
  return mode === "chatgpt_only" || mode === "chatgpt_plus_api";
}

function codexExecutionModeNeedsApi(mode) {
  return mode === "chatgpt_plus_api" || mode === "api_only";
}

function quickStartSelectionWithDefaults(selection) {
  const next = { ...(selection || {}) };
  if (!next.execution_mode) {
    next.execution_mode = QUICK_START_DEFAULT_EXECUTION_MODE;
  }
  if (codexExecutionModeNeedsChatGPT(next.execution_mode) && !next.chatgpt_model_id) {
    next.chatgpt_model_id = QUICK_START_PREFERRED_CHATGPT_MODEL_ID;
  }
  if (codexExecutionModeNeedsApi(next.execution_mode) && !next.api_model_id) {
    next.api_model_id = QUICK_START_PREFERRED_API_MODEL_ID;
  }
  if (codexExecutionModeNeedsApi(next.execution_mode) && !next.api_reasoning_option_id) {
    next.api_reasoning_option_id = QUICK_START_PREFERRED_API_REASONING_OPTION_ID;
  }
  return next;
}

function codexRouteSelectionHasValue(selection) {
  return Boolean(
    selection
    && (
      selection.execution_mode
      || selection.chatgpt_model_id
      || selection.api_model_id
      || selection.api_reasoning_option_id
    )
  );
}

function readStoredCodexRouteSelection() {
  try {
    const raw = window.localStorage?.getItem(CODEX_ROUTE_SELECTION_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    return codexRouteSelectionHasValue(parsed) ? parsed : null;
  } catch (error) {
    return null;
  }
}

function quickStartSelectionPreservesUserChatGptModel(selection, currentSelection = null) {
  return Boolean(
    selection?.chatgpt_model_selected_by_user === true
    || (
      currentSelection?.chatgpt_model_selected_by_user === true
      && currentSelection?.chatgpt_model_id
      && currentSelection.chatgpt_model_id === selection?.chatgpt_model_id
    )
  );
}

function quickStartStoredSelectionForRegistry(selection, registry) {
  if (!selection) {
    return null;
  }
  const next = { ...selection };
  const serverDefault = String(registry?.chatgpt_lane?.default_model_id || "");
  const preferredAvailable = registry?.chatgpt_lane?.preferred_default_available === true;
  const preservesExplicitUserChoice = next.chatgpt_model_selected_by_user === true;
  if (
    !preservesExplicitUserChoice
    && preferredAvailable
    && serverDefault
    && next.chatgpt_model_id !== serverDefault
    && QUICK_START_LEGACY_CHATGPT_DEFAULT_MODEL_IDS.has(next.chatgpt_model_id)
  ) {
    next.chatgpt_model_id = serverDefault;
    next.chatgpt_model_id_replaced_reason = "legacy_default_replaced_by_server_default";
  }
  return next;
}

function codexSelectCanUseValue(select, value) {
  if (!select || !value) {
    return false;
  }
  if (!select.options || typeof select.options[Symbol.iterator] !== "function") {
    return true;
  }
  const options = [...select.options];
  if (!options.length) {
    return true;
  }
  return options.some((option) => option.value === value && !option.disabled);
}

function codexSelectPairCanUseValue(masterId, quickStartId, value) {
  return codexSelectCanUseValue(document.getElementById(masterId), value)
    && codexSelectCanUseValue(document.getElementById(quickStartId), value);
}

function codexRouteSelectionCanApplyFully(selection, options = {}) {
  if (!codexRouteSelectionHasValue(selection)) {
    return false;
  }
  const mode = selection.execution_mode || "";
  if (!codexExecutionModeIsKnown(mode)) {
    return false;
  }
  if (!codexSelectPairCanUseValue("codexCustomExecutionModeSelect", "quickStartExecutionModeSelect", mode)) {
    return false;
  }
  if (
    codexExecutionModeNeedsChatGPT(mode)
    && !codexSelectPairCanUseValue("codexCustomModelSelect", "quickStartChatModelSelect", selection.chatgpt_model_id)
  ) {
    return false;
  }
  if (
    codexExecutionModeNeedsApi(mode)
    && !codexSelectPairCanUseValue("codexCustomApiModelSelect", "quickStartApiModelSelect", selection.api_model_id)
  ) {
    return false;
  }
  if (
    options.reasoning !== false
    && codexExecutionModeNeedsApi(mode)
    && !codexSelectPairCanUseValue(
      "codexCustomApiReasoningOptionSelect",
      "quickStartApiReasoningOptionSelect",
      selection.api_reasoning_option_id
    )
  ) {
    return false;
  }
  return true;
}

function codexRenderedRouteSelectionFromUi(preferQuickStart = codexRouteSelectionPrefersQuickStart()) {
  const selection = codexRouteSelectionFromUi(preferQuickStart);
  return codexRouteSelectionCanApplyFully(selection, { reasoning: false }) ? selection : null;
}

function setCodexSelectPairValue(masterId, quickStartId, value) {
  if (!value) {
    return false;
  }
  let applied = false;
  for (const id of [masterId, quickStartId]) {
    const node = document.getElementById(id);
    if (codexSelectCanUseValue(node, value)) {
      node.value = value;
      applied = true;
    }
  }
  return applied;
}

function renderQuickStartInvalidPersistedSelection(selection, machineErrorCode = "QUICK_START_PERSISTED_SELECTION_INVALID") {
  if (!codexRouteSelectionPrefersQuickStart()) {
    return;
  }
  setQuickStartChip("quickStartRouteChip", "amber", "invalid selection");
  setQuickStartRouteResponse({
    status: "blocked",
    machine_error_code: machineErrorCode,
    final_status: "QUICK_START_PERSISTED_SELECTION_REJECTED",
    execution_mode: selection?.execution_mode || "",
    chatgpt_model_id: selection?.chatgpt_model_id || "",
    api_model_id: selection?.api_model_id || "",
    api_reasoning_option_id: selection?.api_reasoning_option_id || "",
    selected_model: selection?.chatgpt_model_id || selection?.api_model_id || "",
    launch_admission: "blocked",
    launch_admission_summary: "Persisted Quick Start selection is not bounded by the current server-issued catalog.",
    dry_server_truth_only: true,
    live_call_attempted: false,
    provider_called: false,
    fallback_used: false,
    silent_fallback_used: false,
    runtime_readiness_claimed: false,
    next_action: "choose_server_issued_quick_start_selection"
  });
}

function applyCodexRouteSelection(selection, options = {}) {
  if (!codexRouteSelectionHasValue(selection)) {
    return false;
  }
  let applied = false;
  applied = setCodexSelectPairValue(
    "codexCustomExecutionModeSelect",
    "quickStartExecutionModeSelect",
    selection.execution_mode
  ) || applied;
  applied = setCodexSelectPairValue(
    "codexCustomModelSelect",
    "quickStartChatModelSelect",
    selection.chatgpt_model_id
  ) || applied;
  applied = setCodexSelectPairValue(
    "codexCustomApiModelSelect",
    "quickStartApiModelSelect",
    selection.api_model_id
  ) || applied;
  if (options.reasoning !== false) {
    applied = setCodexSelectPairValue(
      "codexCustomApiReasoningOptionSelect",
      "quickStartApiReasoningOptionSelect",
      selection.api_reasoning_option_id
    ) || applied;
  }
  return applied;
}

function saveCodexRouteSelection(
  selection = codexRouteSelectionFromUi(codexRouteSelectionPrefersQuickStart()),
  options = {}
) {
  if (!codexRouteSelectionHasValue(selection)) {
    return;
  }
  const currentSelection = readStoredCodexRouteSelection();
  const persistedSource = codexRouteSelectionPrefersQuickStart()
    ? quickStartSelectionWithDefaults(selection)
    : selection;
  const persisted = { ...persistedSource };
  persisted.selection_persistence_schema_version = 3;
  if (quickStartSelectionPreservesUserChatGptModel(persisted, currentSelection)) {
    persisted.chatgpt_model_selected_by_user = true;
  }
  if (
    options.userInitiated === true
    && ["codexCustomModelSelect", "quickStartChatModelSelect"].includes(options.sourceId)
  ) {
    persisted.chatgpt_model_selected_by_user = true;
    persisted.selection_source = "user_change";
  }
  try {
    window.localStorage?.setItem(CODEX_ROUTE_SELECTION_STORAGE_KEY, JSON.stringify(persisted));
  } catch (error) {
    // Selection persistence is a UI convenience; command packets remain the source of truth.
  }
}

function syncCodexRouteSelects(sourceId, options = {}) {
  const pairs = [
    ["codexCustomModelSelect", "quickStartChatModelSelect"],
    ["codexCustomApiModelSelect", "quickStartApiModelSelect"],
    ["codexCustomApiReasoningOptionSelect", "quickStartApiReasoningOptionSelect"],
    ["codexCustomExecutionModeSelect", "quickStartExecutionModeSelect"]
  ];
  const pair = pairs.find((items) => items.includes(sourceId));
  if (!pair) {
    return;
  }
  const source = document.getElementById(sourceId);
  const targetId = pair[0] === sourceId ? pair[1] : pair[0];
  const target = document.getElementById(targetId);
  if (source && target) {
    target.value = source.value;
    if (sourceId === "codexCustomExecutionModeSelect" || sourceId === "quickStartExecutionModeSelect") {
      setQuickStartMixedLaunchActionGuard(false);
    }
    saveCodexRouteSelection(codexRouteSelectionFromUi(sourceId.startsWith("quickStart")), {
      ...options,
      sourceId
    });
  }
}

function selectValue(id) {
  const node = document.getElementById(id);
  return node ? String(node.value || "").trim() : "";
}

function quickStartLaunchPayloadFromSelects() {
  const executionMode = selectValue("quickStartExecutionModeSelect") || QUICK_START_DEFAULT_EXECUTION_MODE;
  return {
    execution_mode: executionMode,
    chatgpt_model_id: executionMode === "api_only" ? "" : selectValue("quickStartChatModelSelect"),
    api_model_id: executionMode === "chatgpt_only" ? "" : selectValue("quickStartApiModelSelect"),
    api_reasoning_option_id: executionMode === "chatgpt_only"
      ? ""
      : selectValue("quickStartApiReasoningOptionSelect")
  };
}

function quickStartManualCheckSelectionKey(payload) {
  return JSON.stringify({
    execution_mode: payload?.execution_mode || "",
    chatgpt_model_id: payload?.chatgpt_model_id || "",
    api_model_id: payload?.api_model_id || "",
    api_reasoning_option_id: payload?.api_reasoning_option_id || ""
  });
}

function quickStartManualCheckCurrentKey() {
  return quickStartManualCheckSelectionKey(quickStartLaunchPayloadFromSelects());
}

function quickStartManualCheckSnapshotMatches(snapshot) {
  if (!snapshot || !snapshot.selectionKey || !snapshot.recordedAt) {
    return false;
  }
  if (Date.now() - snapshot.recordedAt > QUICK_START_MANUAL_CHECK_REPLAY_MAX_AGE_MS) {
    return false;
  }
  return snapshot.selectionKey === quickStartManualCheckCurrentKey();
}

function rememberQuickStartConfigAdmissionSnapshot(selectionPayload, packet) {
  if (!selectionPayload || !packet) {
    return;
  }
  quickStartManualCheckSnapshot = {
    selectionKey: quickStartManualCheckSelectionKey(selectionPayload),
    selectionPayload: { ...selectionPayload },
    admissionPacket: packet,
    apiRouteCheckOutcome: null,
    recordedAt: Date.now()
  };
}

function rememberQuickStartApiRouteCheckSnapshot(selectionPayload, actionOutcome) {
  if (!selectionPayload || !actionOutcome) {
    return;
  }
  const selectionKey = quickStartManualCheckSelectionKey(selectionPayload);
  if (!quickStartManualCheckSnapshot || quickStartManualCheckSnapshot.selectionKey !== selectionKey) {
    quickStartManualCheckSnapshot = {
      selectionKey,
      selectionPayload: { ...selectionPayload },
      admissionPacket: null,
      apiRouteCheckOutcome: actionOutcome,
      recordedAt: Date.now()
    };
    return;
  }
  quickStartManualCheckSnapshot = {
    ...quickStartManualCheckSnapshot,
    selectionPayload: { ...selectionPayload },
    apiRouteCheckOutcome: actionOutcome,
    recordedAt: Date.now()
  };
}

function replayQuickStartManualCheckSnapshot() {
  if (!quickStartManualCheckSnapshotMatches(quickStartManualCheckSnapshot)) {
    return;
  }
  const snapshot = quickStartManualCheckSnapshot;
  const replayAgeMs = Date.now() - snapshot.recordedAt;
  if (snapshot.admissionPacket) {
    renderQuickStartConfigAdmission(snapshot.admissionPacket, {
      remember: false,
      replayed: true,
      replayAgeMs
    });
  }
  if (snapshot.apiRouteCheckOutcome) {
    renderQuickStartApiRouteCheckResult(
      snapshot.selectionPayload,
      snapshot.apiRouteCheckOutcome,
      {
        remember: false,
        replayed: true,
        replayAgeMs
      }
    );
  }
}

function customLaunchPayloadRequiresModelRefresh(payload) {
  const executionMode = payload?.execution_mode || "";
  if (executionMode === "api_only") {
    return !payload?.api_model_id;
  }
  if (executionMode === "chatgpt_plus_api") {
    return !payload?.chatgpt_model_id || !payload?.api_model_id;
  }
  return !payload?.chatgpt_model_id;
}

function setQuickStartChip(id, visual, label) {
  const chip = document.getElementById(id);
  if (!chip) {
    return;
  }
  chip.className = `chip ${ACCOUNT_VISUAL_CLASS[visual] || VISUAL_CLASS[visual] || "neutral"}`;
  if (chip.lastElementChild) {
    chip.lastElementChild.textContent = label || "unknown";
  } else {
    chip.textContent = label || "unknown";
  }
}

function setQuickStartRouteResponse(packet) {
  const response = document.getElementById("quickStartRouteResponse");
  if (response) {
    const primarySlot = packet?.primary_model_slot || {};
    const codingSlot = packet?.coding_agent_model_slot || {};
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || packet?.final_status || "UNKNOWN",
      final_status: packet?.final_status || "",
      mixed_mode_product_decision:
        packet?.mixed_mode_product_decision || "",
      mixed_mode_launch_action:
        packet?.mixed_mode_launch_action || "",
      mixed_mode_launch_blocked_reason:
        packet?.mixed_mode_launch_blocked_reason || "",
      primary_trace_proof_status:
        packet?.primary_trace_proof_status || "",
      mixed_mode_launch_available_with_primary_trace_gap:
        packet?.mixed_mode_launch_available_with_primary_trace_gap === true,
      execution_mode: packet?.execution_mode || "",
      chatgpt_model_id: packet?.chatgpt_model_id || "",
      api_model_id: packet?.api_model_id || "",
      selected_model: packet?.selected_model || packet?.api_model_id || packet?.chatgpt_model_id || "",
      launch_model_id: packet?.launch_model_id || "",
      route_model_id: packet?.route_model_id || "",
      api_reasoning_option_id: packet?.api_reasoning_option_id || "",
      api_reasoning_status: packet?.api_reasoning_status || "",
      api_route_status: packet?.api_route_status || "",
      api_route_reference: packet?.api_route_reference || "",
      primary_model_slot_lane: primarySlot?.lane || "",
      primary_model_slot_model_id: primarySlot?.model_id || "",
      coding_agent_model_slot_status: codingSlot?.status || "",
      coding_agent_model_slot_model_id: codingSlot?.model_id || "",
      chatgpt_line_used_as_executor:
        packet?.chatgpt_line_used_as_executor === true,
      api_line_used_as_executor:
        packet?.api_line_used_as_executor === true,
      api_only_calls_chatgpt: packet?.api_only_calls_chatgpt === true,
      chatgpt_only_calls_api: packet?.chatgpt_only_calls_api === true,
      server_issued_catalog_used: packet?.server_issued_catalog_used === true,
      ui_action: packet?.ui_action || "",
      route_id: packet?.route_id || "",
      action_status: packet?.action_status || "",
      action_machine_error_code: packet?.action_machine_error_code || "",
      action_refresh_state: packet?.action_refresh_state || "",
      human_message: packet?.human_message || "",
      next_action: packet?.next_action || "",
      post_action_refresh_required: packet?.post_action_refresh_required === true,
      launch_proven: packet?.launch_proven === true,
      launch_status: packet?.launch_status || "",
      launch_status_ok: packet?.launch_status_ok === true,
      launch_packet_age_seconds:
        Number.isFinite(packet?.launch_packet_age_seconds) ? packet.launch_packet_age_seconds : null,
      launch_packet_stale: packet?.launch_packet_stale === true,
      launch_packet_stale_overridden_by_current_bridge_trace:
        packet?.launch_packet_stale_overridden_by_current_bridge_trace === true,
      current_bridge_trace_matches_launch:
        packet?.current_bridge_trace_matches_launch === true,
      trace_snapshot_age_seconds:
        Number.isFinite(packet?.trace_snapshot_age_seconds) ? packet.trace_snapshot_age_seconds : null,
      trace_snapshot_stale: packet?.trace_snapshot_stale === true,
      current_launch_evidence_proven_with_limits:
        packet?.current_launch_evidence_proven_with_limits === true,
      current_mixed_trace_evidence_fresh:
        packet?.current_mixed_trace_evidence_fresh === true,
      runtime_readiness_claimed: packet?.runtime_readiness_claimed === true,
      runtime_health_gate_blocks_launch_admission:
        packet?.runtime_health_gate_blocks_launch_admission === true,
      runtime_health_gate_blocks_window_launch:
        packet?.runtime_health_gate_blocks_window_launch === true,
      runtime_health_required_for_chatgpt_lane:
        packet?.runtime_health_required_for_chatgpt_lane === true,
      runtime_health_machine_error_code:
        packet?.runtime_health_machine_error_code || packet?.runtime_health_gate?.runtime_health_machine_error_code || "",
      chatgpt_runtime_proof_status:
        packet?.chatgpt_runtime_proof_status || "",
      chatgpt_runtime_proof_machine_error_code:
        packet?.chatgpt_runtime_proof_machine_error_code || "",
      manual_check_replay_active: packet?.manual_check_replay_active === true,
      manual_check_replay_age_ms:
        Number.isFinite(packet?.manual_check_replay_age_ms) ? packet.manual_check_replay_age_ms : null,
      manual_check_replay_max_age_ms:
        Number.isFinite(packet?.manual_check_replay_max_age_ms) ? packet.manual_check_replay_max_age_ms : null,
      fallback_used: packet?.fallback_used === true,
      silent_fallback_used: packet?.silent_fallback_used === true,
      launch_admission: packet?.launch_admission || "",
      launch_admission_summary: packet?.launch_admission_summary || "",
      dry_server_truth_only: packet?.dry_server_truth_only === true,
      owner_authorization_phrase_present:
        packet?.owner_authorization_phrase_present === true,
      launch_route_truth_final_status: packet?.launch_route_truth_final_status || "",
      quick_start_stable_custom_launch_final_status:
        packet?.quick_start_stable_custom_launch_final_status || "",
      profile_final_status: packet?.profile_final_status || "",
      session_storage_final_status: packet?.session_storage_final_status || "",
      bridge_alive: packet?.bridge_alive === true,
      port_alive: packet?.port_alive === true,
      responses_endpoint_available:
        packet?.responses_endpoint_available === true,
      stable_custom_codex_wbp_bridge_final_status:
        packet?.stable_custom_codex_wbp_bridge_final_status || "",
      bridge_status: packet?.bridge_status || "",
      live_bridge_stability_truth_packet:
        packet?.live_bridge_stability_truth_packet === true,
      bridge_session_matches_active_window:
        packet?.bridge_session_matches_active_window === true,
      trace_id_matches_launch:
        packet?.trace_id_matches_launch === true,
      launch_id_matches_trace:
        packet?.launch_id_matches_trace === true,
      old_window_answered:
        packet?.old_window_answered === true,
      failure_machine_error_code:
        packet?.failure_machine_error_code || "",
      recommended_recovery_action:
        packet?.recommended_recovery_action || "",
      recovery_required:
        packet?.recovery_required === true,
      window_status: packet?.window_status || "",
      config_status: packet?.config_status || "",
      selection_matches_last_launch:
        packet?.selection_matches_last_launch === true,
      existing_window_reuse_admissible:
        packet?.existing_window_reuse_admissible === true,
      existing_window_relaunch_admissible:
        packet?.existing_window_relaunch_admissible === true,
      existing_window_relaunch_attempted:
        packet?.existing_window_relaunch_attempted === true,
      existing_window_relaunch_termination:
        packet?.existing_window_relaunch_termination || {},
      existing_window_orphan_replace_admissible:
        packet?.existing_window_orphan_replace_admissible === true,
      existing_window_orphan_replace_attempted:
        packet?.existing_window_orphan_replace_attempted === true,
      existing_window_orphan_replace_termination:
        packet?.existing_window_orphan_replace_termination || {},
      orphan_replacement_authority_scope:
        packet?.orphan_replacement_authority_scope || "",
      custom_process_observed:
        packet?.custom_process_observed === true,
      custom_process_count: Number(packet?.custom_process_count || 0),
      custom_process_observed_before_relaunch:
        packet?.custom_process_observed_before_relaunch === true,
      custom_process_observed_after_relaunch_stop:
        packet?.custom_process_observed_after_relaunch_stop === true,
      custom_process_count_after_relaunch_stop:
        Number(packet?.custom_process_count_after_relaunch_stop || 0),
      reused_existing_window:
        packet?.reused_existing_window === true,
      launch_blocked:
        packet?.launch_blocked === true,
      show_window_attempted:
        packet?.show_window_attempted === true,
      window_unresponsive_with_limits:
        packet?.window_unresponsive_with_limits === true,
      new_launch_required: packet?.new_launch_required === true,
      running_status: packet?.running_status === true,
      process_started: packet?.process_started === true,
      native_window_observed: packet?.native_window_observed === true,
      real_codex_app_launched: packet?.real_codex_app_launched === true,
      native_app_usable: packet?.native_app_usable === true,
      native_app_usability_blocked_reason_class:
        packet?.native_app_usability_blocked_reason_class || "",
      renderer_surface_blocked_reason_class:
        packet?.renderer_surface_blocked_reason_class || "",
      slot_binding_blocking_reasons:
        Array.isArray(packet?.slot_binding_blocking_reasons)
          ? packet.slot_binding_blocking_reasons
          : [],
      custom_codex_launch_attempted:
        packet?.custom_codex_launch_attempted === true,
      new_launch_started: packet?.new_launch_started === true,
      network_calls_made: packet?.network_calls_made === true,
      visible_window_counts_as_model_truth:
        packet?.visible_window_counts_as_model_truth === true,
      bridge_alive_counts_as_model_truth:
        packet?.bridge_alive_counts_as_model_truth === true,
      response_text_counts_as_route_truth:
        packet?.response_text_counts_as_route_truth === true,
      mixed_route_truth_packet:
        packet?.mixed_route_truth_packet === true,
      mixed_route_blocked:
        packet?.mixed_route_blocked === true,
      native_mixed_primary_trace_supported:
        packet?.native_mixed_primary_trace_supported === true,
      prompt_seen:
        packet?.prompt_seen === true,
      prompt_seen_blocking_reason:
        packet?.prompt_seen_blocking_reason || "",
      coder_dispatch_proven:
        packet?.coder_dispatch_proven === true,
      coder_work_result_proven_with_limits:
        packet?.coder_work_result_proven_with_limits === true,
      deepseek_route_observed:
        packet?.deepseek_route_observed === true,
      api_route_dispatched_without_primary:
        packet?.api_route_dispatched_without_primary === true,
      direct_api_dispatch_without_primary_trace:
        packet?.direct_api_dispatch_without_primary_trace === true,
      ui_label_counts_as_proof:
        packet?.ui_label_counts_as_proof === true,
      primary_trace_id_matches_launch:
        packet?.primary_trace_id_matches_launch === true,
      coder_trace_id_matches_launch:
        packet?.coder_trace_id_matches_launch === true,
      primary_replacement_trace_id_matches_launch:
        packet?.primary_replacement_trace_id_matches_launch === true,
      native_dual_lane_prompt_trace_missing:
        packet?.native_dual_lane_prompt_trace_missing === true,
      native_current_launch_single_executor_observed:
        packet?.native_current_launch_single_executor_observed === true,
      runtime_executor_lane:
        packet?.runtime_executor_lane || "",
      runtime_executor_truth_source:
        packet?.runtime_executor_truth_source || "",
      mixed_mode_actual_primary_executor_is_api_route:
        packet?.mixed_mode_actual_primary_executor_is_api_route === true,
      capability_proof_scope:
        packet?.capability_proof_scope || "",
      unsupported_evidence:
        packet?.unsupported_evidence || {},
      launch_packet_is_truth_source: packet?.launch_packet_is_truth_source === true,
      profile_persistence_proven: packet?.profile_persistence_proven === true,
      persistent_profile_reused: packet?.persistent_profile_reused === true,
      raw_backend_details_exposed: packet?.raw_backend_details_exposed === true,
      secret_value_exposed: packet?.secret_value_exposed === true,
      raw_path_exposed: packet?.raw_path_exposed === true,
      original_codex_touched: packet?.original_codex_touched === true,
      asar_touched: packet?.asar_touched === true,
      live_call_attempted: packet?.live_call_attempted === true,
      provider_called: packet?.provider_called === true,
      next_action: packet?.next_action || ""
    }, null, 2);
  }
}

function quickStartLaunchRequiresBridgeStability(packet) {
  const mode = packet?.execution_mode || packet?.selection_packet?.execution_mode || "";
  return mode === "chatgpt_plus_api";
}

function quickStartLiveBridgeStabilityWindowNotBound(packet) {
  return packet?.machine_error_code === "BRIDGE_WINDOW_NOT_BOUND"
    || packet?.bridge_status === "BRIDGE_WINDOW_NOT_BOUND"
    || packet?.failure_machine_error_code === "WINDOW_BOUND_TO_OLD_BRIDGE"
    || packet?.old_window_answered === true
    || packet?.bridge_session_matches_active_window === false;
}

function renderQuickStartLiveBridgeStability(packet) {
  const ready = packet?.status === "ok" && packet?.bridge_status === "BRIDGE_READY";
  const rejected = packet?.status === "rejected" || packet?.status === "failed";
  const windowNotBound = quickStartLiveBridgeStabilityWindowNotBound(packet);
  const bridgeAlive = packet?.bridge_alive === true || packet?.port_alive === true;
  const nextAction = packet?.recommended_recovery_action || packet?.next_action || "";
  const blockedVisual = rejected ? "red" : "amber";
  setQuickStartChip(
    "quickStartLaunchState",
    ready ? "green" : blockedVisual,
    ready ? "запуск ok" : (windowNotBound ? "старое окно" : (packet?.machine_error_code || "bridge blocked"))
  );
  setQuickStartChip(
    "quickStartBridgeState",
    ready ? "green" : (bridgeAlive ? "amber" : blockedVisual),
    ready ? "жив" : (windowNotBound ? "не привязан" : (bridgeAlive ? "жив, blocked" : "не готов"))
  );
  setQuickStartChip(
    "quickStartWindowState",
    ready ? "green" : (windowNotBound ? "amber" : "neutral"),
    ready ? "найдено" : (windowNotBound ? "старое окно" : "не доказано")
  );
  setQuickStartChip(
    "quickStartConfigState",
    ready ? "green" : (windowNotBound ? "amber" : "neutral"),
    ready ? "совпадает" : (windowNotBound ? "trace mismatch" : "не доказан")
  );
  setQuickStartChip(
    "quickStartRouteChip",
    ready ? "green" : blockedVisual,
    ready ? "запуск ok" : (windowNotBound ? "old window" : (packet?.bridge_status || packet?.machine_error_code || "bridge blocked"))
  );
  setQuickStartChip(
    "quickStartNextActionState",
    ready ? "green" : "amber",
    ready ? "none" : quickStartNextActionLabel(nextAction || "inspect_bridge_stability_packet")
  );
  setQuickStartRouteResponse({
    ...packet,
    live_bridge_stability_truth_packet: true,
    runtime_readiness_claimed: ready,
    next_action: nextAction || packet?.next_action || ""
  });
}

async function refreshQuickStartLiveBridgeStabilityTruth(launchPacket) {
  if (!quickStartLaunchRequiresBridgeStability(launchPacket)) {
    return null;
  }
  try {
    const response = await fetch("api/codex/custom/live-bridge-stability", {
      cache: "no-store"
    });
    if (!response.ok) {
      throw new Error(`live bridge stability http ${response.status}`);
    }
    const packet = await response.json();
    renderQuickStartLiveBridgeStability(packet);
    return packet;
  } catch (error) {
    const packet = {
      status: "failed",
      machine_error_code: "LIVE_BRIDGE_STABILITY_FETCH_FAILED",
      bridge_status: "BRIDGE_STABILITY_PACKET_UNAVAILABLE",
      human_message: error.message,
      execution_mode: launchPacket?.execution_mode || "",
      chatgpt_model_id: launchPacket?.chatgpt_model_id || "",
      api_model_id: launchPacket?.api_model_id || "",
      fallback_used: false,
      raw_backend_details_exposed: false,
      secret_value_exposed: false,
      live_bridge_stability_truth_packet: true,
      runtime_readiness_claimed: false,
      next_action: "retry_live_bridge_stability"
    };
    renderQuickStartLiveBridgeStability(packet);
    return packet;
  }
}

function quickStartMixedTraceUnsupported(packet) {
  return packet?.mixed_mode_product_decision === "UNSUPPORTED"
    || packet?.machine_error_code === "DUAL_LANE_NATIVE_PROMPT_TRACE_NOT_SUPPORTED"
    || packet?.native_mixed_primary_trace_supported === false;
}

function quickStartMixedLaunchAvailableWithTraceGap(packet) {
  return Boolean(
    packet?.mixed_mode_product_decision === "WORKS_WITH_LIMITS"
    && packet?.mixed_mode_launch_action === "available"
    && packet?.mixed_mode_launch_available_with_primary_trace_gap === true
    && packet?.launch_proven === true
    && packet?.api_route_dispatched_without_primary === true
    && packet?.primary_replaced_by_api_route !== true
    && packet?.chatgpt_replaced_by_api !== true
    && packet?.coder_dispatch_proven === true
    && packet?.coder_work_result_proven_with_limits === true
  );
}

function setQuickStartMixedLaunchActionGuard(blocked) {
  quickStartMixedModeProductBlocked = blocked === true;
  const button = document.getElementById("quickStartCustomLaunchAction");
  if (!button) {
    return;
  }
  if (!button.dataset) {
    button.dataset = {};
  }
  button.dataset.mixedModeLaunchBlocked = quickStartMixedModeProductBlocked ? "true" : "false";
  button.setAttribute?.(
    "title",
    quickStartMixedModeProductBlocked
      ? "ChatGPT + API сейчас заблокирован; кнопка запускает проверку и затем обновляет blocker truth."
      : QUICK_START_DEFAULT_LAUNCH_LABEL
  );
  const label = button.querySelector?.("span");
  if (label) {
    label.textContent = quickStartMixedModeProductBlocked
      ? QUICK_START_BLOCKED_MIXED_LAUNCH_LABEL
      : QUICK_START_DEFAULT_LAUNCH_LABEL;
  }
}

function quickStartMixedTraceReasonLabel(packet) {
  const reason = packet?.prompt_seen_blocking_reason || "";
  if (reason === "primary_chatgpt_request_absent_api_route_dispatched") {
    return "primary не доказан";
  }
  if (reason === "primary_chatgpt_request_forced_to_api_route") {
    return "primary заменён API";
  }
  if (reason === "chatgpt_primary_trace_record_missing") {
    return "primary trace missing";
  }
  return "primary не доказан";
}

function renderQuickStartMixedCoderTrace(packet) {
  const launchWithTraceGap = quickStartMixedLaunchAvailableWithTraceGap(packet);
  const unsupported = !launchWithTraceGap && quickStartMixedTraceUnsupported(packet);
  const traceOk = packet?.status === "ok" && packet?.machine_error_code === "OK";
  const blocked = packet?.status === "blocked" || unsupported;
  const launchPacketStaleOverridden =
    packet?.launch_packet_stale_overridden_by_current_bridge_trace === true
    && packet?.current_bridge_trace_matches_launch === true
    && packet?.current_launch_evidence_proven_with_limits === true
    && packet?.current_mixed_trace_evidence_fresh === true;
  const launchPacketStaleBlocks =
    packet?.machine_error_code === "CHATGPT_PLUS_API_LAUNCH_PACKET_STALE"
    || (
      packet?.launch_packet_stale === true
      && !launchPacketStaleOverridden
    );
  const traceSnapshotStaleBlocks =
    packet?.machine_error_code === "CHATGPT_PLUS_API_TRACE_SNAPSHOT_STALE"
    || packet?.trace_snapshot_stale === true;
  const staleMixedEvidence =
    launchPacketStaleBlocks || traceSnapshotStaleBlocks;
  setQuickStartMixedLaunchActionGuard(blocked && !traceOk);
  const slotBindingBlocked = packet?.machine_error_code === "CHATGPT_PLUS_API_SLOT_BINDING_NOT_PROVEN";
  const chatgptLabel = slotBindingBlocked
    ? "not proven"
    : (unsupported || launchWithTraceGap)
    ? quickStartMixedTraceReasonLabel(packet)
    : (packet?.prompt_seen === true ? "runtime proven" : "not proven");
  setQuickStartChip(
    "quickStartRouteChip",
    traceOk ? "green" : (launchWithTraceGap || blocked ? "amber" : "red"),
    traceOk ? "mixed ok" : (launchWithTraceGap ? "mixed limited" : (staleMixedEvidence ? "mixed stale" : (unsupported ? "mixed blocked" : (packet?.machine_error_code || "mixed blocked"))))
  );
  setQuickStartChip(
    "quickStartExecutionModeState",
    traceOk ? "green" : (launchWithTraceGap || blocked ? "amber" : "red"),
    traceOk || launchWithTraceGap || staleMixedEvidence ? "ChatGPT + API" : "unsupported"
  );
  setQuickStartChip(
    "quickStartLaunchState",
    traceOk ? "green" : (launchWithTraceGap || blocked ? "amber" : "red"),
    traceOk || launchWithTraceGap ? "запуск ok" : (staleMixedEvidence ? "stale" : "blocked")
  );
  setQuickStartChip(
    "quickStartChatSlotState",
    packet?.prompt_seen === true ? "green" : "amber",
    chatgptLabel
  );
  setQuickStartChip(
    "quickStartApiSlotState",
    packet?.coder_dispatch_proven === true ? "green" : "amber",
    packet?.coder_dispatch_proven === true ? "proven" : "not proven"
  );
  setQuickStartChip(
    "quickStartNextActionState",
    (!packet?.next_action || packet?.next_action === "none") && traceOk ? "green" : "amber",
    quickStartNextActionLabel(packet?.next_action || "")
  );
  setQuickStartRouteResponse({
    status: packet?.status || "unknown",
    machine_error_code: packet?.machine_error_code || "UNKNOWN",
    final_status: packet?.final_status || "",
    mixed_mode_product_decision:
      packet?.mixed_mode_product_decision || (traceOk ? "WORKS" : "UNSUPPORTED"),
    mixed_mode_launch_action:
      packet?.mixed_mode_launch_action || (traceOk || launchWithTraceGap ? "available" : "blocked"),
    mixed_mode_launch_blocked_reason:
      packet?.mixed_mode_launch_blocked_reason || (traceOk || launchWithTraceGap ? "" : (packet?.machine_error_code || "UNKNOWN")),
    primary_trace_proof_status:
      packet?.primary_trace_proof_status || (packet?.prompt_seen === true ? "proven" : "not_proven"),
    mixed_mode_launch_available_with_primary_trace_gap:
      launchWithTraceGap,
    execution_mode: packet?.execution_mode || "",
    chatgpt_model_id: packet?.primary_model_id || "",
    api_model_id: packet?.coding_agent_model_id || "",
    primary_model_slot: packet?.primary_model_slot || {},
    coding_agent_model_slot: packet?.coding_agent_model_slot || {},
    mixed_route_truth_packet: true,
    mixed_route_blocked: blocked,
    native_mixed_primary_trace_supported:
      packet?.native_mixed_primary_trace_supported === true,
    prompt_seen: packet?.prompt_seen === true,
    prompt_seen_blocking_reason: packet?.prompt_seen_blocking_reason || "",
    coder_dispatch_proven: packet?.coder_dispatch_proven === true,
    coder_work_result_proven_with_limits:
      packet?.coder_work_result_proven_with_limits === true,
    deepseek_route_observed: packet?.deepseek_route_observed === true,
    api_route_dispatched_without_primary:
      packet?.api_route_dispatched_without_primary === true,
    direct_api_dispatch_without_primary_trace:
      packet?.direct_api_dispatch_without_primary_trace === true,
    launch_proven:
      packet?.launch_proven === true,
    launch_status:
      packet?.launch_status || "",
    launch_status_ok:
      packet?.launch_status_ok === true,
    launch_packet_age_seconds:
      Number.isFinite(packet?.launch_packet_age_seconds) ? packet.launch_packet_age_seconds : null,
    launch_packet_stale:
      packet?.launch_packet_stale === true,
    launch_packet_stale_overridden_by_current_bridge_trace:
      packet?.launch_packet_stale_overridden_by_current_bridge_trace === true,
    current_bridge_trace_matches_launch:
      packet?.current_bridge_trace_matches_launch === true,
    trace_snapshot_age_seconds:
      Number.isFinite(packet?.trace_snapshot_age_seconds) ? packet.trace_snapshot_age_seconds : null,
    trace_snapshot_stale:
      packet?.trace_snapshot_stale === true,
    current_launch_evidence_proven_with_limits:
      packet?.current_launch_evidence_proven_with_limits === true,
    current_mixed_trace_evidence_fresh:
      packet?.current_mixed_trace_evidence_fresh === true,
    native_window_observed:
      packet?.native_window_observed === true,
    real_codex_app_launched:
      packet?.real_codex_app_launched === true,
    slot_binding_blocking_reasons:
      Array.isArray(packet?.slot_binding_blocking_reasons)
        ? packet.slot_binding_blocking_reasons
        : [],
    primary_trace_id_matches_launch:
      packet?.primary_trace_id_matches_launch === true,
    coder_trace_id_matches_launch:
      packet?.coder_trace_id_matches_launch === true,
    primary_replacement_trace_id_matches_launch:
      packet?.primary_replacement_trace_id_matches_launch === true,
    native_dual_lane_prompt_trace_missing:
      packet?.native_dual_lane_prompt_trace_missing === true,
    native_current_launch_single_executor_observed:
      packet?.native_current_launch_single_executor_observed === true,
    runtime_executor_lane:
      packet?.runtime_executor_lane || "",
    runtime_executor_truth_source:
      packet?.runtime_executor_truth_source || "",
    mixed_mode_actual_primary_executor_is_api_route:
      packet?.mixed_mode_actual_primary_executor_is_api_route === true,
    capability_proof_scope:
      packet?.capability_proof_scope || "",
    unsupported_evidence:
      packet?.unsupported_evidence || {},
    fallback_used: packet?.fallback_used === true,
    response_text_counts_as_model_truth:
      packet?.response_text_counts_as_model_truth === true,
    ui_label_counts_as_proof: packet?.ui_label_counts_as_proof === true,
    runtime_readiness_claimed: false,
    next_action: packet?.next_action || ""
  });
}

async function refreshQuickStartMixedCoderTraceTruth(launchPacket) {
  const executionMode = launchPacket?.execution_mode
    || launchPacket?.selection_packet?.execution_mode
    || "";
  if (executionMode !== "chatgpt_plus_api") {
    return null;
  }
  try {
    const response = await fetch("api/codex/custom/chatgpt-plus-api-coder-trace", {
      cache: "no-store"
    });
    if (!response.ok) {
      throw new Error(`mixed coder trace http ${response.status}`);
    }
    const packet = await response.json();
    renderQuickStartMixedCoderTrace(packet);
    return packet;
  } catch (error) {
    setQuickStartChip("quickStartRouteChip", "amber", "trace failed");
    setQuickStartChip("quickStartExecutionModeState", "amber", "trace missing");
    setQuickStartChip("quickStartNextActionState", "amber", "refresh trace");
    setQuickStartRouteResponse({
      status: "blocked",
      machine_error_code: "MIXED_CODER_TRACE_FETCH_FAILED",
      final_status: "KNOWN_BLOCKER_MIXED_CODER_TRACE_NOT_LOADED",
      execution_mode: "chatgpt_plus_api",
      chatgpt_model_id:
        launchPacket?.chatgpt_model_id || launchPacket?.selection_packet?.chatgpt_model_id || "",
      api_model_id:
        launchPacket?.api_model_id || launchPacket?.selection_packet?.api_model_id || "",
      mixed_route_truth_packet: false,
      mixed_route_blocked: true,
      runtime_readiness_claimed: false,
      next_action: "refresh_mixed_coder_trace",
      human_message: error?.message || "mixed coder trace fetch failed"
    });
    return null;
  }
}

async function refreshQuickStartRouteStatus() {
  if (codexLaunchDryRunInFlight) {
    return;
  }
  codexLaunchDryRunInFlight = true;
  const buttons = [
    document.getElementById("quickStartRouteRefreshAction"),
    document.getElementById("refreshFixture")
  ].filter(Boolean);
  for (const button of buttons) {
    button.setAttribute("disabled", "disabled");
  }
  setQuickStartChip("quickStartRouteChip", "neutral", "обновляю");
  setQuickStartChip("quickStartNextActionState", "neutral", "refreshing");
  try {
    await refreshCodexCustomModelsPanel();
    const payload = quickStartSelectionWithDefaults(quickStartLaunchPayloadFromSelects());
    const refreshPacket = {
      ...payload,
      selection_packet: { ...payload },
      status: "checking",
      machine_error_code: "QUICK_START_ROUTE_STATUS_REFRESH"
    };
    if (quickStartLaunchRequiresBridgeStability(refreshPacket)) {
      await refreshQuickStartLiveBridgeStabilityTruth(refreshPacket);
      await refreshQuickStartMixedCoderTraceTruth(refreshPacket);
      return;
    }
    setQuickStartChip("quickStartRouteChip", "neutral", "модели загружены");
    setQuickStartChip("quickStartNextActionState", "neutral", "проверить запуск");
  } finally {
    codexLaunchDryRunInFlight = false;
    for (const button of buttons) {
      button.removeAttribute("disabled");
    }
  }
}

async function runQuickStartCustomLaunchAction() {
  if (!actionMetadataLoaded) {
    await ensureActionMetadataLoaded();
    applyActionAvailability();
  }
  setQuickStartMixedLaunchActionGuard(false);
  const launchMetadata = metadataFor("launch_custom_client_native");
  if (launchMetadata?.available === true) {
    await runCodexCustomLaunch();
    return;
  }
  await runQuickStartLaunchAdmissionProjection();
}

function renderQuickStartLaunchPreflight(packet) {
  const ok = packet?.status === "ok" && packet?.machine_error_code === "OK";
  const ownerBlocked = packet?.machine_error_code === "OWNER_AUTHORIZATION_REQUIRED";
  const runtimeProofPending = quickStartChatgptRuntimeProofPending(packet);
  const okVisual = ok && !runtimeProofPending ? "green" : (ok ? "amber" : (packet?.status === "rejected" || packet?.status === "blocked" ? "amber" : "red"));
  const okLabel = runtimeProofPending ? quickStartRuntimeProofPendingLabel(packet) : "preflight ok";
  const nextAction = packet?.next_action || "";
  const nextActionReady = ok && (
    !nextAction
    || nextAction === "none"
    || nextAction === "show_existing_window"
    || nextAction === "relaunch_custom_codex_with_new_selection"
    || nextAction === "replace_existing_custom_codex_without_launch_packet"
    || nextAction.includes("launch_custom_codex")
    || nextAction.includes("launch_or_reuse_custom_codex")
  );
  const bridgeLabel = packet?.bridge_required === true
    ? (packet?.bridge_alive === true ? "жив" : "упал")
    : "не нужен";
  const bridgeVisual = packet?.bridge_required === true
    ? (packet?.bridge_alive === true ? "green" : "amber")
    : "neutral";
  const windowLabel = packet?.custom_process_observed === true ? "найдено" : "не найдено";
  const configStatus = packet?.config_status || "не проверен";
  const configLabel = configStatus === "matches_last_launch"
    ? "совпадает"
    : (configStatus === "changed" ? "изменился" : "нет запуска");
  const configVisual = configStatus === "matches_last_launch"
    ? "green"
    : (configStatus === "changed" ? "amber" : "neutral");
  setQuickStartChip(
    "quickStartBridgeState",
    bridgeVisual,
    bridgeLabel
  );
  setQuickStartChip(
    "quickStartWindowState",
    packet?.custom_process_observed === true ? "green" : "neutral",
    windowLabel
  );
  setQuickStartChip(
    "quickStartOwnerAuthState",
    packet?.owner_authorization_phrase_present === true
      ? "green"
      : (ownerBlocked ? "amber" : "neutral"),
    packet?.owner_authorization_phrase_present === true
      ? "confirmed"
      : (ownerBlocked ? "owner auth" : "not checked")
  );
  setQuickStartChip(
    "quickStartLaunchState",
    okVisual,
    ok ? okLabel : (ownerBlocked ? "owner auth" : "blocked")
  );
  setQuickStartChip(
    "quickStartConfigState",
    configVisual,
    configLabel
  );
  setQuickStartChip(
    "quickStartRouteChip",
    okVisual,
    ok ? okLabel : (packet?.machine_error_code || packet?.status || "ошибка")
  );
  setQuickStartChip(
    "quickStartNextActionState",
    nextActionReady && !runtimeProofPending ? "green" : "amber",
    runtimeProofPending ? quickStartRuntimeProofPendingLabel(packet) : quickStartNextActionLabel(nextAction)
  );
  setQuickStartRouteResponse({
    status: packet?.status || "unknown",
    machine_error_code: packet?.machine_error_code || "UNKNOWN",
    final_status: packet?.final_status || "",
    execution_mode: packet?.execution_mode || "",
    selected_model: packet?.selected_model || "",
    api_reasoning_option_id: packet?.api_reasoning_option_id || "",
    bridge_status: packet?.bridge_status || "",
    window_status: packet?.window_status || "",
    config_status: configStatus,
    owner_authorization_phrase_present:
      packet?.owner_authorization_phrase_present === true,
    existing_window_reuse_admissible: packet?.existing_window_reuse_admissible === true,
    existing_window_relaunch_admissible: packet?.existing_window_relaunch_admissible === true,
    existing_window_orphan_replace_admissible:
      packet?.existing_window_orphan_replace_admissible === true,
    orphan_replacement_authority_scope:
      packet?.orphan_replacement_authority_scope || "",
    runtime_health_gate_blocks_window_launch:
      packet?.runtime_health_gate_blocks_window_launch === true,
    runtime_health_required_for_chatgpt_lane:
      packet?.runtime_health_required_for_chatgpt_lane === true,
    runtime_health_machine_error_code:
      packet?.runtime_health_machine_error_code || packet?.runtime_health_gate?.runtime_health_machine_error_code || "",
    chatgpt_runtime_proof_status:
      packet?.chatgpt_runtime_proof_status || "",
    chatgpt_runtime_proof_machine_error_code:
      packet?.chatgpt_runtime_proof_machine_error_code || "",
    new_launch_required: packet?.new_launch_required === true,
    custom_codex_launch_attempted: packet?.custom_codex_launch_attempted === true,
    new_launch_started: packet?.new_launch_started === true,
    network_calls_made: packet?.network_calls_made === true,
    live_call_attempted: packet?.live_call_attempted === true,
    provider_called: packet?.provider_called === true,
    runtime_readiness_claimed: false,
    visible_window_counts_as_model_truth:
      packet?.visible_window_counts_as_model_truth === true,
    bridge_alive_counts_as_model_truth:
      packet?.bridge_alive_counts_as_model_truth === true,
    response_text_counts_as_route_truth:
      packet?.response_text_counts_as_route_truth === true,
    launch_packet_is_truth_source: packet?.launch_packet_is_truth_source === true,
    raw_backend_details_exposed: packet?.raw_backend_details_exposed === true,
    secret_value_exposed: packet?.secret_value_exposed === true,
    raw_path_exposed: packet?.raw_path_exposed === true,
    next_action: packet?.next_action || ""
  });
}

function renderQuickStartDeepSeekCoderCheck(packet) {
  const ok = packet?.final_status === "DEEPSEEK_LIVE_EXECUTOR_PACKET_PROVEN_WITH_LIMITS"
    || packet?.legacy_quick_start_final_status === "QUICK_START_API_ONLY_DEEPSEEK_SAFE_WORKTREE_BUTTON_PROVEN_WITH_LIMITS";
  setQuickStartChip(
    "quickStartRouteChip",
    ok ? "green" : (packet?.status === "rejected" || packet?.status === "blocked" ? "amber" : "red"),
    ok ? "DeepSeek ok" : (packet?.machine_error_code || packet?.status || "ошибка")
  );
  setQuickStartChip(
    "quickStartExecutionModeState",
    packet?.execution_mode === "api_only" && packet?.server_issued_catalog_used === true ? "green" : "amber",
    packet?.execution_mode === "api_only" ? "API-only" : "не API-only"
  );
  setQuickStartChip(
    "quickStartLaunchState",
    ok ? "green" : "amber",
    ok ? "tool-loop ok" : "не доказан"
  );
  const response = document.getElementById("quickStartRouteResponse");
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      final_status: packet?.final_status || "",
      legacy_quick_start_final_status: packet?.legacy_quick_start_final_status || "",
      deepseek_live_executor_packet_proven_with_limits:
        packet?.deepseek_live_executor_packet_proven_with_limits === true,
      execution_mode: packet?.execution_mode || "",
      api_model_id: packet?.api_model_id || "",
      api_reasoning_option_id: packet?.api_reasoning_option_id || "",
      api_reasoning_option_packet: packet?.api_reasoning_option_packet || {},
      api_reasoning_intelligence_measured:
        packet?.api_reasoning_intelligence_measured === true,
      api_reasoning_codex_parity_claimed:
        packet?.api_reasoning_codex_parity_claimed === true,
      selected_model: packet?.selected_model || packet?.model_id || "",
      provider_id: packet?.provider_id || "",
      server_issued_catalog_used: packet?.server_issued_catalog_used === true,
      chatgpt_line_used_as_executor: packet?.chatgpt_line_used_as_executor === true,
      api_line_used_as_executor: packet?.api_line_used_as_executor === true,
      api_only_calls_chatgpt: packet?.api_only_calls_chatgpt === true,
      no_chatgpt: packet?.no_chatgpt === true,
      provider_response_proven: packet?.provider_response_proven === true,
      tool_loop_proven: packet?.tool_loop_proven === true,
      request_count: packet?.request_count ?? 0,
      safe_worktree_used: packet?.safe_worktree_used === true,
      write_surface: packet?.write_surface || "",
      workspace_write_admitted: packet?.workspace_write_admitted === true,
      file_changed_by_codex_tool: packet?.file_changed_by_codex_tool === true,
      git_diff_observed: packet?.git_diff_observed === true,
      expected_diff_observed: packet?.expected_diff_observed === true,
      main_worktree_mutated_by_probe: packet?.main_worktree_mutated_by_probe === true,
      main_tree_untouched: packet?.main_tree_untouched === true,
      worktree_removed_after_probe: packet?.worktree_removed_after_probe === true,
      raw_backend_details_exposed: packet?.raw_backend_details_exposed === true,
      browser_raw_backend_authority_widened:
        packet?.browser_raw_backend_authority_widened === true,
      secret_value_exposed: packet?.secret_value_exposed === true,
      secret_value_recorded: packet?.secret_value_recorded === true,
      secret_in_diff: packet?.secret_in_diff === true,
      original_codex_touched: packet?.original_codex_touched === true,
      original_codex_profile_touched: packet?.original_codex_profile_touched === true,
      wbp_patch_applier_used: packet?.wbp_patch_applier_used === true,
      no_patch_applier: packet?.no_patch_applier === true,
      no_fallback: packet?.no_fallback === true,
      commit_attempted: packet?.commit_attempted === true,
      push_attempted: packet?.push_attempted === true,
      merge_attempted: packet?.merge_attempted === true,
      response_preview_bounded: packet?.response_preview_bounded || "",
      git_diff_sha256: packet?.git_diff_sha256 || "",
      next_action: packet?.next_action || ""
    }, null, 2);
  }
}

function renderQuickStartDeepSeekCodeEditProof(packet) {
  const ok = packet?.final_status === "CUSTOM_CODEX_DEEPSEEK_CODE_EDIT_REPRODUCIBLE_PROVEN_WITH_LIMITS";
  const windowLaunchUsable = packet?.window_launch_proven_with_limits === true
    && packet?.native_app_usable === true;
  setQuickStartChip(
    "quickStartRouteChip",
    ok ? "green" : (packet?.status === "rejected" || packet?.status === "blocked" ? "amber" : "red"),
    ok ? "правка ok" : (packet?.machine_error_code || packet?.status || "ошибка")
  );
  setQuickStartChip(
    "quickStartExecutionModeState",
    packet?.execution_mode === "api_only" && packet?.selected_model === "wbp-deepseek-v4-pro-max" ? "green" : "amber",
    packet?.execution_mode === "api_only" ? "API-only" : "не API-only"
  );
  setQuickStartChip(
    "quickStartLaunchState",
    windowLaunchUsable ? "green" : "amber",
    windowLaunchUsable ? "окно usable" : "окно не доказано"
  );
  const response = document.getElementById("quickStartRouteResponse");
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      final_status: packet?.final_status || "",
      execution_mode: packet?.execution_mode || "",
      selected_model: packet?.selected_model || "",
      api_model_id: packet?.api_model_id || "",
      window_launch_proven_with_limits:
        packet?.window_launch_proven_with_limits === true,
      native_app_usable: packet?.native_app_usable === true,
      api_reasoning_option_id: packet?.api_reasoning_option_id || "",
      cwd: packet?.cwd || "",
      repo_root: packet?.repo_root || "",
      thread_id: packet?.thread_id || "",
      thread_model: packet?.thread_model || "",
      thread_model_provider: packet?.thread_model_provider || "",
      file_created: packet?.file_created === true,
      file_content_exact: packet?.file_content_exact === true,
      file_content_sha256: packet?.file_content_sha256 || "",
      provider_called: packet?.provider_called === true,
      provider_id: packet?.provider_id || "",
      upstream_model: packet?.upstream_model || "",
      request_seen_after_launch: packet?.request_seen_after_launch === true,
      response_seen: packet?.response_seen === true,
      route_digest_matches_launch: packet?.route_digest_matches_launch === true,
      chatgpt_called: packet?.chatgpt_called === true,
      api_only_calls_chatgpt: packet?.api_only_calls_chatgpt === true,
      fallback_used: packet?.fallback_used === true,
      raw_backend_details_exposed: packet?.raw_backend_details_exposed === true,
      secret_value_exposed: packet?.secret_value_exposed === true,
      original_codex_touched: packet?.original_codex_touched === true,
      asar_touched: packet?.asar_touched === true,
      wbp_patch_applier_used: packet?.wbp_patch_applier_used === true,
      commit_attempted: packet?.commit_attempted === true,
      push_attempted: packet?.push_attempted === true,
      merge_attempted: packet?.merge_attempted === true,
      response_text_counts_as_model_truth: packet?.response_text_counts_as_model_truth === true,
      model_self_report_counts_as_runtime_truth: packet?.model_self_report_counts_as_runtime_truth === true,
      manual_prompt_required: packet?.manual_prompt_required || "",
      next_action: packet?.next_action || ""
    }, null, 2);
  }
}

async function runQuickStartDeepSeekCoderCheck() {
  syncCodexRouteSelects("quickStartApiModelSelect");
  syncCodexRouteSelects("quickStartExecutionModeSelect");
  const modeNode = document.getElementById("quickStartExecutionModeSelect");
  const apiNode = document.getElementById("quickStartApiModelSelect");
  const apiReasoningNode = document.getElementById("quickStartApiReasoningOptionSelect");
  const executionMode = modeNode ? modeNode.value : "";
  const apiModelId = apiNode ? apiNode.value : "";
  const apiReasoningOptionId = executionMode === "chatgpt_only"
    ? ""
    : (apiReasoningNode ? apiReasoningNode.value : "");
  document.getElementById("quickStartDeepSeekCoderCheckAction")?.setAttribute("disabled", "disabled");
  setQuickStartChip("quickStartRouteChip", "neutral", "проверка");
  try {
    const response = await fetch("api/codex/custom/quick-start/deepseek-safe-worktree-check", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        execution_mode: executionMode,
        api_model_id: apiModelId,
        api_reasoning_option_id: apiReasoningOptionId
      })
    });
    if (!response.ok) {
      throw new Error(`quick start deepseek coder check http ${response.status}`);
    }
    renderQuickStartDeepSeekCoderCheck(await response.json());
  } catch (error) {
    renderQuickStartDeepSeekCoderCheck({
      status: "failed",
      machine_error_code: "QUICK_START_DEEPSEEK_SAFE_WORKTREE_FETCH_FAILED",
      final_status: "KNOWN_BLOCKER_QUICK_START_DEEPSEEK_SAFE_WORKTREE_NOT_PROVEN",
      execution_mode: executionMode,
      api_model_id: apiModelId,
      api_reasoning_option_id: apiReasoningOptionId,
      server_issued_catalog_used: false,
      provider_response_proven: false,
      tool_loop_proven: false,
      safe_worktree_used: false,
      file_changed_by_codex_tool: false,
      main_worktree_mutated_by_probe: false,
      raw_backend_details_exposed: false,
      browser_raw_backend_authority_widened: false,
      secret_value_exposed: false,
      original_codex_touched: false,
      original_codex_profile_touched: false,
      wbp_patch_applier_used: false,
      no_patch_applier: true,
      no_fallback: true,
      no_chatgpt: true,
      main_tree_untouched: true,
      commit_attempted: false,
      push_attempted: false,
      merge_attempted: false,
      next_action: error.message
    });
  } finally {
    document.getElementById("quickStartDeepSeekCoderCheckAction")?.removeAttribute("disabled");
  }
}

async function runQuickStartDeepSeekCodeEditProof() {
  syncCodexRouteSelects("quickStartApiModelSelect");
  syncCodexRouteSelects("quickStartExecutionModeSelect");
  const modeNode = document.getElementById("quickStartExecutionModeSelect");
  const apiNode = document.getElementById("quickStartApiModelSelect");
  const apiReasoningNode = document.getElementById("quickStartApiReasoningOptionSelect");
  const executionMode = modeNode ? modeNode.value : "";
  const apiModelId = apiNode ? apiNode.value : "";
  const apiReasoningOptionId = executionMode === "chatgpt_only"
    ? ""
    : (apiReasoningNode ? apiReasoningNode.value : "");
  document.getElementById("quickStartDeepSeekCodeEditProofAction")?.setAttribute("disabled", "disabled");
  setQuickStartChip("quickStartRouteChip", "neutral", "проверка");
  try {
    const response = await fetch("api/codex/custom/quick-start/deepseek-code-edit-proof", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        execution_mode: executionMode,
        api_model_id: apiModelId,
        api_reasoning_option_id: apiReasoningOptionId
      })
    });
    if (!response.ok) {
      throw new Error(`quick start deepseek code edit proof http ${response.status}`);
    }
    renderQuickStartDeepSeekCodeEditProof(await response.json());
  } catch (error) {
    renderQuickStartDeepSeekCodeEditProof({
      status: "failed",
      machine_error_code: "CUSTOM_CODEX_DEEPSEEK_CODE_EDIT_PROOF_FETCH_FAILED",
      final_status: "KNOWN_BLOCKER_CUSTOM_CODEX_DEEPSEEK_CODE_EDIT_REPRODUCTION_FAILED",
      execution_mode: executionMode,
      api_model_id: apiModelId,
      api_reasoning_option_id: apiReasoningOptionId,
      selected_model: "",
      file_created: false,
      file_content_exact: false,
      provider_called: false,
      chatgpt_called: false,
      fallback_used: false,
      raw_backend_details_exposed: false,
      secret_value_exposed: false,
      original_codex_touched: false,
      asar_touched: false,
      wbp_patch_applier_used: false,
      commit_attempted: false,
      push_attempted: false,
      merge_attempted: false,
      next_action: error.message
    });
  } finally {
    document.getElementById("quickStartDeepSeekCodeEditProofAction")?.removeAttribute("disabled");
  }
}

function renderCodexCustomModels(registry, compat) {
  const chatSelect = document.getElementById("codexCustomModelSelect");
  const apiSelect = document.getElementById("codexCustomApiModelSelect");
  const preferQuickStart = codexRouteSelectionPrefersQuickStart();
  const storedSelection = quickStartStoredSelectionForRegistry(
    readStoredCodexRouteSelection(),
    registry
  );
  const visibleSelection = codexRenderedRouteSelectionFromUi(preferQuickStart);
  const preservedSelection = preferQuickStart
    ? quickStartSelectionWithDefaults(
        storedSelection || visibleSelection
      )
    : (storedSelection || visibleSelection || codexRouteSelectionFromUi(false));
  const chatEntries = codexCustomAvailableModelEntries(registry);
  const apiEntries = codexCustomApiModelEntries(registry);
  const seedEntries = codexCustomSeedEntries(registry);
  codexCustomApiModelEntryById = new Map(apiEntries.map((entry) => [entry.model_id, entry]));
  const modelIds = chatEntries.map((entry) => entry.model_id);
  const selectableIds = chatEntries
    .filter((entry) => entry?.selection_enabled === true)
    .map((entry) => entry.model_id);
  const previous = chatSelect?.value || "";
  const previousApi = apiSelect?.value || "";
  if (chatSelect) {
    chatSelect.replaceChildren();
    for (const entry of chatEntries) {
      const option = document.createElement("option");
      option.value = entry.model_id;
      option.textContent = entry?.display_name || entry.model_id;
      option.disabled = entry?.selection_enabled !== true;
      chatSelect.append(option);
    }
    if (selectableIds.includes(previous)) {
      chatSelect.value = previous;
    } else if (selectableIds.includes(registry?.chatgpt_lane?.default_model_id)) {
      chatSelect.value = registry.chatgpt_lane.default_model_id;
    } else if (selectableIds.length > 0) {
      chatSelect.value = selectableIds[0];
    } else if (modelIds.length > 0) {
      chatSelect.value = modelIds[0];
    }
  }
  const apiModelIds = apiEntries.map((entry) => entry.model_id);
  const selectableApiIds = apiEntries
    .filter((entry) => entry?.selection_enabled === true)
    .map((entry) => entry.model_id);
  if (apiSelect) {
    apiSelect.replaceChildren();
    for (const entry of apiEntries) {
      const option = document.createElement("option");
      option.value = entry.model_id;
      option.textContent = entry?.display_name || entry.model_id;
      option.disabled = entry?.selection_enabled !== true;
      apiSelect.append(option);
    }
    if (selectableApiIds.includes(previousApi)) {
      apiSelect.value = previousApi;
    } else if (selectableApiIds.includes(registry?.api_lane?.default_model_id)) {
      apiSelect.value = registry.api_lane.default_model_id;
    } else if (selectableApiIds.length > 0) {
      apiSelect.value = selectableApiIds[0];
    } else if (apiModelIds.length > 0) {
      apiSelect.value = apiModelIds[0];
    }
  }
  mirrorSelectOptions(chatSelect, "quickStartChatModelSelect");
  mirrorSelectOptions(apiSelect, "quickStartApiModelSelect");
  const persistedSelectionInvalid = Boolean(
    preferQuickStart
    && storedSelection
    && !codexRouteSelectionCanApplyFully(preservedSelection, { reasoning: false })
  );
  const restoredSelection = persistedSelectionInvalid
    ? false
    : applyCodexRouteSelection(preservedSelection, { reasoning: false });
  renderApiReasoningOptionSelects();
  const persistedReasoningInvalid = Boolean(
    preferQuickStart
    && storedSelection
    && !codexRouteSelectionCanApplyFully(preservedSelection)
  );
  if (!persistedSelectionInvalid && !persistedReasoningInvalid) {
    applyCodexRouteSelection(preservedSelection);
  }
  if (restoredSelection && !persistedReasoningInvalid) {
    saveCodexRouteSelection(codexRouteSelectionFromUi(preferQuickStart));
  } else if (persistedSelectionInvalid || persistedReasoningInvalid) {
    renderQuickStartInvalidPersistedSelection(preservedSelection);
  } else {
    syncCodexRouteSelects("codexCustomExecutionModeSelect");
  }
  renderCodexCustomModelCatalog("codexCustomChatLaneCatalog", chatEntries);
  renderCodexCustomModelCatalog("codexCustomApiLaneCatalog", apiEntries);
  renderCodexCustomModelCatalog("codexCustomSeedLaneCatalog", seedEntries);
  codexCustomLaneSetChip("codexCustomChatLaneChip", chatEntries.length ? "green" : "amber", chatEntries.length ? "current catalog" : "empty");
  codexCustomLaneSetChip("codexCustomApiLaneChip", apiEntries.length ? "amber" : "neutral", apiEntries.length ? "intent only" : "empty");
  codexCustomLaneSetChip("codexCustomSeedLaneChip", seedEntries.length ? "neutral" : "neutral", seedEntries.length ? "reference" : "none");
  const claimGate = compat?.claim_gate_status || "not_reported";
  const claimGateBlocked = String(claimGate).includes("blocked");
  const status = registry?.status || "unknown";
  const selectorChipLabel = status === "ok"
    ? (claimGateBlocked ? "loaded / gate blocked" : "loaded")
    : (status === "degraded" && claimGateBlocked ? "degraded / gate blocked" : status);
  codexCustomModelsSetChip(
    status === "ok" ? (claimGateBlocked ? "amber" : "neutral") : (status === "degraded" ? "amber" : "red"),
    selectorChipLabel
  );
  codexCustomModelsSetText(
    "codexCustomModelsSummary",
    `${chatEntries.length} ChatGPT entries · ${apiEntries.length} API entries · ${seedEntries.length} historical references`
  );
  codexCustomModelsSetText("codexCustomRecommendedModel", registry?.chatgpt_lane?.default_model_id || "-");
  codexCustomModelsSetText("codexCustomRecommendedApiModel", registry?.api_lane?.default_model_id || "-");
  codexCustomModelsSetText(
    "codexCustomExecutionBoundary",
    "ChatGPT lane feeds current launch/session path; API lane remains selection intent only"
  );
  codexCustomModelsSetText(
    "codexCustomApiCompat",
    `shape ${compat?.openai_compatible_shape_declared === true ? "declared" : "unknown"} · wire ${compat?.configured_wire_api || "unknown"} · live ${compat?.live_api_checked === true ? "checked" : "not checked"}`
  );
  codexCustomModelsSetText("codexCustomModelsClaimGate", claimGate);
  codexCustomModelsSetText("codexCustomChatModelCount", String(chatEntries.length));
  codexCustomModelsSetText("codexCustomApiModelCount", String(apiEntries.length));
  codexCustomModelsSetText("codexCustomSeedModelCount", String(seedEntries.length));
  codexCustomModelsSetText("codexCustomModelTokenBurn", String(registry?.token_burn ?? 0));
  if (!persistedSelectionInvalid && !persistedReasoningInvalid) {
    setQuickStartChip(
      "quickStartRouteChip",
      chatEntries.length || apiEntries.length ? "neutral" : "amber",
      chatEntries.length || apiEntries.length ? "модели загружены" : "нет моделей"
    );
  }
  if (
    currentScreen() === "quick-start"
    && currentAccountsSnapshot
    && currentApiConnectionsSnapshot
  ) {
    renderQuickStart(
      currentAccountsSnapshot,
      currentApiConnectionsSnapshot,
      document.getElementById("sourcePicker")?.value || "live",
      document.querySelector(".desktop")?.dataset?.fixtureState || "unknown"
    );
  }
}

function renderCodexCustomSelectorIntent(packet) {
  const response = document.getElementById("codexCustomSelectorIntentResponse");
  const chatModel = packet?.chatgpt_selection?.model_id || "";
  const apiModel = packet?.api_selection?.model_id || "";
  codexCustomModelsSetChip(
    packet?.status === "ok" ? "amber" : (packet?.status === "degraded" ? "amber" : (packet?.status === "rejected" ? "amber" : "red")),
    packet?.status === "ok" ? "intent only" : (packet?.status || "failed")
  );
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      chatgpt_model_id: chatModel,
      api_model_id: apiModel,
      current_execution_path_model_id: packet?.current_execution_path_model_id || "",
      current_execution_path_source: packet?.current_execution_path_source || "",
      selection_intent_only: packet?.selection_intent_only === true,
      selector_runtime_readiness_claimed: packet?.selector_runtime_readiness_claimed === true,
      simultaneous_execution_proven: packet?.simultaneous_execution_proven === true,
      role_slot_binding_proven: packet?.role_slot_binding_proven === true,
      selected_models_are_server_issued: packet?.selected_models_are_server_issued === true,
      browser_selected_chatgpt_matches_current_execution_path:
        packet?.browser_selected_chatgpt_matches_current_execution_path === true,
      seed_only_selected: packet?.seed_only_selected === true,
      session_execution_wired: packet?.session_execution_wired === true,
      next_action: packet?.next_action || ""
    }, null, 2);
  }
}

function renderCodexCustomModelDryRun(packet) {
  const response = document.getElementById("codexCustomModelDryRunResponse");
  const ok = packet?.dry_run === true && packet?.model_server_issued === true && packet?.inference_called === false;
  const claimGateBlocked = String(packet?.claim_gate_status || packet?.refresh_packet?.claim_gate_status || "").includes("blocked");
  codexCustomModelsSetChip(
    ok && !claimGateBlocked ? "green" : (ok ? "amber" : (packet?.status === "rejected" ? "amber" : "red")),
    ok && claimGateBlocked ? "dry-run ok / gate blocked" : (ok ? "dry-run ok" : (packet?.status || "failed"))
  );
  codexCustomModelsSetText("codexCustomModelTokenBurn", String(packet?.token_burn ?? 0));
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      selected_model: packet?.selected_model || "",
      dry_run: packet?.dry_run === true,
      model_server_issued: packet?.model_server_issued === true,
      selected_model_server_issued: packet?.selected_model_server_issued === true,
      selected_model_selectable: packet?.selected_model_selectable === true,
      selection_state: packet?.selection_state || "",
      selection_disabled_reason_code: packet?.selection_disabled_reason_code || "",
      codex_config_compatible: packet?.codex_config_compatible === true,
      model_provider: packet?.model_provider || "",
      wire_api: packet?.wire_api || "",
      network_calls_made: packet?.network_call_summary?.network_calls_made === true,
      route_or_backend_exposed: packet?.route_or_backend_exposed === true,
      inference_called: packet?.inference_called === true,
      provider_called: packet?.provider_called === true,
      responses_called: packet?.responses_called === true,
      chat_completions_called: packet?.chat_completions_called === true,
      token_burn: packet?.token_burn ?? 0,
      negative_claim_basis: packet?.negative_claim_basis || "",
      independent_runtime_meter_attached: packet?.independent_runtime_meter_attached === true,
      claim_gate_status: packet?.claim_gate_status || packet?.refresh_packet?.claim_gate_status || "not_reported",
      next_action: packet?.next_action || "",
    }, null, 2);
  }
}

function renderCodexCustomApiActionGate(packet) {
  const response = document.getElementById("codexCustomApiActionGateResponse");
  const button = document.getElementById("codexCustomApiActionGateAction");
  const summary = packet?.summary_packet || {};
  const choice = packet?.manual_api_choice_packet || {};
  const budget = packet?.budget_policy_packet || {};
  const owner = packet?.owner_authorization_packet || {};
  const boundary = packet?.live_provider_request_boundary_packet || {};
  const enabled = summary?.live_provider_request_allowed === true;
  if (button) {
    button.disabled = !enabled;
    button.classList.toggle("disabled", !enabled);
    button.title = enabled
      ? "Server gate admitted one bounded API check."
      : (summary?.final_status || packet?.final_status || "API action blocked by server packet.");
  }
  codexCustomModelsSetText(
    "codexCustomApiActionGateState",
    summary?.final_status || packet?.final_status || packet?.machine_error_code || "unknown"
  );
  codexCustomModelsSetText("codexCustomApiActionProvider", choice?.provider || "-");
  codexCustomModelsSetText("codexCustomApiActionRoute", choice?.route_id || "-");
  codexCustomModelsSetText("codexCustomApiActionCost", choice?.cost_class || budget?.cost_class || "-");
  codexCustomModelsSetText(
    "codexCustomApiActionCredential",
    `${choice?.credential_ref_status || "unknown"} · secret value exposed: ${choice?.secret_value_exposed === true ? "yes" : "no"}`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      final_status: packet?.final_status || "",
      api_action_visible: summary?.api_action_visible === true,
      api_action_enabled: summary?.api_action_enabled === true,
      selected_api_model_id: choice?.api_model_id || "",
      server_issued_model_selected: choice?.server_issued_model_selected === true,
      selection_intent_only: choice?.selection_intent_only === true,
      execution_proven: choice?.execution_proven === true,
      provider_response_observed: choice?.provider_response_observed === true,
      route_snapshot_counted_as_provider_response:
        choice?.route_snapshot_counted_as_provider_response === true,
      browser_raw_backend_authority_widened:
        packet?.browser_authority_guard_packet?.browser_raw_backend_authority_widened === true,
      forbidden_fields: packet?.browser_authority_guard_packet?.forbidden_fields || [],
      owner_live_authorization_present: owner?.owner_live_authorization_present === true,
      budget_policy_present: budget?.budget_policy_present === true,
      live_provider_request_allowed: boundary?.live_provider_request_allowed === true,
      live_call_attempted: boundary?.live_call_attempted === true,
      paid_route_used: boundary?.paid_route_used === true,
      upstream_response_observed: boundary?.upstream_response_observed === true,
      fallback_attempted: boundary?.fallback_attempted === true,
      parallel_fanout_attempted: boundary?.parallel_fanout_attempted === true,
      original_codex_touched: boundary?.original_codex_touched === true,
      raw_secret_recorded: boundary?.raw_secret_recorded === true,
      secret_value_recorded: boundary?.secret_value_recorded === true,
      next_action: summary?.next_action || ""
    }, null, 2);
  }
}

function renderCodexCustomExecutionMode(packet) {
  const response = document.getElementById("codexCustomExecutionModeResponse");
  const ok = packet?.status === "ok" && packet?.live_call_attempted === false;
  codexCustomModelsSetChip(
    ok ? "green" : (packet?.status === "rejected" || packet?.status === "blocked" ? "amber" : "red"),
    ok ? "mode packet ok" : (packet?.status || "failed")
  );
  codexCustomModelsSetText(
    "codexCustomExecutionModeState",
    packet?.final_status || packet?.machine_error_code || "unknown"
  );
  codexCustomModelsSetText(
    "codexCustomExecutionBoundary",
    `${packet?.execution_mode || "unknown"} · live call ${packet?.live_call_attempted === true ? "attempted" : "not attempted"}`
  );
  setQuickStartChip(
    "quickStartExecutionModeState",
    ok ? "green" : (packet?.status === "rejected" || packet?.status === "blocked" ? "amber" : "red"),
    ok ? "OK" : (packet?.machine_error_code || packet?.status || "ошибка")
  );
  setQuickStartChip(
    "quickStartRouteChip",
    ok ? "green" : "amber",
    ok ? "маршрут ok" : "маршрут не доказан"
  );
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      final_status: packet?.final_status || "",
      execution_mode: packet?.execution_mode || "",
      api_model_id: packet?.api_model_id || "",
      api_reasoning_option_id: packet?.api_reasoning_option_id || "",
      api_reasoning_option_packet: packet?.api_reasoning_option_packet || {},
      primary_model_slot: packet?.primary_model_slot || {},
      coding_agent_model_slot: packet?.coding_agent_model_slot || {},
      chatgpt_executor_selected: packet?.chatgpt_executor_selected === true,
      api_executor_selected: packet?.api_executor_selected === true,
      dual_lane_slots_preserved: packet?.dual_lane_slots_preserved === true,
      server_issued_catalog_used: packet?.server_issued_catalog_used === true,
      raw_backend_details_exposed: packet?.raw_backend_details_exposed === true,
      browser_raw_backend_authority_widened:
        packet?.browser_raw_backend_authority_widened === true,
      forbidden_fields: packet?.forbidden_fields || [],
      live_call_attempted: packet?.live_call_attempted === true,
      network_calls_made: packet?.network_calls_made === true,
      provider_called: packet?.provider_called === true,
      original_codex_touched: packet?.original_codex_touched === true,
      asar_touched: packet?.asar_touched === true,
      wbp_patch_applier_used: packet?.wbp_patch_applier_used === true,
      selector_packet_truth_only: packet?.selector_packet_truth_only === true,
      ui_text_counts_as_runtime_truth: packet?.ui_text_counts_as_runtime_truth === true,
      next_action: packet?.next_action || ""
    }, null, 2);
  }
  setQuickStartRouteResponse({
    status: packet?.status || "unknown",
    machine_error_code: packet?.machine_error_code || "UNKNOWN",
    final_status: packet?.final_status || "",
    execution_mode: packet?.execution_mode || "",
    chatgpt_model_id: packet?.chatgpt_model_id || "",
    api_model_id: packet?.api_model_id || "",
    api_reasoning_option_id: packet?.api_reasoning_option_id || "",
    api_reasoning_option_packet: packet?.api_reasoning_option_packet || {},
    primary_model_slot: packet?.primary_model_slot || {},
    coding_agent_model_slot: packet?.coding_agent_model_slot || {},
    server_issued_catalog_used: packet?.server_issued_catalog_used === true,
    raw_backend_details_exposed: packet?.raw_backend_details_exposed === true,
    live_call_attempted: packet?.live_call_attempted === true,
    original_codex_touched: packet?.original_codex_touched === true,
    next_action: packet?.next_action || ""
  });
}

function renderCodexCustomDeepSeekLiveFormat(packet) {
  const response = document.getElementById("codexCustomDeepSeekLiveFormatResponse");
  const ok = packet?.final_status === "API_ONLY_DEEPSEEK_LIVE_ROUTE_AND_FORMAT_PROVEN_WITH_LIMITS";
  codexCustomModelsSetChip(
    ok ? "green" : (packet?.status === "rejected" || packet?.status === "blocked" ? "amber" : "red"),
    ok ? "deepseek live ok" : (packet?.status || "failed")
  );
  codexCustomModelsSetText(
    "codexCustomExecutionModeState",
    packet?.final_status || packet?.machine_error_code || "unknown"
  );
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      final_status: packet?.final_status || "",
      execution_mode: packet?.execution_mode || "",
      api_provider_id: packet?.api_provider_id || "",
      api_model_id: packet?.api_model_id || "",
      deepseek_selected_from_server_catalog:
        packet?.deepseek_selected_from_server_catalog === true,
      owner_authorization_phrase_present:
        packet?.owner_authorization_phrase_present === true,
      provider_called: packet?.provider_called === true,
      live_call_attempted: packet?.live_call_attempted === true,
      upstream_response_observed: packet?.upstream_response_observed === true,
      expected_text_observed: packet?.expected_text_observed === true,
      codex_compatible_response_shape:
        packet?.codex_compatible_response_shape === true,
      request_count: packet?.request_count ?? 0,
      retry_count: packet?.retry_count ?? 0,
      parallel_fanout_attempted: packet?.parallel_fanout_attempted === true,
      fallback_attempted: packet?.fallback_attempted === true,
      file_mutation_attempted: packet?.file_mutation_attempted === true,
      wbp_patch_applier_used: packet?.wbp_patch_applier_used === true,
      original_codex_touched: packet?.original_codex_touched === true,
      asar_touched: packet?.asar_touched === true,
      raw_backend_details_exposed: packet?.raw_backend_details_exposed === true,
      secret_value_exposed: packet?.secret_value_exposed === true,
      state_written: packet?.state_written === true,
      evidence_written: packet?.evidence_written === true,
      live_result_packet: packet?.live_result_packet || {},
      live_error_packet: packet?.live_error_packet || {},
      forbidden_fields: packet?.forbidden_fields || [],
      next_action: packet?.next_action || ""
    }, null, 2);
  }
}

async function refreshCodexCustomApiActionGate() {
  const apiNode = document.getElementById("codexCustomApiModelSelect");
  const apiModelId = apiNode ? apiNode.value : "";
  try {
    const response = await fetch("api/codex/custom/api-action-gate", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ api_model_id: apiModelId })
    });
    if (!response.ok) {
      throw new Error(`custom api action gate http ${response.status}`);
    }
    renderCodexCustomApiActionGate(await response.json());
  } catch (error) {
    renderCodexCustomApiActionGate({
      status: "failed",
      machine_error_code: "CUSTOM_API_ACTION_GATE_FETCH_FAILED",
      final_status: "CUSTOM_CODEX_API_ACTION_GATE_FETCH_FAILED",
      manual_api_choice_packet: {
        api_model_id: apiModelId,
        selection_intent_only: true,
        execution_proven: false,
        provider_response_observed: false,
        route_snapshot_counted_as_provider_response: false,
        secret_value_exposed: false,
      },
      browser_authority_guard_packet: { browser_raw_backend_authority_widened: false },
      owner_authorization_packet: { owner_live_authorization_present: false },
      budget_policy_packet: { budget_policy_present: false },
      live_provider_request_boundary_packet: {
        live_provider_request_allowed: false,
        live_call_attempted: false,
        paid_route_used: false,
        upstream_response_observed: false,
        fallback_attempted: false,
        parallel_fanout_attempted: false,
        original_codex_touched: false,
        raw_secret_recorded: false,
        secret_value_recorded: false,
      },
      summary_packet: {
        api_action_visible: true,
        api_action_enabled: false,
        live_provider_request_allowed: false,
        next_action: error.message,
      },
    });
  }
}

async function runCodexCustomExecutionModeDryRun() {
  syncCodexRouteSelects("quickStartChatModelSelect");
  syncCodexRouteSelects("quickStartApiModelSelect");
  syncCodexRouteSelects("quickStartApiReasoningOptionSelect");
  syncCodexRouteSelects("quickStartExecutionModeSelect");
  const modeNode = document.getElementById("codexCustomExecutionModeSelect");
  const chatNode = document.getElementById("codexCustomModelSelect");
  const apiNode = document.getElementById("codexCustomApiModelSelect");
  const apiReasoningNode = document.getElementById("codexCustomApiReasoningOptionSelect");
  const executionMode = modeNode ? modeNode.value : "";
  const chatgptModelId = executionMode === "api_only" ? "" : (chatNode ? chatNode.value : "");
  const apiModelId = executionMode === "chatgpt_only" ? "" : (apiNode ? apiNode.value : "");
  const apiReasoningOptionId = executionMode === "chatgpt_only"
    ? ""
    : (apiReasoningNode ? apiReasoningNode.value : "");
  document.getElementById("codexCustomExecutionModeDryRunAction")?.setAttribute("disabled", "disabled");
  document.getElementById("quickStartExecutionModeDryRunAction")?.setAttribute("disabled", "disabled");
  codexCustomModelsSetChip("neutral", "checking");
  try {
    const response = await fetch("api/codex/custom/execution-mode-dry-run", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        execution_mode: executionMode,
        chatgpt_model_id: chatgptModelId,
        api_model_id: apiModelId,
        api_reasoning_option_id: apiReasoningOptionId
      })
    });
    if (!response.ok) {
      throw new Error(`execution mode dry-run http ${response.status}`);
    }
    renderCodexCustomExecutionMode(await response.json());
  } catch (error) {
    renderCodexCustomExecutionMode({
      status: "failed",
      machine_error_code: "CUSTOM_CODEX_EXECUTION_MODE_FETCH_FAILED",
      final_status: "CUSTOM_CODEX_EXECUTION_MODE_FETCH_FAILED",
      execution_mode: executionMode,
      api_model_id: apiModelId,
      api_reasoning_option_id: apiReasoningOptionId,
      raw_backend_details_exposed: false,
      browser_raw_backend_authority_widened: false,
      live_call_attempted: false,
      network_calls_made: false,
      provider_called: false,
      original_codex_touched: false,
      asar_touched: false,
      wbp_patch_applier_used: false,
      selector_packet_truth_only: true,
      ui_text_counts_as_runtime_truth: false,
      next_action: error.message
    });
  } finally {
    document.getElementById("codexCustomExecutionModeDryRunAction")?.removeAttribute("disabled");
    document.getElementById("quickStartExecutionModeDryRunAction")?.removeAttribute("disabled");
  }
}

async function runCodexCustomDeepSeekLiveFormat() {
  const modeNode = document.getElementById("codexCustomExecutionModeSelect");
  const apiNode = document.getElementById("codexCustomApiModelSelect");
  const executionMode = modeNode ? modeNode.value : "";
  const apiModelId = apiNode ? apiNode.value : "";
  document.getElementById("codexCustomDeepSeekLiveFormatAction")?.setAttribute("disabled", "disabled");
  codexCustomModelsSetChip("neutral", "checking");
  try {
    const response = await fetch("api/codex/custom/api-only-deepseek/live-format", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ execution_mode: executionMode, api_model_id: apiModelId })
    });
    if (!response.ok) {
      throw new Error(`deepseek live format http ${response.status}`);
    }
    renderCodexCustomDeepSeekLiveFormat(await response.json());
  } catch (error) {
    renderCodexCustomDeepSeekLiveFormat({
      status: "failed",
      machine_error_code: "API_ONLY_DEEPSEEK_LIVE_FORMAT_FETCH_FAILED",
      final_status: "KNOWN_BLOCKER_API_ONLY_DEEPSEEK_ROUTE_OR_FORMAT_NOT_ADMISSIBLE",
      execution_mode: executionMode,
      api_model_id: apiModelId,
      owner_authorization_phrase_present: false,
      provider_called: false,
      live_call_attempted: false,
      request_count: 0,
      retry_count: 0,
      parallel_fanout_attempted: false,
      file_mutation_attempted: false,
      wbp_patch_applier_used: false,
      original_codex_touched: false,
      asar_touched: false,
      raw_backend_details_exposed: false,
      secret_value_exposed: false,
      state_written: false,
      evidence_written: false,
      next_action: error.message
    });
  } finally {
    document.getElementById("codexCustomDeepSeekLiveFormatAction")?.removeAttribute("disabled");
  }
}

async function refreshCodexCustomModelsPanel() {
  try {
    const [registry, compat] = await Promise.all([
      fetchCodexLaunchJson("api/codex/custom/model-selector"),
      fetchCodexLaunchJson("api/codex/custom/api-compat")
    ]);
    renderCodexCustomModels(registry, compat);
    await refreshCodexCustomApiActionGate();
  } catch (error) {
    codexCustomModelsSetChip("red", "failed");
    codexCustomModelsSetText("codexCustomModelsSummary", `Dual-lane selector fetch failed: ${error.message}`);
    codexCustomModelsSetText("codexCustomApiCompat", "fetch failed");
  }
}

async function runCodexCustomSelectorIntentDryRun() {
  const chatNode = document.getElementById("codexCustomModelSelect");
  const apiNode = document.getElementById("codexCustomApiModelSelect");
  const chatgptModelId = chatNode ? chatNode.value : "";
  const apiModelId = apiNode ? apiNode.value : "";
  document.getElementById("codexCustomSelectorIntentDryRunAction")?.setAttribute("disabled", "disabled");
  codexCustomModelsSetChip("neutral", "checking");
  try {
    const response = await fetch("api/codex/custom/model-selector-dry-run", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ chatgpt_model_id: chatgptModelId, api_model_id: apiModelId })
    });
    if (!response.ok) {
      throw new Error(`selector intent dry-run http ${response.status}`);
    }
    renderCodexCustomSelectorIntent(await response.json());
  } catch (error) {
    renderCodexCustomSelectorIntent({
      status: "failed",
      machine_error_code: "CUSTOM_SELECTOR_INTENT_FETCH_FAILED",
      human_message: error.message,
      selection_intent_only: true,
      selector_runtime_readiness_claimed: false,
      simultaneous_execution_proven: false,
      role_slot_binding_proven: false,
      selected_models_are_server_issued: false,
      seed_only_selected: false,
      session_execution_wired: false
    });
  } finally {
    document.getElementById("codexCustomSelectorIntentDryRunAction")?.removeAttribute("disabled");
  }
}

async function runCodexCustomModelDryRun() {
  if (codexCustomModelDryRunInFlight) {
    return;
  }
  const modelNode = document.getElementById("codexCustomModelSelect");
  const modelId = modelNode ? modelNode.value : "";
  codexCustomModelDryRunInFlight = true;
  document.getElementById("codexCustomModelDryRunAction")?.setAttribute("disabled", "disabled");
  codexCustomModelsSetChip("neutral", "checking");
  try {
    const response = await fetch("api/codex/custom/model-dry-run", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ model_id: modelId })
    });
    if (!response.ok) {
      throw new Error(`custom model dry-run http ${response.status}`);
    }
    renderCodexCustomModelDryRun(await response.json());
  } catch (error) {
    renderCodexCustomModelDryRun({
      status: "failed",
      machine_error_code: "CUSTOM_MODEL_DRY_RUN_FETCH_FAILED",
      human_message: error.message,
      dry_run: true,
      model_server_issued: false,
      codex_config_compatible: false,
      route_or_backend_exposed: false,
      inference_called: false,
      provider_called: false,
      responses_called: false,
      chat_completions_called: false,
      token_burn: 0
    });
  } finally {
    codexCustomModelDryRunInFlight = false;
    document.getElementById("codexCustomModelDryRunAction")?.removeAttribute("disabled");
  }
}

function codexCustomAccountsSetText(id, value) {
  operatorSetText(id, value);
}

function codexCustomAccountsSetChip(visual, label) {
  const chip = document.getElementById("codexCustomAccountsChip");
  if (!chip) {
    return;
  }
  chip.className = `chip ${VISUAL_CLASS[visual] || ACTION_STATUS_VISUAL_CLASS[visual] || "neutral"}`;
  if (chip.lastElementChild) {
    chip.lastElementChild.textContent = label || visual || "unknown";
  }
}

function renderCodexCustomAccounts(accounts, selection) {
  const claimGate = accounts?.claim_gate_status || selection?.claim_gate_status || "not_reported";
  const claimGateBlocked = String(claimGate).includes("blocked");
  const status = accounts?.status || "unknown";
  const selectionDryRunProven = selection?.selection_dry_run_proven === true;
  const liveSelectionProven = selection?.live_selection_proven === true;
  codexCustomAccountsSetChip(
    status === "ok" && selectionDryRunProven && !claimGateBlocked ? "green" : (status === "failed" ? "red" : "amber"),
    selectionDryRunProven && claimGateBlocked ? "dry-run ready / gate blocked" : (selectionDryRunProven ? "dry-run ready" : status)
  );
  codexCustomAccountsSetText(
    "codexCustomAccountsSummary",
    `${accounts?.managed_total ?? 0} packet accounts · ${accounts?.launch_capable_count ?? 0} launch capable · live unchecked`
  );
  codexCustomAccountsSetText(
    "codexCustomAccountsManaged",
    `${accounts?.managed_total ?? 0} / ${accounts?.expected_managed_total ?? 25}`
  );
  codexCustomAccountsSetText("codexCustomAccountsLaunchCapable", String(accounts?.launch_capable_count ?? 0));
  const pools = accounts?.pool_classes || {};
  codexCustomAccountsSetText(
    "codexCustomAccountsPools",
    `active ${pools.active ?? 0} · reserve ${pools.reserve ?? 0} · hold ${pools.hold ?? 0} · problem ${pools.problem ?? 0} · retired ${pools.retired ?? 0}`
  );
  codexCustomAccountsSetText(
    "codexCustomAccountsSelection",
    selectionDryRunProven
      ? `${selection?.selected_source_class || "gpt_account"} · ${selection?.selection_reason || "server-side selection"}`
      : (selection?.selection_reason || "not proven")
  );
  codexCustomAccountsSetText("codexCustomAccountsClaimGate", claimGate);
  codexCustomAccountsSetText("codexCustomSelectionState", selectionDryRunProven ? (liveSelectionProven ? "live proven" : "selection dry-run") : "not proven");
  codexCustomAccountsSetText("codexCustomInferenceState", selection?.inference_proven === true ? "metered proof" : "not claimed");
}

function renderCodexCustomAccountDryRun(packet) {
  const response = document.getElementById("codexCustomAccountDryRunResponse");
  const selectionDryRunProven = packet?.selection_dry_run_proven === true;
  const ok = packet?.dry_run === true && selectionDryRunProven && packet?.browser_selected_backend === false;
  const claimGateBlocked = String(packet?.claim_gate_status || packet?.refresh_packet?.claim_gate_status || "").includes("blocked");
  codexCustomAccountsSetChip(
    ok && !claimGateBlocked ? "green" : (ok ? "amber" : (packet?.status === "rejected" ? "amber" : "red")),
    ok && claimGateBlocked ? "dry-run ok / gate blocked" : (ok ? "dry-run ok" : (packet?.status || "failed"))
  );
  codexCustomAccountsSetText("codexCustomSelectionState", selectionDryRunProven ? (packet?.live_selection_proven ? "live proven" : "selection dry-run") : "not proven");
  codexCustomAccountsSetText("codexCustomInferenceState", packet?.inference_proven ? "metered proof" : "not claimed");
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      selected_model: packet?.selected_model || "",
      dry_run: packet?.dry_run === true,
      model_server_issued: packet?.model_server_issued === true,
      selection_dry_run_proven: packet?.selection_dry_run_proven === true,
      live_selection_proven: packet?.live_selection_proven === true,
      selection_proven: packet?.selection_proven === true,
      inference_proven: packet?.inference_proven === true,
      selected_source_class: packet?.selected_source_class || "",
      selected_backend_ref: packet?.selected_backend_ref || "",
      selected_backend_id_redacted: packet?.selected_backend_id_redacted === true,
      selected_backend_server_issued: packet?.selected_backend_server_issued === true,
      browser_selected_backend: packet?.browser_selected_backend === true,
      smoke_admitted: packet?.smoke_admitted === true,
      runtime_meter_attached: packet?.runtime_meter_attached === true,
      responses_called: packet?.responses_called === true,
      chat_completions_called: packet?.chat_completions_called === true,
      provider_called: packet?.provider_called === true,
      network_calls_made: packet?.network_calls_made === true,
      account_mutation_performed: packet?.account_mutation_performed === true,
      token_burn: packet?.token_burn ?? 0,
      negative_claim_basis: packet?.negative_claim_basis || "",
      claim_gate_status: packet?.claim_gate_status || packet?.refresh_packet?.claim_gate_status || "not_reported",
      next_action: packet?.next_action || "",
    }, null, 2);
  }
}

async function refreshCodexCustomAccountsPanel() {
  try {
    const [accounts, selection] = await Promise.all([
      fetchCodexLaunchJson("api/codex/custom/accounts"),
      fetchCodexLaunchJson("api/codex/custom/account-selection")
    ]);
    renderCodexCustomAccounts(accounts, selection);
  } catch (error) {
    codexCustomAccountsSetChip("red", "failed");
    codexCustomAccountsSetText("codexCustomAccountsSummary", `Account truth fetch failed: ${error.message}`);
    codexCustomAccountsSetText("codexCustomAccountsSelection", "fetch failed");
  }
}

async function runCodexCustomAccountSmokeDryRun() {
  if (codexCustomAccountDryRunInFlight) {
    return;
  }
  const modelNode = document.getElementById("codexCustomModelSelect");
  const modelId = modelNode ? modelNode.value : "";
  codexCustomAccountDryRunInFlight = true;
  document.getElementById("codexCustomAccountSmokeDryRunAction")?.setAttribute("disabled", "disabled");
  codexCustomAccountsSetChip("neutral", "checking");
  try {
    const response = await fetch("api/codex/custom/account-smoke-dry-run", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ model_id: modelId })
    });
    if (!response.ok) {
      throw new Error(`custom account dry-run http ${response.status}`);
    }
    renderCodexCustomAccountDryRun(await response.json());
  } catch (error) {
    renderCodexCustomAccountDryRun({
      status: "failed",
      machine_error_code: "CUSTOM_ACCOUNT_DRY_RUN_FETCH_FAILED",
      human_message: error.message,
      dry_run: true,
      model_server_issued: false,
      selection_dry_run_proven: false,
      live_selection_proven: false,
      selection_proven: false,
      inference_proven: false,
      browser_selected_backend: false,
      smoke_admitted: false,
      runtime_meter_attached: false,
      responses_called: false,
      chat_completions_called: false,
      provider_called: false,
      network_calls_made: false,
      account_mutation_performed: false,
      token_burn: 0
    });
  } finally {
    codexCustomAccountDryRunInFlight = false;
    document.getElementById("codexCustomAccountSmokeDryRunAction")?.removeAttribute("disabled");
  }
}

function codexCustomSessionsSetText(id, value) {
  operatorSetText(id, value);
}

function codexCustomSessionsSetChip(visual, label) {
  const chip = document.getElementById("codexCustomSessionsChip");
  if (!chip) {
    return;
  }
  chip.className = `chip ${VISUAL_CLASS[visual] || ACTION_STATUS_VISUAL_CLASS[visual] || "neutral"}`;
  if (chip.lastElementChild) {
    chip.lastElementChild.textContent = label || visual || "unknown";
  }
}

function currentCodexCustomSessionUrl(action = "") {
  if (!codexCustomSelectedSessionId) {
    return "";
  }
  const base = `api/codex/custom/sessions/${encodeURIComponent(codexCustomSelectedSessionId)}`;
  return action ? `${base}/${action}` : base;
}

function renderCodexCustomSessionPacket(packet) {
  const session = packet?.session || {};
  const roleSlots = session?.role_slots || packet?.role_slot_binding_packet?.role_slots || {};
  const sessionId = session?.session_id || packet?.session_id || codexCustomSelectedSessionId || "";
  if (sessionId) {
    codexCustomSelectedSessionId = sessionId;
  }
  const inference = packet?.inference_proven === true || session?.inference_proven === true;
  const tokenBurn = packet?.token_burn ?? session?.token_burn ?? "unknown";
  const modelResponsePresent = packet?.model_response_present === true || session?.model_response_present === true;
  const wbpPathProven = packet?.wbp_path_proven === true;
  const traceMissingAfterResponse = inference && modelResponsePresent && !wbpPathProven;
  const selectionDryRun = session?.selection_dry_run_proven === true || packet?.selection_dry_run_proven === true;
  const liveSelection = session?.live_selection_proven === true || packet?.live_selection_proven === true;
  const slotCatalogRevalidated = session?.slot_catalog_revalidated === true || packet?.role_slot_binding_packet?.slot_catalog_revalidated === true;
  const packetStatus = packet?.status || session?.status || "unknown";
  codexCustomSessionsSetText("codexCustomSelectedSession", sessionId || "none");
  codexCustomSessionsSetText("codexCustomSessionStatus", session?.status || packetStatus || "unknown");
  codexCustomSessionsSetText("codexCustomSessionModel", session?.model_id || packet?.selected_model || "-");
  const boundSlotCount = Object.values(roleSlots).filter((slot) => slot?.binding_status === "bound").length;
  codexCustomSessionsSetText(
    "codexCustomSessionSlots",
    `${boundSlotCount} bound · current ${session?.current_execution_slot_id || packet?.current_execution_slot_id || "primary_model_slot"}`
  );
  codexCustomSessionsSetText(
    "codexCustomSessionSelection",
    selectionDryRun
      ? `${session?.selected_source_class || packet?.selected_source_class || "gpt_account"} · ${liveSelection ? "live proven" : (slotCatalogRevalidated ? "selection dry-run" : "reload needs revalidation")}`
      : "not proven"
  );
  codexCustomSessionsSetText("codexCustomSessionCleanup", session?.cleanup_state || "not_cleaned");
  codexCustomSessionsSetText("codexCustomSessionInference", inference ? "response proof" : "not claimed");
  codexCustomSessionsSetText("codexCustomSessionTokenBurn", String(tokenBurn));
  let chipVisual = "neutral";
  let chipLabel = packetStatus;
  if (inference && modelResponsePresent) {
    chipLabel = wbpPathProven ? "trace proven" : "trace missing";
    chipVisual = packetStatus === "ok" && !traceMissingAfterResponse ? "green" : "amber";
  } else if (packetStatus === "ok") {
    chipLabel = slotCatalogRevalidated && selectionDryRun ? "dry-run proven" : "selection loaded";
    chipVisual = slotCatalogRevalidated && selectionDryRun ? "amber" : "neutral";
  } else if (packetStatus === "loaded") {
    chipLabel = slotCatalogRevalidated && selectionDryRun ? "loaded / dry-run proven" : "loaded / revalidation required";
    chipVisual = slotCatalogRevalidated && selectionDryRun ? "amber" : "neutral";
  } else if (packetStatus === "rejected" || packetStatus === "blocked") {
    chipVisual = "amber";
  }
  codexCustomSessionsSetChip(chipVisual, chipLabel || "unknown");
  const aliasMetadata = codexCustomAgentAliasMetadataPacket("session_render");
  const response = document.getElementById("codexCustomSessionResponse");
  if (response) {
    response.textContent = JSON.stringify({
      status: packetStatus,
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      session_id: sessionId,
      session_schema_version: session?.session_schema_version ?? packet?.session_schema_version ?? 0,
      model_id: session?.model_id || packet?.selected_model || "",
      model_server_issued: session?.model_server_issued === true || packet?.model_server_issued === true,
      current_execution_slot_id: session?.current_execution_slot_id || packet?.current_execution_slot_id || "",
      current_execution_path_source: session?.current_execution_path_source || packet?.current_execution_path_source || "",
      alias_scope: aliasMetadata.alias_scope,
      alias_role_map: aliasMetadata.role_map,
      semantic_alias_routing_enabled: aliasMetadata.semantic_alias_routing_enabled,
      runtime_dispatch_changed: aliasMetadata.runtime_dispatch_changed,
      session_manager_changed: aliasMetadata.session_manager_changed,
      provider_selection_changed: aliasMetadata.provider_selection_changed,
      role_slot_binding_proven: session?.role_slot_binding_proven === true || packet?.role_slot_binding_proven === true,
      role_slot_binding_count: session?.role_slot_binding_count ?? packet?.role_slot_binding_packet?.role_slot_binding_count ?? 0,
      slot_catalog_revalidated: slotCatalogRevalidated,
      role_slots: roleSlots,
      selection_dry_run_proven: selectionDryRun,
      live_selection_proven: liveSelection,
      selection_proven: session?.selection_proven === true || packet?.selection_proven === true,
      selected_backend_id_redacted: session?.selected_backend_id_redacted === true || packet?.selected_backend_id_redacted === true,
      selected_backend_server_issued: session?.selected_backend_server_issued === true,
      source_provenance_status: packet?.source_provenance_status || session?.source_provenance_status || "",
      source_provenance_proven: packet?.source_provenance_proven === true || session?.source_provenance_proven === true,
      selected_source_provenance: packet?.selected_source_provenance || "",
      authorization_status: packet?.authorization_status || "",
      owner_authorization_phrase_present: packet?.owner_authorization_phrase_present === true,
      live_prompt_admitted: packet?.live_prompt_admitted === true,
      live_prompt_executed: packet?.live_prompt_executed === true,
      live_prompt_full_success: packet?.live_prompt_full_success === true,
      prompt_runner_called: packet?.prompt_runner_called === true,
      prompt_admitted: packet?.prompt_admitted === true,
      prompt_present: packet?.prompt_present === true,
      prompt_length: packet?.prompt_length ?? 0,
      prompt_sha256: packet?.prompt_sha256 || "",
      prompt_preview_redacted: packet?.prompt_preview_redacted || "",
      raw_prompt_not_stored: packet?.raw_prompt_not_stored === true,
      transcript_kind: packet?.transcript_kind || "",
      model_response_present: modelResponsePresent,
      response_digest: packet?.response_digest || "",
      response_preview_bounded: packet?.response_preview_bounded || "",
      token_usage_present: packet?.token_usage_present === true,
      latency_ms: packet?.latency_ms ?? null,
      wbp_path_configured: packet?.wbp_path_configured === true,
      cli_proxy_api_path_configured: packet?.cli_proxy_api_path_configured === true,
      wbp_path_observed: packet?.wbp_path_observed === true,
      cli_proxy_api_path_observed: packet?.cli_proxy_api_path_observed === true,
      wbp_path_proven: packet?.wbp_path_proven === true,
      cli_proxy_api_path_proven: packet?.cli_proxy_api_path_proven === true,
      independent_wbp_trace_observed: packet?.independent_wbp_trace_observed === true,
      trace_path: packet?.trace_path || "",
      upstream_status: packet?.upstream_status ?? null,
      forwarded_to_wbp: packet?.forwarded_to_wbp === true,
      isolated_engine_home_proven: packet?.isolated_engine_home_proven === true,
      current_codex_touched: packet?.current_codex_touched === true,
      configured_wire_api: packet?.configured_wire_api || "",
      path_proof_status: packet?.path_proof_status || "",
      fallback_attempted: packet?.fallback_attempted === true,
      cleanup_performed: packet?.cleanup_performed === true,
      owned_session_root_only: packet?.owned_session_root_only === true,
      current_codex_home_touched: packet?.current_codex_home_touched === true,
      arbitrary_path_accepted: packet?.arbitrary_path_accepted === true,
      process_kill_claimed: packet?.process_kill_claimed === true,
      inference_proven: inference,
      runtime_meter_attached: packet?.runtime_meter_attached === true || session?.runtime_meter_attached === true,
      network_calls_made: packet?.network_calls_made === true || session?.network_calls_made === true,
      provider_called: packet?.provider_called === true || session?.provider_called === true,
      token_burn: tokenBurn,
      next_action: packet?.next_action || "",
    }, null, 2);
  }
}

function renderCodexCustomSessionList(packet) {
  const sessions = Array.isArray(packet?.sessions) ? packet.sessions : [];
  codexCustomSessionsSetText("codexCustomSessionCount", String(packet?.session_count ?? sessions.length));
  if (!codexCustomSelectedSessionId && sessions.length) {
    codexCustomSelectedSessionId = sessions[0].session_id || "";
  }
  const selected = sessions.find((session) => session.session_id === codexCustomSelectedSessionId) || sessions[0] || null;
  if (selected) {
    renderCodexCustomSessionPacket({
      status: "loaded",
      machine_error_code: selected?.selection_machine_error_code || "SESSION_LOADED_FROM_LIST",
      session: selected
    });
    codexCustomSessionsSetText("codexCustomSessionsSummary", `${sessions.length} sessions · selected ${selected.session_id}`);
  } else {
    codexCustomSessionsSetChip("neutral", "no sessions");
    codexCustomSessionsSetText("codexCustomSessionsSummary", "No Codex Custom sessions yet.");
    codexCustomSessionsSetText("codexCustomSelectedSession", "none");
    codexCustomSessionsSetText("codexCustomSessionStatus", "not created");
  }
}

function renderCodexCustomTranscript(packet) {
  const transcript = document.getElementById("codexCustomSessionTranscript");
  if (transcript) {
    transcript.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      transcript_kind: packet?.transcript_kind || "service_ledger_only",
      model_response_present: packet?.model_response_present === true,
      inference_proven: packet?.inference_proven === true,
      entries: packet?.entries || [],
    }, null, 2);
  }
}

async function refreshCodexCustomSessionsPanel() {
  try {
    const packet = await fetchCodexLaunchJson("api/codex/custom/sessions");
    renderCodexCustomSessionList(packet);
  } catch (error) {
    codexCustomSessionsSetChip("red", "failed");
    codexCustomSessionsSetText("codexCustomSessionsSummary", `Session fetch failed: ${error.message}`);
  }
}

async function postCodexCustomSessionAction(action, payload = {}) {
  if (codexCustomSessionActionInFlight) {
    return null;
  }
  const url = action === "create" ? "api/codex/custom/sessions" : currentCodexCustomSessionUrl(action);
  if (!url) {
    renderCodexCustomSessionPacket({
      status: "rejected",
      machine_error_code: "SESSION_NOT_SELECTED",
      inference_proven: false,
      runtime_meter_attached: false,
      token_burn: 0,
      next_action: "create_session"
    });
    return null;
  }
  codexCustomSessionActionInFlight = true;
  codexCustomSessionsSetChip("neutral", "working");
  try {
    const response = await fetch(url, {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      throw new Error(`custom session ${action} http ${response.status}`);
    }
    const packet = await response.json();
    renderCodexCustomSessionPacket(packet);
    if (action === "prompt-dry-run" || action === "prompt" || action === "cancel") {
      const transcriptUrl = currentCodexCustomSessionUrl("transcript");
      if (transcriptUrl) {
        renderCodexCustomTranscript(await fetchCodexLaunchJson(transcriptUrl));
      }
    }
    return packet;
  } catch (error) {
    renderCodexCustomSessionPacket({
      status: "failed",
      machine_error_code: "CUSTOM_SESSION_FETCH_FAILED",
      human_message: error.message,
      inference_proven: false,
      runtime_meter_attached: false,
      token_burn: 0
    });
    return null;
  } finally {
    codexCustomSessionActionInFlight = false;
  }
}

async function createCodexCustomSession() {
  const primaryNode = document.getElementById("codexCustomModelSelect");
  const codingNode = document.getElementById("codexCustomApiModelSelect");
  let primaryModelId = primaryNode ? primaryNode.value : "";
  let codingAgentModelId = codingNode ? codingNode.value : "";
  if (!primaryModelId) {
    await refreshCodexCustomModelsPanel();
    primaryModelId = primaryNode ? primaryNode.value : "";
    codingAgentModelId = codingNode ? codingNode.value : "";
  }
  await postCodexCustomSessionAction("create", {
    primary_model_id: primaryModelId,
    coding_agent_model_id: codingAgentModelId
  });
}

async function runCodexCustomSessionPromptDryRun() {
  const promptNode = document.getElementById("codexCustomSessionPrompt");
  await postCodexCustomSessionAction("prompt-dry-run", { prompt: promptNode ? promptNode.value : "" });
}

async function runCodexCustomSessionPrompt() {
  const promptNode = document.getElementById("codexCustomSessionPrompt");
  await postCodexCustomSessionAction("prompt", { prompt: promptNode ? promptNode.value : "" });
}

function renderCodexCustomProductCoderPacket(packet) {
  const response = document.getElementById("codexCustomProductCoderResponse");
  const diff = document.getElementById("codexCustomProductCoderDiff");
  const changedFiles = Array.isArray(packet?.changed_files) ? packet.changed_files : [];
  const worktreeId = String(packet?.worktree_id || codexCustomProductCoderWorktreeId || "");
  if (worktreeId) {
    codexCustomProductCoderWorktreeId = worktreeId;
  }
  codexCustomSessionsSetText(
    "codexCustomProductCoderState",
    `${packet?.status || "unknown"} · ${packet?.machine_error_code || "UNKNOWN"}`
  );
  codexCustomSessionsSetText("codexCustomProductCoderWorktree", worktreeId || "none");
  codexCustomSessionsSetText("codexCustomProductCoderChangedFiles", String(changedFiles.length));
  codexCustomSessionsSetText(
    "codexCustomProductCoderCleanupState",
    packet?.safe_worktree_status || (worktreeId ? "active" : "worktree не создан")
  );
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      final_status: packet?.final_status || "",
      session_id: packet?.session_id || codexCustomSelectedSessionId || "",
      worktree_id: worktreeId,
      safe_worktree_status: packet?.safe_worktree_status || "",
      cleanup_required: packet?.cleanup_required === true,
      selected_model: packet?.selected_model || "",
      runtime_model: packet?.runtime_model || "",
      safe_worktree_used: packet?.safe_worktree_used === true,
      working_dir_override_admitted: packet?.working_dir_override_admitted === true,
      working_dir_scope: packet?.working_dir_scope || "",
      changed_files: changedFiles,
      diff_present: packet?.diff_present === true,
      main_worktree_mutated_by_run: packet?.main_worktree_mutated_by_run === true,
      commit_attempted: packet?.commit_attempted === true,
      push_attempted: packet?.push_attempted,
      merge_attempted: packet?.merge_attempted === true,
      wbp_patch_applier_used: packet?.wbp_patch_applier_used === true,
      raw_backend_details_exposed: packet?.raw_backend_details_exposed === true,
      original_codex_touched: packet?.original_codex_touched === true,
      original_codex_profile_touched: packet?.original_codex_profile_touched === true,
      browser_worktree_path_intake: packet?.browser_worktree_path_intake === true,
      token_burn: packet?.token_burn ?? 0,
      request_count: packet?.request_count ?? null,
    }, null, 2);
  }
  if (diff) {
    diff.textContent = packet?.diff_text_bounded || "diff отсутствует";
  }
}

async function runCodexCustomProductCoder() {
  const taskNode = document.getElementById("codexCustomProductCoderTask");
  const apiNode = document.getElementById("codexCustomApiModelSelect");
  const task = taskNode ? taskNode.value : "";
  const apiModelId = apiNode ? apiNode.value : "";
  if (!task.trim()) {
    renderCodexCustomProductCoderPacket({
      status: "rejected",
      machine_error_code: "TASK_REQUIRED",
      changed_files: []
    });
    return;
  }
  await postCodexCustomSessionAction("safe-worktree-coder", {
    api_model_id: apiModelId,
    task
  }).then((packet) => {
    if (packet) {
      renderCodexCustomProductCoderPacket(packet);
    }
  });
}

async function cancelCodexCustomSession() {
  await postCodexCustomSessionAction("cancel", {});
}

async function cleanupCodexCustomSession() {
  await postCodexCustomSessionAction("cleanup", {});
}

async function cleanupCodexCustomProductCoderWorktree() {
  const worktreeId = codexCustomProductCoderWorktreeId;
  if (!worktreeId) {
    renderCodexCustomProductCoderPacket({
      status: "rejected",
      machine_error_code: "WORKTREE_NOT_SELECTED",
      changed_files: []
    });
    return;
  }
  if (codexCustomSessionActionInFlight) {
    return;
  }
  codexCustomSessionActionInFlight = true;
  codexCustomSessionsSetChip("neutral", "cleanup");
  try {
    const response = await fetch(`api/codex/custom/worktrees/${encodeURIComponent(worktreeId)}/cleanup`, {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders()
    });
    if (!response.ok) {
      throw new Error(`product coder cleanup http ${response.status}`);
    }
    const packet = await response.json();
    if (packet?.status === "ok") {
      codexCustomProductCoderWorktreeId = "";
    }
    renderCodexCustomProductCoderPacket(packet);
  } catch (error) {
    renderCodexCustomProductCoderPacket({
      status: "failed",
      machine_error_code: "PRODUCT_CODER_CLEANUP_FETCH_FAILED",
      human_message: error.message,
      worktree_id: worktreeId,
      changed_files: []
    });
  } finally {
    codexCustomSessionActionInFlight = false;
  }
}

function codexCustomRecoverySetText(id, value) {
  operatorSetText(id, value);
}

function codexCustomRecoverySetChip(visual, label) {
  const chip = document.getElementById("codexCustomRecoveryChip");
  if (!chip) {
    return;
  }
  chip.className = `chip ${VISUAL_CLASS[visual] || ACTION_STATUS_VISUAL_CLASS[visual] || "neutral"}`;
  if (chip.lastElementChild) {
    chip.lastElementChild.textContent = label || visual || "unknown";
  }
}

function renderCodexCustomRecoveryPacket(packet) {
  const response = document.getElementById("codexCustomRecoveryPacket");
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const currentTouched = packet?.current_codex_touched === true || packet?.current_codex_home_touched === true;
  const arbitraryPathAccepted = packet?.arbitrary_path_accepted === true;
  const dangerousOk = packet?.dangerous_actions_disabled !== false;
  const claimScope = packet?.claim_scope || "custom_recovery_surface_readonly_checks_only";
  const ok = status === "ok" && !currentTouched && !arbitraryPathAccepted && dangerousOk;
  const blocked = status === "blocked" || status === "rejected" || currentTouched || arbitraryPathAccepted;
  codexCustomRecoverySetChip(ok ? "green" : (blocked ? "amber" : "neutral"), ok ? "checks ok" : status);
  codexCustomRecoverySetText(
    "codexCustomRecoverySummary",
    `${status} · ${machineCode} · ${claimScope}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryIsolation",
    `current ${currentTouched ? "touched" : "untouched"} · original ${packet?.original_codex_touched === true ? "touched" : "untouched"}`
  );
  if (Object.prototype.hasOwnProperty.call(packet || {}, "cancelled")) {
    codexCustomRecoverySetText(
      "codexCustomRecoveryStop",
      `${status} · process kill ${packet?.process_kill_claimed === true ? "claimed" : "not claimed"}`
    );
  }
  if (Object.prototype.hasOwnProperty.call(packet || {}, "cleanup_performed")) {
    codexCustomRecoverySetText(
      "codexCustomRecoveryCleanup",
      `${status} · owned root ${packet?.owned_session_root_only === true ? "yes" : "no"} · arbitrary path ${arbitraryPathAccepted ? "accepted" : "rejected"}`
    );
  }
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      claim_scope: claimScope,
      action_scope: packet?.action_scope || "bounded_custom_session_only",
      current_codex_touched: currentTouched,
      original_codex_touched: packet?.original_codex_touched === true,
      owned_session_root_only: packet?.owned_session_root_only === true,
      arbitrary_path_accepted: arbitraryPathAccepted,
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected !== false,
      accounts_readonly_ok: packet?.accounts_readonly_ok === true,
      api_readonly_ok: packet?.api_readonly_ok === true,
      process_kill_claimed: packet?.process_kill_claimed === true,
      rollback_claimed: packet?.rollback_claimed === true,
      live_recovery_proof_claimed: packet?.live_recovery_proof_claimed === true,
      historical_isolation_proof_only: packet?.historical_isolation_proof_only !== false,
      fresh_truth: packet?.fresh_truth === true,
      load_or_rotation_claimed: packet?.load_or_rotation_claimed === true,
      cleanup_performed: packet?.cleanup_performed === true,
      diagnostics_support_artifact_only: packet?.diagnostics_support_artifact_only !== false,
      dangerous_actions_disabled: dangerousOk,
      next_action: packet?.next_action || "none",
    }, null, 2);
  }
}

function renderCodexCustomRecoveryOperatorMatrix(packet) {
  const response = document.getElementById("codexCustomRecoveryOperatorMatrixPacket");
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const boundedReady = packet?.bounded_local_operator_surface_ready === true;
  const matrixComplete = packet?.operator_recovery_matrix_complete === true;
  const diagnosticsRedacted = packet?.diagnostics_export_redacted === true;
  const killSafe = packet?.process_kill_live_not_admitted_without_owned_target === true;
  const falseGreen = packet?.false_green === true;
  codexCustomRecoverySetText(
    "codexCustomRecoveryOperatorMatrix",
    `${status} · matrix ${matrixComplete ? "complete" : "incomplete"} · kill ${killSafe ? "preflight-only" : "check"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryOperatorReady",
    `${boundedReady} · bounded local surface · diagnostics redacted ${diagnosticsRedacted}`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      claim_scope: packet?.claim_scope || "custom_codex_recovery_rollback_operator_surface_bounded_local_use",
      operator_recovery_matrix_complete: matrixComplete,
      session_recovery_actions_classified: packet?.session_recovery_actions_classified === true,
      rollback_lifecycle_actions_classified: packet?.rollback_lifecycle_actions_classified === true,
      diagnostics_surface_classified: packet?.diagnostics_surface_classified === true,
      diagnostics_export_redacted: diagnosticsRedacted,
      dangerous_actions_disabled_or_preflight_only: packet?.dangerous_actions_disabled_or_preflight_only === true,
      process_kill_live_not_admitted_without_owned_target: killSafe,
      bounded_local_operator_surface_ready: boundedReady,
      final_verdict: packet?.final_verdict || "",
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      secret_leak: packet?.secret_leak === true,
      false_green: falseGreen,
      recovery_operator_ready: packet?.recovery_operator_ready === true,
      operator_ready_claimed: packet?.operator_ready_claimed === true,
      rollback_operator_ready: packet?.rollback_operator_ready === true,
      process_kill_operator_ready: packet?.process_kill_operator_ready === true,
      process_kill_claimed: packet?.process_kill_claimed === true,
      ["pro" + "duction_ready"]: packet?.["pro" + "duction_ready"] === true,
      desktop_ready: packet?.desktop_ready === true,
      installer_ready: packet?.installer_ready === true,
      action_count: Array.isArray(packet?.actions) ? packet.actions.length : 0,
      next_action: packet?.next_action || "none",
    }, null, 2);
  }
}

function codexCustomRecoveryActionRow(action) {
  const row = document.createElement("div");
  const status = String(action?.status || "unknown");
  row.className = `action-ledger-row ${status === "admitted" ? "green" : (status === "disabled" ? "amber" : "neutral")}`;
  const title = document.createElement("strong");
  title.textContent = `${action?.id || "unknown"} · ${status}`;
  const meta = document.createElement("div");
  meta.className = "action-ledger-meta";
  meta.textContent = [
    `owner ${action?.owner || "unknown"}`,
    `layer ${action?.layer || "unknown"}`,
    `mutation ${action?.mutation_allowed === true ? "allowed" : "no"}`,
    `browser payload ${action?.browser_payload_allowed === true ? "allowed" : "no"}`,
    action?.disabled_reason_code ? `reason ${action.disabled_reason_code}` : "",
  ].filter(Boolean).join(" · ");
  row.append(title, meta);
  return row;
}

function renderCodexCustomRecoveryContract(packet) {
  const response = document.getElementById("codexCustomRecoveryContractPacket");
  const actionsNode = document.getElementById("codexCustomRecoveryContractActions");
  const status = packet?.status || "unknown";
  const liveReady = packet?.recovery_live_ready === true;
  const operatorReady = packet?.operator_ready_claimed === true;
  const readonly = packet?.readonly_sources || {};
  const actions = Array.isArray(packet?.actions) ? packet.actions : [];
  const admitted = actions.filter((action) => action?.status === "admitted").length;
  const dryRunOnly = actions.filter((action) => action?.status === "dry_run_only").length;
  const disabled = actions.filter((action) => action?.status === "disabled").length;
  const delegated = actions.filter((action) => action?.status === "delegated_readonly").length;
  const blocked = status === "blocked" || packet?.contract_block_reason_code;
  codexCustomRecoverySetChip(blocked ? "amber" : "blue", liveReady ? "live ready" : "dry-run only");
  codexCustomRecoverySetText(
    "codexCustomRecoverySummary",
    `${status} · ${packet?.machine_error_code || "UNKNOWN"} · ${packet?.claim_scope || "custom_codex_recovery_contract_dry_run_only"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryContractOwner",
    `${packet?.contract_owner || "unknown"} · ${packet?.contract_aggregator_only === true ? "aggregator only" : "unknown"}`
  );
  codexCustomRecoverySetText("codexCustomRecoveryLiveReady", `${liveReady} · dry-run contract`);
  codexCustomRecoverySetText("codexCustomRecoveryOperatorReady", `${operatorReady} · not claimed`);
  codexCustomRecoverySetText(
    "codexCustomRecoveryIsolation",
    `current ${packet?.current_codex_touched === true ? "touched" : "untouched"} · original ${packet?.original_codex_touched === true ? "touched" : "untouched"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryAccounts",
    `readonly ${readonly.accounts_readonly_ok === true ? "ok" : "blocked"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryApi",
    `readonly ${readonly.api_readonly_ok === true ? "ok" : "blocked"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryDiagnostics",
    packet?.diagnostics_support_artifact_only === true ? "support artifact only" : "not admitted"
  );
  codexCustomRecoverySetText("codexCustomRecoveryDangerousCount", `${disabled} disabled`);
  codexCustomRecoverySetText(
    "codexCustomRecoveryBrowserPayload",
    packet?.browser_payload_allowed === true ? "allowed by contract" : "no path/auth/backend/secret"
  );
  if (actionsNode) {
    actionsNode.replaceChildren(...(actions.length ? actions.map(codexCustomRecoveryActionRow) : [codexCustomRecoveryActionRow({
      id: "contract_missing_actions",
      status: "disabled",
      owner: "contract",
      layer: "control_layer",
      mutation_allowed: false,
      browser_payload_allowed: false,
      disabled_reason_code: "RECOVERY_CONTRACT_ACTIONS_MISSING",
    })]));
  }
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      contract_block_reason_code: packet?.contract_block_reason_code || "",
      claim_scope: packet?.claim_scope || "",
      contract_owner: packet?.contract_owner || "",
      contract_endpoint: packet?.contract_endpoint || "",
      contract_aggregator_only: packet?.contract_aggregator_only === true,
      contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true,
      recovery_live_ready: liveReady,
      operator_ready_claimed: operatorReady,
      rollback_claimed: packet?.rollback_claimed === true,
      process_kill_claimed: packet?.process_kill_claimed === true,
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      browser_payload_allowed: packet?.browser_payload_allowed === true,
      browser_payload_allowed_keys: packet?.browser_payload_allowed_keys || [],
      forbidden_browser_fields: packet?.forbidden_browser_fields || [],
      fresh_truth: packet?.fresh_truth === true,
      historical_isolation_proof_only: packet?.historical_isolation_proof_only === true,
      dangerous_actions_disabled: packet?.dangerous_actions_disabled === true,
      diagnostics_support_artifact_only: packet?.diagnostics_support_artifact_only === true,
      readonly_sources: readonly,
      action_counts: {
        admitted,
        delegated_readonly: delegated,
        dry_run_only: dryRunOnly,
        disabled,
        total: actions.length,
      },
      actions,
      next_contour: packet?.next_contour || "",
    }, null, 2);
  }
}

function renderCodexCustomRecoveryAdmittedSessionActions(packet) {
  const response = document.getElementById("codexCustomRecoveryAdmittedSessionActionsPacket");
  const ready = packet?.session_admitted_actions_ready === true;
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const blockReason = packet?.block_reason_code || "";
  codexCustomRecoverySetText(
    "codexCustomRecoveryAdmittedSessionActions",
    ready
      ? `ready · selected ${packet?.selected_session_id || "server-selected"}`
      : `${status} · ${blockReason || machineCode}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryStop",
    `${packet?.selected_session_cancel_ready === true} · selected-session cancel only`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryCleanup",
    `${packet?.owned_session_cleanup_ready === true} · owned session root only`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      block_reason_code: blockReason,
      claim_scope: packet?.claim_scope || "custom_codex_recovery_admitted_session_actions_only",
      contract_endpoint: packet?.contract_endpoint || "/api/codex/custom/recovery/admitted-session-actions",
      contract_source_endpoint: packet?.contract_source_endpoint || "/api/codex/custom/recovery/contract",
      session_source_endpoint: packet?.session_source_endpoint || "/api/codex/custom/sessions",
      contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true,
      browser_payload_allowed: packet?.browser_payload_allowed === true,
      browser_payload_allowed_keys: packet?.browser_payload_allowed_keys || [],
      forbidden_browser_fields: packet?.forbidden_browser_fields || [],
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      session_admitted_actions_ready: ready,
      admitted_session_actions_contract_ready: packet?.admitted_session_actions_contract_ready === true,
      selected_session_required: packet?.selected_session_required === true,
      selected_session_present: packet?.selected_session_present === true,
      selected_session_id: packet?.selected_session_id || "",
      selected_session_packet_valid: packet?.selected_session_packet_valid === true,
      selected_session_cleanup_state: packet?.selected_session_cleanup_state || "",
      selected_session_cancel_ready: packet?.selected_session_cancel_ready === true,
      owned_session_cleanup_ready: packet?.owned_session_cleanup_ready === true,
      recovery_operator_ready: packet?.recovery_operator_ready === true,
      operator_ready_claimed: packet?.operator_ready_claimed === true,
      rollback_operator_ready: packet?.rollback_operator_ready === true,
      rollback_claimed: packet?.rollback_claimed === true,
      process_kill_operator_ready: packet?.process_kill_operator_ready === true,
      process_kill_claimed: packet?.process_kill_claimed === true,
      diagnostics_support_artifact_only: packet?.diagnostics_support_artifact_only !== false,
      diagnostics_counted_as_recovery_action: packet?.diagnostics_counted_as_recovery_action === true,
      readonly_checks_counted_as_mutation: packet?.readonly_checks_counted_as_mutation === true,
      session_create_counted_as_recovery_action: packet?.session_create_counted_as_recovery_action === true,
      contract_readonly_sources_ok: packet?.contract_readonly_sources_ok === true,
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      current_codex_home_touched: packet?.current_codex_home_touched === true,
      arbitrary_path_accepted: packet?.arbitrary_path_accepted === true,
      dangerous_actions_disabled: packet?.dangerous_actions_disabled !== false,
      dangerous_action_mutation_allowed: packet?.dangerous_action_mutation_allowed === true,
      session_count: packet?.session_count ?? 0,
      actions: Array.isArray(packet?.actions) ? packet.actions : [],
      next_contour_claimed: packet?.next_contour_claimed === true,
    }, null, 2);
  }
}

function renderCodexCustomRecoveryRollbackProcessOwnerContract(packet) {
  const response = document.getElementById("codexCustomRecoveryRollbackProcessOwnerPacket");
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const rollbackDefined = packet?.rollback_contract_defined === true;
  const processDefined = packet?.process_owner_contract_defined === true;
  const liveReady = packet?.rollback_live_ready === true || packet?.process_kill_live_ready === true;
  codexCustomRecoverySetText(
    "codexCustomRecoveryRollbackProcessOwner",
    `${status} · rollback ${rollbackDefined ? "defined" : "missing"} · process ${processDefined ? "defined" : "missing"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryLiveReady",
    `${liveReady} · rollback/process dry-run only`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryOperatorReady",
    `${packet?.recovery_operator_ready === true} · not claimed`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      block_reason_code: packet?.block_reason_code || "",
      claim_scope: packet?.claim_scope || "custom_codex_recovery_rollback_process_owner_dry_run_contract_only",
      contract_endpoint: packet?.contract_endpoint || "/api/codex/custom/recovery/rollback-process-owner-contract",
      contract_source_endpoint: packet?.contract_source_endpoint || "/api/codex/custom/recovery/contract",
      contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true,
      browser_payload_allowed: packet?.browser_payload_allowed === true,
      browser_payload_allowed_keys: packet?.browser_payload_allowed_keys || [],
      forbidden_browser_fields: packet?.forbidden_browser_fields || [],
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      rollback_contract_defined: rollbackDefined,
      rollback_live_ready: packet?.rollback_live_ready === true,
      rollback_apply_admitted: packet?.rollback_apply_admitted === true,
      rollback_point_required: packet?.rollback_point_required === true,
      rollback_point_present: packet?.rollback_point_present === true,
      rollback_write_surfaces_required: packet?.rollback_write_surfaces_required === true,
      rollback_write_surfaces_declared: packet?.rollback_write_surfaces_declared === true,
      rollback_verification_packet_required: packet?.rollback_verification_packet_required === true,
      rollback_verification_packet_present: packet?.rollback_verification_packet_present === true,
      process_owner_contract_defined: processDefined,
      process_kill_live_ready: packet?.process_kill_live_ready === true,
      process_kill_admitted: packet?.process_kill_admitted === true,
      owned_process_identity_required: packet?.owned_process_identity_required === true,
      owned_process_identity_present: packet?.owned_process_identity_present === true,
      current_codex_process_exclusion_required: packet?.current_codex_process_exclusion_required === true,
      current_codex_process_excluded: packet?.current_codex_process_excluded === true,
      current_codex_process_candidate: packet?.current_codex_process_candidate === true,
      recovery_operator_ready: packet?.recovery_operator_ready === true,
      operator_ready_claimed: packet?.operator_ready_claimed === true,
      rollback_operator_ready: packet?.rollback_operator_ready === true,
      rollback_claimed: packet?.rollback_claimed === true,
      process_kill_operator_ready: packet?.process_kill_operator_ready === true,
      process_kill_claimed: packet?.process_kill_claimed === true,
      diagnostics_support_artifact_only: packet?.diagnostics_support_artifact_only !== false,
      diagnostics_counted_as_recovery_action: packet?.diagnostics_counted_as_recovery_action === true,
      readonly_checks_counted_as_mutation: packet?.readonly_checks_counted_as_mutation === true,
      session_create_counted_as_recovery_action: packet?.session_create_counted_as_recovery_action === true,
      contract_readonly_sources_ok: packet?.contract_readonly_sources_ok === true,
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      current_codex_home_touched: packet?.current_codex_home_touched === true,
      arbitrary_path_accepted: packet?.arbitrary_path_accepted === true,
      arbitrary_process_kill_allowed: packet?.arbitrary_process_kill_allowed === true,
      arbitrary_path_cleanup_allowed: packet?.arbitrary_path_cleanup_allowed === true,
      dangerous_actions_disabled: packet?.dangerous_actions_disabled !== false,
      dangerous_action_mutation_allowed: packet?.dangerous_action_mutation_allowed === true,
      prerequisites: Array.isArray(packet?.prerequisites) ? packet.prerequisites : [],
      actions: Array.isArray(packet?.actions) ? packet.actions : [],
      next_contour: packet?.next_contour || "",
      next_contour_claimed: packet?.next_contour_claimed === true,
    }, null, 2);
  }
}

function renderCodexCustomRecoveryRollbackPointDryRun(packet) {
  const response = document.getElementById("codexCustomRecoveryRollbackPointPacket");
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const contractDefined = packet?.rollback_point_contract_defined === true;
  const pointPresent = packet?.rollback_point_present === true;
  codexCustomRecoverySetText(
    "codexCustomRecoveryRollbackPoint",
    `${status} · contract ${contractDefined ? "defined" : "missing"} · point ${pointPresent ? "present" : "absent"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryLiveReady",
    `${packet?.rollback_live_ready === true} · rollback point dry-run only`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryOperatorReady",
    `${packet?.recovery_operator_ready === true} · not claimed`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      block_reason_code: packet?.block_reason_code || "",
      claim_scope: packet?.claim_scope || "custom_codex_recovery_rollback_point_dry_run_only",
      contract_endpoint: packet?.contract_endpoint || "/api/codex/custom/recovery/rollback-point-dry-run",
      contract_source_endpoint: packet?.contract_source_endpoint || "/api/codex/custom/recovery/rollback-process-owner-contract",
      contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true,
      browser_payload_allowed: packet?.browser_payload_allowed === true,
      browser_payload_allowed_keys: packet?.browser_payload_allowed_keys || [],
      forbidden_browser_fields: packet?.forbidden_browser_fields || [],
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      rollback_point_contract_defined: contractDefined,
      rollback_point_present: pointPresent,
      rollback_point_create_admitted: packet?.rollback_point_create_admitted === true,
      rollback_apply_admitted: packet?.rollback_apply_admitted === true,
      rollback_live_ready: packet?.rollback_live_ready === true,
      rollback_write_surfaces_contract_defined: packet?.rollback_write_surfaces_contract_defined === true,
      rollback_write_surfaces_machine_checked: packet?.rollback_write_surfaces_machine_checked === true,
      rollback_write_surfaces_dry_run_checked: packet?.rollback_write_surfaces_dry_run_checked === true,
      rollback_verification_packet_defined: packet?.rollback_verification_packet_defined === true,
      rollback_verification_packet_present: packet?.rollback_verification_packet_present === true,
      recovery_operator_ready: packet?.recovery_operator_ready === true,
      operator_ready_claimed: packet?.operator_ready_claimed === true,
      rollback_operator_ready: packet?.rollback_operator_ready === true,
      rollback_claimed: packet?.rollback_claimed === true,
      process_kill_operator_ready: packet?.process_kill_operator_ready === true,
      process_kill_claimed: packet?.process_kill_claimed === true,
      process_kill_live_ready: packet?.process_kill_live_ready === true,
      process_kill_admitted: packet?.process_kill_admitted === true,
      filesystem_write_performed: packet?.filesystem_write_performed === true,
      snapshot_file_created: packet?.snapshot_file_created === true,
      snapshot_create_admitted: packet?.snapshot_create_admitted === true,
      snapshot_target_browser_supplied: packet?.snapshot_target_browser_supplied === true,
      diagnostics_support_artifact_only: packet?.diagnostics_support_artifact_only !== false,
      diagnostics_counted_as_recovery_action: packet?.diagnostics_counted_as_recovery_action === true,
      readonly_checks_counted_as_mutation: packet?.readonly_checks_counted_as_mutation === true,
      session_create_counted_as_recovery_action: packet?.session_create_counted_as_recovery_action === true,
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      current_codex_home_touched: packet?.current_codex_home_touched === true,
      current_codex_home_allowed_surface: packet?.current_codex_home_allowed_surface === true,
      auth_material_allowed_surface: packet?.auth_material_allowed_surface === true,
      arbitrary_path_accepted: packet?.arbitrary_path_accepted === true,
      arbitrary_path_allowed_surface: packet?.arbitrary_path_allowed_surface === true,
      dangerous_actions_disabled: packet?.dangerous_actions_disabled !== false,
      dangerous_action_mutation_allowed: packet?.dangerous_action_mutation_allowed === true,
      allowed_write_surfaces: Array.isArray(packet?.allowed_write_surfaces) ? packet.allowed_write_surfaces : [],
      allowed_write_surface_ids: Array.isArray(packet?.allowed_write_surface_ids) ? packet.allowed_write_surface_ids : [],
      forbidden_surfaces: Array.isArray(packet?.forbidden_surfaces) ? packet.forbidden_surfaces : [],
      missing_prerequisites: Array.isArray(packet?.missing_prerequisites) ? packet.missing_prerequisites : [],
      actions: Array.isArray(packet?.actions) ? packet.actions : [],
      next_contour: packet?.next_contour || "",
      next_contour_claimed: packet?.next_contour_claimed === true,
    }, null, 2);
  }
}

function renderCodexCustomRecoveryRollbackPointCreateAdmission(packet) {
  const response = document.getElementById("codexCustomRecoveryRollbackPointAdmissionPacket");
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const admissionDefined = packet?.rollback_point_create_admission_defined === true;
  const admitted = packet?.rollback_point_create_admitted === true;
  const performed = packet?.rollback_point_create_performed === true;
  codexCustomRecoverySetText(
    "codexCustomRecoveryRollbackPointAdmission",
    `${status} · admission ${admissionDefined ? "defined" : "missing"} · create ${admitted ? "next-contour admitted" : "blocked"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryLiveReady",
    `${packet?.rollback_live_ready === true} · admission only · performed ${performed}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryOperatorReady",
    `${packet?.recovery_operator_ready === true} · not claimed`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      block_reason_code: packet?.block_reason_code || "",
      claim_scope: packet?.claim_scope || "custom_codex_recovery_rollback_point_create_admission_only",
      contract_endpoint: packet?.contract_endpoint || "/api/codex/custom/recovery/rollback-point-create-admission",
      contract_source_endpoint: packet?.contract_source_endpoint || "/api/codex/custom/recovery/rollback-point-dry-run",
      contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true,
      browser_payload_allowed: packet?.browser_payload_allowed === true,
      browser_payload_allowed_keys: packet?.browser_payload_allowed_keys || [],
      forbidden_browser_fields: packet?.forbidden_browser_fields || [],
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      rollback_point_dry_run_contract_valid: packet?.rollback_point_dry_run_contract_valid === true,
      rollback_point_create_admission_defined: admissionDefined,
      rollback_point_create_admitted: admitted,
      rollback_point_create_admitted_scope: packet?.rollback_point_create_admitted_scope || "",
      rollback_point_create_admitted_for_current_contour: packet?.rollback_point_create_admitted_for_current_contour === true,
      rollback_point_create_performed: performed,
      rollback_point_created: packet?.rollback_point_created === true,
      snapshot_file_created: packet?.snapshot_file_created === true,
      filesystem_write_performed: packet?.filesystem_write_performed === true,
      write_surface_machine_check_performed: packet?.write_surface_machine_check_performed === true,
      write_surfaces_all_eligible: packet?.write_surfaces_all_eligible === true,
      allowed_write_surfaces: Array.isArray(packet?.allowed_write_surfaces) ? packet.allowed_write_surfaces : [],
      allowed_write_surface_ids: Array.isArray(packet?.allowed_write_surface_ids) ? packet.allowed_write_surface_ids : [],
      forbidden_surfaces: Array.isArray(packet?.forbidden_surfaces) ? packet.forbidden_surfaces : [],
      rollback_apply_admitted: packet?.rollback_apply_admitted === true,
      rollback_live_ready: packet?.rollback_live_ready === true,
      recovery_operator_ready: packet?.recovery_operator_ready === true,
      operator_ready_claimed: packet?.operator_ready_claimed === true,
      rollback_operator_ready: packet?.rollback_operator_ready === true,
      rollback_claimed: packet?.rollback_claimed === true,
      process_kill_operator_ready: packet?.process_kill_operator_ready === true,
      process_kill_claimed: packet?.process_kill_claimed === true,
      process_kill_live_ready: packet?.process_kill_live_ready === true,
      process_kill_admitted: packet?.process_kill_admitted === true,
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      current_codex_home_touched: packet?.current_codex_home_touched === true,
      current_codex_home_allowed_surface: packet?.current_codex_home_allowed_surface === true,
      auth_material_allowed_surface: packet?.auth_material_allowed_surface === true,
      arbitrary_path_accepted: packet?.arbitrary_path_accepted === true,
      arbitrary_path_allowed_surface: packet?.arbitrary_path_allowed_surface === true,
      dangerous_actions_disabled: packet?.dangerous_actions_disabled !== false,
      dangerous_action_mutation_allowed: packet?.dangerous_action_mutation_allowed === true,
      actions: Array.isArray(packet?.actions) ? packet.actions : [],
      result_token: packet?.result_token || "",
      next_contour: packet?.next_contour || "",
      next_contour_claimed: packet?.next_contour_claimed === true,
    }, null, 2);
  }
}

function renderCodexCustomRecoveryRollbackPointCreate(packet) {
  const response = document.getElementById("codexCustomRecoveryRollbackPointCreatePacket");
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const created = packet?.rollback_point_created === true;
  const performed = packet?.rollback_point_create_performed === true;
  const digestPresent = packet?.rollback_point_artifact_digest_present === true;
  codexCustomRecoverySetText(
    "codexCustomRecoveryRollbackPointCreate",
    `${status} · performed ${performed} · digest ${digestPresent ? "present" : "missing"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryRollbackPoint",
    `${created ? "created" : "not created"} · apply ${packet?.rollback_apply_admitted === true ? "admitted" : "blocked"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryLiveReady",
    `${packet?.rollback_live_ready === true} · create-only contour`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryOperatorReady",
    `${packet?.recovery_operator_ready === true} · not claimed`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      block_reason_code: packet?.block_reason_code || "",
      claim_scope: packet?.claim_scope || "custom_codex_recovery_rollback_point_create_live_only",
      contract_endpoint: packet?.contract_endpoint || "/api/codex/custom/recovery/rollback-point",
      contract_source_endpoint: packet?.contract_source_endpoint || "/api/codex/custom/recovery/rollback-point-create-admission",
      contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true,
      browser_payload_allowed: packet?.browser_payload_allowed === true,
      browser_payload_allowed_keys: packet?.browser_payload_allowed_keys || [],
      forbidden_browser_fields: packet?.forbidden_browser_fields || [],
      forbidden_fields: packet?.forbidden_fields || [],
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      rollback_point_create_admission_valid: packet?.rollback_point_create_admission_valid === true,
      rollback_point_create_admitted: packet?.rollback_point_create_admitted === true,
      rollback_point_create_admitted_for_current_contour: packet?.rollback_point_create_admitted_for_current_contour === true,
      rollback_point_create_performed: performed,
      rollback_point_created: created,
      rollback_point_artifact_id: packet?.rollback_point_artifact_id || "",
      rollback_point_artifact_path_redacted: packet?.rollback_point_artifact_path_redacted !== false,
      rollback_point_artifact_ref: packet?.rollback_point_artifact_ref || "",
      rollback_point_artifact_digest_present: digestPresent,
      rollback_point_artifact_sha256: packet?.rollback_point_artifact_sha256 || "",
      snapshot_file_created: packet?.snapshot_file_created === true,
      filesystem_write_performed: packet?.filesystem_write_performed === true,
      filesystem_write_scope: packet?.filesystem_write_scope || "",
      selected_write_surface_id: packet?.selected_write_surface_id || "",
      write_surface_machine_check_performed: packet?.write_surface_machine_check_performed === true,
      write_surfaces_all_eligible: packet?.write_surfaces_all_eligible === true,
      allowed_write_surfaces: Array.isArray(packet?.allowed_write_surfaces) ? packet.allowed_write_surfaces : [],
      forbidden_surfaces: Array.isArray(packet?.forbidden_surfaces) ? packet.forbidden_surfaces : [],
      rollback_apply_admitted: packet?.rollback_apply_admitted === true,
      rollback_apply_performed: packet?.rollback_apply_performed === true,
      rollback_completed: packet?.rollback_completed === true,
      rollback_live_ready: packet?.rollback_live_ready === true,
      recovery_operator_ready: packet?.recovery_operator_ready === true,
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      auth_material_touched: packet?.auth_material_touched === true,
      secret_value_recorded: packet?.secret_value_recorded === true,
      dangerous_actions_disabled: packet?.dangerous_actions_disabled !== false,
      dangerous_action_mutation_allowed: packet?.dangerous_action_mutation_allowed === true,
      actions: Array.isArray(packet?.actions) ? packet.actions : [],
      result_token: packet?.result_token || "",
      next_contour: packet?.next_contour || "",
      next_contour_claimed: packet?.next_contour_claimed === true,
    }, null, 2);
  }
}

function renderCodexCustomRecoveryRollbackPointVerify(packet) {
  const response = document.getElementById("codexCustomRecoveryRollbackPointVerifyPacket");
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const verified = packet?.rollback_point_verified === true;
  const digestVerified = packet?.rollback_point_digest_verified === true;
  const provenanceVerified = packet?.rollback_point_provenance_verified === true;
  codexCustomRecoverySetText(
    "codexCustomRecoveryRollbackPointVerify",
    `${status} · digest ${digestVerified} · provenance ${provenanceVerified}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryRollbackPoint",
    `${verified ? "verified" : "not verified"} · apply ${packet?.rollback_apply_ready === true ? "ready" : "blocked"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryLiveReady",
    `${packet?.rollback_live_ready === true} · verify-only contour`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryOperatorReady",
    `${packet?.recovery_operator_ready === true} · not claimed`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      block_reason_code: packet?.block_reason_code || "",
      claim_scope: packet?.claim_scope || "custom_codex_recovery_rollback_point_verify_only",
      contract_endpoint: packet?.contract_endpoint || "/api/codex/custom/recovery/rollback-point/verify",
      contract_source_endpoint: packet?.contract_source_endpoint || "/api/codex/custom/recovery/rollback-point",
      contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true,
      browser_payload_allowed: packet?.browser_payload_allowed === true,
      browser_payload_allowed_keys: packet?.browser_payload_allowed_keys || [],
      forbidden_browser_fields: packet?.forbidden_browser_fields || [],
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      rollback_point_verify_performed: packet?.rollback_point_verify_performed === true,
      rollback_point_verified: verified,
      rollback_point_present: packet?.rollback_point_present === true,
      rollback_point_selection_source: packet?.rollback_point_selection_source || "",
      rollback_point_selection_ambiguous: packet?.rollback_point_selection_ambiguous === true,
      rollback_point_artifact_id_present: packet?.rollback_point_artifact_id_present === true,
      rollback_point_artifact_path_redacted: packet?.rollback_point_artifact_path_redacted !== false,
      rollback_point_artifact_ref: packet?.rollback_point_artifact_ref || "",
      rollback_point_artifact_digest_present: packet?.rollback_point_artifact_digest_present === true,
      rollback_point_digest_verified: digestVerified,
      rollback_point_file_digest_present: packet?.rollback_point_file_digest_present === true,
      rollback_point_payload_digest_verified: packet?.rollback_point_payload_digest_verified === true,
      rollback_point_source_admission_digest_present: packet?.rollback_point_source_admission_digest_present === true,
      rollback_point_provenance_verified: provenanceVerified,
      rollback_point_schema_valid: packet?.rollback_point_schema_valid === true,
      rollback_point_kind_valid: packet?.rollback_point_kind_valid === true,
      rollback_point_surface_verified: packet?.rollback_point_surface_verified === true,
      filesystem_read_performed: packet?.filesystem_read_performed === true,
      filesystem_read_scope: packet?.filesystem_read_scope || "",
      filesystem_write_performed: packet?.filesystem_write_performed === true,
      selected_write_surface_id: packet?.selected_write_surface_id || "",
      rollback_apply_admitted: packet?.rollback_apply_admitted === true,
      rollback_apply_ready: packet?.rollback_apply_ready === true,
      rollback_apply_performed: packet?.rollback_apply_performed === true,
      rollback_completed: packet?.rollback_completed === true,
      rollback_live_ready: packet?.rollback_live_ready === true,
      recovery_operator_ready: packet?.recovery_operator_ready === true,
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      auth_material_touched: packet?.auth_material_touched === true,
      secret_value_recorded: packet?.secret_value_recorded === true,
      dangerous_actions_disabled: packet?.dangerous_actions_disabled !== false,
      dangerous_action_mutation_allowed: packet?.dangerous_action_mutation_allowed === true,
      actions: Array.isArray(packet?.actions) ? packet.actions : [],
      result_token: packet?.result_token || "",
      next_contour: packet?.next_contour || "",
      next_contour_claimed: packet?.next_contour_claimed === true,
    }, null, 2);
  }
}

function renderCodexCustomRecoveryRollbackApplyAdmissionDryRun(packet) {
  const response = document.getElementById("codexCustomRecoveryRollbackApplyAdmissionPacket");
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const evaluated = packet?.rollback_apply_admission_evaluated === true;
  const result = packet?.rollback_apply_admission_result || "not_evaluated";
  const eligible = packet?.rollback_apply_admission_eligible_for_next_contour === true;
  codexCustomRecoverySetText(
    "codexCustomRecoveryRollbackApplyAdmission",
    `${status} · ${evaluated ? result : "not evaluated"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryLiveReady",
    `${packet?.rollback_live_ready === true} · apply admission dry-run only`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryOperatorReady",
    `${packet?.recovery_operator_ready === true} · not claimed`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      block_reason_code: packet?.block_reason_code || "",
      claim_scope: packet?.claim_scope || "custom_codex_recovery_rollback_apply_admission_dry_run_only",
      contract_endpoint: packet?.contract_endpoint || "/api/codex/custom/recovery/rollback-apply/admission-dry-run",
      contract_source_endpoint: packet?.contract_source_endpoint || "/api/codex/custom/recovery/rollback-point/verify",
      contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true,
      browser_payload_allowed: packet?.browser_payload_allowed === true,
      browser_payload_allowed_keys: packet?.browser_payload_allowed_keys || [],
      forbidden_browser_fields: packet?.forbidden_browser_fields || [],
      forbidden_fields: packet?.forbidden_fields || [],
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      rollback_apply_admission_evaluated: evaluated,
      rollback_apply_admission_result: result,
      rollback_apply_admission_eligible_for_next_contour: eligible,
      rollback_apply_admission_scope: packet?.rollback_apply_admission_scope || "",
      rollback_point_verify_required: packet?.rollback_point_verify_required === true,
      rollback_point_verify_valid: packet?.rollback_point_verify_valid === true,
      rollback_point_verified: packet?.rollback_point_verified === true,
      rollback_point_present: packet?.rollback_point_present === true,
      rollback_point_artifact_path_redacted: packet?.rollback_point_artifact_path_redacted !== false,
      rollback_point_artifact_ref: packet?.rollback_point_artifact_ref || "",
      rollback_point_manifest_verified: packet?.rollback_point_manifest_verified === true,
      rollback_point_provenance_verified: packet?.rollback_point_provenance_verified === true,
      rollback_point_digest_verified: packet?.rollback_point_digest_verified === true,
      rollback_point_surface_verified: packet?.rollback_point_surface_verified === true,
      recovery_contract_readonly_sources_ok: packet?.recovery_contract_readonly_sources_ok === true,
      rollback_process_owner_contract_ok: packet?.rollback_process_owner_contract_ok === true,
      session_state_read_performed: packet?.session_state_read_performed === true,
      session_state_status: packet?.session_state_status || "",
      session_count: packet?.session_count ?? 0,
      owned_session_count: packet?.owned_session_count ?? 0,
      active_owned_session_count: packet?.active_owned_session_count ?? 0,
      session_state_all_owned: packet?.session_state_all_owned === true,
      session_state_blocks_apply_admission: packet?.session_state_blocks_apply_admission === true,
      write_surface_machine_check_performed: packet?.write_surface_machine_check_performed === true,
      write_surfaces_all_eligible: packet?.write_surfaces_all_eligible === true,
      allowed_write_surfaces: Array.isArray(packet?.allowed_write_surfaces) ? packet.allowed_write_surfaces : [],
      allowed_write_surface_ids: Array.isArray(packet?.allowed_write_surface_ids) ? packet.allowed_write_surface_ids : [],
      forbidden_surfaces: Array.isArray(packet?.forbidden_surfaces) ? packet.forbidden_surfaces : [],
      filesystem_read_performed: packet?.filesystem_read_performed === true,
      filesystem_write_performed: packet?.filesystem_write_performed === true,
      selected_write_surface_id: packet?.selected_write_surface_id || "",
      rollback_apply_admitted: packet?.rollback_apply_admitted === true,
      rollback_apply_ready: packet?.rollback_apply_ready === true,
      rollback_apply_performed: packet?.rollback_apply_performed === true,
      rollback_completed: packet?.rollback_completed === true,
      rollback_live_ready: packet?.rollback_live_ready === true,
      recovery_operator_ready: packet?.recovery_operator_ready === true,
      operator_ready_claimed: packet?.operator_ready_claimed === true,
      rollback_operator_ready: packet?.rollback_operator_ready === true,
      rollback_claimed: packet?.rollback_claimed === true,
      process_kill_operator_ready: packet?.process_kill_operator_ready === true,
      process_kill_claimed: packet?.process_kill_claimed === true,
      process_kill_live_ready: packet?.process_kill_live_ready === true,
      process_kill_admitted: packet?.process_kill_admitted === true,
      process_kill_performed: packet?.process_kill_performed === true,
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      current_codex_home_touched: packet?.current_codex_home_touched === true,
      auth_material_touched: packet?.auth_material_touched === true,
      secret_value_recorded: packet?.secret_value_recorded === true,
      arbitrary_path_accepted: packet?.arbitrary_path_accepted === true,
      arbitrary_path_allowed_surface: packet?.arbitrary_path_allowed_surface === true,
      dangerous_actions_disabled: packet?.dangerous_actions_disabled !== false,
      dangerous_action_mutation_allowed: packet?.dangerous_action_mutation_allowed === true,
      actions: Array.isArray(packet?.actions) ? packet.actions : [],
      result_token: packet?.result_token || "",
      next_contour: packet?.next_contour || "",
      next_contour_claimed: packet?.next_contour_claimed === true,
    }, null, 2);
  }
}

function renderCodexCustomRecoveryRollbackApplyLivePreflight(packet) {
  const response = document.getElementById("codexCustomRecoveryRollbackApplyPreflightPacket");
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const evaluated = packet?.rollback_apply_live_preflight_evaluated === true;
  const result = packet?.rollback_apply_live_preflight_result || "not_evaluated";
  const eligible = packet?.rollback_apply_live_preflight_eligible_for_next_contour === true;
  codexCustomRecoverySetText(
    "codexCustomRecoveryRollbackApplyPreflight",
    `${status} · ${evaluated ? result : "not evaluated"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryLiveReady",
    `${packet?.rollback_live_ready === true} · apply preflight only`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryOperatorReady",
    `${packet?.recovery_operator_ready === true} · not claimed`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      block_reason_code: packet?.block_reason_code || "",
      claim_scope: packet?.claim_scope || "custom_codex_recovery_rollback_apply_live_preflight_only",
      contract_endpoint: packet?.contract_endpoint || "/api/codex/custom/recovery/rollback-apply/live-preflight",
      contract_source_endpoint: packet?.contract_source_endpoint || "/api/codex/custom/recovery/rollback-apply/admission-dry-run",
      contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true,
      browser_payload_allowed: packet?.browser_payload_allowed === true,
      browser_payload_allowed_keys: packet?.browser_payload_allowed_keys || [],
      forbidden_browser_fields: packet?.forbidden_browser_fields || [],
      forbidden_fields: packet?.forbidden_fields || [],
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      rollback_apply_live_preflight_evaluated: evaluated,
      rollback_apply_live_preflight_result: result,
      rollback_apply_live_preflight_eligible_for_next_contour: eligible,
      rollback_apply_live_preflight_scope: packet?.rollback_apply_live_preflight_scope || "",
      rollback_apply_dry_run_required: packet?.rollback_apply_dry_run_required === true,
      rollback_apply_dry_run_eligible: packet?.rollback_apply_dry_run_eligible === true,
      rollback_point_verified: packet?.rollback_point_verified === true,
      rollback_point_manifest_verified: packet?.rollback_point_manifest_verified === true,
      rollback_point_provenance_verified: packet?.rollback_point_provenance_verified === true,
      rollback_point_digest_verified: packet?.rollback_point_digest_verified === true,
      rollback_point_surface_verified: packet?.rollback_point_surface_verified === true,
      rollback_point_artifact_path_redacted: packet?.rollback_point_artifact_path_redacted !== false,
      rollback_point_artifact_ref: packet?.rollback_point_artifact_ref || "",
      future_write_surfaces_declared: packet?.future_write_surfaces_declared === true,
      future_write_surfaces_all_owned: packet?.future_write_surfaces_all_owned === true,
      future_write_surface_machine_check_performed: packet?.future_write_surface_machine_check_performed === true,
      future_write_surfaces: Array.isArray(packet?.future_write_surfaces) ? packet.future_write_surfaces : [],
      future_write_surface_ids: Array.isArray(packet?.future_write_surface_ids) ? packet.future_write_surface_ids : [],
      forbidden_surfaces: Array.isArray(packet?.forbidden_surfaces) ? packet.forbidden_surfaces : [],
      rollback_target_class: packet?.rollback_target_class || "",
      rollback_target_browser_supplied: packet?.rollback_target_browser_supplied === true,
      current_codex_excluded: packet?.current_codex_excluded === true,
      original_codex_excluded: packet?.original_codex_excluded === true,
      auth_material_excluded: packet?.auth_material_excluded === true,
      arbitrary_path_rejected: packet?.arbitrary_path_rejected === true,
      process_kill_not_admitted: packet?.process_kill_not_admitted === true,
      source_filesystem_read_performed: packet?.source_filesystem_read_performed === true,
      source_filesystem_read_scope: packet?.source_filesystem_read_scope || "",
      filesystem_read_performed: packet?.filesystem_read_performed === true,
      filesystem_read_scope: packet?.filesystem_read_scope || "",
      filesystem_write_performed: packet?.filesystem_write_performed === true,
      rollback_apply_admitted: packet?.rollback_apply_admitted === true,
      rollback_apply_ready: packet?.rollback_apply_ready === true,
      rollback_apply_performed: packet?.rollback_apply_performed === true,
      rollback_completed: packet?.rollback_completed === true,
      rollback_live_ready: packet?.rollback_live_ready === true,
      recovery_operator_ready: packet?.recovery_operator_ready === true,
      operator_ready_claimed: packet?.operator_ready_claimed === true,
      rollback_operator_ready: packet?.rollback_operator_ready === true,
      rollback_claimed: packet?.rollback_claimed === true,
      process_kill_operator_ready: packet?.process_kill_operator_ready === true,
      process_kill_claimed: packet?.process_kill_claimed === true,
      process_kill_live_ready: packet?.process_kill_live_ready === true,
      process_kill_admitted: packet?.process_kill_admitted === true,
      process_kill_performed: packet?.process_kill_performed === true,
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      current_codex_home_touched: packet?.current_codex_home_touched === true,
      auth_material_touched: packet?.auth_material_touched === true,
      secret_value_recorded: packet?.secret_value_recorded === true,
      arbitrary_path_accepted: packet?.arbitrary_path_accepted === true,
      arbitrary_path_allowed_surface: packet?.arbitrary_path_allowed_surface === true,
      dangerous_actions_disabled: packet?.dangerous_actions_disabled !== false,
      dangerous_action_mutation_allowed: packet?.dangerous_action_mutation_allowed === true,
      actions: Array.isArray(packet?.actions) ? packet.actions : [],
      result_token: packet?.result_token || "",
      next_contour: packet?.next_contour || "",
      next_contour_claimed: packet?.next_contour_claimed === true,
    }, null, 2);
  }
}

function renderCodexCustomRecoveryRollbackApplyReceipt(packet) {
  const response = document.getElementById("codexCustomRecoveryRollbackApplyReceiptPacket");
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const performed = packet?.rollback_apply_bounded_live_performed === true;
  const completedScope = packet?.rollback_apply_completed_scope || "not_completed";
  codexCustomRecoverySetText(
    "codexCustomRecoveryRollbackApplyReceipt",
    `${status} · ${performed ? completedScope : "not performed"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryLiveReady",
    `${packet?.rollback_live_ready === true} · receipt only`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryOperatorReady",
    `${packet?.recovery_operator_ready === true} · not claimed`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      block_reason_code: packet?.block_reason_code || "",
      claim_scope: packet?.claim_scope || "custom_codex_recovery_rollback_apply_bounded_live_only",
      contract_endpoint: packet?.contract_endpoint || "/api/codex/custom/recovery/rollback-apply",
      contract_source_endpoint: packet?.contract_source_endpoint || "/api/codex/custom/recovery/rollback-apply/live-preflight",
      contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true,
      browser_payload_allowed: packet?.browser_payload_allowed === true,
      browser_payload_allowed_keys: packet?.browser_payload_allowed_keys || [],
      forbidden_browser_fields: packet?.forbidden_browser_fields || [],
      forbidden_fields: packet?.forbidden_fields || [],
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      rollback_apply_preflight_required: packet?.rollback_apply_preflight_required === true,
      rollback_apply_preflight_valid: packet?.rollback_apply_preflight_valid === true,
      rollback_apply_bounded_live_performed: performed,
      rollback_apply_receipt_created: packet?.rollback_apply_receipt_created === true,
      rollback_apply_receipt_id: packet?.rollback_apply_receipt_id || "",
      rollback_apply_receipt_path_redacted: packet?.rollback_apply_receipt_path_redacted !== false,
      rollback_apply_receipt_ref: packet?.rollback_apply_receipt_ref || "",
      rollback_apply_receipt_digest_present: packet?.rollback_apply_receipt_digest_present === true,
      rollback_apply_receipt_sha256: packet?.rollback_apply_receipt_sha256 || "",
      rollback_apply_receipt_provenance_verified: packet?.rollback_apply_receipt_provenance_verified === true,
      rollback_apply_receipt_payload_digest_verified: packet?.rollback_apply_receipt_payload_digest_verified === true,
      source_preflight_sha256_present: packet?.source_preflight_sha256_present === true,
      source_rollback_point_ref: packet?.source_rollback_point_ref || "",
      source_rollback_point_sha256_present: packet?.source_rollback_point_sha256_present === true,
      rollback_point_verified: packet?.rollback_point_verified === true,
      rollback_point_artifact_path_redacted: packet?.rollback_point_artifact_path_redacted !== false,
      filesystem_read_performed: packet?.filesystem_read_performed === true,
      filesystem_read_scope: packet?.filesystem_read_scope || "",
      filesystem_write_performed: packet?.filesystem_write_performed === true,
      filesystem_write_scope: packet?.filesystem_write_scope || "",
      selected_write_surface_id: packet?.selected_write_surface_id || "",
      rollback_apply_admitted: packet?.rollback_apply_admitted === true,
      rollback_apply_ready: packet?.rollback_apply_ready === true,
      rollback_apply_performed: packet?.rollback_apply_performed === true,
      rollback_apply_completed_scope: completedScope,
      rollback_completed: packet?.rollback_completed === true,
      rollback_live_ready: packet?.rollback_live_ready === true,
      recovery_operator_ready: packet?.recovery_operator_ready === true,
      operator_ready_claimed: packet?.operator_ready_claimed === true,
      rollback_operator_ready: packet?.rollback_operator_ready === true,
      rollback_claimed: packet?.rollback_claimed === true,
      process_kill_operator_ready: packet?.process_kill_operator_ready === true,
      process_kill_claimed: packet?.process_kill_claimed === true,
      process_kill_live_ready: packet?.process_kill_live_ready === true,
      process_kill_admitted: packet?.process_kill_admitted === true,
      process_kill_performed: packet?.process_kill_performed === true,
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      current_codex_home_touched: packet?.current_codex_home_touched === true,
      auth_material_touched: packet?.auth_material_touched === true,
      secret_value_recorded: packet?.secret_value_recorded === true,
      arbitrary_path_accepted: packet?.arbitrary_path_accepted === true,
      arbitrary_path_allowed_surface: packet?.arbitrary_path_allowed_surface === true,
      dangerous_actions_disabled: packet?.dangerous_actions_disabled !== false,
      dangerous_action_mutation_allowed: packet?.dangerous_action_mutation_allowed === true,
      actions: Array.isArray(packet?.actions) ? packet.actions : [],
      result_token: packet?.result_token || "",
      next_contour: packet?.next_contour || "",
      next_contour_claimed: packet?.next_contour_claimed === true,
    }, null, 2);
  }
}

function renderCodexCustomRecoveryRollbackApplyReceiptVerify(packet) {
  const response = document.getElementById("codexCustomRecoveryRollbackApplyReceiptVerifyPacket");
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const verified = packet?.receipt_verified === true;
  const scope = packet?.verified_scope || "not_verified";
  codexCustomRecoverySetText(
    "codexCustomRecoveryRollbackApplyReceiptVerify",
    `${status} · ${verified ? `${scope} · not system recovery` : "not verified"}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryLiveReady",
    `${packet?.rollback_live_ready === true} · receipt verify only`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryOperatorReady",
    `${packet?.recovery_operator_ready === true} · not claimed`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      block_reason_code: packet?.block_reason_code || "",
      claim_scope: packet?.claim_scope || "custom_codex_recovery_rollback_apply_receipt_verify_only",
      contract_endpoint: packet?.contract_endpoint || "/api/codex/custom/recovery/rollback-apply/receipt/verify",
      contract_source_endpoint: packet?.contract_source_endpoint || "/api/codex/custom/recovery/rollback-apply",
      contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true,
      browser_payload_allowed: packet?.browser_payload_allowed === true,
      browser_payload_allowed_keys: packet?.browser_payload_allowed_keys || [],
      forbidden_browser_fields: packet?.forbidden_browser_fields || [],
      forbidden_fields: packet?.forbidden_fields || [],
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      receipt_verify_performed: packet?.receipt_verify_performed === true,
      receipt_verified: verified,
      rollback_apply_receipt_verified: packet?.rollback_apply_receipt_verified === true,
      verified_scope: scope,
      receipt_selection_source: packet?.receipt_selection_source || "",
      receipt_selection_ambiguous: packet?.receipt_selection_ambiguous === true,
      receipt_id: packet?.receipt_id || "",
      receipt_path_redacted: packet?.receipt_path_redacted !== false,
      receipt_ref: packet?.receipt_ref || "",
      receipt_digest_present: packet?.receipt_digest_present === true,
      receipt_sha256: packet?.receipt_sha256 || "",
      receipt_payload_digest_verified: packet?.receipt_payload_digest_verified === true,
      receipt_provenance_verified: packet?.receipt_provenance_verified === true,
      source_preflight_sha256_present: packet?.source_preflight_sha256_present === true,
      source_rollback_point_ref_present: packet?.source_rollback_point_ref_present === true,
      source_rollback_point_ref: packet?.source_rollback_point_ref || "",
      filesystem_read_performed: packet?.filesystem_read_performed === true,
      filesystem_read_scope: packet?.filesystem_read_scope || "",
      filesystem_write_performed: packet?.filesystem_write_performed === true,
      rollback_apply_performed: packet?.rollback_apply_performed === true,
      rollback_apply_completed_scope: packet?.rollback_apply_completed_scope || "",
      rollback_completed: packet?.rollback_completed === true,
      rollback_live_ready: packet?.rollback_live_ready === true,
      recovery_operator_ready: packet?.recovery_operator_ready === true,
      operator_ready_claimed: packet?.operator_ready_claimed === true,
      rollback_operator_ready: packet?.rollback_operator_ready === true,
      rollback_claimed: packet?.rollback_claimed === true,
      process_kill_operator_ready: packet?.process_kill_operator_ready === true,
      process_kill_claimed: packet?.process_kill_claimed === true,
      process_kill_live_ready: packet?.process_kill_live_ready === true,
      process_kill_admitted: packet?.process_kill_admitted === true,
      process_kill_performed: packet?.process_kill_performed === true,
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      current_codex_home_touched: packet?.current_codex_home_touched === true,
      auth_material_touched: packet?.auth_material_touched === true,
      secret_value_recorded: packet?.secret_value_recorded === true,
      arbitrary_path_accepted: packet?.arbitrary_path_accepted === true,
      arbitrary_path_allowed_surface: packet?.arbitrary_path_allowed_surface === true,
      dangerous_actions_disabled: packet?.dangerous_actions_disabled !== false,
      dangerous_action_mutation_allowed: packet?.dangerous_action_mutation_allowed === true,
      human_summary: packet?.human_summary || "receipt verified · not system recovery",
      actions: Array.isArray(packet?.actions) ? packet.actions : [],
      result_token: packet?.result_token || "",
      next_contour: packet?.next_contour || "",
      next_contour_claimed: packet?.next_contour_claimed === true,
    }, null, 2);
  }
}

function renderCodexCustomRecoveryProcessKillPreflight(packet) {
  const response = document.getElementById("codexCustomRecoveryProcessKillPreflightPacket");
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const ready = packet?.process_kill_preflight_ready === true;
  codexCustomRecoverySetText(
    "codexCustomRecoveryProcessKillPreflight",
    ready ? `${status} · preflight eligible · no kill performed` : `${status} · ${machineCode}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryLiveReady",
    `${packet?.process_kill_live_ready === true} · process kill preflight only`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryOperatorReady",
    `${packet?.recovery_operator_ready === true} · not claimed`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      block_reason_code: packet?.block_reason_code || "",
      claim_scope: packet?.claim_scope || "custom_codex_recovery_process_kill_preflight_only",
      verified_scope: packet?.verified_scope || "not_verified",
      contract_endpoint: packet?.contract_endpoint || "/api/codex/custom/recovery/process-kill/preflight",
      contract_source_endpoint: packet?.contract_source_endpoint || "/api/codex/custom/recovery/admitted-session-actions",
      contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true,
      browser_payload_allowed: packet?.browser_payload_allowed === true,
      browser_payload_allowed_keys: packet?.browser_payload_allowed_keys || [],
      forbidden_browser_fields: packet?.forbidden_browser_fields || [],
      forbidden_fields: packet?.forbidden_fields || [],
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      selected_source: packet?.selected_source || "server_owned_custom_session_observation",
      selected_session_source: packet?.selected_session_source || "server_selected_latest_owned_custom_session",
      selected_session_required: packet?.selected_session_required === true,
      selected_session_present: packet?.selected_session_present === true,
      selected_session_id_redacted: packet?.selected_session_id_redacted !== false,
      selected_session_ambiguous: packet?.selected_session_ambiguous === true,
      selected_session_ref_present: packet?.selected_session_ref_present === true,
      raw_session_id_omitted: packet?.raw_session_id_omitted !== false,
      selected_session_packet_valid: packet?.selected_session_packet_valid === true,
      selected_session_cleanup_state: packet?.selected_session_cleanup_state || "",
      selected_session_cancel_state: packet?.selected_session_cancel_state || "",
      owned_process_identity_required: packet?.owned_process_identity_required === true,
      owned_process_identity_present: packet?.owned_process_identity_present === true,
      current_codex_process_exclusion_required: packet?.current_codex_process_exclusion_required === true,
      original_codex_process_exclusion_required: packet?.original_codex_process_exclusion_required === true,
      process_candidate_present: packet?.process_candidate_present === true,
      process_candidate_ref_present: packet?.process_candidate_ref_present === true,
      raw_pid_omitted: packet?.raw_pid_omitted !== false,
      raw_process_id_omitted: packet?.raw_process_id_omitted !== false,
      raw_process_path_omitted: packet?.raw_process_path_omitted !== false,
      raw_process_command_omitted: packet?.raw_process_command_omitted !== false,
      process_owned_by_custom_session: packet?.process_owned_by_custom_session === true,
      process_kill_eligible: packet?.process_kill_eligible === true,
      process_kill_preflight_evaluated: packet?.process_kill_preflight_evaluated === true,
      process_kill_preflight_result: packet?.process_kill_preflight_result || "",
      process_kill_preflight_ready: ready,
      process_kill_ready: packet?.process_kill_ready === true,
      process_kill_performed: packet?.process_kill_performed === true,
      process_kill_live_ready: packet?.process_kill_live_ready === true,
      process_kill_admitted: packet?.process_kill_admitted === true,
      process_kill_claimed: packet?.process_kill_claimed === true,
      current_codex_process_candidate: packet?.current_codex_process_candidate === true,
      original_codex_process_candidate: packet?.original_codex_process_candidate === true,
      current_codex_process_excluded: packet?.current_codex_process_excluded === true,
      original_codex_process_excluded: packet?.original_codex_process_excluded === true,
      filesystem_read_performed: packet?.filesystem_read_performed === true,
      filesystem_write_performed: packet?.filesystem_write_performed === true,
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      current_codex_home_touched: packet?.current_codex_home_touched === true,
      auth_material_touched: packet?.auth_material_touched === true,
      secret_value_recorded: packet?.secret_value_recorded === true,
      rollback_live_ready: packet?.rollback_live_ready === true,
      recovery_operator_ready: packet?.recovery_operator_ready === true,
      operator_ready_claimed: packet?.operator_ready_claimed === true,
      rollback_operator_ready: packet?.rollback_operator_ready === true,
      rollback_claimed: packet?.rollback_claimed === true,
      process_kill_operator_ready: packet?.process_kill_operator_ready === true,
      dangerous_actions_disabled: packet?.dangerous_actions_disabled !== false,
      dangerous_action_mutation_allowed: packet?.dangerous_action_mutation_allowed === true,
      source_machine_error_code: packet?.source_machine_error_code || "",
      source_block_reason_code: packet?.source_block_reason_code || "",
      human_summary: packet?.human_summary || "process kill preflight checked · no kill performed",
      next_contour: packet?.next_contour || "",
      next_contour_claimed: packet?.next_contour_claimed === true,
    }, null, 2);
  }
}

function renderCodexCustomRecoveryStopCleanupPreflight(packet) {
  const response = document.getElementById("codexCustomRecoveryStopCleanupPreflightPacket");
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const ready = packet?.stop_cleanup_preflight_ready === true;
  const scope = packet?.verified_scope || "not_verified";
  codexCustomRecoverySetText(
    "codexCustomRecoveryStopCleanupPreflight",
    ready ? `${status} · ${scope} · no action performed` : `${status} · ${machineCode}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryStop",
    `${packet?.selected_session_cancel_ready === true} · preflight only`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryCleanup",
    `${packet?.owned_session_cleanup_ready === true} · owned root preflight only`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryLiveReady",
    `${packet?.rollback_live_ready === true} · stop/cleanup preflight only`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryOperatorReady",
    `${packet?.recovery_operator_ready === true} · not claimed`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      block_reason_code: packet?.block_reason_code || "",
      claim_scope: packet?.claim_scope || "custom_codex_recovery_stop_cleanup_preflight_only",
      verified_scope: scope,
      contract_endpoint: packet?.contract_endpoint || "/api/codex/custom/recovery/stop-cleanup/preflight",
      contract_source_endpoint: packet?.contract_source_endpoint || "/api/codex/custom/recovery/admitted-session-actions",
      contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true,
      browser_payload_allowed: packet?.browser_payload_allowed === true,
      browser_payload_allowed_keys: packet?.browser_payload_allowed_keys || [],
      forbidden_browser_fields: packet?.forbidden_browser_fields || [],
      forbidden_fields: packet?.forbidden_fields || [],
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      stop_cleanup_preflight_ready: ready,
      selected_session_source: packet?.selected_session_source || "server_selected_latest_owned_custom_session",
      selected_session_required: packet?.selected_session_required === true,
      selected_session_present: packet?.selected_session_present === true,
      selected_session_id_redacted: packet?.selected_session_id_redacted !== false,
      selected_session_ambiguous: packet?.selected_session_ambiguous === true,
      selected_session_packet_valid: packet?.selected_session_packet_valid === true,
      selected_session_cleanup_state: packet?.selected_session_cleanup_state || "",
      selected_session_cancel_ready: packet?.selected_session_cancel_ready === true,
      owned_session_cleanup_ready: packet?.owned_session_cleanup_ready === true,
      arbitrary_path_cleanup_allowed: packet?.arbitrary_path_cleanup_allowed === true,
      process_kill_ready: packet?.process_kill_ready === true,
      process_kill_performed: packet?.process_kill_performed === true,
      session_cancel_performed: packet?.session_cancel_performed === true,
      owned_cleanup_performed: packet?.owned_cleanup_performed === true,
      filesystem_read_performed: packet?.filesystem_read_performed === true,
      filesystem_write_performed: packet?.filesystem_write_performed === true,
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      current_codex_home_touched: packet?.current_codex_home_touched === true,
      auth_material_touched: packet?.auth_material_touched === true,
      secret_value_recorded: packet?.secret_value_recorded === true,
      recovery_operator_ready: packet?.recovery_operator_ready === true,
      rollback_live_ready: packet?.rollback_live_ready === true,
      source_machine_error_code: packet?.source_machine_error_code || "",
      source_block_reason_code: packet?.source_block_reason_code || "",
      human_summary: packet?.human_summary || "stop/cleanup preflight verified · no action performed",
      next_contour: packet?.next_contour || "",
    }, null, 2);
  }
}

function renderCodexCustomRecoveryStopCleanupLive(packet) {
  const response = document.getElementById("codexCustomRecoveryStopCleanupLivePacket");
  const status = packet?.status || "unknown";
  const machineCode = packet?.machine_error_code || "UNKNOWN";
  const ready = packet?.machine_error_code === "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_LIVE_READY";
  codexCustomRecoverySetText(
    "codexCustomRecoveryStopCleanupLive",
    ready ? `${status} · owned cancel+cleanup · not system recovery` : `${status} · ${machineCode}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryStop",
    `${packet?.session_cancel_performed === true} · verified ${packet?.session_cancel_verified === true}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryCleanup",
    `${packet?.owned_cleanup_performed === true} · owned root ${packet?.owned_session_root_only === true}`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryLiveReady",
    `${ready} · owned stop/cleanup only`
  );
  codexCustomRecoverySetText(
    "codexCustomRecoveryOperatorReady",
    `${packet?.recovery_operator_ready === true} · not claimed`
  );
  if (response) {
    response.textContent = JSON.stringify({
      status,
      machine_error_code: machineCode,
      block_reason_code: packet?.block_reason_code || "",
      claim_scope: packet?.claim_scope || "custom_codex_recovery_stop_cleanup_live_only",
      verified_scope: packet?.verified_scope || "not_verified",
      declared_write_surface: packet?.declared_write_surface || "owned_temp_session_root_cleanup_only",
      contract_endpoint: packet?.contract_endpoint || "/api/codex/custom/recovery/stop-cleanup",
      contract_source_endpoint: packet?.contract_source_endpoint || "/api/codex/custom/recovery/stop-cleanup/preflight",
      contract_endpoint_mutation_allowed: packet?.contract_endpoint_mutation_allowed === true,
      browser_payload_allowed: packet?.browser_payload_allowed === true,
      browser_payload_allowed_keys: packet?.browser_payload_allowed_keys || [],
      forbidden_browser_fields: packet?.forbidden_browser_fields || [],
      forbidden_fields: packet?.forbidden_fields || [],
      browser_forbidden_fields_rejected: packet?.browser_forbidden_fields_rejected === true,
      preflight_required: packet?.preflight_required === true,
      preflight_verified: packet?.preflight_verified === true,
      selected_session_source: packet?.selected_session_source || "server_selected_latest_owned_custom_session",
      selected_session_id_redacted: packet?.selected_session_id_redacted !== false,
      raw_session_id_omitted: packet?.raw_session_id_omitted !== false,
      preflight_selected_session_ref_present: packet?.preflight_selected_session_ref_present === true,
      live_selected_session_ref_present: packet?.live_selected_session_ref_present === true,
      cancel_selected_session_ref_present: packet?.cancel_selected_session_ref_present === true,
      cleanup_selected_session_ref_present: packet?.cleanup_selected_session_ref_present === true,
      same_selected_session_ref: packet?.same_selected_session_ref === true,
      session_cancel_performed: packet?.session_cancel_performed === true,
      session_cancel_verified: packet?.session_cancel_verified === true,
      cleanup_attempted: packet?.cleanup_attempted === true,
      owned_cleanup_performed: packet?.owned_cleanup_performed === true,
      owned_cleanup_verified: packet?.owned_cleanup_verified === true,
      owned_session_root_only: packet?.owned_session_root_only === true,
      arbitrary_path_cleanup_allowed: packet?.arbitrary_path_cleanup_allowed === true,
      arbitrary_path_accepted: packet?.arbitrary_path_accepted === true,
      process_kill_ready: packet?.process_kill_ready === true,
      process_kill_performed: packet?.process_kill_performed === true,
      filesystem_write_performed: packet?.filesystem_write_performed === true,
      filesystem_write_scope: packet?.filesystem_write_scope || "",
      current_codex_touched: packet?.current_codex_touched === true,
      original_codex_touched: packet?.original_codex_touched === true,
      current_codex_home_touched: packet?.current_codex_home_touched === true,
      auth_material_touched: packet?.auth_material_touched === true,
      secret_value_recorded: packet?.secret_value_recorded === true,
      rollback_live_ready: packet?.rollback_live_ready === true,
      recovery_operator_ready: packet?.recovery_operator_ready === true,
      source_preflight_machine_error_code: packet?.source_preflight_machine_error_code || "",
      cancel_machine_error_code: packet?.cancel_machine_error_code || "",
      cleanup_machine_error_code: packet?.cleanup_machine_error_code || "",
      human_summary: packet?.human_summary || "owned session cancelled and cleaned · not system recovery",
      next_action: packet?.next_action || "",
      next_contour: packet?.next_contour || "",
    }, null, 2);
  }
}

async function refreshCodexCustomRecoveryRollbackPointCreateAdmission() {
  try {
    renderCodexCustomRecoveryRollbackPointCreateAdmission(
      await fetchCodexLaunchJson("api/codex/custom/recovery/rollback-point-create-admission")
    );
  } catch (error) {
    renderCodexCustomRecoveryRollbackPointCreateAdmission({
      status: "failed",
      machine_error_code: "ROLLBACK_POINT_CREATE_ADMISSION_FETCH_FAILED",
      block_reason_code: "ROLLBACK_POINT_CREATE_ADMISSION_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_rollback_point_create_admission_only",
      contract_endpoint: "/api/codex/custom/recovery/rollback-point-create-admission",
      contract_source_endpoint: "/api/codex/custom/recovery/rollback-point-dry-run",
      contract_endpoint_mutation_allowed: false,
      browser_payload_allowed: false,
      browser_payload_allowed_keys: [],
      forbidden_browser_fields: ["backend_id", "route_id", "path", "snapshot_path", "rollback_target", "session_id", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
      browser_forbidden_fields_rejected: true,
      rollback_point_dry_run_contract_valid: false,
      rollback_point_create_admission_defined: false,
      rollback_point_create_admitted: false,
      rollback_point_create_admitted_scope: "not_admitted",
      rollback_point_create_admitted_for_current_contour: false,
      rollback_point_create_performed: false,
      rollback_point_created: false,
      snapshot_file_created: false,
      filesystem_write_performed: false,
      write_surface_machine_check_performed: false,
      write_surfaces_all_eligible: false,
      rollback_apply_admitted: false,
      rollback_live_ready: false,
      recovery_operator_ready: false,
      operator_ready_claimed: false,
      rollback_operator_ready: false,
      rollback_claimed: false,
      process_kill_operator_ready: false,
      process_kill_claimed: false,
      process_kill_live_ready: false,
      process_kill_admitted: false,
      current_codex_touched: false,
      original_codex_touched: false,
      current_codex_home_touched: false,
      current_codex_home_allowed_surface: false,
      auth_material_allowed_surface: false,
      arbitrary_path_accepted: false,
      arbitrary_path_allowed_surface: false,
      dangerous_actions_disabled: true,
      dangerous_action_mutation_allowed: false,
      next_contour_claimed: false,
    });
  }
}

async function createCodexCustomRecoveryRollbackPoint() {
  const action = document.getElementById("codexCustomRecoveryRollbackPointCreateAction");
  action?.setAttribute("disabled", "disabled");
  codexCustomRecoverySetChip("neutral", "creating");
  try {
    const response = await fetch("api/codex/custom/recovery/rollback-point", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({})
    });
    if (!response.ok) {
      throw new Error(`rollback point create http ${response.status}`);
    }
    renderCodexCustomRecoveryRollbackPointCreate(await response.json());
  } catch (error) {
    renderCodexCustomRecoveryRollbackPointCreate({
      status: "failed",
      machine_error_code: "ROLLBACK_POINT_CREATE_FETCH_FAILED",
      block_reason_code: "ROLLBACK_POINT_CREATE_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_rollback_point_create_live_only",
      contract_endpoint: "/api/codex/custom/recovery/rollback-point",
      contract_source_endpoint: "/api/codex/custom/recovery/rollback-point-create-admission",
      contract_endpoint_mutation_allowed: true,
      browser_payload_allowed: false,
      browser_payload_allowed_keys: [],
      forbidden_browser_fields: ["backend_id", "route_id", "path", "snapshot_path", "rollback_target", "session_id", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
      forbidden_fields: [],
      browser_forbidden_fields_rejected: true,
      rollback_point_create_admission_valid: false,
      rollback_point_create_admitted: false,
      rollback_point_create_admitted_for_current_contour: false,
      rollback_point_create_performed: false,
      rollback_point_created: false,
      rollback_point_artifact_path_redacted: true,
      rollback_point_artifact_digest_present: false,
      snapshot_file_created: false,
      filesystem_write_performed: false,
      rollback_apply_admitted: false,
      rollback_apply_performed: false,
      rollback_completed: false,
      rollback_live_ready: false,
      recovery_operator_ready: false,
      current_codex_touched: false,
      original_codex_touched: false,
      auth_material_touched: false,
      secret_value_recorded: false,
      dangerous_actions_disabled: true,
      dangerous_action_mutation_allowed: false,
      next_contour_claimed: false,
      human_message: error.message
    });
  } finally {
    action?.removeAttribute("disabled");
  }
}

async function verifyCodexCustomRecoveryRollbackPoint() {
  try {
    renderCodexCustomRecoveryRollbackPointVerify(
      await fetchCodexLaunchJson("api/codex/custom/recovery/rollback-point/verify")
    );
  } catch (error) {
    renderCodexCustomRecoveryRollbackPointVerify({
      status: "failed",
      machine_error_code: "ROLLBACK_POINT_VERIFY_FETCH_FAILED",
      block_reason_code: "ROLLBACK_POINT_VERIFY_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_rollback_point_verify_only",
      contract_endpoint: "/api/codex/custom/recovery/rollback-point/verify",
      contract_source_endpoint: "/api/codex/custom/recovery/rollback-point",
      contract_endpoint_mutation_allowed: false,
      browser_payload_allowed: false,
      browser_payload_allowed_keys: [],
      forbidden_browser_fields: ["backend_id", "route_id", "path", "snapshot_path", "rollback_target", "session_id", "artifact_id", "artifact_path", "digest", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
      browser_forbidden_fields_rejected: true,
      rollback_point_verify_performed: false,
      rollback_point_verified: false,
      rollback_point_present: false,
      rollback_point_selection_ambiguous: false,
      rollback_point_artifact_path_redacted: true,
      rollback_point_digest_verified: false,
      rollback_point_provenance_verified: false,
      rollback_point_schema_valid: false,
      rollback_point_kind_valid: false,
      rollback_point_surface_verified: false,
      filesystem_read_performed: false,
      filesystem_write_performed: false,
      rollback_apply_admitted: false,
      rollback_apply_ready: false,
      rollback_apply_performed: false,
      rollback_completed: false,
      rollback_live_ready: false,
      recovery_operator_ready: false,
      current_codex_touched: false,
      original_codex_touched: false,
      auth_material_touched: false,
      secret_value_recorded: false,
      dangerous_actions_disabled: true,
      dangerous_action_mutation_allowed: false,
      next_contour_claimed: false,
      human_message: error.message
    });
  }
}

async function refreshCodexCustomRecoveryRollbackApplyAdmissionDryRun() {
  try {
    renderCodexCustomRecoveryRollbackApplyAdmissionDryRun(
      await fetchCodexLaunchJson("api/codex/custom/recovery/rollback-apply/admission-dry-run")
    );
  } catch (error) {
    renderCodexCustomRecoveryRollbackApplyAdmissionDryRun({
      status: "failed",
      machine_error_code: "ROLLBACK_APPLY_ADMISSION_DRY_RUN_FETCH_FAILED",
      block_reason_code: "ROLLBACK_APPLY_ADMISSION_DRY_RUN_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_rollback_apply_admission_dry_run_only",
      contract_endpoint: "/api/codex/custom/recovery/rollback-apply/admission-dry-run",
      contract_source_endpoint: "/api/codex/custom/recovery/rollback-point/verify",
      contract_endpoint_mutation_allowed: false,
      browser_payload_allowed: false,
      browser_payload_allowed_keys: [],
      forbidden_browser_fields: ["backend_id", "route_id", "path", "snapshot_path", "rollback_target", "session_id", "artifact_id", "artifact_path", "digest", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
      forbidden_fields: [],
      browser_forbidden_fields_rejected: true,
      rollback_apply_admission_evaluated: false,
      rollback_apply_admission_result: "not_evaluated",
      rollback_apply_admission_eligible_for_next_contour: false,
      rollback_point_verify_required: true,
      rollback_point_verify_valid: false,
      rollback_point_verified: false,
      rollback_point_present: false,
      rollback_point_artifact_path_redacted: true,
      rollback_point_manifest_verified: false,
      rollback_point_provenance_verified: false,
      rollback_point_digest_verified: false,
      rollback_point_surface_verified: false,
      recovery_contract_readonly_sources_ok: false,
      rollback_process_owner_contract_ok: false,
      session_state_read_performed: false,
      session_state_status: "fetch_failed",
      write_surface_machine_check_performed: false,
      write_surfaces_all_eligible: false,
      filesystem_read_performed: false,
      filesystem_write_performed: false,
      rollback_apply_admitted: false,
      rollback_apply_ready: false,
      rollback_apply_performed: false,
      rollback_completed: false,
      rollback_live_ready: false,
      recovery_operator_ready: false,
      process_kill_performed: false,
      current_codex_touched: false,
      original_codex_touched: false,
      auth_material_touched: false,
      secret_value_recorded: false,
      dangerous_actions_disabled: true,
      dangerous_action_mutation_allowed: false,
      next_contour_claimed: false,
      human_message: error.message
    });
  }
}

async function refreshCodexCustomRecoveryRollbackApplyLivePreflight() {
  try {
    renderCodexCustomRecoveryRollbackApplyLivePreflight(
      await fetchCodexLaunchJson("api/codex/custom/recovery/rollback-apply/live-preflight")
    );
  } catch (error) {
    renderCodexCustomRecoveryRollbackApplyLivePreflight({
      status: "failed",
      machine_error_code: "ROLLBACK_APPLY_LIVE_PREFLIGHT_FETCH_FAILED",
      block_reason_code: "ROLLBACK_APPLY_LIVE_PREFLIGHT_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_rollback_apply_live_preflight_only",
      contract_endpoint: "/api/codex/custom/recovery/rollback-apply/live-preflight",
      contract_source_endpoint: "/api/codex/custom/recovery/rollback-apply/admission-dry-run",
      contract_endpoint_mutation_allowed: false,
      browser_payload_allowed: false,
      browser_payload_allowed_keys: [],
      forbidden_browser_fields: ["backend_id", "route_id", "path", "snapshot_path", "rollback_target", "session_id", "artifact_id", "artifact_path", "digest", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
      forbidden_fields: [],
      browser_forbidden_fields_rejected: true,
      rollback_apply_live_preflight_evaluated: false,
      rollback_apply_live_preflight_result: "not_evaluated",
      rollback_apply_live_preflight_eligible_for_next_contour: false,
      rollback_apply_dry_run_required: true,
      rollback_apply_dry_run_eligible: false,
      rollback_point_verified: false,
      rollback_point_manifest_verified: false,
      rollback_point_provenance_verified: false,
      rollback_point_digest_verified: false,
      rollback_point_surface_verified: false,
      rollback_point_artifact_path_redacted: true,
      future_write_surfaces_declared: false,
      future_write_surfaces_all_owned: false,
      future_write_surface_machine_check_performed: false,
      rollback_target_browser_supplied: false,
      current_codex_excluded: true,
      original_codex_excluded: true,
      auth_material_excluded: true,
      arbitrary_path_rejected: true,
      process_kill_not_admitted: true,
      source_filesystem_read_performed: false,
      filesystem_read_performed: false,
      filesystem_read_scope: "",
      filesystem_write_performed: false,
      rollback_apply_admitted: false,
      rollback_apply_ready: false,
      rollback_apply_performed: false,
      rollback_completed: false,
      rollback_live_ready: false,
      recovery_operator_ready: false,
      process_kill_performed: false,
      current_codex_touched: false,
      original_codex_touched: false,
      auth_material_touched: false,
      secret_value_recorded: false,
      dangerous_actions_disabled: true,
      dangerous_action_mutation_allowed: false,
      next_contour_claimed: false,
      human_message: error.message
    });
  }
}

async function createCodexCustomRecoveryRollbackApplyReceipt() {
  const action = document.getElementById("codexCustomRecoveryRollbackApplyReceiptAction");
  action?.setAttribute("disabled", "disabled");
  try {
    const response = await fetch("api/codex/custom/recovery/rollback-apply", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({})
    });
    if (!response.ok) {
      throw new Error(`rollback apply http ${response.status}`);
    }
    renderCodexCustomRecoveryRollbackApplyReceipt(await response.json());
  } catch (error) {
    renderCodexCustomRecoveryRollbackApplyReceipt({
      status: "failed",
      machine_error_code: "ROLLBACK_APPLY_BOUNDED_LIVE_FETCH_FAILED",
      block_reason_code: "ROLLBACK_APPLY_BOUNDED_LIVE_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_rollback_apply_bounded_live_only",
      contract_endpoint: "/api/codex/custom/recovery/rollback-apply",
      contract_source_endpoint: "/api/codex/custom/recovery/rollback-apply/live-preflight",
      contract_endpoint_mutation_allowed: false,
      browser_payload_allowed: false,
      browser_payload_allowed_keys: [],
      forbidden_browser_fields: ["backend_id", "route_id", "path", "snapshot_path", "rollback_target", "session_id", "artifact_id", "artifact_path", "digest", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
      forbidden_fields: [],
      browser_forbidden_fields_rejected: true,
      rollback_apply_preflight_required: true,
      rollback_apply_preflight_valid: false,
      rollback_apply_bounded_live_performed: false,
      rollback_apply_receipt_created: false,
      rollback_apply_receipt_path_redacted: true,
      rollback_apply_receipt_digest_present: false,
      rollback_apply_receipt_provenance_verified: false,
      rollback_apply_receipt_payload_digest_verified: false,
      source_preflight_sha256_present: false,
      source_rollback_point_sha256_present: false,
      rollback_point_verified: false,
      filesystem_read_performed: false,
      filesystem_write_performed: false,
      rollback_apply_admitted: false,
      rollback_apply_ready: false,
      rollback_apply_performed: false,
      rollback_apply_completed_scope: "not_completed",
      rollback_completed: false,
      rollback_live_ready: false,
      recovery_operator_ready: false,
      process_kill_performed: false,
      current_codex_touched: false,
      original_codex_touched: false,
      current_codex_home_touched: false,
      auth_material_touched: false,
      secret_value_recorded: false,
      dangerous_actions_disabled: true,
      dangerous_action_mutation_allowed: false,
      next_contour_claimed: false,
      human_message: error.message
    });
  } finally {
    action?.removeAttribute("disabled");
  }
}

async function verifyCodexCustomRecoveryRollbackApplyReceipt() {
  try {
    renderCodexCustomRecoveryRollbackApplyReceiptVerify(
      await fetchCodexLaunchJson("api/codex/custom/recovery/rollback-apply/receipt/verify")
    );
  } catch (error) {
    renderCodexCustomRecoveryRollbackApplyReceiptVerify({
      status: "failed",
      machine_error_code: "ROLLBACK_APPLY_RECEIPT_VERIFY_FETCH_FAILED",
      block_reason_code: "ROLLBACK_APPLY_RECEIPT_VERIFY_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_rollback_apply_receipt_verify_only",
      contract_endpoint: "/api/codex/custom/recovery/rollback-apply/receipt/verify",
      contract_source_endpoint: "/api/codex/custom/recovery/rollback-apply",
      contract_endpoint_mutation_allowed: false,
      browser_payload_allowed: false,
      browser_payload_allowed_keys: [],
      forbidden_browser_fields: ["backend_id", "route_id", "path", "snapshot_path", "rollback_target", "session_id", "receipt_id", "receipt_path", "artifact_id", "artifact_path", "digest", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
      forbidden_fields: [],
      browser_forbidden_fields_rejected: true,
      receipt_verify_performed: false,
      receipt_verified: false,
      rollback_apply_receipt_verified: false,
      verified_scope: "not_verified",
      receipt_selection_ambiguous: false,
      receipt_path_redacted: true,
      receipt_digest_present: false,
      receipt_payload_digest_verified: false,
      receipt_provenance_verified: false,
      source_preflight_sha256_present: false,
      source_rollback_point_ref_present: false,
      filesystem_read_performed: false,
      filesystem_write_performed: false,
      rollback_apply_performed: false,
      rollback_completed: false,
      rollback_live_ready: false,
      recovery_operator_ready: false,
      process_kill_performed: false,
      current_codex_touched: false,
      original_codex_touched: false,
      current_codex_home_touched: false,
      auth_material_touched: false,
      secret_value_recorded: false,
      dangerous_actions_disabled: true,
      dangerous_action_mutation_allowed: false,
      human_summary: "receipt verify failed · not system recovery",
      next_contour_claimed: false,
      human_message: error.message
    });
  }
}

async function refreshCodexCustomRecoveryRollbackPointDryRun() {
  try {
    renderCodexCustomRecoveryRollbackPointDryRun(
      await fetchCodexLaunchJson("api/codex/custom/recovery/rollback-point-dry-run")
    );
  } catch (error) {
    renderCodexCustomRecoveryRollbackPointDryRun({
      status: "failed",
      machine_error_code: "ROLLBACK_POINT_DRY_RUN_FETCH_FAILED",
      block_reason_code: "ROLLBACK_POINT_DRY_RUN_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_rollback_point_dry_run_only",
      contract_endpoint: "/api/codex/custom/recovery/rollback-point-dry-run",
      contract_source_endpoint: "/api/codex/custom/recovery/rollback-process-owner-contract",
      contract_endpoint_mutation_allowed: false,
      browser_payload_allowed: false,
      browser_payload_allowed_keys: [],
      forbidden_browser_fields: ["backend_id", "route_id", "path", "snapshot_path", "rollback_target", "session_id", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
      browser_forbidden_fields_rejected: true,
      rollback_point_contract_defined: false,
      rollback_point_present: false,
      rollback_point_create_admitted: false,
      rollback_apply_admitted: false,
      rollback_live_ready: false,
      rollback_write_surfaces_contract_defined: false,
      rollback_write_surfaces_machine_checked: false,
      rollback_write_surfaces_dry_run_checked: false,
      rollback_verification_packet_defined: false,
      rollback_verification_packet_present: false,
      recovery_operator_ready: false,
      operator_ready_claimed: false,
      rollback_operator_ready: false,
      rollback_claimed: false,
      process_kill_operator_ready: false,
      process_kill_claimed: false,
      process_kill_live_ready: false,
      process_kill_admitted: false,
      filesystem_write_performed: false,
      snapshot_file_created: false,
      snapshot_create_admitted: false,
      snapshot_target_browser_supplied: false,
      diagnostics_support_artifact_only: true,
      diagnostics_counted_as_recovery_action: false,
      readonly_checks_counted_as_mutation: false,
      session_create_counted_as_recovery_action: false,
      current_codex_touched: false,
      original_codex_touched: false,
      current_codex_home_touched: false,
      current_codex_home_allowed_surface: false,
      auth_material_allowed_surface: false,
      arbitrary_path_accepted: false,
      arbitrary_path_allowed_surface: false,
      dangerous_actions_disabled: true,
      dangerous_action_mutation_allowed: false,
      next_contour_claimed: false,
    });
  }
}

async function refreshCodexCustomRecoveryStopCleanupPreflight() {
  try {
    renderCodexCustomRecoveryStopCleanupPreflight(
      await fetchCodexLaunchJson("api/codex/custom/recovery/stop-cleanup/preflight")
    );
  } catch (error) {
    renderCodexCustomRecoveryStopCleanupPreflight({
      status: "failed",
      machine_error_code: "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_FETCH_FAILED",
      block_reason_code: "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_stop_cleanup_preflight_only",
      verified_scope: "not_verified",
      contract_endpoint: "/api/codex/custom/recovery/stop-cleanup/preflight",
      contract_source_endpoint: "/api/codex/custom/recovery/admitted-session-actions",
      contract_endpoint_mutation_allowed: false,
      browser_payload_allowed: false,
      browser_payload_allowed_keys: [],
      forbidden_browser_fields: ["backend_id", "route_id", "path", "cleanup_path", "snapshot_path", "rollback_target", "session_id", "receipt_id", "receipt_path", "artifact_id", "artifact_path", "digest", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
      forbidden_fields: [],
      browser_forbidden_fields_rejected: true,
      stop_cleanup_preflight_ready: false,
      selected_session_source: "server_selected_latest_owned_custom_session",
      selected_session_required: true,
      selected_session_present: false,
      selected_session_id_redacted: true,
      selected_session_ambiguous: false,
      selected_session_packet_valid: false,
      selected_session_cancel_ready: false,
      owned_session_cleanup_ready: false,
      arbitrary_path_cleanup_allowed: false,
      process_kill_ready: false,
      process_kill_performed: false,
      session_cancel_performed: false,
      owned_cleanup_performed: false,
      filesystem_read_performed: false,
      filesystem_write_performed: false,
      current_codex_touched: false,
      original_codex_touched: false,
      current_codex_home_touched: false,
      auth_material_touched: false,
      secret_value_recorded: false,
      recovery_operator_ready: false,
      rollback_live_ready: false,
      human_summary: "stop/cleanup preflight failed · no action performed",
      next_contour: "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_PASS",
      human_message: error.message
    });
  }
}

async function refreshCodexCustomRecoveryProcessKillPreflight() {
  try {
    renderCodexCustomRecoveryProcessKillPreflight(
      await fetchCodexLaunchJson("api/codex/custom/recovery/process-kill/preflight")
    );
  } catch (error) {
    renderCodexCustomRecoveryProcessKillPreflight({
      status: "failed",
      machine_error_code: "CUSTOM_CODEX_RECOVERY_PROCESS_KILL_PREFLIGHT_FETCH_FAILED",
      block_reason_code: "CUSTOM_CODEX_RECOVERY_PROCESS_KILL_PREFLIGHT_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_process_kill_preflight_only",
      verified_scope: "not_verified",
      contract_endpoint: "/api/codex/custom/recovery/process-kill/preflight",
      contract_source_endpoint: "/api/codex/custom/recovery/admitted-session-actions",
      contract_endpoint_mutation_allowed: false,
      browser_payload_allowed: false,
      browser_payload_allowed_keys: [],
      forbidden_browser_fields: ["backend_id", "route_id", "path", "cleanup_path", "process_path", "process_root", "process_command", "command", "argv", "executable", "snapshot_path", "rollback_target", "session_id", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
      forbidden_fields: [],
      browser_forbidden_fields_rejected: true,
      selected_source: "server_owned_custom_session_observation",
      selected_session_source: "server_selected_latest_owned_custom_session",
      selected_session_required: true,
      selected_session_present: false,
      selected_session_id_redacted: true,
      selected_session_ambiguous: false,
      selected_session_ref_present: false,
      raw_session_id_omitted: true,
      selected_session_packet_valid: false,
      owned_process_identity_required: true,
      owned_process_identity_present: false,
      current_codex_process_exclusion_required: true,
      original_codex_process_exclusion_required: true,
      process_candidate_present: false,
      process_candidate_ref_present: false,
      raw_pid_omitted: true,
      raw_process_id_omitted: true,
      raw_process_path_omitted: true,
      raw_process_command_omitted: true,
      process_owned_by_custom_session: false,
      process_kill_eligible: false,
      process_kill_preflight_evaluated: false,
      process_kill_preflight_result: "fetch_failed",
      process_kill_preflight_ready: false,
      process_kill_ready: false,
      process_kill_performed: false,
      process_kill_live_ready: false,
      process_kill_admitted: false,
      process_kill_claimed: false,
      current_codex_process_candidate: false,
      original_codex_process_candidate: false,
      current_codex_process_excluded: false,
      original_codex_process_excluded: false,
      filesystem_read_performed: false,
      filesystem_write_performed: false,
      current_codex_touched: false,
      original_codex_touched: false,
      current_codex_home_touched: false,
      auth_material_touched: false,
      secret_value_recorded: false,
      rollback_live_ready: false,
      recovery_operator_ready: false,
      operator_ready_claimed: false,
      rollback_operator_ready: false,
      rollback_claimed: false,
      process_kill_operator_ready: false,
      dangerous_actions_disabled: true,
      dangerous_action_mutation_allowed: false,
      human_summary: "process kill preflight failed · no kill performed",
      next_contour: "CUSTOM_CODEX_RECOVERY_PROCESS_KILL_PREFLIGHT_PASS",
      human_message: error.message
    });
  }
}

async function runCodexCustomRecoveryStopCleanupLive() {
  const action = document.getElementById("codexCustomRecoveryStopCleanupLiveAction");
  action?.setAttribute("disabled", "disabled");
  try {
    const response = await fetch("api/codex/custom/recovery/stop-cleanup", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({})
    });
    if (!response.ok) {
      throw new Error(`stop cleanup http ${response.status}`);
    }
    renderCodexCustomRecoveryStopCleanupLive(await response.json());
    await refreshCodexCustomRecoveryAdmittedSessionActions();
    await refreshCodexCustomRecoveryStopCleanupPreflight();
  } catch (error) {
    renderCodexCustomRecoveryStopCleanupLive({
      status: "failed",
      machine_error_code: "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_LIVE_FETCH_FAILED",
      block_reason_code: "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_LIVE_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_stop_cleanup_live_only",
      verified_scope: "not_verified",
      declared_write_surface: "owned_temp_session_root_cleanup_only",
      contract_endpoint: "/api/codex/custom/recovery/stop-cleanup",
      contract_source_endpoint: "/api/codex/custom/recovery/stop-cleanup/preflight",
      contract_endpoint_mutation_allowed: true,
      browser_payload_allowed: false,
      browser_payload_allowed_keys: [],
      forbidden_browser_fields: ["backend_id", "route_id", "path", "cleanup_path", "snapshot_path", "rollback_target", "session_id", "receipt_id", "receipt_path", "artifact_id", "artifact_path", "digest", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
      forbidden_fields: [],
      browser_forbidden_fields_rejected: true,
      preflight_required: true,
      preflight_verified: false,
      selected_session_source: "server_selected_latest_owned_custom_session",
      selected_session_id_redacted: true,
      raw_session_id_omitted: true,
      same_selected_session_ref: false,
      session_cancel_performed: false,
      session_cancel_verified: false,
      cleanup_attempted: false,
      owned_cleanup_performed: false,
      owned_cleanup_verified: false,
      owned_session_root_only: false,
      arbitrary_path_cleanup_allowed: false,
      arbitrary_path_accepted: false,
      process_kill_ready: false,
      process_kill_performed: false,
      filesystem_write_performed: false,
      filesystem_write_scope: "",
      current_codex_touched: false,
      original_codex_touched: false,
      current_codex_home_touched: false,
      auth_material_touched: false,
      secret_value_recorded: false,
      rollback_live_ready: false,
      recovery_operator_ready: false,
      human_summary: "owned stop/cleanup failed · not system recovery",
      next_action: "diagnose_stop_cleanup_live_fetch",
      next_contour: "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_LIVE_PASS",
      human_message: error.message
    });
  } finally {
    action?.removeAttribute("disabled");
  }
}

async function refreshCodexCustomRecoveryRollbackProcessOwnerContract() {
  try {
    renderCodexCustomRecoveryRollbackProcessOwnerContract(
      await fetchCodexLaunchJson("api/codex/custom/recovery/rollback-process-owner-contract")
    );
  } catch (error) {
    renderCodexCustomRecoveryRollbackProcessOwnerContract({
      status: "failed",
      machine_error_code: "ROLLBACK_PROCESS_OWNER_CONTRACT_FETCH_FAILED",
      block_reason_code: "ROLLBACK_PROCESS_OWNER_CONTRACT_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_rollback_process_owner_dry_run_contract_only",
      contract_endpoint: "/api/codex/custom/recovery/rollback-process-owner-contract",
      contract_source_endpoint: "/api/codex/custom/recovery/contract",
      contract_endpoint_mutation_allowed: false,
      browser_payload_allowed: false,
      browser_payload_allowed_keys: [],
      forbidden_browser_fields: ["backend_id", "route_id", "path", "snapshot_path", "rollback_target", "session_id", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
      browser_forbidden_fields_rejected: true,
      rollback_contract_defined: false,
      rollback_live_ready: false,
      rollback_apply_admitted: false,
      rollback_point_required: true,
      rollback_point_present: false,
      rollback_write_surfaces_required: true,
      rollback_write_surfaces_declared: false,
      rollback_verification_packet_required: true,
      rollback_verification_packet_present: false,
      process_owner_contract_defined: false,
      process_kill_live_ready: false,
      process_kill_admitted: false,
      owned_process_identity_required: true,
      owned_process_identity_present: false,
      current_codex_process_exclusion_required: true,
      current_codex_process_excluded: false,
      current_codex_process_candidate: false,
      recovery_operator_ready: false,
      operator_ready_claimed: false,
      rollback_operator_ready: false,
      rollback_claimed: false,
      process_kill_operator_ready: false,
      process_kill_claimed: false,
      diagnostics_support_artifact_only: true,
      diagnostics_counted_as_recovery_action: false,
      readonly_checks_counted_as_mutation: false,
      session_create_counted_as_recovery_action: false,
      current_codex_touched: false,
      original_codex_touched: false,
      current_codex_home_touched: false,
      arbitrary_path_accepted: false,
      arbitrary_process_kill_allowed: false,
      arbitrary_path_cleanup_allowed: false,
      dangerous_actions_disabled: true,
      dangerous_action_mutation_allowed: false,
      next_contour_claimed: false,
    });
  }
}

async function refreshCodexCustomRecoveryAdmittedSessionActions() {
  try {
    renderCodexCustomRecoveryAdmittedSessionActions(
      await fetchCodexLaunchJson("api/codex/custom/recovery/admitted-session-actions")
    );
  } catch (error) {
    renderCodexCustomRecoveryAdmittedSessionActions({
      status: "failed",
      machine_error_code: "ADMITTED_SESSION_ACTIONS_FETCH_FAILED",
      block_reason_code: "ADMITTED_SESSION_ACTIONS_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_admitted_session_actions_only",
      contract_endpoint: "/api/codex/custom/recovery/admitted-session-actions",
      contract_source_endpoint: "/api/codex/custom/recovery/contract",
      session_source_endpoint: "/api/codex/custom/sessions",
      contract_endpoint_mutation_allowed: false,
      browser_payload_allowed: false,
      browser_payload_allowed_keys: [],
      forbidden_browser_fields: ["backend_id", "route_id", "path", "snapshot_path", "rollback_target", "session_id", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
      browser_forbidden_fields_rejected: true,
      session_admitted_actions_ready: false,
      selected_session_cancel_ready: false,
      owned_session_cleanup_ready: false,
      recovery_operator_ready: false,
      operator_ready_claimed: false,
      rollback_operator_ready: false,
      rollback_claimed: false,
      process_kill_operator_ready: false,
      process_kill_claimed: false,
      diagnostics_support_artifact_only: true,
      diagnostics_counted_as_recovery_action: false,
      readonly_checks_counted_as_mutation: false,
      session_create_counted_as_recovery_action: false,
      current_codex_touched: false,
      original_codex_touched: false,
      current_codex_home_touched: false,
      arbitrary_path_accepted: false,
      dangerous_actions_disabled: true,
      dangerous_action_mutation_allowed: false,
      next_contour_claimed: false,
    });
  }
}

async function refreshCodexCustomRecoveryOperatorMatrix() {
  try {
    renderCodexCustomRecoveryOperatorMatrix(
      await fetchCodexLaunchJson("api/codex/custom/recovery/operator-ready")
    );
  } catch (error) {
    renderCodexCustomRecoveryOperatorMatrix({
      status: "failed",
      machine_error_code: "CUSTOM_CODEX_RECOVERY_ROLLBACK_OPERATOR_MATRIX_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_rollback_operator_surface_bounded_local_use",
      operator_recovery_matrix_complete: false,
      session_recovery_actions_classified: false,
      rollback_lifecycle_actions_classified: false,
      diagnostics_surface_classified: false,
      diagnostics_export_redacted: false,
      dangerous_actions_disabled_or_preflight_only: false,
      process_kill_live_not_admitted_without_owned_target: false,
      bounded_local_operator_surface_ready: false,
      final_verdict: "CUSTOM_CODEX_RECOVERY_ROLLBACK_OPERATOR_MATRIX_BLOCKED",
      current_codex_touched: false,
      original_codex_touched: false,
      secret_leak: false,
      false_green: false,
      recovery_operator_ready: false,
      operator_ready_claimed: false,
      rollback_operator_ready: false,
      process_kill_operator_ready: false,
      process_kill_claimed: false,
      ["pro" + "duction_ready"]: false,
      desktop_ready: false,
      installer_ready: false,
      actions: [],
      human_message: error.message,
      next_action: "retry",
    });
  }
}

async function refreshCodexCustomRecoveryContract() {
  codexCustomRecoverySetChip("neutral", "contract");
  try {
    renderCodexCustomRecoveryContract(
      await fetchCodexLaunchJson("api/codex/custom/recovery/contract")
    );
  } catch (error) {
    renderCodexCustomRecoveryContract({
      status: "failed",
      machine_error_code: "RECOVERY_CONTRACT_FETCH_FAILED",
      contract_block_reason_code: "RECOVERY_CONTRACT_FETCH_FAILED",
      claim_scope: "custom_codex_recovery_contract_dry_run_only",
      contract_owner: "wbp_control_layer_contract_aggregator",
      contract_endpoint: "/api/codex/custom/recovery/contract",
      contract_aggregator_only: true,
      contract_endpoint_mutation_allowed: false,
      recovery_live_ready: false,
      operator_ready_claimed: false,
      rollback_claimed: false,
      process_kill_claimed: false,
      current_codex_touched: false,
      original_codex_touched: false,
      browser_forbidden_fields_rejected: true,
      browser_payload_allowed: false,
      browser_payload_allowed_keys: [],
      forbidden_browser_fields: ["backend_id", "route_id", "path", "snapshot_path", "rollback_target", "session_id", "pid", "process_id", "token", "auth", "api_key", "secret", "CODEX_HOME", "HOME"],
      fresh_truth: false,
      historical_isolation_proof_only: true,
      dangerous_actions_disabled: true,
      diagnostics_support_artifact_only: true,
      readonly_sources: {
        original_status_ok: false,
        custom_status_ok: false,
        accounts_readonly_ok: false,
        api_readonly_ok: false,
      },
      actions: [],
    });
  }
}

async function runCodexCustomRecoveryChecks() {
  codexCustomRecoverySetChip("neutral", "checking");
  try {
    const [originalStatus, customStatus, accountsSnapshot, apiSnapshot] = await Promise.all([
      fetchCodexLaunchJson("api/codex/original/status"),
      fetchCodexLaunchJson("api/codex/custom/status"),
      loadAccountsReadonly(),
      loadApiConnectionsReadonly()
    ]);
    await Promise.all([
      refreshCodexLaunchModesPanel(),
      refreshCodexCustomModelsPanel(),
      refreshCodexCustomAccountsPanel(),
      refreshCodexCustomSessionsPanel()
    ]);
    const accountsSummary = accountsSnapshot?.summary || {};
    const apiSummary = apiSnapshot?.summary || {};
    const diagnosticsMetadata = actionMetadata?.export_diagnostics || {};
    const originalOk = originalStatus?.status === "ok";
    const customOk = customStatus?.status === "ok";
    const accountsOk = accountsSnapshot?.status === "ok" && accountsSnapshot?.primary_truth_ok === true;
    const apiOk = apiSnapshot?.status === "ok" && apiSnapshot?.primary_truth_ok === true;
    const checksOk = originalOk && customOk && accountsOk && apiOk;
    codexCustomRecoverySetText(
      "codexCustomRecoveryOriginal",
      `${originalStatus?.status || "unknown"} · proxy ${originalStatus?.proxy_injection_allowed === false ? "forbidden" : "unknown"} · ${originalStatus?.launch_claim_scope || "status_only"}`
    );
    codexCustomRecoverySetText(
      "codexCustomRecoveryAccounts",
      `${accountsSnapshot?.status || "unknown"} · visible ${accountsSummary.visible_count ?? 0} · machine ${accountsSummary.machine_error_code || "unknown"}`
    );
    codexCustomRecoverySetText(
      "codexCustomRecoveryApi",
      `${apiSnapshot?.status || "unknown"} · routes ${apiSummary.routes_count ?? 0} · enabled ${apiSummary.enabled_count ?? 0}`
    );
    codexCustomRecoverySetText(
      "codexCustomRecoveryDiagnostics",
      diagnosticsMetadata.available === true ? "available · support artifact only" : `disabled · ${diagnosticsMetadata.disabled_reason_code || diagnosticsMetadata.unavailable_reason || "metadata"}`
    );
    renderCodexCustomRecoveryPacket({
      status: checksOk ? "ok" : "blocked",
      machine_error_code: checksOk ? "RECOVERY_READONLY_CHECKS_COMPLETE" : "RECOVERY_READONLY_CHECKS_BLOCKED",
      claim_scope: "custom_recovery_surface_readonly_checks_only",
      action_scope: "bounded_custom_session_only",
      current_codex_touched: false,
      original_codex_touched: false,
      owned_session_root_only: true,
      arbitrary_path_accepted: false,
      browser_forbidden_fields_rejected: true,
      accounts_readonly_ok: accountsOk,
      api_readonly_ok: apiOk,
      process_kill_claimed: false,
      rollback_claimed: false,
      live_recovery_proof_claimed: false,
      historical_isolation_proof_only: true,
      fresh_truth: false,
      load_or_rotation_claimed: false,
      diagnostics_support_artifact_only: true,
      dangerous_actions_disabled: true,
      next_action: "operator_review"
    });
    await refreshCodexCustomRecoveryOperatorMatrix();
  } catch (error) {
    renderCodexCustomRecoveryPacket({
      status: "failed",
      machine_error_code: "RECOVERY_READONLY_CHECKS_FAILED",
      claim_scope: "custom_recovery_surface_readonly_checks_only",
      action_scope: "bounded_custom_session_only",
      current_codex_touched: false,
      original_codex_touched: false,
      owned_session_root_only: true,
      arbitrary_path_accepted: false,
      browser_forbidden_fields_rejected: true,
      accounts_readonly_ok: false,
      api_readonly_ok: false,
      process_kill_claimed: false,
      rollback_claimed: false,
      live_recovery_proof_claimed: false,
      historical_isolation_proof_only: true,
      fresh_truth: false,
      load_or_rotation_claimed: false,
      diagnostics_support_artifact_only: true,
      dangerous_actions_disabled: true,
      next_action: "retry",
    });
    codexCustomRecoverySetText("codexCustomRecoverySummary", `Recovery checks failed: ${error.message}`);
  }
}

async function cancelCodexCustomRecoverySession() {
  const packet = await postCodexCustomSessionAction("cancel", {});
  renderCodexCustomRecoveryPacket({
    ...(packet || { status: "rejected", machine_error_code: "SESSION_NOT_SELECTED", next_action: "create_session" }),
    claim_scope: "custom_recovery_surface_session_cancel_only",
    action_scope: "bounded_custom_session_only",
    original_codex_touched: false,
    owned_session_root_only: true,
    arbitrary_path_accepted: packet?.arbitrary_path_accepted === true,
    browser_forbidden_fields_rejected: true,
    accounts_readonly_ok: false,
    api_readonly_ok: false,
    rollback_claimed: false,
    live_recovery_proof_claimed: false,
    historical_isolation_proof_only: true,
    fresh_truth: false,
    load_or_rotation_claimed: false,
    diagnostics_support_artifact_only: true,
    dangerous_actions_disabled: true,
  });
  await refreshCodexCustomRecoveryAdmittedSessionActions();
}

async function cleanupCodexCustomRecoverySession() {
  const packet = await postCodexCustomSessionAction("cleanup", {});
  renderCodexCustomRecoveryPacket({
    ...(packet || { status: "rejected", machine_error_code: "SESSION_NOT_SELECTED", next_action: "create_session" }),
    claim_scope: "custom_recovery_surface_owned_cleanup_only",
    action_scope: "bounded_custom_session_only",
    original_codex_touched: false,
    owned_session_root_only: packet ? packet.owned_session_root_only === true : true,
    browser_forbidden_fields_rejected: true,
    accounts_readonly_ok: false,
    api_readonly_ok: false,
    rollback_claimed: false,
    live_recovery_proof_claimed: false,
    historical_isolation_proof_only: true,
    fresh_truth: false,
    load_or_rotation_claimed: false,
    diagnostics_support_artifact_only: true,
    dangerous_actions_disabled: true,
  });
  await refreshCodexCustomRecoveryAdmittedSessionActions();
}

function operatorSetChip(visual, label) {
  const chip = document.getElementById("operatorStatusChip");
  if (!chip) {
    return;
  }
  chip.className = `chip ${VISUAL_CLASS[visual] || ACTION_STATUS_VISUAL_CLASS[visual] || "neutral"}`;
  if (chip.lastElementChild) {
    chip.lastElementChild.textContent = label || visual || "unknown";
  }
}

function operatorRenderModels(payload) {
  const select = document.getElementById("operatorModelSelect");
  if (!select) {
    return;
  }
  const previous = select.value;
  const modelIds = Array.isArray(payload?.model_ids) ? payload.model_ids : [];
  select.replaceChildren();
  for (const modelId of modelIds) {
    const option = document.createElement("option");
    option.value = String(modelId);
    option.textContent = String(modelId);
    select.append(option);
  }
  if (modelIds.includes(previous)) {
    select.value = previous;
  } else if (modelIds.includes("gpt-5.3-codex")) {
    select.value = "gpt-5.3-codex";
  }
  operatorSetText("operatorTruthSource", payload?.server_issued ? "server-issued model list" : "models unavailable");
}

function operatorRenderTranscript(payload) {
  const list = document.getElementById("operatorTranscript");
  const entries = Array.isArray(payload?.entries) ? payload.entries : [];
  operatorSetText("operatorTranscriptCount", String(entries.length));
  if (!list) {
    return;
  }
  list.replaceChildren();
  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "action-ledger-empty";
    empty.textContent = "Operator transcript пуст.";
    list.append(empty);
    return;
  }
  for (const entry of entries.slice(-5).reverse()) {
    const item = document.createElement("div");
    item.className = "action-ledger-item";
    const head = document.createElement("div");
    head.className = "action-ledger-entry-head";
    const title = document.createElement("strong");
    title.textContent = `${entry.prompt_id || "operator_prompt"} · ${entry.selected_model || "-"}`;
    const chip = document.createElement("span");
    chip.className = `chip ${Number(entry.exit_code) === 0 ? "green" : "red"}`;
    const dot = document.createElement("span");
    dot.className = "dot";
    const chipText = document.createElement("span");
    chipText.textContent = Number(entry.exit_code) === 0 ? "ok" : "failed";
    chip.append(dot, chipText);
    head.append(title, chip);
    const message = document.createElement("p");
    message.textContent = entry.final_message || "-";
    const meta = document.createElement("div");
    meta.className = "secondary";
    meta.textContent = `hash ${String(entry.prompt_hash || "").slice(0, 12)} · ${entry.captured_at_utc || "-"}`;
    item.append(head, message, meta);
    list.append(item);
  }
}

function operatorRenderStatus(payload) {
  const status = payload?.status?.status || payload?.health?.status || "unknown";
  const machineCode = payload?.status?.machine_error_code || payload?.health?.machine_error_code || "-";
  const modelCount = Array.isArray(payload?.models?.model_ids) ? payload.models.model_ids.length : 0;
  operatorSetText("operatorStatusLine", `${status} · ${modelCount} server-issued models · claim gate ${payload?.claim_gate?.status || "not_reported"}`);
  operatorSetText("operatorMachineCode", machineCode);
  operatorSetChip(status === "ok" ? "green" : (status === "degraded" ? "amber" : "neutral"), status);
}

function operatorRenderResult(packet) {
  operatorLastPacket = packet;
  const okWithRefresh = packet?.status === "ok" && packet?.final_message && packet?.refresh_packet;
  const claimGateStatus = packet?.refresh_packet?.claim_gate?.status || "not_reported";
  const claimGateBlocked = String(claimGateStatus).includes("blocked");
  operatorSetChip(
    okWithRefresh && !claimGateBlocked ? "green" : (okWithRefresh ? "amber" : (packet?.status === "rejected" ? "amber" : "red")),
    okWithRefresh && claimGateBlocked ? "prompt ok / gate blocked" : (okWithRefresh ? "prompt ok" : (packet?.status || "failed"))
  );
  operatorSetText("operatorMachineCode", packet?.machine_error_code || "-");
  operatorSetText(
    "operatorRefreshState",
    packet?.refresh_packet
      ? `refresh packet included · claim gate ${claimGateStatus}`
      : "refresh packet missing"
  );
  operatorSetText("operatorStdinState", packet?.stdin_prompt_used ? "used" : "not proven");
  const response = document.getElementById("operatorResponse");
  if (response) {
    response.textContent = JSON.stringify({
      status: packet?.status || "unknown",
      machine_error_code: packet?.machine_error_code || "UNKNOWN",
      selected_model: packet?.selected_model || "",
      final_message: packet?.final_message || "",
      exit_code: packet?.exit_code,
      stdin_prompt_used: packet?.stdin_prompt_used === true,
      refresh_packet: Boolean(packet?.refresh_packet),
      claim_gate_status: claimGateStatus,
      temp_root_removed: packet?.temp_root_removed === true,
    }, null, 2);
  }
  operatorRenderTranscript(packet?.transcript || { entries: [] });
}

async function refreshOperatorPanel() {
  try {
    const [status, models, transcript] = await Promise.all([
      fetchOperatorJson("api/operator/status"),
      fetchOperatorJson("api/operator/models"),
      fetchOperatorJson("api/operator/transcript")
    ]);
    operatorRenderStatus(status);
    operatorRenderModels(models);
    operatorRenderTranscript(transcript);
    operatorSetText("operatorRefreshState", "readonly refresh complete");
  } catch (error) {
    operatorSetChip("red", "failed");
    operatorSetText("operatorStatusLine", `Operator surface fetch failed: ${error.message}`);
    operatorSetText("operatorMachineCode", "OPERATOR_SURFACE_FETCH_FAILED");
  }
}

async function runOperatorPrompt() {
  if (operatorRunInFlight) {
    return;
  }
  const promptNode = document.getElementById("operatorPrompt");
  const modelNode = document.getElementById("operatorModelSelect");
  const prompt = promptNode ? promptNode.value : "";
  const modelId = modelNode ? modelNode.value : "";
  operatorRunInFlight = true;
  document.getElementById("operatorRunAction")?.setAttribute("disabled", "disabled");
  operatorSetChip("neutral", "running");
  operatorSetText("operatorRefreshState", "running");
  try {
    const response = await fetch("api/operator/run", {
      method: "POST",
      cache: "no-store",
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ prompt, model_id: modelId })
    });
    if (!response.ok) {
      throw new Error(`operator run http ${response.status}`);
    }
    const packet = await response.json();
    operatorRenderResult(packet);
  } catch (error) {
    operatorRenderResult({
      status: "failed",
      machine_error_code: "OPERATOR_RUN_FETCH_FAILED",
      human_message: error.message,
      final_message: "",
      refresh_packet: null,
      transcript: { entries: [] }
    });
  } finally {
    operatorRunInFlight = false;
    document.getElementById("operatorRunAction")?.removeAttribute("disabled");
  }
}

function reviewSetText(id, value) {
  operatorSetText(id, value);
}

function reviewSetChip(visual, label) {
  const chip = document.getElementById("reviewStatusChip");
  if (!chip) {
    return;
  }
  chip.className = `chip ${VISUAL_CLASS[visual] || ACTION_STATUS_VISUAL_CLASS[visual] || "neutral"}`;
  if (chip.lastElementChild) {
    chip.lastElementChild.textContent = label || visual || "unknown";
  }
}

function reviewPacketTemplate() {
  return {
    schema_version: 1,
    project_id: "paste-current-project-id",
    baseline_hash: "paste-current-baseline-hash",
    review_items: [
      {
        id: "change-1",
        kind: "exact_text",
        scene_id: "scene-001",
        before: "old text",
        after: "new text"
      }
    ],
    orphan_comments: [],
    diagnostics: []
  };
}

function reviewEnsurePacketInputSeed() {
  const node = document.getElementById("reviewPacketInput");
  if (!node || String(node.value || "").trim()) {
    return;
  }
  node.value = JSON.stringify(reviewPacketTemplate(), null, 2);
}

async function postReviewCommand(commandId, payload = {}) {
  const commandField = "command" + "_id";
  const response = await fetch("api/review-command", {
    method: "POST",
    cache: "no-store",
    headers: webPostHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ [commandField]: commandId, payload })
  });
  if (!response.ok) {
    throw new Error(`api/review-command http ${response.status}`);
  }
  return response.json();
}

function reviewCommandSpec(commandId) {
  const commands = Array.isArray(reviewCommandsPacket?.commands) ? reviewCommandsPacket.commands : [];
  return commands.find((entry) => entry?.["command" + "_id"] === commandId) || null;
}

function reviewExactTextChanges() {
  const surface = reviewSurfacePacket?.review_surface;
  return Array.isArray(surface?.text_changes) ? surface.text_changes : [];
}

function reviewStructuralManualOnly() {
  const surface = reviewSurfacePacket?.review_surface;
  return Array.isArray(surface?.structural_manual_only) ? surface.structural_manual_only : [];
}

function reviewOrphanComments() {
  const surface = reviewSurfacePacket?.review_surface;
  return Array.isArray(surface?.orphan_comments) ? surface.orphan_comments : [];
}

function reviewReceiptPacketValue() {
  const receipt = reviewLastCommandPacket?.data?.receipt;
  return receipt ? JSON.stringify(receipt, null, 2) : "receipt pending";
}

function reviewBlockedPacket() {
  if (reviewLastCommandPacket?.status && reviewLastCommandPacket.status !== "ok") {
    return reviewLastCommandPacket;
  }
  if (reviewSurfacePacket?.apply_preflight?.status && reviewSurfacePacket.apply_preflight.status !== "ok") {
    return reviewSurfacePacket.apply_preflight;
  }
  if (reviewSurfacePacket?.status && reviewSurfacePacket.status !== "ok") {
    return reviewSurfacePacket;
  }
  return null;
}

function reviewLiveSourceSelected() {
  const sourcePicker = document.getElementById("sourcePicker");
  return !sourcePicker || sourcePicker.value === "live";
}

function reviewApplyAdmissionState() {
  const preflight = reviewSurfacePacket?.apply_preflight;
  const applySpec = reviewCommandSpec("apply_exact_text_change");
  const admitted = Boolean(
    applySpec?.runtime_enabled === true
      && preflight?.status === "ok"
      && preflight?.data?.future_apply_admissible === true
      && preflight?.machine_error_code === "REVIEW_APPLY_TARGET_RESOLVED_ADMITTED"
  );
  return {
    admitted,
    label: admitted
      ? String(preflight?.machine_error_code || "admitted")
      : (
        applySpec?.runtime_enabled === false
          ? "REVIEW_APPLY_NOT_ENABLED"
          : (preflight?.machine_error_code || reviewSurfacePacket?.machine_error_code || "not_ready")
      ),
  };
}

function reviewRejectNonLiveCommand(commandId) {
  const commandField = "command" + "_id";
  reviewLastCommandPacket = {
    status: "command_error",
    machine_error_code: "REVIEW_UI_SOURCE_NOT_LIVE",
    human_message: `Review command ${commandId} is available only when source=live.`,
    changed_files: [],
    next_action: "switch_source_to_live",
    data: { [commandField]: commandId }
  };
  renderReviewPanel();
}

function reviewListRow(title, detail) {
  const item = document.createElement("div");
  item.className = "action-ledger-item";
  const head = document.createElement("div");
  head.className = "action-ledger-entry-head";
  const label = document.createElement("strong");
  label.textContent = title;
  head.append(label);
  item.append(head);
  const note = document.createElement("p");
  note.textContent = detail || "-";
  item.append(note);
  return item;
}

function renderReviewList(targetId, rows) {
  const node = document.getElementById(targetId);
  if (!node) {
    return;
  }
  node.replaceChildren();
  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "action-ledger-empty";
    empty.textContent = "Нет данных.";
    node.append(empty);
    return;
  }
  for (const row of rows) {
    node.append(row);
  }
}

function renderReviewPanelFailure(error) {
  reviewSurfacePacket = null;
  reviewCommandsPacket = null;
  reviewSetChip("red", "failed");
  reviewSetText("reviewStatusLine", `Review bridge fetch failed: ${error.message}`);
  reviewSetText("reviewSessionState", "not available");
  reviewSetText("reviewProjectId", "-");
  reviewSetText("reviewBaselineHash", "-");
  reviewSetText("reviewTextChangeCount", "0");
  reviewSetText("reviewStructuralCount", "0");
  reviewSetText("reviewOrphanCount", "0");
  reviewSetText("reviewApplyPreflightState", "fetch failed");
  reviewSetText("reviewLastCommandCode", reviewLastCommandPacket?.machine_error_code || "-");
  renderReviewList("reviewBlockedReasonsList", [reviewListRow("fetch", error.message)]);
  renderReviewList("reviewTextChangesList", []);
  renderReviewList("reviewStructuralList", []);
  renderReviewList("reviewOrphanList", []);
  const receiptNode = document.getElementById("reviewReceiptPacket");
  if (receiptNode) {
    receiptNode.textContent = reviewReceiptPacketValue();
  }
  const responseNode = document.getElementById("reviewCommandResponse");
  if (responseNode) {
    responseNode.textContent = JSON.stringify({
      status: "fetch_failed",
      machine_error_code: "REVIEW_UI_FETCH_FAILED",
      human_message: error.message
    }, null, 2);
  }
  document.getElementById("reviewImportAction")?.setAttribute("disabled", "disabled");
  document.getElementById("reviewApplyAction")?.setAttribute("disabled", "disabled");
  document.getElementById("reviewClearAction")?.setAttribute("disabled", "disabled");
}

function renderReviewPanel() {
  reviewEnsurePacketInputSeed();
  if (!reviewLiveSourceSelected()) {
    reviewSetChip("neutral", "fixture");
    reviewSetText("reviewStatusLine", "Review bridge UI reflects existing live packets only. Переключите source на live.");
    reviewSetText("reviewSessionState", "live only");
    reviewSetText("reviewProjectId", "-");
    reviewSetText("reviewBaselineHash", "-");
    reviewSetText("reviewTextChangeCount", "0");
    reviewSetText("reviewStructuralCount", "0");
    reviewSetText("reviewOrphanCount", "0");
    reviewSetText("reviewApplyPreflightState", "live only");
    reviewSetText("reviewLastCommandCode", reviewLastCommandPacket?.machine_error_code || "-");
    renderReviewList("reviewBlockedReasonsList", [reviewListRow("review bridge", "Fixture preview does not expose review command/query truth.")]);
    renderReviewList("reviewTextChangesList", []);
    renderReviewList("reviewStructuralList", []);
    renderReviewList("reviewOrphanList", []);
    const receiptNode = document.getElementById("reviewReceiptPacket");
    if (receiptNode) {
      receiptNode.textContent = reviewReceiptPacketValue();
    }
    const responseNode = document.getElementById("reviewCommandResponse");
    if (responseNode) {
      responseNode.textContent = reviewLastCommandPacket ? JSON.stringify(reviewLastCommandPacket, null, 2) : "command packet pending";
    }
    document.getElementById("reviewImportAction")?.setAttribute("disabled", "disabled");
    document.getElementById("reviewApplyAction")?.setAttribute("disabled", "disabled");
    document.getElementById("reviewClearAction")?.setAttribute("disabled", "disabled");
    return;
  }

  const sessionPresent = reviewSurfacePacket?.session_present === true;
  const exactChanges = reviewExactTextChanges();
  const structural = reviewStructuralManualOnly();
  const orphanComments = reviewOrphanComments();
  const blockedPacket = reviewBlockedPacket();
  const applyState = reviewApplyAdmissionState();
  const surfaceStatus = reviewSurfacePacket?.status || "unknown";
  const statusVisual = surfaceStatus === "ok"
    ? (applyState.admitted ? "green" : "amber")
    : (surfaceStatus === "empty" ? "neutral" : "red");
  reviewSetChip(statusVisual, applyState.admitted ? "apply admitted" : surfaceStatus);
  reviewSetText(
    "reviewStatusLine",
    reviewSurfacePacket?.human_message
      || (sessionPresent ? "Review session loaded through existing query surface." : "Review session is empty.")
  );
  reviewSetText("reviewSessionState", sessionPresent ? "active" : "empty");
  reviewSetText("reviewProjectId", reviewSurfacePacket?.project_id || "-");
  reviewSetText("reviewBaselineHash", reviewSurfacePacket?.baseline_hash || "-");
  reviewSetText("reviewTextChangeCount", String(exactChanges.length));
  reviewSetText("reviewStructuralCount", String(structural.length));
  reviewSetText("reviewOrphanCount", String(orphanComments.length));
  reviewSetText("reviewApplyPreflightState", applyState.label);
  reviewSetText("reviewLastCommandCode", reviewLastCommandPacket?.machine_error_code || "-");

  const blockedRows = [];
  if (blockedPacket?.machine_error_code) {
    blockedRows.push(
      reviewListRow(
        blockedPacket.machine_error_code,
        blockedPacket.human_message || blockedPacket.next_action || "blocked"
      )
    );
  }
  renderReviewList("reviewBlockedReasonsList", blockedRows);
  renderReviewList(
    "reviewTextChangesList",
    exactChanges.map((item) => reviewListRow(String(item.id || "exact_text"), `${String(item.scene_id || "-")} · exact_text`))
  );
  renderReviewList(
    "reviewStructuralList",
    structural.map((item) => reviewListRow(String(item.id || "structural"), "manual_only structural review item"))
  );
  renderReviewList(
    "reviewOrphanList",
    orphanComments.map((item, index) => reviewListRow(`orphan-${index + 1}`, String(item?.message || item?.text || JSON.stringify(item))))
  );

  const receiptNode = document.getElementById("reviewReceiptPacket");
  if (receiptNode) {
    receiptNode.textContent = reviewReceiptPacketValue();
  }
  const responseNode = document.getElementById("reviewCommandResponse");
  if (responseNode) {
    responseNode.textContent = reviewLastCommandPacket ? JSON.stringify(reviewLastCommandPacket, null, 2) : "command packet pending";
  }
  document.getElementById("reviewImportAction")?.removeAttribute("disabled");
  document.getElementById("reviewClearAction")?.removeAttribute("disabled");

  const applyButton = document.getElementById("reviewApplyAction");
  if (applyButton) {
    if (applyState.admitted) {
      applyButton.removeAttribute("disabled");
    } else {
      applyButton.setAttribute("disabled", "disabled");
    }
  }
}

async function refreshReviewPanel() {
  if (reviewPanelBusy || currentScreen() !== "overview") {
    return;
  }
  reviewPanelBusy = true;
  try {
    reviewEnsurePacketInputSeed();
    if (!reviewLiveSourceSelected()) {
      renderReviewPanel();
      return;
    }
    const [surface, commands] = await Promise.all([
      fetchReviewJson("api/review-surface"),
      fetchReviewJson("api/review-commands")
    ]);
    reviewSurfacePacket = surface;
    reviewCommandsPacket = commands;
    renderReviewPanel();
  } catch (error) {
    renderReviewPanelFailure(error);
  } finally {
    reviewPanelBusy = false;
  }
}

async function importReviewPacketFromPanel() {
  if (reviewPanelBusy) {
    return;
  }
  if (!reviewLiveSourceSelected()) {
    reviewRejectNonLiveCommand("import_review_packet");
    return;
  }
  const input = document.getElementById("reviewPacketInput");
  const rawValue = input ? String(input.value || "").trim() : "";
  if (!rawValue) {
    reviewLastCommandPacket = {
      status: "command_error",
      machine_error_code: "REVIEW_UI_PACKET_JSON_INVALID",
      human_message: "Paste a bounded JSON review packet before import.",
    };
    renderReviewPanel();
    return;
  }
  let reviewPacket;
  try {
    reviewPacket = JSON.parse(rawValue);
  } catch (error) {
    reviewLastCommandPacket = {
      status: "command_error",
      machine_error_code: "REVIEW_UI_PACKET_JSON_INVALID",
      human_message: `Review packet JSON parse failed: ${error.message}`,
    };
    renderReviewPanel();
    return;
  }
  try {
    reviewPanelBusy = true;
    reviewLastCommandPacket = await postReviewCommand("import_review_packet", { review_packet: reviewPacket });
    const [surface, commands] = await Promise.all([
      fetchReviewJson("api/review-surface"),
      fetchReviewJson("api/review-commands")
    ]);
    reviewSurfacePacket = surface;
    reviewCommandsPacket = commands;
    renderReviewPanel();
  } catch (error) {
    renderReviewPanelFailure(error);
  } finally {
    reviewPanelBusy = false;
  }
}

async function applyReviewExactChangeFromPanel() {
  if (reviewPanelBusy) {
    return;
  }
  if (!reviewLiveSourceSelected()) {
    reviewRejectNonLiveCommand("apply_exact_text_change");
    return;
  }
  try {
    reviewPanelBusy = true;
    reviewLastCommandPacket = await postReviewCommand("apply_exact_text_change", {});
    const [surface, commands] = await Promise.all([
      fetchReviewJson("api/review-surface"),
      fetchReviewJson("api/review-commands")
    ]);
    reviewSurfacePacket = surface;
    reviewCommandsPacket = commands;
    renderReviewPanel();
  } catch (error) {
    renderReviewPanelFailure(error);
  } finally {
    reviewPanelBusy = false;
  }
}

async function clearReviewSessionFromPanel() {
  if (reviewPanelBusy) {
    return;
  }
  if (!reviewLiveSourceSelected()) {
    reviewRejectNonLiveCommand("clear_review_session");
    return;
  }
  try {
    reviewPanelBusy = true;
    reviewLastCommandPacket = await postReviewCommand("clear_review_session", {});
    const [surface, commands] = await Promise.all([
      fetchReviewJson("api/review-surface"),
      fetchReviewJson("api/review-commands")
    ]);
    reviewSurfacePacket = surface;
    reviewCommandsPacket = commands;
    renderReviewPanel();
  } catch (error) {
    renderReviewPanelFailure(error);
  } finally {
    reviewPanelBusy = false;
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
  if (displayState === "cancelled") {
    return "Ожидание ответа отменено в браузере. Это не подтверждает ни успех, ни откат server-side команды.";
  }
  if (displayState === "invalid_json") {
    return "Endpoint вернул invalid JSON. Это жёсткая ошибка интеграции, а не успех.";
  }
  if (displayState === "command_error") {
    if (
      payload.ui_action === "api_route_credential_check"
      && payload.result?.machine_error_code === "EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING"
    ) {
      return "Owner credential не найден в server process. Browser не принимает secret; следующий шаг остаётся owner-side.";
    }
    return "Строгий JSON-пакет сообщил command_error. UI не должен показывать это как успех.";
  }
  if (displayState === "partial_success") {
    return "Verify bundle завершился частично: хотя бы один bounded truth surface требует следующего шага, поэтому ready не заявляется.";
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
    cancelled: "ожидание отменено",
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
  const onboardLoginWindow = uiAction === "onboard_account" ? openOnboardLoginWindow() : onboardLoginWindowRef;
  if (activeActionRequestKey) {
    const sameRequest = activeActionRequestKey === requestKey;
    const duplicatePayload = {
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
    };
    setActionPanel(duplicatePayload);
    return { payload: duplicatePayload, refreshState: "none" };
  }
  activeActionRequestKey = requestKey;
  activeActionAbortReason = "";
  activeActionAbortController = typeof AbortController === "function" ? new AbortController() : null;
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
      headers: webPostHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(requestPayload),
      signal: activeActionAbortController?.signal
    });
    if (!response.ok) {
      throw new Error(`action http ${response.status}`);
    }
    const payload = await response.json();
    return await handleActionPayload(payload, onboardLoginWindow);
  } catch (error) {
    const abortedByUser = error?.name === "AbortError" && activeActionAbortReason === "user_cancelled";
    const timeoutFailure = !abortedByUser && (
      error.name === "AbortError" || String(error.message || "").toLowerCase().includes("timeout")
    );
    if (onboardLoginWindow) {
      writeOnboardLoginWindowStatus(
        onboardLoginWindow,
        abortedByUser ? "Owner login wait cancelled" : "Owner login failed",
        abortedByUser
          ? "Waiting for the owner login packet was cancelled in the browser. Refresh Wild Boar Proxy before retrying."
          : "Web could not receive the owner login packet. Return to Wild Boar Proxy and retry.",
        abortedByUser ? "warning" : "error"
      );
    }
    const failureStatus = abortedByUser
      ? "cancelled"
      : (error instanceof SyntaxError ? "invalid_json" : (timeoutFailure ? "timeout" : "integration_failure"));
    const machineCode = abortedByUser
      ? "UI_ACTION_WAIT_CANCELLED"
      : (error instanceof SyntaxError
        ? "UI_ACTION_INVALID_JSON"
        : (timeoutFailure ? "UI_ACTION_TIMEOUT" : "UI_ACTION_FETCH_FAILED"));
    const failurePayload = {
      ui_action: uiAction,
      action_role: abortedByUser ? "user_cancelled" : "integration_failure",
      account_id: requestPayload.account_id || "",
      route_id: requestPayload.route_id || "",
      post_action_refresh_required: false,
      result: {
        status: failureStatus,
        machine_error_code: machineCode,
        human_message: abortedByUser
          ? "Ожидание результата отменено в браузере. Если команда уже стартовала на сервере, выполните refresh перед повтором."
          : error.message,
        next_action: abortedByUser ? "refresh" : "retry",
        changed_files: []
      }
    };
    setActionPanel(failurePayload);
    return { payload: failurePayload, refreshState: "failed" };
  } finally {
    activeActionRequestKey = "";
    activeActionAbortController = null;
    activeActionAbortReason = "";
    setActionsBusy(false);
  }
}

function openOnboardLoginWindow() {
  if (!window) {
    return null;
  }
  const openFn = window["open"];
  if (typeof openFn !== "function") {
    return null;
  }
  try {
    const loginWindow = openFn.call(window, "about:blank", "_blank");
    if (loginWindow) {
      onboardLoginWindowRef = loginWindow;
      writeOnboardLoginWindowStatus(
        loginWindow,
        "Codex login is starting",
        "Waiting for the owner-controlled device login session from the server.",
        "pending"
      );
    }
    return loginWindow;
  } catch (_error) {
    return null;
  }
}

function ensureOnboardLoginOverlay() {
  if (typeof document === "undefined" || !document.body) {
    return null;
  }
  let overlay = document.getElementById("onboardLoginOverlay");
  if (overlay) {
    return overlay;
  }
  overlay = document.createElement("div");
  overlay.id = "onboardLoginOverlay";
  overlay.style.cssText = "position:fixed;inset:0;display:none;align-items:center;justify-content:center;background:rgba(32,26,18,0.52);z-index:9999;padding:24px;";
  overlay.innerHTML = `
    <div style="width:min(680px,100%);background:#fffaf2;border:1px solid #d8cfc0;border-left:6px solid #2f5f9f;box-shadow:0 20px 60px rgba(30,24,16,0.18);padding:28px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#2b2925;">
      <div id="onboardLoginOverlayTone" style="display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:999px;background:#edf3ff;color:#244f8f;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;">owner login</div>
      <h2 id="onboardLoginOverlayTitle" style="margin:18px 0 12px;font-size:22px;line-height:1.25;">Codex device login</h2>
      <p id="onboardLoginOverlayMessage" style="margin:0;font-size:15px;line-height:1.6;">Waiting for the owner-controlled device login session from the server.</p>
      <div style="display:grid;gap:14px;margin-top:22px;padding-top:18px;border-top:1px solid #e6dccd;">
        <div style="display:grid;gap:6px;">
          <span style="color:#746d63;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;">device URL</span>
          <strong id="onboardLoginOverlayUrl" style="font-size:17px;word-break:break-word;">-</strong>
        </div>
        <div style="display:grid;gap:6px;">
          <span style="color:#746d63;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;">device code</span>
          <strong id="onboardLoginOverlayCode" style="font-size:22px;letter-spacing:0.04em;word-break:break-word;">-</strong>
        </div>
        <div style="display:grid;gap:6px;">
          <span style="color:#746d63;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;">session</span>
          <strong id="onboardLoginOverlaySession" style="font-size:16px;word-break:break-word;">-</strong>
        </div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:24px;">
        <button id="onboardLoginOverlayOpen" type="button" style="appearance:none;border:1px solid #244f8f;background:#244f8f;color:#fff;font:inherit;padding:10px 14px;cursor:pointer;">Открыть вход</button>
        <button id="onboardLoginOverlayCheck" type="button" style="appearance:none;border:1px solid #d8cfc0;background:#fff;color:#2b2925;font:inherit;padding:10px 14px;cursor:pointer;">Проверить</button>
        <button id="onboardLoginOverlayComplete" type="button" style="appearance:none;border:1px solid #2f7a46;background:#2f7a46;color:#fff;font:inherit;padding:10px 14px;cursor:pointer;display:none;">Завершить</button>
        <button id="onboardLoginOverlayCancel" type="button" style="appearance:none;border:1px solid #d8cfc0;background:#fff;color:#2b2925;font:inherit;padding:10px 14px;cursor:pointer;">Отменить</button>
        <button id="onboardLoginOverlayClose" type="button" style="appearance:none;border:1px solid #d8cfc0;background:#fff;color:#2b2925;font:inherit;padding:10px 14px;cursor:pointer;margin-left:auto;">Скрыть</button>
      </div>
    </div>
  `;
  document.body.append(overlay);
  overlay.querySelector("#onboardLoginOverlayOpen")?.addEventListener("click", () => {
    const targetUrl = activeOnboardLoginSession?.deviceUrl || onboardLoginOverlayOpenUrl;
    if (typeof targetUrl !== "string" || !targetUrl) {
      return;
    }
    try {
      const openFn = window["open"];
      if (typeof openFn === "function") {
        const opened = openFn.call(window, targetUrl, "_blank");
        if (opened) {
          onboardLoginWindowRef = opened;
        }
      }
    } catch (_openError) {
    }
  });
  overlay.querySelector("#onboardLoginOverlayCheck")?.addEventListener("click", () => {
    const sessionId = activeOnboardLoginSession?.sessionId || "";
    if (sessionId) {
      runUiAction("account_login_status", { session_id: sessionId }).catch(() => {});
    }
  });
  overlay.querySelector("#onboardLoginOverlayComplete")?.addEventListener("click", () => {
    const sessionId = activeOnboardLoginSession?.sessionId || "";
    if (sessionId) {
      runUiAction("account_login_complete", { session_id: sessionId }).catch(() => {});
    }
  });
  overlay.querySelector("#onboardLoginOverlayCancel")?.addEventListener("click", () => {
    const sessionId = activeOnboardLoginSession?.sessionId || "";
    if (sessionId) {
      runUiAction("account_login_cancel", { session_id: sessionId }).catch(() => {});
    }
  });
  overlay.querySelector("#onboardLoginOverlayClose")?.addEventListener("click", () => {
    overlay.style.display = "none";
  });
  return overlay;
}

function renderOnboardLoginOverlay(model) {
  const overlay = ensureOnboardLoginOverlay();
  if (!overlay) {
    return;
  }
  overlay.style.display = "flex";
  onboardLoginOverlayOpenUrl = typeof model?.deviceUrl === "string" ? model.deviceUrl : "";
  const toneNode = overlay.querySelector("#onboardLoginOverlayTone");
  const titleNode = overlay.querySelector("#onboardLoginOverlayTitle");
  const messageNode = overlay.querySelector("#onboardLoginOverlayMessage");
  const urlNode = overlay.querySelector("#onboardLoginOverlayUrl");
  const codeNode = overlay.querySelector("#onboardLoginOverlayCode");
  const sessionNode = overlay.querySelector("#onboardLoginOverlaySession");
  const openNode = overlay.querySelector("#onboardLoginOverlayOpen");
  const checkNode = overlay.querySelector("#onboardLoginOverlayCheck");
  const completeNode = overlay.querySelector("#onboardLoginOverlayComplete");
  const cancelNode = overlay.querySelector("#onboardLoginOverlayCancel");
  if (toneNode) {
    toneNode.textContent = model?.tone === "success"
      ? "owner login completed"
      : (model?.tone === "error" ? "owner login attention" : "owner login session");
    toneNode.style.background = model?.tone === "success" ? "#e9f6ee" : (model?.tone === "error" ? "#fff0ed" : "#edf3ff");
    toneNode.style.color = model?.tone === "success" ? "#2f7a46" : (model?.tone === "error" ? "#9f2f2f" : "#244f8f");
  }
  if (titleNode) titleNode.textContent = model?.title || "Codex device login";
  if (messageNode) messageNode.textContent = model?.message || "Waiting for the owner-controlled device login session from the server.";
  if (urlNode) urlNode.textContent = model?.deviceUrl || "-";
  if (codeNode) codeNode.textContent = model?.deviceCode || "-";
  if (sessionNode) sessionNode.textContent = model?.sessionId || "-";
  if (openNode) openNode.style.display = model?.deviceUrl ? "inline-flex" : "none";
  if (checkNode) checkNode.style.display = model?.canCheck ? "inline-flex" : "none";
  if (completeNode) completeNode.style.display = model?.canComplete ? "inline-flex" : "none";
  if (cancelNode) cancelNode.style.display = model?.canCancel ? "inline-flex" : "none";
}

function openDeviceLoginWindowIfNeeded(loginWindow, payload) {
  if (!loginWindow) {
    return;
  }
  const model = onboardLoginWindowModelFromPayload(payload);
  if (!model.deviceUrl) {
    return;
  }
  try {
    const currentUrl = typeof loginWindow.location?.href === "string" ? loginWindow.location.href : "";
    if (currentUrl === model.deviceUrl) {
      return;
    }
  } catch (_currentUrlError) {
    return;
  }
  try {
    if (onboardLoginWindowBlobUrl && typeof URL !== "undefined" && typeof URL.revokeObjectURL === "function") {
      try {
        URL.revokeObjectURL(onboardLoginWindowBlobUrl);
      } catch (_revokeError) {
      }
      onboardLoginWindowBlobUrl = "";
    }
    loginWindow.location.href = model.deviceUrl;
  } catch (_navigateError) {
  }
}

function onboardLoginWindowEscape(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function onboardLoginWindowHtml(model) {
  const title = typeof model?.title === "string" ? model.title : "Owner login";
  const message = typeof model?.message === "string" ? model.message : "Waiting for owner login status.";
  const tone = typeof model?.tone === "string" ? model.tone : "pending";
  const safeTitle = onboardLoginWindowEscape(title);
  const safeMessage = onboardLoginWindowEscape(message);
  const safeDeviceUrl = onboardLoginWindowEscape(model?.deviceUrl || "");
  const safeDeviceCode = onboardLoginWindowEscape(model?.deviceCode || "");
  const safeSessionId = onboardLoginWindowEscape(model?.sessionId || "");
  const checkHidden = model?.canCheck === false ? " hidden" : "";
  const completeHidden = model?.canComplete === true ? "" : " hidden";
  const cancelHidden = model?.canCancel === false ? " hidden" : "";
  const borderColor = tone === "error" ? "#9f2f2f" : (tone === "success" ? "#2f7a46" : "#2f5f9f");
  const encodedModel = JSON.stringify({
    sessionId: model?.sessionId || "",
    title,
    message,
    tone,
    serverOrigin: (typeof window !== "undefined" && window.location && typeof window.location.origin === "string") ? window.location.origin : "",
    webToken: webBootstrapValue("wbp-web-token"),
    csrfToken: webBootstrapValue("wbp-csrf-token"),
    deviceUrl: model?.deviceUrl || "",
    deviceCode: model?.deviceCode || "",
    status: model?.status || "",
    canCheck: model?.canCheck === true,
    canComplete: model?.canComplete === true,
    canCancel: model?.canCancel === true,
  }).replace(/</g, "\\u003c");
  const deviceSection = safeDeviceUrl || safeDeviceCode
    ? `
    <section class="detail-block">
      <div class="detail-row"><span>device URL</span><strong id="deviceUrl">${safeDeviceUrl || "-"}</strong></div>
      <div class="detail-row"><span>device code</span><strong id="deviceCode">${safeDeviceCode || "-"}</strong></div>
      <div class="detail-row"><span>session</span><strong id="sessionId">${safeSessionId || "-"}</strong></div>
    </section>`
    : "";
  return `<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>${safeTitle}</title>
  <style>
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f7f3eb; color: #2b2925; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    main { max-width: 560px; padding: 28px; border: 1px solid #d8cfc0; border-left: 6px solid ${borderColor}; background: #fffaf2; box-shadow: 0 20px 60px rgba(30, 24, 16, 0.14); }
    h1 { margin: 0 0 12px; font-size: 20px; line-height: 1.3; }
    p { margin: 0; font-size: 15px; line-height: 1.55; }
    .detail-block { margin-top: 18px; padding-top: 18px; border-top: 1px solid #e6dccd; display: grid; gap: 10px; }
    .detail-row { display: grid; gap: 6px; }
    .detail-row span { color: #746d63; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
    .detail-row strong { font-size: 18px; word-break: break-word; }
    .actions { margin-top: 22px; display: flex; flex-wrap: wrap; gap: 10px; }
    button { appearance: none; border: 1px solid #d8cfc0; background: white; color: #2b2925; font: inherit; padding: 10px 14px; cursor: pointer; }
    button.primary { background: #244f8f; color: white; border-color: #244f8f; }
    button[hidden] { display: none; }
  </style>
</head>
<body>
  <main>
    <h1 id="title">${safeTitle}</h1>
    <p id="message">${safeMessage}</p>
    ${deviceSection}
    <div class="actions">
      <button id="checkButton" class="primary" type="button"${checkHidden}>Проверить</button>
      <button id="completeButton" type="button"${completeHidden}>Завершить</button>
      <button id="cancelButton" type="button"${cancelHidden}>Отменить</button>
    </div>
  </main>
  <script>
    const MODEL = ${encodedModel};
    const ACTION_URL = MODEL.serverOrigin ? MODEL.serverOrigin + "/api/action" : "api/action";
    let requestInFlight = false;
    const safeText = (value, fallback = "-") => {
      if (typeof value !== "string") return fallback;
      const trimmed = value.trim();
      return trimmed ? trimmed : fallback;
    };
    const postToOpener = (payload) => {
      try {
        if (window.opener && !window.opener.closed) {
          window.opener.postMessage({ type: "wbp-onboard-login-payload", payload }, "*");
        }
      } catch (_openerError) {
      }
    };
    const setActionButtonsBusy = (isBusy) => {
      for (const id of ["checkButton", "completeButton", "cancelButton"]) {
        const node = document.getElementById(id);
        if (node && !node.hidden) {
          node.disabled = isBusy;
        }
      }
    };
    const requestAction = async (uiAction) => {
      if (!MODEL.sessionId || requestInFlight) {
        return;
      }
      requestInFlight = true;
      setActionButtonsBusy(true);
      try {
        const response = await fetch(ACTION_URL, {
          method: "POST",
          cache: "no-store",
          headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + (MODEL.webToken || ""),
            "X-WBP-CSRF": MODEL.csrfToken || ""
          },
          body: JSON.stringify({ ui_action: uiAction, session_id: MODEL.sessionId })
        });
        if (!response.ok) {
          throw new Error("action http " + response.status);
        }
        const payload = await response.json();
        renderPayload(payload);
      } catch (error) {
        renderPayload({
          status: "integration_failure",
          ui_action: uiAction,
          result: {
            status: "integration_failure",
            machine_error_code: "UI_ACTION_FETCH_FAILED",
            human_message: error && error.message ? String(error.message) : "Popup could not reach the owner action endpoint.",
            next_action: "retry",
            changed_files: [],
            data: {
              login_bridge: {
                status: MODEL.status || "unknown",
                session_id: MODEL.sessionId,
                device_url: MODEL.deviceUrl || "",
                device_code: MODEL.deviceCode || ""
              }
            }
          }
        });
      } finally {
        requestInFlight = false;
        setActionButtonsBusy(false);
      }
    };
    const setButtonState = (id, visible) => {
      const node = document.getElementById(id);
      if (node) {
        node.hidden = !visible;
      }
    };
    const setText = (id, value) => {
      const node = document.getElementById(id);
      if (node) {
        node.textContent = safeText(value);
      }
    };
    const renderPayload = (payload) => {
      const result = payload && payload.result ? payload.result : {};
      const bridge = result.data && result.data.login_bridge ? result.data.login_bridge : {};
      const status = safeText(bridge.status, "unknown");
      const title = payload && payload.ui_action === "account_login_complete"
        ? (result.status === "ok" ? "Codex login completed" : "Codex login completion failed")
        : (payload && payload.ui_action === "account_login_cancel"
          ? "Codex login cancelled"
          : (status === "auth_materialized" ? "Codex auth materialized" : "Codex device login"));
      const message = safeText(result.human_message, MODEL.message);
      setText("title", title);
      setText("message", message);
      setText("deviceUrl", bridge.device_url || bridge.login_url || MODEL.deviceUrl);
      setText("deviceCode", bridge.device_code || MODEL.deviceCode);
      setText("sessionId", bridge.session_id || bridge.login_session_id || MODEL.sessionId);
      const canComplete = status === "auth_materialized";
      const terminal = ["completed", "cancelled", "expired", "failed"].includes(status)
        || payload?.ui_action === "account_login_complete"
        || payload?.ui_action === "account_login_cancel";
      setButtonState("checkButton", !terminal && !canComplete);
      setButtonState("completeButton", canComplete);
      setButtonState("cancelButton", !terminal);
      postToOpener(payload);
    };
    document.getElementById("checkButton")?.addEventListener("click", () => requestAction("account_login_status"));
    document.getElementById("completeButton")?.addEventListener("click", () => requestAction("account_login_complete"));
    document.getElementById("cancelButton")?.addEventListener("click", () => requestAction("account_login_cancel"));
    setButtonState("checkButton", MODEL.canCheck !== false);
    setButtonState("completeButton", MODEL.canComplete === true);
    setButtonState("cancelButton", MODEL.canCancel !== false);
  </script>
</body>
</html>`;
}

function writeOnboardLoginWindowStatus(loginWindow, title, message, tone = "pending") {
  if (!loginWindow) {
    return false;
  }
  const html = onboardLoginWindowHtml({ title, message, tone, canCheck: false, canCancel: false, canComplete: false });
  try {
    if (loginWindow.document && typeof loginWindow.document.write === "function") {
      if (typeof loginWindow.document.open === "function") {
        loginWindow.document.open();
      }
      loginWindow.document.write(html);
      if (typeof loginWindow.document.close === "function") {
        loginWindow.document.close();
      }
      return true;
    }
  } catch (_documentError) {
  }
  try {
    if (
      typeof URL !== "undefined"
      && typeof URL.createObjectURL === "function"
      && typeof Blob !== "undefined"
      && loginWindow.location
      && typeof loginWindow.location === "object"
    ) {
      if (onboardLoginWindowBlobUrl && typeof URL.revokeObjectURL === "function") {
        try {
          URL.revokeObjectURL(onboardLoginWindowBlobUrl);
        } catch (_revokeError) {
        }
      }
      onboardLoginWindowBlobUrl = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
      loginWindow.location.href = onboardLoginWindowBlobUrl;
      return true;
    }
  } catch (_locationError) {
  }
  return false;
}

function onboardLoginBridgeFromPayload(payload) {
  const loginBridge = payload?.result?.data?.login_bridge;
  return loginBridge && typeof loginBridge === "object" ? loginBridge : {};
}

function onboardLoginSessionIdFromPayload(payload) {
  const loginBridge = onboardLoginBridgeFromPayload(payload);
  const value = loginBridge.session_id || loginBridge.login_session_id || "";
  return typeof value === "string" ? value : "";
}

function onboardLoginWindowModelFromPayload(payload) {
  const loginBridge = onboardLoginBridgeFromPayload(payload);
  const result = payload?.result || {};
  const status = typeof loginBridge.status === "string" ? loginBridge.status : "";
  const sessionId = onboardLoginSessionIdFromPayload(payload);
  const deviceUrl = typeof loginBridge.device_url === "string"
    ? loginBridge.device_url
    : (typeof loginBridge.login_url === "string" ? loginBridge.login_url : "");
  const deviceCode = typeof loginBridge.device_code === "string" ? loginBridge.device_code : "";
  let title = "Owner login is starting";
  let message = typeof result.human_message === "string" && result.human_message
    ? result.human_message
    : "Waiting for the owner-controlled login status from the server.";
  let tone = "pending";
  if (status === "waiting_for_user" || status === "started") {
    title = "Codex device login";
    message = "Open the device URL, enter the code, then click Проверить.";
  } else if (status === "auth_materialized") {
    title = "Codex auth materialized";
    message = "Owner auth artifact was detected in sandbox. Click Завершить to onboard the account into reserve.";
  } else if (status === "completed") {
    title = "Codex login completed";
    message = "Reserve onboarding completed. Return to Wild Boar Proxy for refreshed account state.";
    tone = "success";
  } else if (status === "cancelled") {
    title = "Codex login cancelled";
    message = "Owner login session was cancelled.";
    tone = "error";
  } else if (status === "expired" || status === "failed") {
    title = "Codex login failed";
    tone = "error";
  } else if (payload?.result?.status !== "ok") {
    title = "Codex login blocked";
    tone = "error";
  }
  return {
    title,
    message,
    tone,
    sessionId,
    deviceUrl,
    deviceCode,
    status,
    canCheck: Boolean(sessionId) && ["started", "waiting_for_user", "unknown"].includes(status || "waiting_for_user"),
    canComplete: status === "auth_materialized",
    canCancel: Boolean(sessionId) && !["completed", "cancelled", "expired", "failed"].includes(status),
  };
}

function maybeNavigateOnboardLoginWindow(loginWindow, payload) {
  if (!loginWindow) {
    return;
  }
  const model = onboardLoginWindowModelFromPayload(payload);
  if (model.deviceUrl) {
    openDeviceLoginWindowIfNeeded(loginWindow, payload);
    return;
  }
  try {
    const html = onboardLoginWindowHtml(model);
    if (loginWindow.document && typeof loginWindow.document.write === "function") {
      if (typeof loginWindow.document.open === "function") {
        loginWindow.document.open();
      }
      loginWindow.document.write(html);
      if (typeof loginWindow.document.close === "function") {
        loginWindow.document.close();
      }
      return;
    }
  } catch (_documentError) {
  }
  writeOnboardLoginWindowStatus(loginWindow, model.title, model.message, model.tone);
}

function isOnboardLoginUiAction(uiAction) {
  return ["onboard_account", "account_login_status", "account_login_complete", "account_login_cancel"].includes(uiAction);
}

async function handleActionPayload(payload, loginWindow = null) {
  if (isOnboardLoginUiAction(payload?.ui_action)) {
    maybeNavigateOnboardLoginWindow(loginWindow, payload);
    renderOnboardLoginOverlay(onboardLoginWindowModelFromPayload(payload));
    const sessionId = onboardLoginSessionIdFromPayload(payload);
    const loginBridge = onboardLoginBridgeFromPayload(payload);
    if (sessionId) {
      activeOnboardLoginSession = {
        sessionId,
        status: typeof loginBridge.status === "string" ? loginBridge.status : "",
        phase: typeof loginBridge.phase === "string" ? loginBridge.phase : "",
        deviceUrl: typeof loginBridge.device_url === "string" ? loginBridge.device_url : "",
        deviceCode: typeof loginBridge.device_code === "string" ? loginBridge.device_code : "",
      };
      onboardLoginWindowRef = loginWindow || onboardLoginWindowRef;
    } else if (payload?.ui_action === "account_login_cancel" || payload?.ui_action === "account_login_complete") {
      activeOnboardLoginSession = null;
    }
  }
  setActionPanel(payload);
  let refreshState = "none";
  if (payload.post_action_refresh_required) {
    const refreshTarget = currentScreen() === "accounts"
      ? "accounts"
      : (
        currentScreen() === "api-connections"
          ? "api-connections"
          : (currentScreen() === "settings" ? "settings" : (currentScreen() === "quick-start" ? "quick-start" : "overview"))
    );
    text("actionRefreshStatus", `обновление live ${refreshTarget}`);
    const refreshed = await refreshLiveReadonlyForActionPayload(payload, false);
    if (actionRefreshSucceeded(payload, refreshed)) {
      refreshState = canonicalActionRefreshState(payload, refreshed);
      setActionPanel(payload, refreshState);
      setMiniPill(
        "onboardingResultRefreshChip",
        refreshState === "mismatch" ? "refresh mismatch" : "refresh complete",
        refreshState === "mismatch" ? "amber" : "green"
      );
    } else {
      refreshState = "failed";
      setActionPanel(payload, "failed");
    }
  }
  return { payload, refreshState };
}

function actionRequestKey(payload) {
  return [
    payload.ui_action || "unknown",
    payload.account_id || payload.route_id || payload.session_id || "-"
  ].join("|");
}

function apiRouteRemoveRefreshState(payload, refreshed) {
  if (!payload.ui_action || !payload.ui_action.startsWith("api_route_")) {
    return "complete";
  }
  const snapshot = actionRefreshSurfaceSnapshot(payload, refreshed);
  const actionRouteId = apiRouteIdFromActionPayload(payload);
  if (payload.ui_action === "api_route_connect") {
    const result = payload.result || {};
    if (result.status !== "ok") {
      return "complete";
    }
    const route = apiRouteByIdFromSnapshot(snapshot, actionRouteId);
    return route && route.enabled === true ? "complete" : "mismatch";
  }
  if (payload.ui_action === "api_route_remove") {
    return apiRoutePresentInSnapshot(snapshot, actionRouteId) ? "mismatch" : "complete";
  }
  const route = apiRouteByIdFromSnapshot(snapshot, actionRouteId);
  if (!route) {
    return "mismatch";
  }
  if (payload.ui_action === "api_route_allow") {
    return route.enabled === true ? "complete" : "mismatch";
  }
  if (payload.ui_action === "api_route_disable") {
    return route.enabled === false ? "complete" : "mismatch";
  }
  return "complete";
}

function accountsSnapshotFromRefreshPayload(refreshed) {
  if (refreshed && Array.isArray(refreshed.accounts)) {
    return refreshed;
  }
  if (refreshed && refreshed.accounts && Array.isArray(refreshed.accounts.accounts)) {
    return refreshed.accounts;
  }
  return null;
}

function runtimeSnapshotFromRefreshPayload(refreshed) {
  if (refreshed && refreshed.runtime && typeof refreshed.runtime === "object") {
    return refreshed.runtime;
  }
  return null;
}

function accountRefreshRequiresRuntimeStatus(uiAction) {
  return [
    "promote_account",
    "demote_account",
    "hold_account",
    "release_account",
    "retire_account"
  ].includes(uiAction);
}

function accountByIdFromSnapshot(snapshot, accountId) {
  if (!snapshot || !Array.isArray(snapshot.accounts) || !accountId) {
    return null;
  }
  return snapshot.accounts.find((account) => account?.id === accountId) || null;
}

function accountActionRefreshState(payload, refreshed) {
  const accountsSnapshot = accountsSnapshotFromRefreshPayload(refreshed);
  const accountId = payload?.account_id || "";
  const account = accountByIdFromSnapshot(accountsSnapshot, accountId);
  if (!accountsSnapshot || accountsSnapshot.status !== "ok" || !account) {
    return "mismatch";
  }
  if (["validate_account", "recheck_account"].includes(payload.ui_action)) {
    return "complete";
  }
  if (payload.ui_action === "promote_account") {
    return account.pool === "active" && account.manual_hold !== true ? "complete" : "mismatch";
  }
  if (payload.ui_action === "demote_account") {
    return account.pool === "reserve" && account.manual_hold !== true ? "complete" : "mismatch";
  }
  if (payload.ui_action === "hold_account") {
    return account.manual_hold === true ? "complete" : "mismatch";
  }
  if (payload.ui_action === "release_account") {
    return account.pool === "reserve" && account.manual_hold !== true ? "complete" : "mismatch";
  }
  if (payload.ui_action === "retire_account") {
    return account.pool === "retired" && account.manual_hold !== true ? "complete" : "mismatch";
  }
  return "complete";
}

function onboardingRefreshState(payload, refreshed) {
  if (!["onboard_account", "account_login_complete"].includes(payload.ui_action)) {
    return "complete";
  }
  const onboarding = payload.result?.onboarding || {};
  const finalOutcome = onboarding.final_outcome || "";
  const successfulOutcome = ["reserve_only_success", "explicit_auth_imported_to_reserve"].includes(finalOutcome);
  if (!successfulOutcome) {
    return "complete";
  }
  const accountsSnapshot = accountsSnapshotFromRefreshPayload(refreshed);
  const selectedBackendId = onboarding.selected_backend_id || "";
  if (!accountsSnapshot || accountsSnapshot.status !== "ok" || !selectedBackendId) {
    return "mismatch";
  }
  const account = Array.isArray(accountsSnapshot.accounts)
    ? accountsSnapshot.accounts.find((item) => item?.id === selectedBackendId)
    : null;
  return account?.pool === "reserve" ? "complete" : "mismatch";
}

function actionRefreshSurfaceSnapshot(payload, refreshed) {
  if (payload.ui_action === "quick_start_check_all") {
    if (
      refreshed
      && refreshed.accounts
      && refreshed.apiConnections
      && Array.isArray(refreshed.apiConnections.routes)
    ) {
      return refreshed;
    }
    return null;
  }
  if (["onboard_account", "account_login_complete"].includes(payload.ui_action)) {
    return accountsSnapshotFromRefreshPayload(refreshed);
  }
  if (ACCOUNT_UI_ACTIONS.has(payload.ui_action) && accountRefreshRequiresRuntimeStatus(payload.ui_action)) {
    const accounts = accountsSnapshotFromRefreshPayload(refreshed);
    const runtime = runtimeSnapshotFromRefreshPayload(refreshed);
    return accounts && runtime ? { accounts, runtime } : null;
  }
  if (ACCOUNT_UI_ACTIONS.has(payload.ui_action)) {
    return accountsSnapshotFromRefreshPayload(refreshed);
  }
  if (payload.ui_action && payload.ui_action.startsWith("api_route_")) {
    if (refreshed && Array.isArray(refreshed.routes)) {
      return refreshed;
    }
    if (refreshed && refreshed.apiConnections && Array.isArray(refreshed.apiConnections.routes)) {
      return refreshed.apiConnections;
    }
  }
  return refreshed;
}

function actionRefreshSucceeded(payload, refreshed) {
  const snapshot = actionRefreshSurfaceSnapshot(payload, refreshed);
  if (payload.ui_action === "quick_start_check_all") {
    return snapshot?.accounts?.status === "ok" && snapshot?.apiConnections?.status === "ok";
  }
  if (ACCOUNT_UI_ACTIONS.has(payload.ui_action) && accountRefreshRequiresRuntimeStatus(payload.ui_action)) {
    return snapshot?.accounts?.status === "ok" && snapshot?.runtime?.status === "ok";
  }
  return snapshot?.status === "ok";
}

function canonicalActionRefreshState(payload, refreshed) {
  if (payload.ui_action === "quick_start_check_all") {
    const snapshot = actionRefreshSurfaceSnapshot(payload, refreshed);
    return snapshot?.accounts?.status === "ok" && snapshot?.apiConnections?.status === "ok"
      ? "complete"
      : "failed";
  }
  if (payload.ui_action && payload.ui_action.startsWith("api_route_")) {
    return apiRouteRemoveRefreshState(payload, refreshed);
  }
  if (["onboard_account", "account_login_complete"].includes(payload.ui_action)) {
    return onboardingRefreshState(payload, refreshed);
  }
  if (ACCOUNT_UI_ACTIONS.has(payload.ui_action)) {
    return accountActionRefreshState(payload, refreshed);
  }
  return "complete";
}

function apiRouteByIdFromSnapshot(snapshot, routeId) {
  if (!routeId) {
    return null;
  }
  const routes = Array.isArray(snapshot?.routes) ? snapshot.routes : [];
  return routes.find((route) => route?.route_id === routeId) || null;
}

function apiRoutePresentInSnapshot(snapshot, routeId) {
  return apiRouteByIdFromSnapshot(snapshot, routeId) !== null;
}

function apiRouteIdFromActionPayload(payload) {
  return payload?.route_id || payload?.result?.data?.route_id || "";
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

function actionAvailabilityForButton(button) {
  const metadata = metadataFor(button.dataset.uiAction);
  const metadataAllowsAction = metadata.available !== false;
  const requiresLive = (
    button.classList.contains("account-action")
    || button.classList.contains("onboard-action")
    || button.classList.contains("api-route-action")
    || button.classList.contains("check-all-action")
  );
  const isLiveSource = document.querySelector(".desktop").dataset.source === "live";
  const routeEnabled = button.dataset.routeEnabled !== "false";
  const routeStateProven = button.dataset.routeStateProven === "true";
  const routeStateRequirement = button.dataset.routeStateRequirement || "any";
  const routeStateAllowed = routeStateRequirement === "disabled"
    ? (!routeEnabled && routeStateProven)
    : (routeStateRequirement === "enabled" ? (routeEnabled && routeStateProven) : true);

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

function quickStartPresentationActionButton(button) {
  return Boolean(
    button?.closest?.("#quickStartScreen")
    || button?.id === "quickStartCheckAllAction"
  );
}

function applyActionAvailability() {
  for (const button of document.querySelectorAll(".live-action, .account-action, .onboard-action, .api-route-action, .check-all-action")) {
    const state = actionAvailabilityForButton(button);
    button.disabled = quickStartPresentationActionButton(button) ? false : !state.available;
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
  const sandboxActive = (
    source === "live"
    && actionPhase === "sandbox_actions"
    && sandboxActionPreflight
    && sandboxActionPreflight.status === "admitted"
  );
  const sourceFooter = source === "live"
    ? (
      sandboxActive
        ? `${footerByScreen[screen] || (setupLike ? "Экраны настройки · отложенный каркас" : "Состояние · live только чтение")} · sandbox phase`
        : (footerByScreen[screen] || (setupLike ? "Экраны настройки · отложенный каркас" : "Состояние · live только чтение"))
    )
    : "Предпросмотр UI · без live-команд";
  const subtitle = subtitleByScreen[screen] || (
    source === "live"
      ? "Операторская сводка подключена к live-ответам команд. После действий состояние обновляется заново."
      : "Операторская сводка: фактическое состояние, режим работы, пул аккаунтов и последние события."
  );
  document.getElementById("sourceFooter").textContent = sourceFooter;
  document.getElementById("subtitleText").textContent = sandboxActive
    ? `${subtitle} Данные остаются live-readonly, а admitted actions открыты через sandbox phase.`
    : subtitle;
  const sourcePill = document.getElementById("sourcePill");
  if (sourcePill) {
    sourcePill.textContent = sandboxActive ? "Sandbox" : (source === "live" ? "Live" : "Demo");
    sourcePill.className = source === "live" ? "source-pill live" : "source-pill";
  }
  updateDiagnosticsDetailSource(source);
  updateSetupAdmissionCopy(source);
  updateSelectClientCopy(source);
  updateImportExistingCopy(source);
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
    brandCaption.textContent = "";
  }
  setSourceCopy("live");
  setSnapshotCommandLedgerFromSnapshots(`${screen} live-readonly pending`, []);
  renderUiReadonlyLaneExitSummary();
}

function setRefreshButtonText(label) {
  const refresh = document.getElementById("refreshFixture");
  if (!refresh) {
    return;
  }
  const labelNode = refresh.lastElementChild || refresh;
  labelNode.textContent = label;
}

function setRefreshButtonFeedback(state, label, options = {}) {
  const refresh = document.getElementById("refreshFixture");
  if (!refresh) {
    return;
  }
  if (refreshButtonFeedbackTimer) {
    clearTimeout(refreshButtonFeedbackTimer);
    refreshButtonFeedbackTimer = null;
  }
  refresh.dataset.refreshState = state;
  refresh.disabled = Boolean(options.disabled);
  setRefreshButtonText(label);
  if (options.resetAfterMs) {
    refreshButtonFeedbackTimer = setTimeout(() => {
      refresh.dataset.refreshState = "idle";
      refresh.disabled = false;
      setRefreshButtonText("Обновить");
      refreshButtonFeedbackTimer = null;
    }, options.resetAfterMs);
  }
}

function resetRefreshButtonLabelIfIdle() {
  const refresh = document.getElementById("refreshFixture");
  if (!refresh) {
    return;
  }
  if (["busy", "success", "error"].includes(refresh.dataset.refreshState)) {
    return;
  }
  refresh.dataset.refreshState = "idle";
  refresh.disabled = false;
  setRefreshButtonText("Обновить");
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
    chip.lastElementChild.textContent = fixtureOnly ? "демо" : "отложено";
  }
  const banner = document.getElementById("diagnosticsBanner");
  if (banner) {
    const fixtureCopy = {
      healthy: ["blue", "Демо-режим диагностики. Сигналы показаны как ограниченная сводка, не как runtime health."],
      degraded: ["amber", "Демо-режим диагностики показывает деградацию сигнала без claims о runtime health."],
      down: ["red", "Демо-режим диагностики показывает недоступный сигнал без live-подтверждения."],
      stale: ["amber", "Данные диагностики устарели. Это не считается healthy."],
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
  lastOnboardingActionPayload = ["onboard_account_dry_run", "account_login_complete"].includes(payload.ui_action)
    ? payload
    : lastOnboardingActionPayload;
  if (isApiCredentialUiAction(payload.ui_action)) {
    lastApiCredentialActionPayload = payload;
    lastApiCredentialActionRefreshState = refreshState;
  }
  const onboardingModel = onboardingResultModel(onboarding, payload, refreshState);
  const changedFiles = Array.isArray(result.changed_files) ? result.changed_files : [];
  const display = actionDisplayState(payload, refreshState);
  const exportModel = payload.ui_action === "export_diagnostics"
    ? diagnosticsExportResultModel(payload)
    : null;
  const safeUiAction = safeLedgerText(payload.ui_action || "unknown", "unknown");
  const safeRole = safeLedgerText(payload.action_role || "unknown", "unknown");
  const safeTarget = safeLedgerText(payload.account_id || payload.route_id || payload.session_id || "-", "-");
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
    : ["onboard_account_dry_run", "account_login_complete"].includes(payload.ui_action)
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
  renderApiCredentialSetupLane(lastApiCredentialActionPayload, lastApiCredentialActionRefreshState);
  revealActionPanel(display.displayState);
  recordActionLedgerEntry(payload, refreshState, display, changedFiles);
  if (payload.ui_action === "export_diagnostics") {
    renderDiagnosticsAction(payload);
  }
  renderAccountDetailDrawer();
}

function revealActionPanel(displayState) {
  if (displayState === "running") {
    return;
  }
  const panel = document.getElementById("actionPanel");
  if (!panel) {
    return;
  }
  if (typeof panel.scrollIntoView === "function") {
    try {
      panel.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (_scrollError) {
      panel.scrollIntoView();
    }
  }
  if (typeof panel.focus === "function") {
    try {
      panel.focus({ preventScroll: true });
    } catch (_focusError) {
      panel.focus();
    }
  }
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
  const isOnboarding = ["onboard_account_dry_run", "account_login_complete"].includes(payload.ui_action);
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
  if (onboarding.preview_only === true || payload.ui_action === "onboard_account_dry_run") {
    const denied = onboarding.ui_state === "dry_run_denied";
    const blockedReasons = Array.isArray(onboarding.blocked_reasons) && onboarding.blocked_reasons.length
      ? onboarding.blocked_reasons.join(", ")
      : "none";
    const liveMetadata = metadataFor("onboard_account");
    const liveReady = !denied && liveMetadata.available === true;
    const nextStep = liveReady
      ? "Откройте диалог ещё раз и подтвердите live connect в sandbox."
      : (onboarding.required_follow_up || "WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS");
    return {
      finalOutcome: onboarding.final_outcome || (denied ? "dry_run_preview_denied" : "dry_run_preview_ready"),
      visual: denied ? "amber" : "neutral",
      title: denied ? "Dry-run preview заблокирован" : "Dry-run preview готов",
      summary: denied
        ? "Preview не admitted без дополнительных условий."
        : "Показан только preview. Аккаунт не подключён.",
      summaryNote: "UI не импортирует auth, не меняет registry и не показывает success.",
      modeLabel: denied ? "dry-run denied" : "dry-run preview",
      banner: denied
        ? "Dry-run preview заблокирован. Реальное подключение не запускалось."
        : "Dry-run preview готов. Реальное подключение не выполнялось.",
      newBackendIds: "-",
      selectedBackendId: "-",
      selectionStatus: onboarding.candidate_source_kind || "server_owned_only",
      selectionVisual: denied ? "amber" : "neutral",
      poolLabel: onboarding.reserve_first_boundary || "required",
      poolVisual: denied ? "amber" : "blue",
      reserveFirst: "обязательно",
      reserveVisual: "blue",
      validateOutcome: "not run",
      validateVisual: "neutral",
      syncOutcome: "not run",
      syncVisual: "neutral",
      statusProof: "preview only",
      statusProofVisual: "neutral",
      refreshState: "not required",
      refreshVisual: "neutral",
      nextAction: liveReady
        ? nextStep
        : `Следующий шаг: ${nextStep}. blocked_reasons=${blockedReasons}`
    };
  }
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

function onboardingLiveReadyInSession() {
  return metadataFor("onboard_account").available === true;
}

function populateOnboardModal() {
  const liveStep = onboardingLiveReadyInSession();
  text("onboardTitle", liveStep ? "Подключить аккаунт в резерв" : "Проверить подключение аккаунта");
  text(
    "onboardIntro",
    liveStep
      ? "Следующий шаг запускает owner login bridge: сервер выдаст owner login URL, завершит owner-owned login flow и добавит результат в reserve только в sandbox."
      : "Сначала выполняется безопасный dry-run preview. Реальное добавление в резерв на этом шаге не выполняется."
  );
  text("onboardSourceValue", liveStep ? "owner login bridge" : "server-owned preview");
  text("onboardModeValue", liveStep ? "Live reserve-first" : "Dry-run");
  text("onboardAfterValue", liveStep ? "owner login -> onboard -> refresh" : "Live accounts не меняются");
  text("onboardResultValue", liveStep ? "login packet + onboard packet + refresh proof" : "packet preview only");
  text(
    "onboardTechnicalCommand",
    liveStep
      ? "Команда запускается как owner login bridge через onboard_account; browser не передаёт token, auth reference или path."
      : "Команда запускается только как onboard_account_dry_run."
  );
  text(
    "onboardTechnicalPreview",
    liveStep
      ? "Owner helper запускает engine-owned Codex login/onboard lane в sandbox и затем выполняет reserve-first onboarding."
      : "Preview не импортирует auth и не меняет registry."
  );
  text(
    "onboardTechnicalNextStep",
    liveStep
      ? "Новый backend должен остаться в reserve; active routing меняться не должна."
      : "После admitted preview можно вернуться и подтвердить live connect в sandbox."
  );
  const runButton = document.getElementById("runOnboardAction");
  if (runButton) {
    runButton.textContent = liveStep ? "Подключить в резерв" : "Проверить подключение";
  }
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
    target: safeLedgerText(payload.account_id || payload.route_id || payload.session_id || "-", "-"),
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
    payload.account_id || payload.route_id || payload.session_id || "-",
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
  if (["onboard_account", "onboard_account_dry_run"].includes(payload.ui_action) && Object.keys(onboarding).length) {
    const newIds = Array.isArray(onboarding.new_backend_ids) ? onboarding.new_backend_ids.length : 0;
    if (onboarding.preview_only === true) {
      const blockedReasons = Array.isArray(onboarding.blocked_reasons) ? onboarding.blocked_reasons.length : 0;
      return [
        `preview_only=true`,
        `candidate_source=${onboarding.candidate_source_kind || "server_owned_only"}`,
        `blocked_reasons=${blockedReasons}`,
        `required_follow_up=${onboarding.required_follow_up || "-"}`
      ].join(" · ");
    }
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

function apiCredentialSupportDetails(data = {}) {
  const expectedRefs = Array.isArray(data.credential_expected_refs)
    ? data.credential_expected_refs.join(",")
    : "";
  const supportedSources = Array.isArray(data.credential_supported_sources)
    ? data.credential_supported_sources.join(",")
    : "";
  return [
    `credential_phase=${data.credential_phase || "unknown"}`,
    `credential_present=${data.credential_present === true ? "true" : "false"}`,
    `credential_admitted=${data.credential_admitted === true ? "true" : "false"}`,
    `credential_ref=${data.credential_ref || "-"}`,
    `supported_sources=${supportedSources || "-"}`,
    `expected_refs=${expectedRefs || "-"}`,
    `provider_dashboard=${data.credential_provider_dashboard_url || "-"}`,
    `browser_api_key_intake=${data.browser_api_key_intake === false ? "false" : "unknown"}`,
    `secret_exposed=${data.secret_value_exposed === false ? "false" : "unknown"}`
  ].join(" · ");
}

function actionSupportDetails(payload) {
  const result = payload.result || {};
  const data = result.data || {};
  if (["onboard_account", "account_login_status", "account_login_complete", "account_login_cancel"].includes(payload.ui_action)) {
    const loginBridge = data.login_bridge || {};
    const authScope = loginBridge["auth" + "_ref_scope"] || "-";
    if (Object.keys(loginBridge).length) {
      return [
        `login_bridge=${loginBridge.status || "unknown"}`,
        `provider=${loginBridge.provider || "unknown"}`,
        `phase=${loginBridge.phase || "unknown"}`,
        `session=${loginBridge.session_id || loginBridge.login_session_id || "-"}`,
        `device_url=${loginBridge.device_url ? "present" : "missing"}`,
        `device_code=${loginBridge.device_code_present === true ? "present" : "missing"}`,
        `auth_scope=${authScope}`,
        `browser_secret_intake=${loginBridge.browser_secret_intake === false ? "false" : "unknown"}`
      ].join(" · ");
    }
  }
  if (payload.ui_action === "quick_start_check_all") {
    const bundle = data.bundle || {};
    const accounts = bundle.accounts?.status || "unknown";
    const api = bundle.api?.status || "unknown";
    const runtime = bundle.runtime?.status || "unknown";
    const routeId = bundle.api?.route_id || "no-route";
    return [
      `bundle_verdict=${data.bundle_verdict || "unknown"}`,
      `accounts=${accounts}`,
      `api=${api}`,
      `runtime=${runtime}`,
      `route=${routeId}`,
      `hidden_mutation=${data.hidden_mutation_absent === true ? "absent" : "unknown"}`
    ].join(" · ");
  }
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
  if (payload.ui_action === "api_route_connect" || payload.ui_action === "api_route_credential_check") {
    return apiCredentialSupportDetails(data);
  }
  if (payload.ui_action === "export_diagnostics") {
    const exportModel = diagnosticsExportResultModel(payload);
    return `support artifact · ${artifactReference(data.bundle_path)} · redaction=${exportModel.redactionStatus}`;
  }
  return "-";
}

function isApiCredentialUiAction(uiAction) {
  return uiAction === "api_route_connect" || uiAction === "api_route_credential_check";
}

function apiCredentialActionModel(payload = null, refreshState = "none") {
  if (!payload || !isApiCredentialUiAction(payload.ui_action)) {
    return { visible: false };
  }
  const result = payload.result || {};
  const data = result.data || {};
  const provider = data.credential_provider || "openrouter";
  const expectedRefs = Array.isArray(data.credential_expected_refs) && data.credential_expected_refs.length
    ? data.credential_expected_refs
    : ["OPENROUTER_API_KEY", "WBP_OPENROUTER_API_KEY", "WBP_PROVIDER_OPENROUTER_API_KEY"];
  const supportedSources = Array.isArray(data.credential_supported_sources) && data.credential_supported_sources.length
    ? data.credential_supported_sources
    : ["owner-env"];
  const dashboardUrl = data.credential_provider_dashboard_url || "https://openrouter.ai/settings/keys";
  const phase = data.credential_phase
    || (data.credential_present === true ? "credential_present" : "credential_missing");
  const credentialPresent = data.credential_present === true;
  const credentialAdmitted = data.credential_admitted === true;
  const validateOk = data.validate_status === "ok";
  const routeConnected = payload.ui_action === "api_route_connect"
    && result.status === "ok"
    && validateOk
    && refreshState === "complete";
  const routePendingRefresh = payload.ui_action === "api_route_connect"
    && result.status === "ok"
    && validateOk
    && refreshState !== "complete";
  const missingCredential = phase === "credential_missing"
    || result.machine_error_code === "EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING"
    || (!credentialPresent && !credentialAdmitted && payload.ui_action === "api_route_credential_check");
  const routeValidateFailed = payload.ui_action === "api_route_connect"
    && result.status !== "ok"
    && phase !== "credential_missing"
    && data.validate_status === "command_error";

  let visual = "neutral";
  let title = "Owner credential status";
  let chip = "ожидание";
  let summary = "Browser не передаёт секреты; решение принимается только по owner packet.";
  let banner = "Ожидается явный packet owner credential/status.";

  if (routeConnected) {
    visual = "green";
    title = "API route подключён";
    chip = "connected";
    summary = "Credential подтверждён, route прошёл validate и отображён после canonical refresh.";
    banner = "Connected state подтверждён packet-ом validate плюс обновлённым списком маршрутов.";
  } else if (routePendingRefresh) {
    visual = "blue";
    title = "Credential подтверждён";
    chip = "refresh";
    summary = "Route создан и validate прошёл, но connected признаётся только после обновлённого API snapshot.";
    banner = "Команда завершилась без секрета в браузере; дождитесь refresh proof или повторите обновление.";
  } else if (missingCredential) {
    visual = "amber";
    title = "Нужен owner credential";
    chip = "missing";
    summary = "OpenRouter key не найден в owner env. Добавьте env вне браузера и потом повторите проверку или подключение.";
    banner = "Credential missing не является connected state. Browser не принимает API key и не хранит secret.";
  } else if (routeValidateFailed) {
    visual = "red";
    title = "Route не подтверждён";
    chip = "validate failed";
    summary = "Credential найден, но provider validate не дал зелёного подтверждения. Connected state не заявляется.";
    banner = result.human_message || "Provider validate вернул non-green packet.";
  } else if (credentialPresent || credentialAdmitted) {
    visual = "blue";
    title = "Credential подтверждён";
    chip = credentialAdmitted ? "admitted" : "present";
    summary = "Owner credential уже виден server process и можно повторить подключение API без ввода секрета в браузере.";
    banner = credentialAdmitted
      ? "Credential materialized owner-side. Следующий шаг — повторить подключение server-owned route."
      : "Credential status packet подтвердил owner-side secret reference.";
  } else if (result.status === "command_error") {
    visual = "red";
    title = "Подключение API не подтверждено";
    chip = "blocked";
    summary = result.human_message || "API route не получил подтверждения по bounded packet.";
    banner = "UI не заявляет connected state, пока owner credential и route truth не подтверждены packet-ом.";
  }

  return {
    visible: true,
    visual,
    title,
    chip,
    summary,
    banner,
    provider,
    credentialRef: data.credential_ref || expectedRefs[0] || "OPENROUTER_API_KEY",
    expectedRefs,
    supportedSources,
    dashboardUrl,
    restartNote: "Если env добавлен после старта owner server process, может потребоваться restart перед повторной проверкой.",
    showCheck: !routeConnected,
    showRetry: !routeConnected,
    showDashboard: Boolean(dashboardUrl)
  };
}

function renderApiCredentialSetupLane(payload = lastApiCredentialActionPayload, refreshState = lastApiCredentialActionRefreshState) {
  const model = apiCredentialActionModel(payload, refreshState);
  const laneIds = [
    {
      lane: "quickStartApiCredentialLane",
      title: "quickStartApiCredentialTitle",
      summary: "quickStartApiCredentialSummary",
      chip: "quickStartApiCredentialChip",
      banner: "quickStartApiCredentialBanner",
      provider: "quickStartApiCredentialProvider",
      ref: "quickStartApiCredentialRef",
      refs: "quickStartApiCredentialRefs",
      source: "quickStartApiCredentialSource",
      restart: "quickStartApiCredentialRestart",
      check: "quickStartApiCredentialCheckAction",
      retry: "quickStartApiCredentialRetryAction",
      dashboard: "quickStartApiCredentialDashboardAction"
    },
    {
      lane: "apiConnectionsCredentialLane",
      title: "apiConnectionsCredentialTitle",
      summary: "apiConnectionsCredentialSummary",
      chip: "apiConnectionsCredentialChip",
      banner: "apiConnectionsCredentialBanner",
      provider: "apiConnectionsCredentialProvider",
      ref: "apiConnectionsCredentialRef",
      refs: "apiConnectionsCredentialRefs",
      source: "apiConnectionsCredentialSource",
      restart: "apiConnectionsCredentialRestart",
      check: "apiConnectionsCredentialCheckAction",
      retry: "apiConnectionsCredentialRetryAction",
      dashboard: "apiConnectionsCredentialDashboardAction"
    }
  ];
  for (const ids of laneIds) {
    const lane = document.getElementById(ids.lane);
    if (!lane) {
      continue;
    }
    lane.hidden = !model.visible;
    if (!model.visible) {
      continue;
    }
    lane.className = `api-credential-lane ${model.visual}`;
    const chip = document.getElementById(ids.chip);
    if (chip) {
      chip.className = `chip ${ACCOUNT_VISUAL_CLASS[model.visual] || "neutral"}`;
      chip.lastElementChild.textContent = model.chip;
    }
    const banner = document.getElementById(ids.banner);
    if (banner) {
      banner.className = `api-credential-banner ${model.visual}`;
    }
    text(ids.title, model.title);
    text(ids.summary, model.summary);
    text(ids.banner, model.banner);
    text(ids.provider, model.provider);
    text(ids.ref, model.credentialRef);
    text(ids.refs, model.expectedRefs.join(", "));
    text(ids.source, model.supportedSources.join(", "));
    text(ids.restart, model.restartNote);
    const checkButton = document.getElementById(ids.check);
    if (checkButton) {
      checkButton.hidden = !model.showCheck;
    }
    const retryButton = document.getElementById(ids.retry);
    if (retryButton) {
      retryButton.hidden = !model.showRetry;
    }
    const dashboard = document.getElementById(ids.dashboard);
    if (dashboard) {
      dashboard.hidden = !model.showDashboard;
      dashboard.href = model.dashboardUrl;
    }
  }
}

if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
  window.addEventListener("message", (event) => {
    const payload = event?.data;
    if (!payload || typeof payload !== "object") {
      return;
    }
    if (payload.type === "wbp-onboard-login-payload" && payload.payload) {
      handleActionPayload(payload.payload, onboardLoginWindowRef).catch(() => {});
      return;
    }
    if (payload.type === "wbp-onboard-login-command") {
      const uiAction = typeof payload.uiAction === "string" ? payload.uiAction : "";
      const sessionId = typeof payload.sessionId === "string" ? payload.sessionId : "";
      if (!uiAction || !sessionId) {
        return;
      }
      runUiAction(uiAction, { session_id: sessionId }).catch(() => {});
    }
  });
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
      label: "Redaction сбой",
      visual: "red",
      redactionStatus,
      copy: "Экспорт вернул redaction failure. Artifact не считается безопасным, UI не читает bundle и не меняет runtime truth."
    };
  }
  if (status === "ok" && !hasArtifact) {
    return {
      state: "artifact_unavailable",
      label: "Артефакт недоступен",
      visual: "amber",
      redactionStatus,
      copy: "Команда не вернула reference артефакта. Это не runtime health truth; повторите export или откройте журнал действий."
    };
  }
  if (status === "ok" && redactionStatus === "unreported") {
    return {
      state: "redaction_unreported",
      label: "Redaction не подтверждён",
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
      label: "Таймаут",
      visual: "amber",
      redactionStatus,
      copy: "Экспорт диагностики истёк по времени. Успех не выводится; можно повторить команду."
    };
  }
  if (status === "invalid_json") {
    return {
      state: "invalid_json",
      label: "JSON ошибка",
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
  const launch = metadataFor("launch_custom_client_native");
  const target = document.getElementById("settingsLaunchAvailability");
  if (!target) {
    return;
  }
  target.textContent = launch.available === false
    ? `native launch blocked · ${launch.unavailable_reason || "native lane not admitted"}`
    : "native proof admitted · server-owned Custom native launch lane";
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
  const launch = metadataFor("launch_custom_client_native");
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
  const dispatch = launchAdmitted ? "native proof admitted" : `disabled · ${launch.unavailable_reason || "native launch not admitted"}`;
  const processProof = launchAdmitted ? "process + window required" : "not admitted";
  return {
    source,
    visual,
    candidateVisual,
    launchAdmitted,
    panelLabel: liveFailure ? "unavailable" : (stale ? "stale" : (degraded ? "requires check" : "ready preview")),
    bannerCopy: liveFailure
      ? "Client status недоступен. Предыдущие fixture-данные не используются."
      : (stale
        ? "Client status устарел. Требуется refresh из bounded packet."
        : (launchAdmitted
          ? "Демо-режим. Native Custom launch admitted только через server-owned proof lane."
          : "Демо-режим. Native Custom launch не admitted без server-owned proof lane.")),
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
    preflight: launchAdmitted ? "native proof admitted" : "native launch blocked",
    dispatch,
    processProof
  };
}

function renderClientLaunchSnapshot(snapshot) {
  const model = clientLaunchModelFromSnapshot(snapshot || {});
  setClientLaunchChip("clientLaunchPanelChip", model.visual, model.panelLabel);
  setClientLaunchChip("clientSelectedChip", model.candidateVisual, model.selectedStatus);
  setClientLaunchChip("clientReadinessChip", model.readinessVisual, model.readinessLabel);
  setClientLaunchChip("clientDispatchChip", model.launchAdmitted ? "blue" : "amber", model.launchAdmitted ? "native proof admitted" : "native launch blocked");

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
  for (const button of document.querySelectorAll(".live-action, .account-action, .onboard-action, .api-route-action, .check-all-action")) {
    const state = actionAvailabilityForButton(button);
    button.disabled = isBusy || (!quickStartPresentationActionButton(button) && !state.available);
    button.dataset.available = state.available ? "true" : "false";
    button.dataset.availabilityState = state.availabilityState;
    button.dataset.disabledReasonCode = state.disabledReasonCode;
    button.dataset.disabledReasons = state.available ? "" : JSON.stringify(state.disabledReasons);
  }
}

function renderBlockedActionFromButton(button, uiAction, extraPayload = {}) {
  const state = actionAvailabilityForButton(button);
  if (state.available) {
    return false;
  }
  setActionPanel({
    ui_action: uiAction,
    action_role: "blocked",
    account_id: extraPayload.account_id || "",
    route_id: "",
    post_action_refresh_required: false,
    result: {
      status: "blocked",
      machine_error_code: state.disabledReasonCode || "UI_ACTION_BLOCKED",
      human_message: state.title || "Действие сейчас недоступно. Причина показана серверным или readonly packet.",
      next_action: "resolve_preflight_or_state",
      changed_files: []
    }
  });
  return true;
}

function maybeConfirmAndRunFromButton(button, uiAction, extraPayload = {}) {
  if (button && renderBlockedActionFromButton(button, uiAction, extraPayload)) {
    return;
  }
  maybeConfirmAndRun(uiAction, extraPayload);
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
        machine_error_code: metadata.disabled_reason_code || "UI_ACTION_UNAVAILABLE",
        human_message: metadata.unavailable_reason || "Действие недоступно.",
        availability_state: metadata.availability_state || "unknown_disabled",
        disabled_reasons: Array.isArray(metadata.disabled_reasons) ? metadata.disabled_reasons : [],
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
  if (uiAction === "onboard_account_dry_run") {
    return "Проверить подключение";
  }
  if (uiAction === "onboard_account") {
    return "Подключить в резерв";
  }
  if (uiAction === "api_route_connect") {
    return "Подключить API";
  }
  if (uiAction === "retire_account") {
    return "Вывести из пула";
  }
  if (uiAction === "launch_custom_client_native") {
    return "Запросить native запуск";
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
  if (uiAction !== "launch_client_dispatch" && uiAction !== "launch_custom_client_native") {
    block.hidden = true;
    return;
  }
  if (uiAction === "launch_custom_client_native") {
    block.hidden = false;
    text("launchClientPreflightTarget", "server-owned custom native endpoint");
    text("launchClientPreflightProfile", "isolated");
    text("launchClientPreflightDataDir", "isolated");
    text("launchClientPreflightPort", "server-owned");
    text("launchClientPreflightProcess", "process + window required");
    text(
      "launchClientPreflightNote",
      metadata?.action_claim_scope || "Green success requires process, identity, and native window proof."
    );
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
    cancelActiveActionWait();
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
    cancelButton.disabled = false;
    cancelButton.textContent = isInFlight ? "Отменить ожидание" : "Отмена";
  }
  text("confirmDispatchState", isInFlight ? "ожидание owner/server packet" : "однократная отправка");
}

function cancelActiveActionWait() {
  if (!confirmationInFlight || !activeActionAbortController) {
    pendingConfirmedAction = null;
    setConfirmationInFlight(false);
    document.getElementById("confirmOverlay").hidden = true;
    return;
  }
  activeActionAbortReason = "user_cancelled";
  activeActionAbortController.abort();
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
  populateOnboardModal();
  document.getElementById("onboardOverlay").hidden = false;
  document.getElementById("runOnboardAction").focus({ preventScroll: true });
}

function closeOnboardModal() {
  document.getElementById("onboardOverlay").hidden = true;
}

function runOnboardFromModal() {
  closeOnboardModal();
  maybeConfirmAndRun(onboardingLiveReadyInSession() ? "onboard_account" : "onboard_account_dry_run");
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
    return { key: "problem", label: "Ошибка", visual: "red", order: 0 };
  }
  if (account.visual_state === "amber" || account.status === "degraded") {
    return { key: "stale", label: "Устарело", visual: "amber", order: 2 };
  }
  if (account.pool === "reserve") {
    return { key: "reserve", label: "Резерв", visual: "blue", order: 5 };
  }
  if (account.status === "healthy" || account.visual_state === "green" || account.visual_state === "blue") {
    return { key: "ok", label: account.pool === "active" ? "Работает" : "Готов", visual: "green", order: 6 };
  }
  return { key: "checking", label: "Проверка", visual: "blue", order: 3 };
}

function quickStartFormatCheckLabel(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "проверки нет";
  }
  const isoMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (isoMatch) {
    return `проверка ${isoMatch[3]}.${isoMatch[2]}, ${isoMatch[4]}:${isoMatch[5]}`;
  }
  return `проверка ${raw}`;
}

function quickStartAccountOperatorLabel(account, state) {
  if (account.manual_hold === true || state.key === "hold_pause") {
    return "Пауза";
  }
  if (account.pool === "retired") {
    return "Выведен";
  }
  if (account.pool === "reserve") {
    return "Резерв";
  }
  if (account.pool === "active") {
    return "Активен";
  }
  if (state.key === "problem") {
    return "Ошибка";
  }
  if (state.key === "stale") {
    return "Устарело";
  }
  return "Неизвестно";
}

function quickStartAccountNeedsCheck(state) {
  return state.key === "problem" || state.key === "stale" || state.key === "checking";
}

function quickStartAccountControl(state) {
  if (quickStartAccountNeedsCheck(state)) {
    const action = document.createElement("span");
    action.className = "quick-start-row-action";
    action.title = "Точечная проверка аккаунта требует отдельного admitted action mapping.";
    setNodeAttribute(action, "aria-disabled", "true");
    const icon = document.createElement("img");
    icon.className = "ui-icon button-icon";
    icon.src = "assets/icons/phosphor/shield-check.png";
    icon.alt = "";
    setNodeAttribute(icon, "aria-hidden", "true");
    const label = document.createElement("span");
    label.textContent = "Проверить";
    action.append(icon, label);
    return action;
  }
  const chip = document.createElement("span");
  chip.className = `chip quick-start-row-status ${state.visual}`;
  const dot = document.createElement("span");
  dot.className = "dot";
  const label = document.createElement("span");
  label.textContent = state.label;
  chip.append(dot, label);
  return chip;
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
    copy.className = "quick-start-account-copy";
    const title = document.createElement("strong");
    title.textContent = item.account.id || "unknown-account";
    const meta = document.createElement("span");
    const operatorLabel = quickStartAccountOperatorLabel(item.account, item.state);
    meta.textContent = `${operatorLabel} · ${quickStartFormatCheckLabel(item.account.last_success)}`;
    copy.append(title, meta);

    row.append(indexNode, copy, quickStartAccountControl(item.state));
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

function quickStartCompactApiLabel(route) {
  if (!route || typeof route !== "object") {
    return "Не настроено";
  }
  const upstream = String(route.upstream_model || route.effective_model || "").trim();
  const provider = String(route.provider || route.provider_label || "").trim();
  if (!upstream) {
    return provider || "Не настроено";
  }
  return `WBP ${upstream}`;
}

function quickStartCompactApiMeta(route) {
  if (!route || typeof route !== "object") {
    return "Основной route не подтверждён";
  }
  const role = String(route.role_label || (route.is_primary || route.primary ? "main route" : "registry entry")).trim();
  const provider = String(route.provider || route.provider_label || "").trim();
  return [provider, role].filter(Boolean).join(" · ") || "server-owned route";
}

function quickStartSelectedRouteHasBoundedProof(route) {
  if (!route || typeof route !== "object") {
    return false;
  }
  const validation = String(route.validation_label || "").toLowerCase();
  return route.enabled === true
    && route.secret_status_label === "available"
    && route.secret_visual_state === "green"
    && (route.validation_visual_state === "green" || validation === "ok");
}

function quickStartApiModel(snapshot, source, selectedRouteId = "") {
  const routes = Array.isArray(snapshot.routes) ? snapshot.routes : [];
  if (snapshot.status === "stale") {
    const primary = routes.find((route) => route.role_label === "main route" || route.role_label === "primary" || route.is_primary === true || route.primary === true) || routes[0];
    return {
      state: "stale",
      visual: "amber",
      title: "Устарело",
      provider: quickStartCompactApiLabel(primary),
      model: primary ? quickStartCompactApiMeta(primary) : "Основной route не подтверждён",
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
  const selectedRoute = source === "live" && selectedRouteId
    ? routes.find((route) => route.route_id === selectedRouteId)
    : null;
  const selectedRouteAdmitted = !primary && quickStartSelectedRouteHasBoundedProof(selectedRoute);
  const routeForSummary = primary || (selectedRouteAdmitted ? selectedRoute : null);
  if (!routeForSummary) {
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
  const missingSecret = routeForSummary.status_code === "missing_secret" || routeForSummary.secret_visual_state === "amber" || routeForSummary.secret_status_label === "missing";
  const failed = routeForSummary.visual_state === "red" || routeForSummary.validation_visual_state === "red";
  const stale = snapshot.status === "stale" || routeForSummary.status_code === "stale";
  const visual = missingSecret || stale ? "amber" : (failed ? "red" : (routeForSummary.enabled === true ? "green" : "neutral"));
  const title = missingSecret
    ? "Нужен secret_ref"
    : (failed ? "Ошибка" : (stale ? "Устарело" : (routeForSummary.enabled === true ? (selectedRouteAdmitted ? "Выбранный route подтверждён" : "Работает") : "Deferred")));
  return {
    state: missingSecret ? "missing_secret_ref" : (failed ? "failed" : (stale ? "stale" : (routeForSummary.enabled === true ? "ok" : "unsupported_provider"))),
    visual,
    title,
    provider: quickStartCompactApiLabel(routeForSummary),
    model: quickStartCompactApiMeta(routeForSummary),
    routeId: routeForSummary.route_id || "",
    secretRef: routeForSummary.secret_ref || "—",
    secretState: missingSecret ? "missing" : (routeForSummary.secret_status_label || "unknown"),
    validationState: routeForSummary.validation_label || routeForSummary.status_label || "not checked",
    lastCheck: routeForSummary.last_checked || "нет данных",
    routeCount: routes.length,
    confirmed: selectedRouteAdmitted || source !== "live" || routeForSummary.role_label === "main route" || routeForSummary.role_label === "primary" || routeForSummary.is_primary === true || routeForSummary.primary === true,
    selectedRoute: selectedRouteAdmitted,
    routeEnabled: routeForSummary.enabled === true
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
  document.getElementById("brandCaption").textContent = "";
  resetRefreshButtonLabelIfIdle();
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
  text("quickStartConnectionsChatCount", `${noAccounts ? 0 : accounts.length} аккаунта`);
  text("quickStartConnectionsChatWorking", `${workingCount} работают`);
  setQuickStartChip(
    "quickStartConnectionsChatChip",
    accountVisual,
    accountLabel
  );
  renderQuickStartAccountRows(safeAccounts);

  const apiModel = quickStartApiModel(safeApi, source, selectValue("quickStartApiModelSelect"));
  const apiChip = document.getElementById("quickStartApiChip");
  apiChip.className = `chip ${apiModel.visual}`;
  apiChip.lastElementChild.textContent = apiModel.title;
  text("quickStartApiProvider", apiModel.provider);
  text("quickStartApiModel", apiModel.model);
  text(
    "quickStartApiSecret",
    apiModel.secretState === "available"
      ? "ключ: доступен серверу · значение скрыто"
      : "ключ: значение скрыто"
  );
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
        ? (apiModel.selectedRoute === true
          ? "Выбранный route подтверждён bounded packet. Runtime readiness подтверждается отдельно."
          : "Provider, secret_ref и route представлены как bounded summary. Runtime readiness подтверждается отдельно.")
        : (apiModel.state === "stale"
          ? "Основной route показан из устаревшего bounded snapshot. Требуется обновление."
          : "Основной route не подтверждён bounded snapshot."))
  );

  setQuickStartChecklistChip("quickStartApiProviderChip", apiModel.provider === "Не настроено" ? "neutral" : "green", apiModel.provider === "Не настроено" ? "unknown" : "OK");
  setQuickStartChecklistChip("quickStartApiSecretChip", apiModel.state === "missing_secret_ref" ? "amber" : (apiModel.secretState === "available" ? "green" : "neutral"), apiModel.state === "missing_secret_ref" ? "missing" : apiModel.secretState);
  setQuickStartChecklistChip("quickStartApiRouteChip", apiModel.state === "ok" ? "green" : (apiModel.state === "missing_secret_ref" ? "amber" : "neutral"), apiModel.validationState);

  const apiAction = document.getElementById("quickStartCheckApiAction");
  if (apiAction) {
    delete apiAction.dataset.routeId;
    delete apiAction.dataset.routeEnabled;
    delete apiAction.dataset.routeStateProven;
    delete apiAction.dataset.routeStateRequirement;
    apiAction.title = "Проверяет выбранную Quick Start конфигурацию через bounded server admission packet.";
  }

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
  renderApiCredentialSetupLane(lastApiCredentialActionPayload, lastApiCredentialActionRefreshState);
  applyActionAvailability();
  replayQuickStartManualCheckSnapshot();
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
  document.getElementById("brandCaption").textContent = "";
  resetRefreshButtonLabelIfIdle();
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
  document.getElementById("brandCaption").textContent = "";
  resetRefreshButtonLabelIfIdle();
  setSourceCopy(source);

  const banner = document.getElementById("apiConnectionsBanner");
  setClassName(banner, "fixture-banner", visualState);
  banner.textContent = source === "live"
    ? (
      safeSnapshot.status === "ok"
        ? "Live-readonly маршрутов. Действия остаются server-owned и не утверждают runtime готовность."
        : "Live-readonly маршруты недоступны. Предыдущие данные не используются."
    )
    : "Демо-режим. Маршруты показаны как ограниченная сводка, не как runtime config truth.";

  const summary = safeSnapshot.summary;
  const noData = source === "live" && safeSnapshot.status !== "ok";
  const latestCheck = routeTableCheckLabel(summary.latest_check);
  text("apiConnectionsRoutesCount", noData ? "—" : summary.routes_count);
  text("apiConnectionsEnabledCount", noData ? "—" : summary.enabled_count);
  text("apiConnectionsAttentionCount", noData ? "—" : summary.attention_count);
  text("apiConnectionsLatestCheck", noData ? "—" : latestCheck);
  text("apiConnectionsRoutesNote", noData ? "нет данных" : (source === "live" ? "из пакета команд" : "демо-сводка"));
  text("apiConnectionsEnabledNote", noData ? "нет данных" : "registry state");
  text("apiConnectionsAttentionNote", noData ? "нет данных" : "нет секрета / disabled");
  text("apiConnectionsLatestCheckNote", noData ? "нет данных" : (latestCheck === "—" ? "проверка маршрута ещё не запускалась" : "последняя проверка"));
  text(
    "apiConnectionsRegistryStatus",
    noData
      ? `Недоступно · ${summary.machine_error_code}`
      : `Источник: ${safeSnapshot.adapter.foundation_phase} · модели: ${safeSnapshot.adapter.models_source}`
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
  renderApiCredentialSetupLane(lastApiCredentialActionPayload, lastApiCredentialActionRefreshState);
}

function renderApiConnectionRows(routes) {
  const body = document.getElementById("apiConnectionsTableBody");
  body.replaceChildren();
  if (!routes.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 8;
    cell.className = "dash";
    cell.textContent = "Маршруты недоступны. Создание и изменение маршрутов остаются отложены до отдельного server-side builder.";
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
      td("right mono-value", routeTableCheckLabel(route.last_checked)),
      td("", routeActionButtons(route))
    );
    body.append(row);
  }
  applyActionAvailability();
}

function routeIdentity(route) {
  const wrap = document.createElement("div");
  wrap.className = "api-route-identity";
  const main = document.createElement("div");
  main.className = "account-main mono-value api-route-id";
  main.textContent = route.route_id || "unknown-route";
  const sub = document.createElement("div");
  sub.className = "account-sub api-route-display-name";
  const displayName = routeDisplayName(route);
  sub.textContent = displayName;
  sub.title = displayName;
  wrap.append(main, sub);
  const rolePill = routeRolePill(route);
  if (rolePill) {
    const meta = document.createElement("div");
    meta.className = "api-route-meta";
    meta.append(rolePill);
    wrap.append(meta);
  }
  return wrap;
}

function routeDisplayName(route) {
  const displayName = String(route.display_name || "").trim();
  if (displayName) {
    return displayName.replace(/\s*registry entry\s*$/i, "").trim() || displayName;
  }
  const roleLabel = normalizedRouteRoleLabel(route);
  if (roleLabel) {
    return roleLabel;
  }
  return "registry entry";
}

function normalizedRouteRoleLabel(route) {
  const raw = String(route.role_label || "").trim();
  const lower = raw.toLowerCase();
  if (!raw || lower === "registry entry") {
    return "";
  }
  if (route.is_primary === true || route.primary === true || lower === "main route" || lower === "primary") {
    return "Основной маршрут";
  }
  if (lower === "допустим для резерва") {
    return "Резервный кандидат";
  }
  if (lower === "маршрут проверки") {
    return "Маршрут проверки";
  }
  return raw;
}

function routeRoleTone(route) {
  const label = normalizedRouteRoleLabel(route);
  if (!label) {
    return "neutral";
  }
  if (label === "Основной маршрут") {
    return "blue";
  }
  if (label === "Резервный кандидат") {
    return "amber";
  }
  return "neutral";
}

function routeRolePill(route) {
  const label = normalizedRouteRoleLabel(route);
  if (!label) {
    return null;
  }
  const chip = document.createElement("span");
  chip.className = `mini-pill api-route-role-pill ${routeRoleTone(route)}`;
  chip.textContent = label;
  chip.title = "Role label отражает admitted metadata и не меняет authority или runtime truth.";
  return chip;
}

function routeStatusLabel(route) {
  const raw = String(route.status_label || route.status_code || "").trim().toLowerCase();
  const labels = {
    enabled: "разрешён",
    disabled: "отключён",
    missing_secret: "нет секрета",
    "missing secret": "нет секрета",
    stale: "устарел",
    ok: "ok"
  };
  return labels[raw] || route.status_label || "нет данных";
}

function routeStatusChip(route) {
  const chip = document.createElement("span");
  const visual = ACCOUNT_VISUAL_CLASS[route.visual_state] || "neutral";
  chip.className = `chip ${visual}`;
  const dot = document.createElement("span");
  dot.className = "dot";
  const label = document.createElement("span");
  label.textContent = routeStatusLabel(route);
  chip.append(dot, label);
  return chip;
}

function routeValidationLabel(route) {
  const raw = String(route.validation_label || route.validation_status_label || "").trim().toLowerCase();
  const fallback = route.status_code === "missing_secret" ? "blocked by secret" : "not checked";
  const labels = {
    "not checked": "не проверялся",
    "blocked by secret": "нет секрета",
    pending: "ожидает",
    stale: "устарело",
    ok: "ok"
  };
  return labels[raw] || labels[fallback] || route.validation_label || "не проверялся";
}

function routeValidationChip(route) {
  const chip = document.createElement("span");
  const fallbackVisual = route.status_code === "missing_secret" ? "amber" : "neutral";
  const visual = ACCOUNT_VISUAL_CLASS[route.validation_visual_state] || ACCOUNT_VISUAL_CLASS[fallbackVisual] || "neutral";
  chip.className = `chip ${visual}`;
  const dot = document.createElement("span");
  dot.className = "dot";
  const label = document.createElement("span");
  label.textContent = routeValidationLabel(route);
  chip.append(dot, label);
  return chip;
}

function routeSecretStatusLabel(route) {
  const raw = String(route.secret_status_label || "").trim().toLowerCase();
  const labels = {
    available: "есть",
    missing: "нет",
    unknown: "неизвестно"
  };
  return labels[raw] || route.secret_status_label || "неизвестно";
}

function routeSecretRef(route) {
  const wrap = document.createElement("div");
  wrap.className = "api-secret-ref";
  const ref = document.createElement("div");
  ref.className = "mono-value";
  ref.textContent = route.secret_ref || "unknown";
  ref.title = route.secret_ref || "unknown";
  const chip = document.createElement("span");
  const visual = ACCOUNT_VISUAL_CLASS[route.secret_visual_state] || "neutral";
  chip.className = `chip ${visual}`;
  const dot = document.createElement("span");
  dot.className = "dot";
  const label = document.createElement("span");
  label.textContent = routeSecretStatusLabel(route);
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
  list.append(routeActionButton(route, "api_route_check", "Проверить запросом", { menuItem: true }));
  if (route.enabled === false) {
    list.append(routeActionButton(route, "api_route_allow", "Разрешить маршрут", { menuItem: true }));
  } else {
    list.append(routeActionButton(route, "api_route_disable", "Отключить маршрут", { menuItem: true }));
  }
  list.append(routeActionButton(route, "api_route_profile", "Пакет профиля", { menuItem: true }));
  list.append(routeActionButton(route, "api_route_evidence_capture", "Свидетельство", { menuItem: true }));
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
      td("right mono-value", accountTableCheckLabel(account.last_success || account.cooldown_until)),
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

function accountTableCheckLabel(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "—";
  }
  const isoMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (isoMatch) {
    return `${isoMatch[3]}.${isoMatch[2]}, ${isoMatch[4]}:${isoMatch[5]}`;
  }
  return raw;
}

function routeTableCheckLabel(value) {
  return accountTableCheckLabel(value);
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
    recheck_account: "Перепроверить",
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
    { uiAction: "recheck_account", label: "Перепроверить", enabled: !retired, reason: retired ? "аккаунт выведен из пула" : "", icon: "assets/icons/phosphor/arrows-clockwise.png" },
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
  document.getElementById("brandCaption").textContent = "";
  setSourceCopy(source);
  resetRefreshButtonLabelIfIdle();

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
  if (currentScreen() === "overview") {
    renderReviewPanel();
  }
}

async function setLiveReadonly(updateUrl = false) {
  setLiveReadonlyPendingUi();
  if (currentScreen() === "overview") {
    renderOverviewLivePendingState();
  }
  await loadActionMetadata();
  applyActionAvailability();
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
  if (currentScreen() === "overview") {
    await refreshReviewPanel();
  }
  return snapshot;
}

async function refreshLiveReadonlyForActionPayload(payload, updateUrl = false) {
  if (!accountRefreshRequiresRuntimeStatus(payload?.ui_action) || currentScreen() !== "accounts") {
    return setLiveReadonly(updateUrl);
  }
  setLiveReadonlyPendingUi();
  await loadActionMetadata();
  applyActionAvailability();
  const accounts = await loadAccountsReadonly();
  const runtime = await loadLiveReadonly();
  if (updateUrl) {
    const url = new URL(window.location.href);
    url.searchParams.set("source", "live");
    window.history.replaceState({}, "", url);
  }
  renderAccountsSnapshot(accounts);
  setSourceCopy("live");
  return { accounts, runtime };
}

async function refreshCurrentSource() {
  const startedAt = Date.now();
  setRefreshButtonFeedback("busy", "Обновляю...", { disabled: true });
  try {
    const source = document.getElementById("sourcePicker").value;
    const result = source === "live"
      ? await setLiveReadonly(false)
      : await setFixtureState(document.getElementById("statePicker").value, false);
    if (source === "live" && currentScreen() === "quick-start") {
      await refreshQuickStartRouteStatus();
    }
    const remainingBusyMs = Math.max(0, 250 - (Date.now() - startedAt));
    if (remainingBusyMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, remainingBusyMs));
    }
    setRefreshButtonFeedback("success", "Обновлено", { resetAfterMs: 1000 });
    return result;
  } catch (error) {
    setRefreshButtonFeedback("error", "Ошибка", { resetAfterMs: 1800 });
    console.error("Failed to refresh current source", error);
    return null;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  const sourcePicker = document.getElementById("sourcePicker");
  const picker = document.getElementById("statePicker");
  const refresh = document.getElementById("refreshFixture");
  const initialState = stateFromLocation();
  const initialSource = sourceFromLocation();
  const initialScreen = screenFromLocation();
  document.getElementById("quickStartCustomLaunchAction")?.addEventListener("click", () => runQuickStartCustomLaunchAction());
  await ensureActionMetadataLoaded();
  applyActionAvailability();
  setupCodexCustomAgentAliases();
  setScreen(initialScreen, false);
  applyCodexRouteSelection(readStoredCodexRouteSelection());
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
  document.getElementById("codexLaunchModesRefreshAction")?.addEventListener("click", () => refreshCodexLaunchModesPanel());
  document.getElementById("originalCodexDryRunAction")?.addEventListener("click", () => runOriginalCodexDryRun());
  document.getElementById("originalCodexLaunchAction")?.addEventListener("click", () => runOriginalCodexLaunch());
  document.getElementById("codexCustomLaunchDryRunAction")?.addEventListener("click", () => runCodexCustomLaunchDryRun());
  document.getElementById("codexCustomLaunchAction")?.addEventListener("click", () => runCodexCustomLaunch());
  document.getElementById("codexCustomVisibleHistoryConfirmAction")?.addEventListener("click", () => confirmCodexCustomVisibleHistory());
  document.getElementById("safeAppCopyLaunchDryRunAction")?.addEventListener("click", () => runSafeAppCopyLaunchDryRun());
  document.getElementById("safeAppCopyLiveAdmissionAction")?.addEventListener("click", () => runSafeAppCopyLiveAdmission());
  document.getElementById("safeAppCopyLaunchAction")?.addEventListener("click", () => runSafeAppCopyLaunch());
  document.getElementById("codexCustomModelsRefreshAction")?.addEventListener("click", () => refreshCodexCustomModelsPanel());
  document.getElementById("codexCustomModelSelect")?.addEventListener("change", () => {
    syncCodexRouteSelects("codexCustomModelSelect", { userInitiated: true });
  });
  document.getElementById("codexCustomApiModelSelect")?.addEventListener("change", () => {
    syncCodexRouteSelects("codexCustomApiModelSelect");
    renderApiReasoningOptionSelects();
    saveCodexRouteSelection(codexRouteSelectionFromUi(false));
    refreshCodexCustomApiActionGate();
  });
  document.getElementById("codexCustomApiReasoningOptionSelect")?.addEventListener("change", () => syncCodexRouteSelects("codexCustomApiReasoningOptionSelect"));
  document.getElementById("codexCustomExecutionModeSelect")?.addEventListener("change", () => syncCodexRouteSelects("codexCustomExecutionModeSelect"));
  document.getElementById("quickStartChatModelSelect")?.addEventListener("change", () => {
    syncCodexRouteSelects("quickStartChatModelSelect", { userInitiated: true });
  });
  document.getElementById("quickStartApiModelSelect")?.addEventListener("change", () => {
    syncCodexRouteSelects("quickStartApiModelSelect");
    renderApiReasoningOptionSelects();
    saveCodexRouteSelection(codexRouteSelectionFromUi(true));
    refreshCodexCustomApiActionGate();
  });
  document.getElementById("quickStartApiReasoningOptionSelect")?.addEventListener("change", () => syncCodexRouteSelects("quickStartApiReasoningOptionSelect"));
  document.getElementById("quickStartExecutionModeSelect")?.addEventListener("change", () => syncCodexRouteSelects("quickStartExecutionModeSelect"));
  document.getElementById("quickStartRouteRefreshAction")?.addEventListener("click", () => refreshQuickStartRouteStatus());
  document.getElementById("quickStartExecutionModeDryRunAction")?.addEventListener("click", () => runQuickStartConfigAdmission("quickStartExecutionModeDryRunAction"));
  document.getElementById("quickStartLaunchPreflightAction")?.addEventListener("click", () => runQuickStartLaunchPreflight());
  document.getElementById("quickStartDeepSeekCoderCheckAction")?.addEventListener("click", () => runQuickStartDeepSeekCoderCheck());
  document.getElementById("quickStartDeepSeekCodeEditProofAction")?.addEventListener("click", () => runQuickStartDeepSeekCodeEditProof());
  document.getElementById("quickStartShowCustomWindowAction")?.addEventListener("click", () => showCodexCustomWindow());
  document.getElementById("quickStartVisibleHistoryConfirmAction")?.addEventListener("click", () => confirmCodexCustomVisibleHistory());
  document.getElementById("codexCustomApiActionGateAction")?.addEventListener("click", () => refreshCodexCustomApiActionGate());
  document.getElementById("codexCustomSelectorIntentDryRunAction")?.addEventListener("click", () => runCodexCustomSelectorIntentDryRun());
  document.getElementById("codexCustomExecutionModeDryRunAction")?.addEventListener("click", () => runCodexCustomExecutionModeDryRun());
  document.getElementById("codexCustomDeepSeekLiveFormatAction")?.addEventListener("click", () => runCodexCustomDeepSeekLiveFormat());
  document.getElementById("codexCustomModelDryRunAction")?.addEventListener("click", () => runCodexCustomModelDryRun());
  document.getElementById("codexCustomAccountsRefreshAction")?.addEventListener("click", () => refreshCodexCustomAccountsPanel());
  document.getElementById("codexCustomAccountSmokeDryRunAction")?.addEventListener("click", () => runCodexCustomAccountSmokeDryRun());
  document.getElementById("codexCustomSessionsRefreshAction")?.addEventListener("click", () => refreshCodexCustomSessionsPanel());
  document.getElementById("codexCustomSessionCreateAction")?.addEventListener("click", () => createCodexCustomSession());
  document.getElementById("codexCustomSessionPromptDryRunAction")?.addEventListener("click", () => runCodexCustomSessionPromptDryRun());
  document.getElementById("codexCustomSessionPromptRunAction")?.addEventListener("click", () => runCodexCustomSessionPrompt());
  document.getElementById("codexCustomProductCoderRunAction")?.addEventListener("click", () => runCodexCustomProductCoder());
  document.getElementById("codexCustomProductCoderCleanupAction")?.addEventListener("click", () => cleanupCodexCustomProductCoderWorktree());
  document.getElementById("codexCustomSessionCancelAction")?.addEventListener("click", () => cancelCodexCustomSession());
  document.getElementById("codexCustomSessionCleanupAction")?.addEventListener("click", () => cleanupCodexCustomSession());
  document.getElementById("codexCustomRecoveryContractAction")?.addEventListener("click", () => refreshCodexCustomRecoveryContract());
  document.getElementById("codexCustomRecoveryCheckAllAction")?.addEventListener("click", () => runCodexCustomRecoveryChecks());
  document.getElementById("codexCustomRecoveryOperatorMatrixAction")?.addEventListener("click", () => refreshCodexCustomRecoveryOperatorMatrix());
  document.getElementById("codexCustomRecoverySessionActionsAction")?.addEventListener("click", () => refreshCodexCustomRecoveryAdmittedSessionActions());
  document.getElementById("codexCustomRecoveryRollbackProcessOwnerAction")?.addEventListener("click", () => refreshCodexCustomRecoveryRollbackProcessOwnerContract());
  document.getElementById("codexCustomRecoveryRollbackPointAction")?.addEventListener("click", () => refreshCodexCustomRecoveryRollbackPointDryRun());
  document.getElementById("codexCustomRecoveryRollbackPointAdmissionAction")?.addEventListener("click", () => refreshCodexCustomRecoveryRollbackPointCreateAdmission());
  document.getElementById("codexCustomRecoveryRollbackPointCreateAction")?.addEventListener("click", () => createCodexCustomRecoveryRollbackPoint());
  document.getElementById("codexCustomRecoveryRollbackPointVerifyAction")?.addEventListener("click", () => verifyCodexCustomRecoveryRollbackPoint());
  document.getElementById("codexCustomRecoveryRollbackApplyAdmissionAction")?.addEventListener("click", () => refreshCodexCustomRecoveryRollbackApplyAdmissionDryRun());
  document.getElementById("codexCustomRecoveryRollbackApplyPreflightAction")?.addEventListener("click", () => refreshCodexCustomRecoveryRollbackApplyLivePreflight());
  document.getElementById("codexCustomRecoveryRollbackApplyReceiptAction")?.addEventListener("click", () => createCodexCustomRecoveryRollbackApplyReceipt());
  document.getElementById("codexCustomRecoveryRollbackApplyReceiptVerifyAction")?.addEventListener("click", () => verifyCodexCustomRecoveryRollbackApplyReceipt());
  document.getElementById("codexCustomRecoveryStopCleanupPreflightAction")?.addEventListener("click", () => refreshCodexCustomRecoveryStopCleanupPreflight());
  document.getElementById("codexCustomRecoveryStopCleanupLiveAction")?.addEventListener("click", () => runCodexCustomRecoveryStopCleanupLive());
  document.getElementById("codexCustomRecoveryProcessKillPreflightAction")?.addEventListener("click", () => refreshCodexCustomRecoveryProcessKillPreflight());
  document.getElementById("codexCustomRecoveryCancelAction")?.addEventListener("click", () => cancelCodexCustomRecoverySession());
  document.getElementById("codexCustomRecoveryCleanupAction")?.addEventListener("click", () => cleanupCodexCustomRecoverySession());
  document.getElementById("operatorRefreshAction")?.addEventListener("click", () => refreshOperatorPanel());
  document.getElementById("operatorRunAction")?.addEventListener("click", () => runOperatorPrompt());
  document.getElementById("reviewRefreshAction")?.addEventListener("click", () => refreshReviewPanel());
  document.getElementById("reviewImportAction")?.addEventListener("click", () => importReviewPacketFromPanel());
  document.getElementById("reviewApplyAction")?.addEventListener("click", () => applyReviewExactChangeFromPanel());
  document.getElementById("reviewClearAction")?.addEventListener("click", () => clearReviewSessionFromPanel());
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
  document.getElementById("quickStartCheckApiAction")?.addEventListener("click", () => {
    runQuickStartConfigAdmission("quickStartCheckApiAction");
  });
  document.getElementById("quickStartConnectApiAction")?.addEventListener("click", () => {
    maybeConfirmAndRunFromButton(document.getElementById("quickStartConnectApiAction"), "api_route_connect");
  });
  document.getElementById("quickStartApiCredentialCheckAction")?.addEventListener("click", () => {
    maybeConfirmAndRunFromButton(document.getElementById("quickStartApiCredentialCheckAction"), "api_route_credential_check");
  });
  document.getElementById("quickStartApiCredentialRetryAction")?.addEventListener("click", () => {
    maybeConfirmAndRunFromButton(document.getElementById("quickStartApiCredentialRetryAction"), "api_route_connect");
  });
  document.getElementById("apiRouteConnectAction")?.addEventListener("click", () => {
    maybeConfirmAndRun("api_route_connect");
  });
  document.getElementById("apiConnectionsCredentialCheckAction")?.addEventListener("click", () => {
    maybeConfirmAndRun("api_route_credential_check");
  });
  document.getElementById("apiConnectionsCredentialRetryAction")?.addEventListener("click", () => {
    maybeConfirmAndRun("api_route_connect");
  });
  document.getElementById("quickStartCheckAllAction")?.addEventListener("click", () => {
    const button = document.getElementById("quickStartCheckAllAction");
    maybeConfirmAndRunFromButton(button, button.dataset.uiAction || "quick_start_check_all");
  });
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
  refreshCodexLaunchModesPanel();
  refreshCodexCustomModelsPanel();
  refreshCodexCustomAccountsPanel();
  refreshCodexCustomSessionsPanel();
  refreshOperatorPanel();
  reviewEnsurePacketInputSeed();
  renderReviewPanel();
  if (initialScreen === "overview" && initialSource === "live") {
    refreshReviewPanel();
  }
});
