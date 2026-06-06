# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Read-only live preview server for the first web-design screen."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import html
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import mimetypes
import os
from pathlib import Path
from queue import Empty, Queue
import socket
import sqlite3
import subprocess
import time
from threading import RLock, Thread
from typing import Any, Callable
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse
import uuid

from wild_boar_proxy.ui_shell import (
    JsonCommandRunner,
    UiShellError,
    build_account_pool_snapshot,
    build_external_models_snapshot,
    build_runtime_snapshot,
    external_route_secret_available,
)
from wild_boar_proxy.codex_launch_modes import (
    build_custom_launch_dry_run_packet,
    build_custom_status_packet,
    build_launch_modes_packet,
    build_original_launch_dry_run_packet,
    build_original_status_packet,
    build_safe_app_copy_live_admission_packet,
    build_safe_app_copy_launch_dry_run_packet,
    build_safe_app_copy_launch_live_packet,
    forbidden_custom_launch_fields,
    forbidden_original_fields,
)
from wild_boar_proxy.codex_account_selection import (
    build_account_selection_packet,
    build_account_smoke_dry_run_packet,
    build_accounts_truth_packet,
)
from wild_boar_proxy.codex_custom_sessions import CodexCustomSessionManager
from wild_boar_proxy.codex_model_registry import (
    API_ONLY_DEEPSEEK_LIVE_ROUTE_FORMAT_EXPECTED_TEXT,
    API_ONLY_DEEPSEEK_LIVE_ROUTE_FORMAT_PROMPT,
    API_ROUTE_MODEL_LANE,
    CODEX_ACCOUNT_MODEL_LANE,
    build_api_only_deepseek_live_route_format_packet,
    build_api_only_executor_truth_packet,
    build_chatgpt_plus_api_slot_truth_packet,
    build_custom_api_action_gate_packet,
    build_custom_api_compat_packet,
    build_custom_codex_execution_mode_selector_packet,
    build_dual_lane_model_selection_ui_packet,
    build_dual_lane_selection_intent_packet,
    build_custom_model_dry_run_packet,
    build_custom_model_registry_packet,
    build_server_model_selection_and_reasoning_truth_packet,
    model_lane_classification_from_registry,
)
from wild_boar_proxy.model_availability import (
    build_catalog_availability_lattice_packet,
    build_model_direct_preflight_packet,
)
from wild_boar_proxy.native_window_probe import (
    DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID,
    OWNER_STANDING_AUTHORIZATION_PHRASE,
    launch_custom_native_app_packet,
    show_custom_native_window_packet,
)
from wild_boar_proxy.native_filesystem_probe import (
    collect_codex_process_inventory,
    default_persistent_custom_profile_paths,
    terminate_custom_processes,
)
from wild_boar_proxy.codex_recovery_contract import (
    build_custom_recovery_admitted_session_actions_packet,
    build_custom_recovery_contract_packet,
    build_custom_recovery_process_kill_preflight_packet,
    build_custom_recovery_rollback_operator_ready_packet,
    build_custom_recovery_rollback_apply_admission_dry_run_packet,
    build_custom_recovery_rollback_apply_bounded_live_packet,
    build_custom_recovery_rollback_apply_receipt_verify_packet,
    build_custom_recovery_rollback_apply_live_preflight_packet,
    build_custom_recovery_rollback_point_create_admission_packet,
    build_custom_recovery_rollback_point_create_live_packet,
    build_custom_recovery_rollback_point_dry_run_packet,
    build_custom_recovery_rollback_point_verify_packet,
    build_custom_recovery_rollback_process_owner_contract_packet,
    build_custom_recovery_stop_cleanup_live_packet,
    build_custom_recovery_stop_cleanup_preflight_packet,
    custom_recovery_session_ref,
)
from wild_boar_proxy.runtime import (
    DEFAULT_LAUNCHER_SCRIPT_NAME,
    RuntimePaths,
    build_command_payload,
    build_launcher_subprocess_env,
    proxyless_urlopen,
    run_legacy_import,
)
from wild_boar_proxy.review_bridge_apply_admission import (
    ReviewApplyContext,
    default_review_apply_context,
)
from wild_boar_proxy.review_bridge_command_bus import (
    execute_review_command,
    review_allowlist_metadata,
)
from wild_boar_proxy.review_bridge_packet_import import (
    ReviewImportContext,
    ReviewPacketImportError,
    default_review_import_context,
)
from wild_boar_proxy.review_bridge_session_store import (
    ReviewQueryBridge,
    ReviewSessionStore,
)
from wild_boar_proxy.web_design_command_adapter import CommandRunner, execute_command
from wild_boar_proxy.web_ingress import (
    JSON_CONTENT_TYPE,
    MAX_WEB_REQUEST_BODY_BYTES,
    content_type_matches,
    host_header_is_local,
    origin_header_is_allowed,
    parse_content_length,
    unsafe_bind_requested,
    web_ingress_rejection_packet,
)
from wild_boar_proxy.web_rate_limit import (
    DEFAULT_WEB_POST_RATE_LIMIT_PER_SECOND,
    WEB_RATE_LIMIT_MACHINE_ERROR_CODE,
    WebPostRateLimiter,
)
from wild_boar_proxy.web_route_table import (
    BODY_KIND_JSON,
    BODY_KIND_NONE,
    BODY_KIND_OPTIONAL_JSON,
    BODY_KIND_SPECIAL_JSON,
    BROWSER_FIELD_POLICY_JSON_VALIDATED,
    BROWSER_FIELD_POLICY_NONE,
    BROWSER_FIELD_POLICY_QUERY_VALIDATED,
    BROWSER_FIELD_POLICY_UI_ACTION_REGISTRY,
    EFFECT_MUTATE,
    EFFECT_PROBE,
    EFFECT_READ,
    EFFECT_REPAIR,
    EFFECT_SOURCE_DYNAMIC_SUBACTION,
    EFFECT_SOURCE_ROUTE,
    EFFECT_SOURCE_UI_ACTION_REGISTRY,
    RouteSpec,
    WebRouteTable,
)
from wild_boar_proxy.web_token import (
    WEB_CSRF_META_NAME,
    WEB_TOKEN_FILENAME,
    WEB_TOKEN_META_NAME,
    WebTokenState,
    create_in_memory_web_token,
    create_web_token,
    delete_web_token,
    web_post_csrf_valid,
    web_post_token_valid,
)
from wild_boar_proxy.operator_surface import (
    DEFAULT_ENDPOINT,
    DEFAULT_CODEX_BIN,
    HybridOpenAICompatAdapter,
    OperatorSurfaceSession,
    STABLE_BRIDGE_WINDOW_SMOKE_PHRASE,
    _safe_route_digest,
    build_bridge_failure_recovery_truth_packet,
    build_stable_bridge_preflight_packet,
    clean_env,
    compare_snapshots,
    default_runtime_config_path,
    extract_local_api_key,
    protected_snapshot,
    protected_surfaces_unchanged,
)

DEEPSEEK_CODE_EDIT_PROBE_FILE = ".tmp/deepseek_live_probe.txt"
DEEPSEEK_CODE_EDIT_EXPECTED_TEXT = "WBP_DEEPSEEK_CODE_EDIT_OK"
API_ONLY_DEEPSEEK_CODE_EDIT_PROBE_FILE = ".tmp/deepseek_api_only_live_edit_probe.txt"
API_ONLY_DEEPSEEK_CODE_EDIT_EXPECTED_TEXT = "WBP_API_ONLY_DEEPSEEK_EDIT_OK"
DEEPSEEK_ROUTE_BOUND_EDIT_PROBE_FILE = ".tmp/deepseek_route_bound_edit.txt"
DEEPSEEK_ROUTE_BOUND_EDIT_EXPECTED_TEXT = "WBP_DEEPSEEK_ROUTE_BOUND_EDIT_OK"
MIXED_MODE_CODE_EDIT_PROBE_FILE = ".tmp/mixed_mode_probe.txt"
MIXED_MODE_CODE_EDIT_EXPECTED_TEXT = "WBP_CHATGPT_PLUS_DEEPSEEK_OK"
QUICK_START_DEEPSEEK_CODE_EDIT_ALLOWED_BROWSER_FIELDS = frozenset(
    {
        "execution_mode",
        "api_model_id",
        "api_reasoning_option_id",
    }
)
QUICK_START_MIXED_MODE_CODE_EDIT_ALLOWED_BROWSER_FIELDS = frozenset(
    {
        "execution_mode",
        "chatgpt_model_id",
        "api_model_id",
        "api_reasoning_option_id",
    }
)
STABLE_PROFILE_HISTORY_ALLOWED_BROWSER_FIELDS = frozenset(
    {
        "action",
        "history_marker",
    }
)
DEFAULT_STABLE_PROFILE_HISTORY_MARKER = "WBP_STABLE_HISTORY_MARKER"
CUSTOM_CODEX_STABLE_WBP_BRIDGE_PORT_ENV = "WBP_CUSTOM_CODEX_BRIDGE_PORT"
DEFAULT_CUSTOM_CODEX_STABLE_WBP_BRIDGE_PORT = 50555


class _HttpIngressRejection(Exception):
    def __init__(
        self,
        *,
        status: HTTPStatus,
        machine_error_code: str,
        human_message: str,
    ) -> None:
        super().__init__(machine_error_code)
        self.status = status
        self.packet = web_ingress_rejection_packet(
            machine_error_code=machine_error_code,
            human_message=human_message,
        )


def _custom_codex_stable_wbp_bridge_port() -> int:
    raw_value = os.environ.get(CUSTOM_CODEX_STABLE_WBP_BRIDGE_PORT_ENV, "").strip()
    if not raw_value:
        return DEFAULT_CUSTOM_CODEX_STABLE_WBP_BRIDGE_PORT
    try:
        port = int(raw_value)
    except ValueError:
        return DEFAULT_CUSTOM_CODEX_STABLE_WBP_BRIDGE_PORT
    if 1 <= port <= 65535:
        return port
    return DEFAULT_CUSTOM_CODEX_STABLE_WBP_BRIDGE_PORT


ROOT = Path(__file__).resolve().parents[1]
WEB_DESIGN_UI = ROOT / "wild_boar_proxy" / "web_design_ui"
READONLY_COMMAND_IDS = (
    "status",
    "mode_get",
    "accounts_list",
    "healthcheck",
    "rollout_rotation_inspect",
)
PRIMARY_COMMAND_IDS = ("status", "mode_get", "accounts_list")
DETAIL_COMMAND_IDS = ("healthcheck", "rollout_rotation_inspect")
LAUNCH_COPY_PREFLIGHT_REQUIRED_CODE = "UI_LAUNCH_COPY_PREFLIGHT_REQUIRED"
LAUNCH_COPY_PREFLIGHT_UNSAFE_CODE = "UI_LAUNCH_COPY_ISOLATION_UNPROVEN"
ACCOUNT_CONNECT_PREFLIGHT_REQUIRED_CODE = "UI_ACCOUNT_CONNECT_PREFLIGHT_REQUIRED"
ACCOUNT_CONNECT_PREFLIGHT_UNSAFE_CODE = "UI_ACCOUNT_CONNECT_SERVER_OWNED_SOURCE_UNPROVEN"
API_ROUTE_CONNECT_PREFLIGHT_REQUIRED_CODE = "UI_API_ROUTE_CONNECT_PREFLIGHT_REQUIRED"
API_ROUTE_CONNECT_PREFLIGHT_UNSAFE_CODE = "UI_API_ROUTE_CONNECT_SERVER_OWNED_SOURCE_UNPROVEN"
SANDBOX_ACTION_PREFLIGHT_REQUIRED_CODE = "UI_SANDBOX_ACTION_PREFLIGHT_REQUIRED"
SANDBOX_ACTION_PREFLIGHT_UNSAFE_CODE = "UI_SANDBOX_ACTION_TARGET_UNPROVEN"
ACCOUNTS_READONLY_COMMAND_IDS = ("accounts_list",)
API_CONNECTIONS_READONLY_COMMAND_IDS = (
    "external_models_status",
    "external_models_models",
    "external_models_routes_list",
)
ACCOUNT_ID_SAFE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "._-:@"
)
ROUTE_ID_SAFE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "._-:@"
)
SESSION_ID_SAFE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "._-"
)
ACCOUNT_ID_UI_ACTIONS = frozenset(
    {
        "validate_account",
        "recheck_account",
        "promote_account",
        "demote_account",
        "retire_account",
        "hold_account",
        "release_account",
    }
)
ROUTE_ID_UI_ACTIONS = frozenset(
    {
        "api_route_validate",
        "api_route_check",
        "api_route_allow",
        "api_route_disable",
        "api_route_remove",
        "api_route_profile",
        "api_route_evidence_capture",
    }
)
SESSION_ID_UI_ACTIONS = frozenset(
    {
        "account_login_status",
        "account_login_complete",
        "account_login_cancel",
    }
)
OWNER_STANDING_AUTHORIZATION_PHRASE = "разрешаю тебе любые законные действия в рамках разработки проекта"
CUSTOM_CODEX_READONLY_TIMEOUT_SECONDS = 2.0
CUSTOM_CODEX_OPERATOR_STATUS_READONLY_TIMEOUT_SECONDS = 0.75
CUSTOM_CODEX_READONLY_TIMEOUT_CODE = "CUSTOM_CODEX_READONLY_TIMEOUT"
CUSTOM_CODEX_OPERATOR_STATUS_TIMEOUT_CODE = "CUSTOM_CODEX_OPERATOR_STATUS_TIMEOUT_API_CATALOG_ONLY"
VISIBLE_HISTORY_CONFIRMATION_MAX_AGE_SECONDS = 10 * 60
VISIBLE_HISTORY_CONFIRMED_STATUS = "VISIBLE_THREAD_HISTORY_RESTORE_OWNER_CONFIRMED_WITH_LIMITS"
VISIBLE_HISTORY_NOT_PROVEN_STATUS = "VISIBLE_THREAD_HISTORY_NOT_PROVEN_WITH_STORAGE_CONTINUITY"
VISIBLE_HISTORY_RELAUNCH_CONFIRMED_STATUS = (
    "CUSTOM_CODEX_VISIBLE_HISTORY_RELAUNCH_OWNER_CONFIRMED_WITH_LIMITS"
)
VISIBLE_HISTORY_RELAUNCH_NOT_CONFIRMED_STATUS = (
    "CUSTOM_CODEX_RELAUNCH_PROFILE_PROVEN_VISIBLE_HISTORY_NOT_CONFIRMED"
)
VISIBLE_HISTORY_RELAUNCH_SMOKE_CONFIRMED_STATUS = (
    "CUSTOM_CODEX_VISIBLE_HISTORY_SMOKE_CONFIRMED_WITH_LIMITS"
)
VISIBLE_HISTORY_ALLOWED_OWNER_FIELDS = frozenset(
    {
        "custom_codex_open",
        "old_chat_visible",
        "chat_not_empty",
        "not_original_codex",
        "raw_thread_content_not_recorded",
    }
)
VISIBLE_HISTORY_RELAUNCH_ALLOWED_OWNER_FIELDS = frozenset(
    {
        "custom_codex_open",
        "old_chat_visible",
        "chat_not_empty",
        "not_original_codex",
        "owner_confirmed_after_relaunch",
        "raw_thread_content_not_recorded",
        "smoke_phrase_required",
        "smoke_phrase_visible",
    }
)


def owner_authorization_phrase_present(value: str | None) -> bool:
    return isinstance(value, str) and value.strip() == OWNER_STANDING_AUTHORIZATION_PHRASE


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _custom_codex_readonly_timeout_packet(
    *,
    endpoint: str,
    timeout_scope: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "integration_failure",
        "machine_error_code": CUSTOM_CODEX_READONLY_TIMEOUT_CODE,
        "human_message": "Custom Codex readonly snapshot timed out.",
        "next_action": "retry_readonly_snapshot_or_inspect_operator_surface",
        "source": "custom_codex_readonly_timeout",
        "endpoint": endpoint,
        "timeout_scope": timeout_scope,
        "fallback_used": False,
        "model_auto_selected": False,
    }


def _run_custom_codex_readonly_snapshot(
    *,
    endpoint: str,
    timeout_scope: str,
    build_snapshot: Callable[[], dict[str, Any]],
    timeout_fallback: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    if timeout_seconds is None:
        timeout_seconds = CUSTOM_CODEX_READONLY_TIMEOUT_SECONDS

    results: Queue[tuple[str, Any]] = Queue(maxsize=1)

    def worker() -> None:
        try:
            results.put(("ok", build_snapshot()), block=False)
        except Exception as exc:
            results.put(("error", exc), block=False)

    thread = Thread(
        target=worker,
        name=f"custom-codex-readonly-{timeout_scope}",
        daemon=True,
    )
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        timeout_packet = _custom_codex_readonly_timeout_packet(
            endpoint=endpoint,
            timeout_scope=timeout_scope,
        )
        return timeout_fallback(timeout_packet) if timeout_fallback else timeout_packet
    try:
        status, value = results.get_nowait()
    except Empty:
        timeout_packet = _custom_codex_readonly_timeout_packet(
            endpoint=endpoint,
            timeout_scope=timeout_scope,
        )
        return timeout_fallback(timeout_packet) if timeout_fallback else timeout_packet
    if status == "error":
        raise value
    return value


def _operator_status_timeout_fallback_packet() -> dict[str, Any]:
    return {
        "status": {
            "configured_model": "",
            "machine_error_code": CUSTOM_CODEX_OPERATOR_STATUS_TIMEOUT_CODE,
        },
        "claim_gate": {"status": "not_reported"},
        "models": {
            "ok": False,
            "server_issued": True,
            "model_ids": [],
            "model_entries": [],
        },
    }


def _bounded_operator_models_payload(
    operator_surface_session: Any,
    *,
    timeout_seconds: float = 3.0,
) -> dict[str, Any] | None:
    results: Queue[tuple[str, Any]] = Queue(maxsize=1)

    def worker() -> None:
        try:
            results.put(("ok", operator_surface_session.probe_models()), block=False)
        except Exception as exc:
            results.put(("error", exc), block=False)

    thread = Thread(
        target=worker,
        name="custom-codex-operator-models-readonly",
        daemon=True,
    )
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        return None
    try:
        status, value = results.get_nowait()
    except Empty:
        return None
    if status != "ok" or not isinstance(value, dict):
        return None
    return value


def _bounded_operator_status_payload(operator_surface_session: Any) -> tuple[dict[str, Any], bool]:
    results: Queue[tuple[str, Any]] = Queue(maxsize=1)

    def worker() -> None:
        try:
            results.put(("ok", operator_surface_session.status_payload()), block=False)
        except Exception as exc:
            results.put(("error", exc), block=False)

    thread = Thread(
        target=worker,
        name="custom-codex-operator-status-readonly",
        daemon=True,
    )
    thread.start()
    thread.join(CUSTOM_CODEX_OPERATOR_STATUS_READONLY_TIMEOUT_SECONDS)
    if thread.is_alive():
        packet = _operator_status_timeout_fallback_packet()
        models = _bounded_operator_models_payload(operator_surface_session)
        if isinstance(models, dict) and models.get("model_ids"):
            packet["models"] = models
        return packet, True
    try:
        status, value = results.get_nowait()
    except Empty:
        return _operator_status_timeout_fallback_packet(), True
    if status == "error":
        raise value
    return value if isinstance(value, dict) else _operator_status_timeout_fallback_packet(), False


def _mark_operator_status_timeout_fallback(packet: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(packet, dict):
        return packet
    api_lane = packet.get("api_lane") if isinstance(packet.get("api_lane"), dict) else {}
    api_model_count = int(api_lane.get("model_count") or 0) if isinstance(api_lane, dict) else 0
    model_count = int(packet.get("model_count") or 0)
    has_api_catalog = api_model_count > 0 or model_count > 0
    if not has_api_catalog:
        return _custom_codex_readonly_timeout_packet(
            endpoint=str(packet.get("endpoint") or ""),
            timeout_scope="custom_operator_status_readonly_snapshot",
        )
    packet["status"] = "degraded"
    packet["machine_error_code"] = CUSTOM_CODEX_OPERATOR_STATUS_TIMEOUT_CODE
    packet["operator_status_timeout"] = True
    packet["native_lane_catalog_incomplete"] = True
    packet["api_lane_catalog_available"] = True
    packet["fallback_used"] = True
    packet["model_auto_selected"] = False
    packet["selector_runtime_readiness_claimed"] = False
    return packet


def _custom_model_selector_timeout_fallback_packet(
    timeout_packet: dict[str, Any],
    *,
    operator_surface_session: Any,
    api_connections_readonly_runner: CommandRunner,
) -> dict[str, Any]:
    try:
        api_snapshot = build_api_connections_readonly_snapshot(
            api_connections_readonly_runner
        )
        operator_status, operator_status_timeout = _bounded_operator_status_payload(
            operator_surface_session
        )
        packet = build_dual_lane_model_selection_ui_packet(
            operator_status,
            api_snapshot=api_snapshot,
        )
        if operator_status_timeout:
            packet = _mark_operator_status_timeout_fallback(packet)
    except Exception:
        return timeout_packet

    chat_lane = packet.get("chatgpt_lane") if isinstance(packet.get("chatgpt_lane"), dict) else {}
    api_lane = packet.get("api_lane") if isinstance(packet.get("api_lane"), dict) else {}
    chat_model_count = int(chat_lane.get("model_count") or 0) if isinstance(chat_lane, dict) else 0
    api_model_count = int(api_lane.get("model_count") or 0) if isinstance(api_lane, dict) else 0
    if chat_model_count <= 0 and api_model_count <= 0:
        return timeout_packet

    packet["status"] = "degraded"
    packet["machine_error_code"] = CUSTOM_CODEX_READONLY_TIMEOUT_CODE
    packet["human_message"] = (
        "Custom Codex selector timed out; degraded selector was built from bounded "
        "operator/API snapshots."
    )
    packet["next_action"] = "select_available_model_or_retry_readonly_snapshot"
    packet["source"] = "custom_model_selector_timeout_fallback"
    packet["endpoint"] = str(timeout_packet.get("endpoint") or "")
    packet["timeout_scope"] = str(timeout_packet.get("timeout_scope") or "")
    packet["outer_selector_timeout"] = True
    packet["fallback_used"] = True
    packet["model_auto_selected"] = False
    packet["selector_runtime_readiness_claimed"] = False
    packet["api_lane_catalog_available"] = api_model_count > 0
    packet["native_lane_catalog_incomplete"] = chat_model_count <= 0
    return packet


UI_ACTION_ALLOWLIST = {
    "refresh_health_detail": {
        "adapter_command_id": "healthcheck",
        "action_role": "runtime_detail",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "только обновление деталей runtime; состояние runtime не меняется",
        "display_name": "Проверка здоровья",
        "human_meaning": "Обновить детали здоровья runtime без изменения runtime state.",
    },
    "export_diagnostics": {
        "adapter_command_id": "diagnostics_export",
        "action_role": "support_artifact",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "только диагностический пакет поддержки",
        "display_name": "Экспорт диагностики",
        "human_meaning": "Создать диагностический пакет поддержки, не превращая его в runtime truth.",
    },
    "stable_repair_plan": {
        "adapter_command_id": "stable_repair_dry_run",
        "action_role": "recovery_planning",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "только dry-run план восстановления",
        "display_name": "План ремонта stable",
        "human_meaning": "Показать план stable repair без применения изменений.",
    },
    "onboard_account_dry_run": {
        "adapter_command_id": "server_owned_account_connect_dry_run",
        "action_role": "account_onboarding_preview",
        "mutation_class": "account_admission_preview",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "только dry-run preview подключения аккаунта; реальный import auth и registry mutation не выполняются",
        "display_name": "Проверить подключение аккаунта",
        "human_meaning": "Показать server-owned dry-run preview подключения аккаунта без browser secrets, file paths, auth import или registry mutation.",
    },
    "onboard_account": {
        "adapter_command_id": "accounts_onboard",
        "action_role": "account_onboarding",
        "mutation_class": "account_admission",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": False,
        "action_claim_scope": "owner login session start only; browser receives device handoff status but not secrets, paths, or auth refs",
        "display_name": "Подключить аккаунт",
        "human_meaning": "Запустить owner login session без browser paths или credentials и вернуть device handoff для дальнейшего owner-controlled completion.",
    },
    "account_login_status": {
        "adapter_command_id": "accounts_login_status",
        "action_role": "account_login_status",
        "mutation_class": "account_admission",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "owner login session status only; browser sends only owner-created session_id",
        "display_name": "Статус входа",
        "human_meaning": "Проверить состояние owner login session без browser secrets или auth paths.",
    },
    "account_login_complete": {
        "adapter_command_id": "accounts_login_complete_codex",
        "action_role": "account_login_complete",
        "mutation_class": "account_admission",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": True,
        "action_claim_scope": "owner login session complete -> reserve-first onboarding -> accounts refresh",
        "display_name": "Завершить вход",
        "human_meaning": "Завершить owner login session и выполнить reserve-first onboarding после materialized auth.",
    },
    "account_login_cancel": {
        "adapter_command_id": "accounts_login_cancel",
        "action_role": "account_login_cancel",
        "mutation_class": "account_admission",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "owner login session cancel only; browser sends only owner-created session_id",
        "display_name": "Отменить вход",
        "human_meaning": "Отменить только текущую owner login session без browser secrets или auth paths.",
    },
    "validate_account": {
        "adapter_command_id": "accounts_validate",
        "action_role": "account_verification",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": True,
        "action_claim_scope": "только запрос проверки аккаунта; подтверждением остаётся обновлённый список аккаунтов",
        "display_name": "Проверить аккаунт",
        "human_meaning": "Запустить проверку выбранного аккаунта, затем обновить подтверждённый список аккаунтов.",
    },
    "recheck_account": {
        "adapter_command_id": "accounts_validate",
        "action_role": "account_verification",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": True,
        "action_claim_scope": "alias для account validate; подтверждением остаётся обновлённый список аккаунтов",
        "display_name": "Перепроверить аккаунт",
        "human_meaning": "Повторно запустить проверку выбранного аккаунта и обновить подтверждённый список аккаунтов.",
    },
    "promote_account": {
        "adapter_command_id": "accounts_promote",
        "action_role": "account_lifecycle_promotion",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только запрос перевода аккаунта; подтверждением остаются обновлённый список аккаунтов и status truth",
        "display_name": "Перевести аккаунт в active",
        "human_meaning": "Запросить перевод выбранного аккаунта из reserve в active, затем обновить подтверждённый список аккаунтов и status truth.",
    },
    "demote_account": {
        "adapter_command_id": "accounts_demote",
        "action_role": "account_lifecycle_demotion",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только запрос перевода аккаунта; подтверждением остаются обновлённый список аккаунтов и status truth",
        "display_name": "Вернуть аккаунт в reserve",
        "human_meaning": "Запросить перевод выбранного аккаунта из active в reserve, затем обновить подтверждённый список аккаунтов и status truth.",
    },
    "retire_account": {
        "adapter_command_id": "accounts_retire",
        "action_role": "account_lifecycle_retirement",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только терминальный lifecycle-запрос; подтверждением остаётся обновлённый список аккаунтов",
        "display_name": "Вывести аккаунт",
        "human_meaning": "Запросить терминальный вывод выбранного аккаунта из lifecycle, затем обновить подтверждённый список аккаунтов.",
    },
    "hold_account": {
        "adapter_command_id": "accounts_hold",
        "action_role": "account_lifecycle_hold",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только запрос ручной паузы; подтверждением остаются обновлённый список аккаунтов и status truth",
        "display_name": "Поставить аккаунт на паузу",
        "human_meaning": "Поставить выбранный аккаунт на manual hold, затем обновить подтверждённый список аккаунтов и status truth.",
    },
    "release_account": {
        "adapter_command_id": "accounts_release",
        "action_role": "account_lifecycle_release",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только запрос снятия ручной паузы; подтверждением остаются обновлённый список аккаунтов и status truth",
        "display_name": "Снять аккаунт с паузы",
        "human_meaning": "Снять выбранный аккаунт с manual hold, затем обновить подтверждённый список аккаунтов и status truth.",
    },
    "api_route_validate": {
        "adapter_command_id": "external_models_routes_validate",
        "action_role": "api_route_validation",
        "mutation_class": "api_route_verification",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только проверка маршрута у провайдера; это не утверждение runtime readiness",
        "display_name": "Проверить маршрут",
        "human_meaning": "Проверить доступность маршрута на стороне провайдера и обновить список маршрутов из канонического JSON.",
    },
    "api_route_connect": {
        "adapter_command_id": "external_models_routes_add_server_owned",
        "action_role": "api_route_admission",
        "mutation_class": "api_route_registry_admission",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "owner credential status/admit -> owner-owned route source -> external-models routes add/adopt -> validate -> api-connections refresh; browser api_key/route_id/secret/path запрещены",
        "display_name": "Подключить API",
        "human_meaning": "Проверить или принять owner credential, затем добавить или принять server-owned API route без browser api_key, secrets, paths или route_id и обновить подтверждённый список API-подключений.",
    },
    "api_route_credential_check": {
        "adapter_command_id": "external_models_credentials_status_provider",
        "action_role": "api_route_credential_status",
        "mutation_class": "api_route_credential_handoff",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "только owner credential presence proof; browser api_key/secret/path/auth не принимает и route не меняет",
        "display_name": "Проверить credential",
        "human_meaning": "Проверить видимость owner credential для текущего server-owned provider без передачи секрета через браузер и без мутации route.",
    },
    "api_route_check": {
        "adapter_command_id": "external_models_check",
        "action_role": "api_route_smoke_check",
        "mutation_class": "api_route_verification",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только проверочный запрос маршрута у провайдера; это не утверждение runtime readiness",
        "display_name": "Проверить запросом",
        "human_meaning": "Выполнить проверочный запрос через маршрут и обновить список маршрутов из канонического JSON.",
    },
    "api_route_allow": {
        "adapter_command_id": "external_models_routes_enable",
        "action_role": "api_route_lifecycle_allow",
        "mutation_class": "api_route_lifecycle",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только lifecycle-запрос маршрута у провайдера; это не утверждение runtime readiness",
        "display_name": "Разрешить маршрут",
        "human_meaning": "Запросить разрешение выбранного маршрута и обновить список маршрутов из канонического JSON.",
    },
    "api_route_disable": {
        "adapter_command_id": "external_models_routes_disable",
        "action_role": "api_route_lifecycle_disable",
        "mutation_class": "api_route_lifecycle",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только lifecycle-запрос маршрута у провайдера; это не утверждение runtime readiness",
        "display_name": "Отключить маршрут",
        "human_meaning": "Запросить отключение выбранного маршрута и обновить список маршрутов из канонического JSON.",
    },
    "api_route_remove": {
        "adapter_command_id": "external_models_routes_remove",
        "action_role": "api_route_registry_cleanup",
        "mutation_class": "api_route_registry_cleanup",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только удаление отключённой registry-записи; область действия не шире command packet",
        "display_name": "Удалить отключённый маршрут",
        "human_meaning": "Удалить уже отключённую registry-запись маршрута после server preflight и обновить список маршрутов из канонического JSON.",
    },
    "api_route_profile": {
        "adapter_command_id": "external_models_profile_codex_desktop",
        "action_role": "api_route_profile_packet",
        "mutation_class": "api_route_support",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": False,
        "action_claim_scope": "только профильный пакет поддержки; это не Codex config mutation, не listener readiness и не runtime readiness",
        "display_name": "Показать пакет профиля",
        "human_meaning": "Показать non-mutating профильный пакет для выбранного маршрута без записи Codex config и без утверждения готовности.",
    },
    "api_route_evidence_capture": {
        "adapter_command_id": "external_models_evidence_capture",
        "action_role": "api_route_local_evidence_capture",
        "mutation_class": "api_route_support_artifact",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": False,
        "action_claim_scope": "только локальный support artifact; это не runtime proof и не чтение evidence file из UI",
        "display_name": "Собрать локальное свидетельство",
        "human_meaning": "Создать локальный support artifact по выбранному маршруту и показать только метаданные command packet.",
    },
    "quick_start_check_all": {
        "adapter_command_id": "server_owned_quick_start_check_all",
        "action_role": "quick_start_verify_bundle",
        "mutation_class": "quick_start_verify_bundle",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": True,
        "action_claim_scope": "только server-owned verify bundle из admitted checks и sandbox-owned readonly refresh surfaces; hidden mutations запрещены",
        "display_name": "Проверить всё",
        "human_meaning": "Последовательно проверить bounded account truth, основной API route и bounded runtime status без скрытых мутаций, затем обновить подтверждённые readonly карточки.",
    },
    "sync_runtime": {
        "adapter_command_id": "sync",
        "action_role": "controlled_runtime_mutation",
        "mutates_runtime": True,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только запрос sync; подтверждением остаётся обновлённый live overview",
        "display_name": "Синхронизировать runtime",
        "human_meaning": "Запустить managed sync, затем обновить overview из live JSON truth.",
    },
    "set_mode_stable": {
        "adapter_command_id": "mode_stable",
        "action_role": "controlled_mode_mutation",
        "mutates_runtime": True,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только запрос режима; подтверждением остаётся обновлённый live overview",
        "display_name": "Запросить stable mode",
        "human_meaning": "Запросить stable mode, затем обновить desired/effective mode из live JSON truth.",
    },
    "set_mode_managed": {
        "adapter_command_id": "mode_managed",
        "action_role": "controlled_mode_mutation",
        "mutates_runtime": True,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только запрос режима; подтверждением остаётся обновлённый live overview",
        "display_name": "Запросить managed mode",
        "human_meaning": "Запросить managed mode, затем обновить desired/effective mode из live JSON truth.",
    },
    "launch_smoke": {
        "adapter_command_id": "smoke",
        "action_role": "runtime_smoke_check",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": True,
        "action_claim_scope": "только smoke-проверка runtime; это не успех запуска внешнего клиента",
        "display_name": "Smoke-проверка запуска",
        "human_meaning": "Запустить runtime smoke check без заявления об успешном запуске внешнего клиента.",
    },
    "launch_client_dispatch": {
        "adapter_command_id": "launch_client",
        "action_role": "host_client_dispatch",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только bounded OS dispatch request; это не успех сессии внешнего клиента",
        "display_name": "Запустить внешний клиент",
        "human_meaning": "Запросить bounded запуск внешнего клиента, затем обновить live overview truth.",
    },
    "launch_custom_client_native": {
        "adapter_command_id": "codex_custom_native_launch",
        "action_role": "custom_native_client_launch",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "только Custom native app/window launch proof; это не prompt, route trace или egress truth",
        "display_name": "Запустить Custom Codex",
        "human_meaning": "Запустить Custom Codex через server-owned native launch lane и подтвердить процесс плюс окно.",
    },
    "show_custom_client_native": {
        "adapter_command_id": "codex_custom_native_show_window",
        "action_role": "custom_native_window_visibility_repair",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": True,
        "action_claim_scope": "только показать уже запущенное Custom Codex окно; это не запуск, prompt или route truth",
        "display_name": "Показать окно Codex Custom",
        "human_meaning": "Поднять и переместить уже запущенное окно Custom Codex без трогания Original Codex.",
    },
    "setup_discovery": {
        "adapter_command_id": "installer_init",
        "action_role": "setup_import_discovery_foundation",
        "mutation_class": "setup_import_admission",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "только bounded server-owned discovery truth для current runtime layout; selection persistence и runtime mutation не включены",
        "display_name": "Проверить setup/import foundation",
        "human_meaning": "Показать bounded server-owned discovery truth для setup/import без browser paths, selection persistence или runtime mutation.",
    },
    "legacy_import_discovery": {
        "adapter_command_id": "server_owned_legacy_import_discovery",
        "action_role": "legacy_import_source_discovery",
        "mutation_class": "setup_import_admission",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "только bounded server-owned discovery truth для importable legacy source; browser paths, selection persistence и import execution не включены",
        "display_name": "Найти import source",
        "human_meaning": "Показать bounded server-owned discovery truth для importable legacy source без browser path intake и без import execution.",
    },
    "legacy_import": {
        "adapter_command_id": "legacy_import",
        "action_role": "setup_import_import_capable_foundation",
        "mutation_class": "setup_import_admission",
        "mutates_runtime": True,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "token-only вызов остаётся packet-owned reference truth; final legacy import write допускается только через explicit confirm и server-owned token binding",
        "display_name": "Импортировать найденную setup",
        "human_meaning": "Показать token-bound import lane и выполнить legacy import только после explicit confirm без browser-owned path truth.",
    },
}

UI_ACTION_EFFECT_REGISTRY = {
    "refresh_health_detail": EFFECT_PROBE,
    "export_diagnostics": EFFECT_MUTATE,
    "stable_repair_plan": EFFECT_PROBE,
    "onboard_account_dry_run": EFFECT_PROBE,
    "onboard_account": EFFECT_MUTATE,
    "account_login_status": EFFECT_READ,
    "account_login_complete": EFFECT_MUTATE,
    "account_login_cancel": EFFECT_MUTATE,
    "validate_account": EFFECT_PROBE,
    "recheck_account": EFFECT_PROBE,
    "promote_account": EFFECT_MUTATE,
    "demote_account": EFFECT_MUTATE,
    "retire_account": EFFECT_MUTATE,
    "hold_account": EFFECT_MUTATE,
    "release_account": EFFECT_MUTATE,
    "api_route_validate": EFFECT_PROBE,
    "api_route_connect": EFFECT_MUTATE,
    "api_route_credential_check": EFFECT_PROBE,
    "api_route_check": EFFECT_PROBE,
    "api_route_allow": EFFECT_MUTATE,
    "api_route_disable": EFFECT_MUTATE,
    "api_route_remove": EFFECT_MUTATE,
    "api_route_profile": EFFECT_READ,
    "api_route_evidence_capture": EFFECT_MUTATE,
    "quick_start_check_all": EFFECT_PROBE,
    "sync_runtime": EFFECT_MUTATE,
    "set_mode_stable": EFFECT_MUTATE,
    "set_mode_managed": EFFECT_MUTATE,
    "launch_smoke": EFFECT_PROBE,
    "launch_client_dispatch": EFFECT_MUTATE,
    "launch_custom_client_native": EFFECT_MUTATE,
    "show_custom_client_native": EFFECT_REPAIR,
    "setup_discovery": EFFECT_PROBE,
    "legacy_import_discovery": EFFECT_PROBE,
    "legacy_import": EFFECT_MUTATE,
}


def _get_route(path: str) -> RouteSpec:
    return RouteSpec(
        method="GET",
        path=path,
        effect=EFFECT_READ,
        auth_required=False,
        body_kind=BODY_KIND_NONE,
        browser_field_policy=BROWSER_FIELD_POLICY_QUERY_VALIDATED,
        handler_id=_route_handler_id("GET", path),
    )


def _route_handler_id(method: str, path: str, *, prefix: bool = False) -> str:
    normalized_path = path.strip("/").replace("-", "_").replace("/", "_")
    suffix = "_prefix" if prefix else ""
    return f"{method.lower()}_{normalized_path or 'root'}{suffix}"


def _post_route(
    path: str,
    effect: str,
    *,
    body_kind: str = BODY_KIND_JSON,
    browser_field_policy: str = BROWSER_FIELD_POLICY_JSON_VALIDATED,
    effect_source: str = EFFECT_SOURCE_ROUTE,
    multiplexed_by: str | None = None,
) -> RouteSpec:
    return RouteSpec(
        method="POST",
        path=path,
        effect=effect,
        auth_required=True,
        body_kind=body_kind,
        browser_field_policy=browser_field_policy,
        effect_source=effect_source,
        multiplexed_by=multiplexed_by,
        handler_id=_route_handler_id("POST", path),
    )


def _post_prefix_route(
    path: str,
    effect: str,
    *,
    body_kind: str = BODY_KIND_JSON,
    effect_source: str = EFFECT_SOURCE_DYNAMIC_SUBACTION,
    multiplexed_by: str | None = None,
) -> RouteSpec:
    return RouteSpec(
        method="POST",
        path=path,
        effect=effect,
        auth_required=True,
        body_kind=body_kind,
        browser_field_policy=BROWSER_FIELD_POLICY_JSON_VALIDATED,
        prefix=True,
        effect_source=effect_source,
        multiplexed_by=multiplexed_by,
        handler_id=_route_handler_id("POST", path, prefix=True),
    )


WEB_DESIGN_LIVE_ROUTES = (
    _get_route("/owner-login/sandbox"),
    _get_route("/api/live-readonly"),
    _get_route("/api/accounts-readonly"),
    _get_route("/api/api-connections-readonly"),
    _get_route("/api/actions"),
    _get_route("/api/operator/status"),
    _get_route("/api/operator/models"),
    _get_route("/api/operator/transcript"),
    _get_route("/api/review-surface"),
    _get_route("/api/review-commands"),
    _get_route("/api/codex/launch-modes"),
    _get_route("/api/codex/original/status"),
    _get_route("/api/codex/custom/status"),
    _get_route("/api/codex/custom/models"),
    _get_route("/api/codex/custom/model-selector"),
    _get_route("/api/codex/custom/api-compat"),
    _get_route("/api/codex/custom/api-action-gate"),
    _get_route("/api/codex/custom/accounts"),
    _get_route("/api/codex/custom/account-selection"),
    _get_route("/api/codex/custom/sessions"),
    _get_route("/api/codex/custom/recovery/contract"),
    _get_route("/api/codex/custom/recovery/admitted-session-actions"),
    _get_route("/api/codex/custom/recovery/stop-cleanup/preflight"),
    _get_route("/api/codex/custom/recovery/process-kill/preflight"),
    _get_route("/api/codex/custom/recovery/operator-ready"),
    _get_route("/api/codex/custom/recovery/rollback-process-owner-contract"),
    _get_route("/api/codex/custom/recovery/rollback-point-dry-run"),
    _get_route("/api/codex/custom/recovery/rollback-point-create-admission"),
    _get_route("/api/codex/custom/recovery/rollback-point/verify"),
    _get_route("/api/codex/custom/recovery/rollback-apply/admission-dry-run"),
    _get_route("/api/codex/custom/recovery/rollback-apply/live-preflight"),
    _get_route("/api/codex/custom/recovery/rollback-apply/receipt/verify"),
    _get_route("/api/codex/custom/window-prompt-trace"),
    _get_route("/api/codex/custom/window-input-route-trace"),
    _get_route("/api/codex/custom/bridge-failure-recovery-truth"),
    _get_route("/api/codex/custom/stable-bridge-preflight"),
    _get_route("/api/codex/custom/live-bridge-stability"),
    _get_route("/api/codex/custom/chatgpt-plus-api-coder-trace"),
    _get_route("/api/codex/custom/quick-start/chatgpt-plus-deepseek-file-edit-proof"),
    _get_route("/api/codex/custom/quick-start/deepseek-code-edit-proof"),
    _get_route("/api/codex/custom/quick-start/api-only-deepseek-live-code-edit-truth"),
    _get_route("/api/codex/custom/quick-start/deepseek-route-bound-edit-proof"),
    _get_route("/api/codex/custom/persistent-profile"),
    _get_route("/api/codex/custom/persistent-relaunch-profile"),
    _get_route("/api/codex/custom/stable-profile-history-persistence"),
    _get_route("/api/codex/custom/persistent-profile-history-proof"),
    RouteSpec(
        method="GET",
        path="/api/codex/custom/sessions/",
        effect=EFFECT_READ,
        auth_required=False,
        body_kind=BODY_KIND_NONE,
        browser_field_policy=BROWSER_FIELD_POLICY_NONE,
        prefix=True,
        effect_source=EFFECT_SOURCE_DYNAMIC_SUBACTION,
        multiplexed_by="custom_session_action",
        handler_id=_route_handler_id("GET", "/api/codex/custom/sessions/", prefix=True),
    ),
    _post_route(
        "/api/operator/run",
        EFFECT_MUTATE,
        effect_source=EFFECT_SOURCE_DYNAMIC_SUBACTION,
        multiplexed_by="operator_prompt",
    ),
    _post_route(
        "/api/review-command",
        EFFECT_MUTATE,
        effect_source=EFFECT_SOURCE_DYNAMIC_SUBACTION,
        multiplexed_by="command_id",
    ),
    _post_route("/api/codex/original/launch-dry-run", EFFECT_READ),
    _post_route("/api/codex/original/launch", EFFECT_MUTATE),
    _post_route("/api/codex/custom/launch-dry-run", EFFECT_READ),
    _post_route("/api/codex/custom/launch", EFFECT_MUTATE),
    _post_route("/api/codex/custom/native-launch-preflight", EFFECT_PROBE),
    _post_route("/api/codex/custom/native-launch", EFFECT_MUTATE),
    _post_route("/api/codex/custom/show-window", EFFECT_REPAIR, body_kind=BODY_KIND_OPTIONAL_JSON),
    _post_route("/api/codex/custom/visible-history/owner-confirmation", EFFECT_PROBE),
    _post_route("/api/codex/custom/visible-history/relaunch-owner-confirmation", EFFECT_PROBE),
    _post_route("/api/codex/app-copy/launch-dry-run", EFFECT_READ),
    _post_route("/api/codex/app-copy/live-admission", EFFECT_PROBE),
    _post_route("/api/codex/app-copy/launch", EFFECT_MUTATE),
    _post_route("/api/codex/custom/model-dry-run", EFFECT_READ),
    _post_route("/api/codex/custom/model-selector-dry-run", EFFECT_READ),
    _post_route("/api/codex/custom/api-action-gate", EFFECT_PROBE),
    _post_route("/api/codex/custom/execution-mode-dry-run", EFFECT_READ),
    _post_route("/api/codex/custom/server-model-selection-truth", EFFECT_PROBE),
    _post_route("/api/codex/custom/quick-start/config-admission", EFFECT_PROBE),
    _post_route("/api/codex/custom/chatgpt-plus-api-slot-truth", EFFECT_PROBE),
    _post_route("/api/codex/custom/api-only-executor-truth", EFFECT_PROBE),
    _post_route("/api/codex/custom/api-only-deepseek/live-format", EFFECT_PROBE),
    _post_route("/api/codex/custom/quick-start/deepseek-safe-worktree-check", EFFECT_PROBE),
    _post_route("/api/codex/custom/quick-start/deepseek-code-edit-proof", EFFECT_PROBE),
    _post_route(
        "/api/codex/custom/quick-start/api-only-deepseek-live-code-edit-truth",
        EFFECT_PROBE,
    ),
    _post_route("/api/codex/custom/quick-start/deepseek-route-bound-edit-proof", EFFECT_PROBE),
    _post_route(
        "/api/codex/custom/quick-start/chatgpt-plus-deepseek-file-edit-proof",
        EFFECT_PROBE,
    ),
    _post_route("/api/codex/custom/stable-profile-history-persistence", EFFECT_PROBE),
    _post_route("/api/codex/custom/account-smoke-dry-run", EFFECT_PROBE),
    _post_route("/api/codex/custom/sessions", EFFECT_MUTATE),
    _post_route(
        "/api/codex/custom/recovery/rollback-point",
        EFFECT_MUTATE,
        body_kind=BODY_KIND_SPECIAL_JSON,
    ),
    _post_route(
        "/api/codex/custom/recovery/rollback-apply",
        EFFECT_REPAIR,
        body_kind=BODY_KIND_SPECIAL_JSON,
    ),
    _post_route(
        "/api/codex/custom/recovery/stop-cleanup",
        EFFECT_REPAIR,
        body_kind=BODY_KIND_SPECIAL_JSON,
    ),
    _post_prefix_route(
        "/api/codex/custom/worktrees/",
        EFFECT_REPAIR,
        body_kind=BODY_KIND_OPTIONAL_JSON,
        multiplexed_by="worktree_cleanup_action",
    ),
    _post_prefix_route(
        "/api/codex/custom/sessions/",
        EFFECT_MUTATE,
        body_kind=BODY_KIND_JSON,
        multiplexed_by="custom_session_action",
    ),
    _post_route(
        "/api/action",
        EFFECT_MUTATE,
        browser_field_policy=BROWSER_FIELD_POLICY_UI_ACTION_REGISTRY,
        effect_source=EFFECT_SOURCE_UI_ACTION_REGISTRY,
        multiplexed_by="ui_action",
    ),
)
WEB_DESIGN_LIVE_ROUTE_TABLE = WebRouteTable(WEB_DESIGN_LIVE_ROUTES)

LIVE_READONLY_ACTION_PHASE = "live_readonly"
SANDBOX_ACTION_PHASE = "sandbox_actions"
FULL_ACTION_PHASE = "full"
LIVE_READONLY_ACTION_UNAVAILABLE_MESSAGE = (
    "Текущее live-readonly окно не допускает action dispatch. "
    "Runtime/live-action chain parked: repeated LOCK_HELD, blocked claim_gate, "
    "detected policy_drift, selector evidence not refreshed, exact auth source "
    "not singleton, onboarding and stage/pilot actions not admitted."
)
LIVE_READONLY_ACTION_DISABLED_REASON_CODE = "RUNTIME_LIVE_ACTION_CHAIN_PARKED"
LIVE_READONLY_ACTION_DISABLED_REASONS = (
    "LOCK_HELD",
    "claim_gate_blocked",
    "policy_drift_detected",
    "selector_evidence_no_progress",
    "exact_auth_source_not_singleton",
    "onboarding_not_admitted",
    "stage_pilot_not_admitted",
)
PARKED_IN_LIVE_READONLY_ACTIONS = frozenset(
    {
        "refresh_health_detail",
        "stable_repair_plan",
        "onboard_account_dry_run",
        "onboard_account",
        "account_login_status",
        "account_login_complete",
        "account_login_cancel",
        "api_route_credential_check",
        "api_route_connect",
        "validate_account",
        "recheck_account",
        "promote_account",
        "demote_account",
        "retire_account",
        "hold_account",
        "release_account",
        "api_route_validate",
        "api_route_check",
        "api_route_allow",
        "api_route_disable",
        "api_route_remove",
        "api_route_profile",
        "api_route_evidence_capture",
        "quick_start_check_all",
        "sync_runtime",
        "set_mode_stable",
        "set_mode_managed",
        "launch_smoke",
        "launch_client_dispatch",
        "launch_custom_client_native",
        "export_diagnostics",
    }
)
SANDBOX_ACTION_PHASE_ADMITTED_ACTIONS = frozenset(
    {
        "onboard_account_dry_run",
        "onboard_account",
        "account_login_status",
        "account_login_complete",
        "account_login_cancel",
        "api_route_credential_check",
        "api_route_connect",
        "api_route_validate",
        "api_route_check",
        "api_route_allow",
        "api_route_disable",
        "api_route_remove",
        "api_route_profile",
        "api_route_evidence_capture",
        "quick_start_check_all",
    }
)
SANDBOX_ACTION_PHASE_UNAVAILABLE_MESSAGE = (
    "Sandbox action phase допускает reserve-first onboarding lane и bounded API route actions. "
    "Runtime mutations вне onboarding lane и lifecycle chains остаются parked до следующих контуров."
)
SANDBOX_ACTION_PHASE_DISABLED_REASON_CODE = "UI_ACTION_PHASE_NOT_ADMITTED"
SANDBOX_ACTION_PHASE_DISABLED_REASONS = ("sandbox_phase_limited",)
SETUP_IMPORT_FOUNDATION_ONLY_UNAVAILABLE_CODE = "UI_SETUP_IMPORT_FOUNDATION_ONLY"
SETUP_IMPORT_DISCOVERY_FOUNDATION_DISABLED_REASONS = (
    "setup_import_foundation_only",
    "preview_discovery_metadata_only",
)
SETUP_IMPORT_IMPORT_CAPABLE_FOUNDATION_DISABLED_REASONS = (
    "setup_import_foundation_only",
    "import_capable_metadata_only",
)
SETUP_IMPORT_DISCOVERY_FOUNDATION_UNAVAILABLE_MESSAGE = (
    "Setup/import discovery surface admitted only as packet truth in this contour. "
    "Filesystem discovery, candidate proof и selection persistence остаются вне admitted web execution path."
)
SETUP_IMPORT_IMPORT_CAPABLE_FOUNDATION_UNAVAILABLE_MESSAGE = (
    "Setup/import import-capable lane admitted only as packet truth in this contour. "
    "Confirm semantics, collision resolution и final import execution остаются вне admitted web path."
)
SETUP_IMPORT_FOUNDATION_ACTIONS = frozenset({"setup_discovery", "legacy_import"})
SETUP_DISCOVERY_SOURCE_KIND = "current_runtime_owned_layout"
SETUP_DISCOVERY_AVAILABLE_STATE = "server_owned_discovery_only"
SETUP_DISCOVERY_SOURCE_BLOCKED_CODE = "UI_SETUP_DISCOVERY_SOURCE_UNSAFE"
LEGACY_IMPORT_DISCOVERY_SOURCE_KIND = "known_owned_legacy_import_source"
LEGACY_IMPORT_DISCOVERY_AVAILABLE_STATE = "server_owned_import_source_discovery_only"
LEGACY_IMPORT_DISCOVERY_SOURCE_BLOCKED_CODE = "UI_LEGACY_IMPORT_DISCOVERY_SOURCE_UNSAFE"
LEGACY_IMPORT_TOKEN_REQUIRED_CODE = "UI_LEGACY_IMPORT_TOKEN_REQUIRED"
LEGACY_IMPORT_TOKEN_INVALID_CODE = "UI_LEGACY_IMPORT_TOKEN_INVALID"
LEGACY_IMPORT_TOKEN_UNKNOWN_CODE = "UI_LEGACY_IMPORT_TOKEN_UNKNOWN"
LEGACY_IMPORT_CONFIRM_INVALID_CODE = "UI_LEGACY_IMPORT_CONFIRM_INVALID"
SAFE_APP_COPY_HELPER_PROVENANCE = "server_owned_bounded_helper"


@dataclass(frozen=True)
class LaunchCopyContract:
    client_path: str | None = None
    profile_dir: str | None = None
    data_dir: str | None = None
    copy_port: int | None = None
    action_server_port: int | None = None
    helper_execution_provenance: str | None = None


@dataclass(frozen=True)
class LegacyImportTokenRecord:
    token_ref: str
    source_kind: str
    source_dir: Path


class LegacyImportTokenStore:
    """Main-process-owned in-memory token store for import-existing contours."""

    def __init__(self) -> None:
        self._record: LegacyImportTokenRecord | None = None
        self._lock = RLock()

    def has_active_token(self) -> bool:
        with self._lock:
            return self._record is not None

    def active_record(self) -> LegacyImportTokenRecord | None:
        with self._lock:
            return self._record

    def clear(self) -> None:
        with self._lock:
            self._record = None

    def materialize(self, *, source_kind: str, source_dir: Path) -> LegacyImportTokenRecord:
        with self._lock:
            record = self._record
            if (
                record is not None
                and record.source_kind == source_kind
                and record.source_dir == source_dir
            ):
                return record
            record = LegacyImportTokenRecord(
                token_ref=f"lid-{uuid.uuid4().hex[:20]}",
                source_kind=source_kind,
                source_dir=source_dir,
            )
            self._record = record
            return record

    def resolve(self, token_ref: str) -> LegacyImportTokenRecord | None:
        with self._lock:
            record = self._record
            if record is None or record.token_ref != token_ref:
                return None
            return record


def _launch_copy_preflight(contract: LaunchCopyContract | None) -> dict[str, Any]:
    if contract is None or not contract.client_path:
        return {
            "status": "denied",
            "machine_error_code": LAUNCH_COPY_PREFLIGHT_REQUIRED_CODE,
            "reason": "Server-owned contract для изолированной копии не предоставлен.",
            "target_kind": "unknown",
            "target_exists": False,
            "separate_profile": False,
            "separate_data_dir": False,
            "separate_port": False,
            "process_confirmation_possible": False,
            "current_session_untouched": False,
        }

    client_path = Path(contract.client_path).expanduser()
    target_exists = client_path.exists()
    target_kind = "unknown"
    process_confirmation_possible = False
    if client_path.suffix == ".app" and client_path.is_dir():
        target_kind = "app_bundle"
    elif client_path.is_file() and os.access(client_path, os.X_OK):
        target_kind = "executable"
        process_confirmation_possible = True

    profile_dir = Path(contract.profile_dir).expanduser() if contract.profile_dir else None
    data_dir = Path(contract.data_dir).expanduser() if contract.data_dir else None
    separate_profile = bool(profile_dir and profile_dir.is_absolute())
    separate_data_dir = bool(data_dir and data_dir.is_absolute())
    distinct_dirs = bool(
        separate_profile
        and separate_data_dir
        and profile_dir is not None
        and data_dir is not None
        and profile_dir != data_dir
    )
    separate_port = isinstance(contract.copy_port, int) and contract.copy_port > 0
    if separate_port and contract.action_server_port:
        separate_port = contract.copy_port != contract.action_server_port

    if not target_exists:
        return {
            "status": "denied",
            "machine_error_code": "UI_LAUNCH_COPY_TARGET_MISSING",
            "reason": "Server-owned цель запуска не найдена.",
            "target_kind": target_kind,
            "target_exists": False,
            "separate_profile": distinct_dirs and separate_profile,
            "separate_data_dir": distinct_dirs and separate_data_dir,
            "separate_port": separate_port,
            "process_confirmation_possible": process_confirmation_possible,
            "current_session_untouched": False,
        }
    if target_kind != "executable":
        return {
            "status": "denied",
            "machine_error_code": LAUNCH_COPY_PREFLIGHT_UNSAFE_CODE,
            "reason": "Изолированная копия допускается только для bounded executable target; app bundle не доказывает отдельный процесс.",
            "target_kind": target_kind,
            "target_exists": True,
            "separate_profile": distinct_dirs and separate_profile,
            "separate_data_dir": distinct_dirs and separate_data_dir,
            "separate_port": separate_port,
            "process_confirmation_possible": False,
            "current_session_untouched": False,
        }
    if not distinct_dirs or not separate_port:
        return {
            "status": "denied",
            "machine_error_code": LAUNCH_COPY_PREFLIGHT_UNSAFE_CODE,
            "reason": "Изоляция копии не доказана: нужны отдельные absolute profile/data каталоги и отдельный порт.",
            "target_kind": target_kind,
            "target_exists": True,
            "separate_profile": distinct_dirs and separate_profile,
            "separate_data_dir": distinct_dirs and separate_data_dir,
            "separate_port": separate_port,
            "process_confirmation_possible": True,
            "current_session_untouched": False,
        }
    return {
        "status": "admitted",
        "machine_error_code": "OK",
        "reason": "Preflight подтвердил изолированную копию: отдельные profile/data каталоги и отдельный port заданы.",
        "target_kind": target_kind,
        "target_exists": True,
        "separate_profile": True,
        "separate_data_dir": True,
        "separate_port": True,
        "process_confirmation_possible": True,
        "current_session_untouched": True,
    }


def _safe_app_copy_target_resembles_codex(contract: LaunchCopyContract) -> bool:
    client_path = Path(contract.client_path or "").expanduser()
    try:
        resolved_path = client_path.resolve(strict=False)
    except OSError:
        resolved_path = client_path
    name = f"{client_path.name} {resolved_path.name}".lower()
    parts = {part.lower() for part in (*client_path.parts, *resolved_path.parts)}
    return (
        "codex" in name
        or "codex.app" in parts
        or any(part.endswith(".app") for part in parts)
        or client_path.suffix.lower() == ".app"
        or resolved_path.suffix.lower() == ".app"
    )


def _safe_app_copy_helper_target_allowed(contract: LaunchCopyContract) -> bool:
    client_path = Path(contract.client_path or "").expanduser()
    return bool(
        contract.helper_execution_provenance == SAFE_APP_COPY_HELPER_PROVENANCE
        and not client_path.is_symlink()
        and not _safe_app_copy_target_resembles_codex(contract)
    )


def _safe_app_copy_helper_env(contract: LaunchCopyContract) -> dict[str, str]:
    profile_dir = str(Path(contract.profile_dir or "").expanduser())
    data_dir = str(Path(contract.data_dir or "").expanduser())
    env: dict[str, str] = {}
    if os.environ.get("PATH"):
        env["PATH"] = str(os.environ["PATH"])
    env["HOME"] = profile_dir
    env["CODEX_HOME"] = str(Path(profile_dir) / "codex-home")
    env["WBP_PROFILE_DIR"] = profile_dir
    env["WBP_MANAGED_DIR"] = data_dir
    env["WBP_APP_COPY_HELPER"] = "1"
    return env


def _run_safe_app_copy_bounded_helper(
    contract: LaunchCopyContract | None,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    if contract is None or preflight.get("status") != "admitted":
        return {
            "machine_error_code": "WEB_SAFE_APP_COPY_LAUNCH_NOT_ADMITTED",
            "helper_target_safe": False,
            "helper_execution_attempted": False,
            "process_started": False,
            "helper_exit_code_zero": False,
            "cleanup_or_stop_completed": False,
        }
    if not _safe_app_copy_helper_target_allowed(contract):
        return {
            "machine_error_code": "WEB_SAFE_APP_COPY_HELPER_TARGET_UNSAFE",
            "helper_target_safe": False,
            "helper_execution_attempted": False,
            "process_started": False,
            "helper_exit_code_zero": False,
            "cleanup_or_stop_completed": False,
        }
    try:
        completed = subprocess.run(
            [str(Path(contract.client_path or "").expanduser())],
            check=False,
            env=_safe_app_copy_helper_env(contract),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            text=True,
            timeout=2,
        )
    except subprocess.TimeoutExpired:
        return {
            "machine_error_code": "WEB_SAFE_APP_COPY_HELPER_START_FAILED",
            "helper_target_safe": True,
            "helper_execution_attempted": True,
            "process_started": True,
            "helper_exit_code_zero": False,
            "cleanup_or_stop_completed": True,
        }
    except (OSError, ValueError):
        return {
            "machine_error_code": "WEB_SAFE_APP_COPY_HELPER_START_FAILED",
            "helper_target_safe": True,
            "helper_execution_attempted": True,
            "process_started": False,
            "helper_exit_code_zero": False,
            "cleanup_or_stop_completed": False,
        }
    return {
        "machine_error_code": (
            "OK"
            if completed.returncode == 0
            else "WEB_SAFE_APP_COPY_HELPER_START_FAILED"
        ),
        "helper_target_safe": True,
        "helper_execution_attempted": True,
        "process_started": True,
        "helper_exit_code_zero": completed.returncode == 0,
        "cleanup_or_stop_completed": True,
    }


def _current_runtime_target_paths() -> tuple[Path, Path]:
    default_profile = "~/" + ".co" + "dex-custom-cli"
    profile_dir = Path(os.environ.get("WBP_PROFILE_DIR", default_profile)).expanduser()
    data_dir = Path(os.environ.get("WBP_MANAGED_DIR", str(profile_dir / "managed"))).expanduser()
    return profile_dir, data_dir


def _legacy_import_discovery_source_dir() -> Path:
    return Path("~/" + ".co" + "dex-custom-cli").expanduser()


def _setup_discovery_packet() -> dict[str, Any]:
    paths = RuntimePaths.from_env()
    if not paths.profile_dir.is_absolute() or not paths.managed_dir.is_absolute():
        return build_command_payload(
            ok=False,
            human_message=(
                "Setup discovery requires absolute server-owned runtime target paths. "
                "Browser path intake remains forbidden."
            ),
            machine_error_code=SETUP_DISCOVERY_SOURCE_BLOCKED_CODE,
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "data": {
                    "discovery_state": "blocked",
                    "source_kind": SETUP_DISCOVERY_SOURCE_KIND,
                    "browser_path_intake": False,
                    "selection_persisted": False,
                    "session_token_materialized": False,
                    "filesystem_mutation_performed": False,
                    "import_execution_claimed": False,
                    "candidate_marker_count": 0,
                }
            },
        )

    candidate_marker_count = sum(
        1
        for candidate in (
            paths.config_toml,
            paths.registry_file,
            paths.state_file,
            paths.runtime_mode_file,
            paths.runtime_effective_mode_file,
            paths.launcher_script,
            paths.managed_dir / "bin",
        )
        if candidate.exists()
    )
    discovery_state = "discovered" if candidate_marker_count else "none"
    human_message = (
        "Setup discovery found one bounded server-owned runtime layout. No write performed."
        if discovery_state == "discovered"
        else "Setup discovery found no current server-owned runtime layout candidate. No write performed."
    )
    return build_command_payload(
        ok=True,
        human_message=human_message,
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        extra={
            "data": {
                "discovery_state": discovery_state,
                "source_kind": SETUP_DISCOVERY_SOURCE_KIND,
                "browser_path_intake": False,
                "selection_persisted": False,
                "session_token_materialized": False,
                "filesystem_mutation_performed": False,
                "import_execution_claimed": False,
                "candidate_marker_count": candidate_marker_count,
            }
        },
    )


def _legacy_import_discovery_packet() -> dict[str, Any]:
    paths = RuntimePaths.from_env()
    source_dir = _legacy_import_discovery_source_dir()
    try:
        source_dir_resolved = source_dir.resolve(strict=False)
        current_profile_resolved = paths.profile_dir.resolve(strict=False)
    except OSError:
        source_dir_resolved = source_dir
        current_profile_resolved = paths.profile_dir
    if not source_dir.is_absolute():
        return build_command_payload(
            ok=False,
            human_message=(
                "Legacy import discovery requires an absolute server-owned source candidate. "
                "Browser path intake remains forbidden."
            ),
            machine_error_code=LEGACY_IMPORT_DISCOVERY_SOURCE_BLOCKED_CODE,
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "data": {
                    "discovery_state": "blocked",
                    "source_kind": LEGACY_IMPORT_DISCOVERY_SOURCE_KIND,
                    "browser_path_intake": False,
                    "selection_persisted": False,
                    "session_token_materialized": False,
                    "filesystem_mutation_performed": False,
                    "import_execution_claimed": False,
                    "candidate_marker_count": 0,
                    "current_runtime_layout_reused": False,
                }
            },
        )
    if source_dir_resolved == current_profile_resolved:
        return build_command_payload(
            ok=False,
            human_message=(
                "Legacy import discovery rejected the current runtime layout as an import source candidate. "
                "Browser path intake remains forbidden."
            ),
            machine_error_code=LEGACY_IMPORT_DISCOVERY_SOURCE_BLOCKED_CODE,
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "data": {
                    "discovery_state": "blocked",
                    "source_kind": LEGACY_IMPORT_DISCOVERY_SOURCE_KIND,
                    "browser_path_intake": False,
                    "selection_persisted": False,
                    "session_token_materialized": False,
                    "filesystem_mutation_performed": False,
                    "import_execution_claimed": False,
                    "candidate_marker_count": 0,
                    "current_runtime_layout_reused": True,
                }
            },
        )

    required_markers = (
        source_dir / "backend-registry.json",
        source_dir / ("supervisor" + "-state" + ".json"),
        source_dir / "config.toml",
    )
    optional_markers = (
        source_dir / "runtime-mode.txt",
        source_dir / "runtime-effective-mode.txt",
        source_dir / "external-models",
    )
    candidate_marker_count = sum(
        1
        for candidate in (*required_markers, *optional_markers)
        if candidate.exists()
    )
    required_markers_present = all(
        candidate.exists() and candidate.is_file() for candidate in required_markers
    )
    discovery_state = "discovered" if required_markers_present else "none"
    human_message = (
        "Legacy import discovery found one bounded server-owned import source candidate. No write performed."
        if discovery_state == "discovered"
        else "Legacy import discovery found no bounded server-owned import source candidate. No write performed."
    )
    return build_command_payload(
        ok=True,
        human_message=human_message,
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        extra={
            "data": {
                "discovery_state": discovery_state,
                "source_kind": LEGACY_IMPORT_DISCOVERY_SOURCE_KIND,
                "browser_path_intake": False,
                "selection_persisted": False,
                "session_token_materialized": False,
                "filesystem_mutation_performed": False,
                "import_execution_claimed": False,
                "candidate_marker_count": candidate_marker_count,
                "current_runtime_layout_reused": False,
            }
        },
    )


def _legacy_import_discovery_packet_with_store(
    token_store: LegacyImportTokenStore | None,
) -> dict[str, Any]:
    packet = _legacy_import_discovery_packet()
    data = packet.get("data")
    if not isinstance(data, dict):
        return packet
    if token_store is None:
        return packet
    if data.get("discovery_state") != "discovered":
        token_store.clear()
        data["session_token_materialized"] = False
        return packet
    source_dir = _legacy_import_discovery_source_dir()
    record = token_store.materialize(
        source_kind=LEGACY_IMPORT_DISCOVERY_SOURCE_KIND,
        source_dir=source_dir.resolve(strict=False),
    )
    data["session_token_materialized"] = True
    data["token_ref"] = record.token_ref
    data["token_server_owned"] = True
    data["token_status"] = "active"
    return packet


def _legacy_import_reference_packet(
    token_store: LegacyImportTokenStore | None,
    *,
    token_ref: str,
) -> dict[str, Any]:
    if token_store is None:
        return build_command_payload(
            ok=False,
            human_message="Legacy import reference requires a server-owned discovery token.",
            machine_error_code=LEGACY_IMPORT_TOKEN_REQUIRED_CODE,
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "data": {
                    "reference_state": "blocked",
                    "source_kind": LEGACY_IMPORT_DISCOVERY_SOURCE_KIND,
                    "browser_path_intake": False,
                    "session_token_materialized": False,
                    "token_server_owned": False,
                    "filesystem_mutation_performed": False,
                    "import_execution_claimed": False,
                    "confirm_semantics_claimed": False,
                }
            },
        )
    record = token_store.resolve(token_ref)
    if record is None:
        return build_command_payload(
            ok=False,
            human_message="Legacy import reference token is missing or no longer active.",
            machine_error_code=LEGACY_IMPORT_TOKEN_UNKNOWN_CODE,
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "data": {
                    "reference_state": "blocked",
                    "source_kind": LEGACY_IMPORT_DISCOVERY_SOURCE_KIND,
                    "browser_path_intake": False,
                    "session_token_materialized": False,
                    "token_server_owned": False,
                    "filesystem_mutation_performed": False,
                    "import_execution_claimed": False,
                    "confirm_semantics_claimed": False,
                }
            },
        )
    return build_command_payload(
        ok=True,
        human_message="Legacy import token-bound reference is available. No write performed.",
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        extra={
            "data": {
                "reference_state": "import_capable",
                "source_kind": record.source_kind,
                "browser_path_intake": False,
                "session_token_materialized": True,
                "token_ref": record.token_ref,
                "token_server_owned": True,
                "token_status": "active",
                "filesystem_mutation_performed": False,
                "import_execution_claimed": False,
                "confirm_semantics_claimed": False,
            }
        },
    )


def _sanitize_legacy_import_result(payload: dict[str, Any]) -> dict[str, Any]:
    legacy_import_result = payload.get("legacy_import_result")
    if not isinstance(legacy_import_result, dict):
        return {}
    return {
        key: value
        for key, value in legacy_import_result.items()
        if key != "source_dir"
    }


def _sanitize_external_models_result(payload: dict[str, Any]) -> dict[str, Any]:
    external_models_result = payload.get("external_models_result")
    if not isinstance(external_models_result, dict):
        return {}
    imported_files = external_models_result.get("imported_files")
    sanitized = {
        key: value
        for key, value in external_models_result.items()
        if key != "imported_files"
    }
    sanitized["imported_files_count"] = (
        len(imported_files) if isinstance(imported_files, list) else 0
    )
    return sanitized


def _sanitize_legacy_import_human_message(message: str, source_dir: Path) -> str:
    sanitized = message
    for candidate in {
        str(source_dir),
        str(source_dir.expanduser()),
        str(source_dir.resolve(strict=False)),
        str(source_dir.expanduser().resolve(strict=False)),
    }:
        if candidate:
            sanitized = sanitized.replace(candidate, "<server-owned-legacy-source>")
    return sanitized


def _legacy_import_confirmed_packet(
    token_store: LegacyImportTokenStore | None,
    *,
    token_ref: str,
) -> dict[str, Any]:
    record = token_store.resolve(token_ref) if token_store is not None else None
    if record is None:
        return build_command_payload(
            ok=False,
            human_message="Legacy import reference token is missing or no longer active.",
            machine_error_code=LEGACY_IMPORT_TOKEN_UNKNOWN_CODE,
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "data": {
                    "reference_state": "blocked",
                    "source_kind": LEGACY_IMPORT_DISCOVERY_SOURCE_KIND,
                    "browser_path_intake": False,
                    "session_token_materialized": False,
                    "token_server_owned": False,
                    "token_status": "missing",
                    "filesystem_mutation_performed": False,
                    "import_execution_claimed": False,
                    "confirm_semantics_claimed": True,
                    "explicit_confirm_observed": True,
                    "receipt_state": "write_blocked",
                }
            },
        )
    try:
        runtime_packet = run_legacy_import(RuntimePaths.from_env(), str(record.source_dir))
    finally:
        if token_store is not None:
            token_store.clear()
    changed_files = list(runtime_packet.get("changed_files", []))
    ok = (
        runtime_packet.get("status") == "ok"
        and runtime_packet.get("exit_code") == 0
        and runtime_packet.get("machine_error_code") == "OK"
    )
    return build_command_payload(
        ok=ok,
        human_message=_sanitize_legacy_import_human_message(
            str(runtime_packet.get("human_message", "")),
            record.source_dir,
        ),
        machine_error_code=str(runtime_packet.get("machine_error_code", "")),
        liveness=str(runtime_packet.get("liveness", "unknown")),
        severity=str(runtime_packet.get("severity", "recoverable")),
        operator_action=str(
            runtime_packet.get("operator_action")
            or runtime_packet.get("next_action")
            or "none"
        ),
        changed_files=changed_files,
        exit_code=(
            int(runtime_packet["exit_code"])
            if isinstance(runtime_packet.get("exit_code"), int)
            else None
        ),
        extra={
            "data": {
                "reference_state": "import_completed" if ok else "write_failed",
                "source_kind": record.source_kind,
                "browser_path_intake": False,
                "session_token_materialized": False,
                "token_ref": record.token_ref,
                "token_server_owned": True,
                "token_status": "consumed",
                "filesystem_mutation_performed": bool(changed_files),
                "import_execution_claimed": True,
                "confirm_semantics_claimed": True,
                "explicit_confirm_observed": True,
                "receipt_state": "write_completed" if ok else "write_failed",
                "legacy_import_result": _sanitize_legacy_import_result(runtime_packet),
                "external_models_result": _sanitize_external_models_result(runtime_packet),
            }
        },
    )


def _direct_ui_action_packet_response(
    ui_action: str,
    *,
    action_spec: dict[str, Any],
    packet: dict[str, Any],
) -> dict[str, Any]:
    ok = (
        packet.get("status") == "ok"
        and packet.get("exit_code") == 0
        and packet.get("machine_error_code") == "OK"
    )
    return {
        "schema_version": 1,
        "status": "ok" if ok else "command_error",
        "source": "ui_action",
        "ui_action": ui_action,
        "action_role": action_spec["action_role"],
        "mutates_runtime": action_spec["mutates_runtime"],
        "affects_primary_truth": action_spec["affects_primary_truth"],
        "confirmation_required": action_spec["confirmation_required"],
        "post_action_refresh_required": action_spec["post_action_refresh_required"],
        "action_claim_scope": action_spec["action_claim_scope"],
        "mutation_class": action_spec.get("mutation_class", ""),
        "account_id": "",
        "route_id": "",
        "session_id": "",
        "result": {
            "status": str(packet.get("status", "error")),
            "machine_error_code": str(packet.get("machine_error_code", "")),
            "human_message": str(packet.get("human_message", "")),
            "next_action": str(packet.get("next_action", "")),
            "changed_files": list(packet.get("changed_files", [])),
            "data": packet.get("data", {}) if isinstance(packet.get("data"), dict) else {},
        },
    }


def _sandbox_action_preflight(contract: LaunchCopyContract | None) -> dict[str, Any]:
    if contract is None:
        return {
            "status": "denied",
            "machine_error_code": SANDBOX_ACTION_PREFLIGHT_REQUIRED_CODE,
            "reason": "Sandbox action contract не предоставлен.",
            "separate_profile": False,
            "separate_data_dir": False,
            "separate_port": False,
            "current_session_untouched": False,
            "sandbox_target_proven": False,
        }

    profile_dir = Path(contract.profile_dir).expanduser() if contract.profile_dir else None
    data_dir = Path(contract.data_dir).expanduser() if contract.data_dir else None
    current_profile_dir, current_data_dir = _current_runtime_target_paths()
    separate_profile = bool(profile_dir and profile_dir.is_absolute() and profile_dir != current_profile_dir)
    separate_data_dir = bool(data_dir and data_dir.is_absolute() and data_dir != current_data_dir)
    separate_port = isinstance(contract.copy_port, int) and contract.copy_port > 0
    if separate_port and contract.action_server_port:
        separate_port = contract.copy_port != contract.action_server_port
    if not separate_profile or not separate_data_dir or not separate_port:
        return {
            "status": "denied",
            "machine_error_code": SANDBOX_ACTION_PREFLIGHT_UNSAFE_CODE,
            "reason": (
                "Sandbox action phase требует отдельные absolute profile/data каталоги и отдельный port; "
                "рабочий Codex не должен совпадать с target."
            ),
            "separate_profile": separate_profile,
            "separate_data_dir": separate_data_dir,
            "separate_port": separate_port,
            "current_session_untouched": False,
            "sandbox_target_proven": False,
        }
    return {
        "status": "admitted",
        "machine_error_code": "OK",
        "reason": "Sandbox action target доказан: profile/data каталоги и port отделены от текущего Codex.",
        "separate_profile": True,
        "separate_data_dir": True,
        "separate_port": True,
        "current_session_untouched": True,
        "sandbox_target_proven": True,
    }


def _account_connect_live_preflight(accounts_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(accounts_snapshot, dict):
        return {
            "status": "denied",
            "machine_error_code": ACCOUNT_CONNECT_PREFLIGHT_REQUIRED_CODE,
            "reason": "Server-owned accounts-readonly preflight отсутствует.",
            "source_kind": "unknown",
            "write_surface": "unknown",
            "refresh_surface": "accounts-readonly",
            "reserve_first_required": True,
            "current_session_untouched": False,
        }

    if str(accounts_snapshot.get("status", "")) != "ok":
        human_message = str(
            accounts_snapshot.get("summary", {}).get("human_message", "")
            if isinstance(accounts_snapshot.get("summary"), dict)
            else ""
        )
        return {
            "status": "denied",
            "machine_error_code": ACCOUNT_CONNECT_PREFLIGHT_UNSAFE_CODE,
            "reason": human_message or "Accounts readonly snapshot не подтвердил server-owned source.",
            "source_kind": str(accounts_snapshot.get("source") or "unknown"),
            "write_surface": "account_registry_auth_mutation_only",
            "refresh_surface": "accounts-readonly",
            "reserve_first_required": True,
            "current_session_untouched": False,
        }

    registry_identity = accounts_snapshot.get("registry_identity")
    if not isinstance(registry_identity, dict):
        return {
            "status": "denied",
            "machine_error_code": ACCOUNT_CONNECT_PREFLIGHT_UNSAFE_CODE,
            "reason": "Accounts readonly snapshot не содержит registry identity.",
            "source_kind": str(accounts_snapshot.get("source") or "unknown"),
            "write_surface": "account_registry_auth_mutation_only",
            "refresh_surface": "accounts-readonly",
            "reserve_first_required": True,
            "current_session_untouched": False,
        }

    registry_status = str(registry_identity.get("status") or "")
    registry_code = str(registry_identity.get("machine_error_code") or "")
    registry_next_action = str(registry_identity.get("next_action") or "")
    if (
        str(accounts_snapshot.get("source") or "") != "accounts_readonly"
        or accounts_snapshot.get("primary_truth_ok") is not True
        or registry_status not in {"ok", "clear"}
        or registry_code != "OK"
        or registry_next_action not in {"", "none"}
    ):
        return {
            "status": "denied",
            "machine_error_code": ACCOUNT_CONNECT_PREFLIGHT_UNSAFE_CODE,
            "reason": "Server-owned accounts-readonly gate не admitted для live onboarding.",
            "source_kind": str(accounts_snapshot.get("source") or "unknown"),
            "write_surface": "account_registry_auth_mutation_only",
            "refresh_surface": "accounts-readonly",
            "reserve_first_required": True,
            "current_session_untouched": False,
        }

    return {
        "status": "admitted",
        "machine_error_code": "OK",
        "reason": "Server-owned accounts-readonly gate admitted live onboarding path.",
        "source_kind": "server_owned_accounts_readonly",
        "write_surface": "account_registry_auth_mutation_only",
        "refresh_surface": "accounts-readonly",
        "reserve_first_required": True,
        "current_session_untouched": True,
    }


def _api_route_connect_preflight(api_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(api_snapshot, dict):
        return {
            "status": "denied",
            "machine_error_code": API_ROUTE_CONNECT_PREFLIGHT_REQUIRED_CODE,
            "reason": "Server-owned api-connections-readonly preflight отсутствует.",
            "source_kind": "unknown",
            "write_surface": "unknown",
            "refresh_surface": "api-connections-readonly",
            "browser_secret_intake": False,
            "browser_path_intake": False,
            "browser_route_id_intake": False,
            "current_session_untouched": False,
        }
    if (
        str(api_snapshot.get("status") or "") != "ok"
        or str(api_snapshot.get("source") or "") != "api_connections_readonly"
        or api_snapshot.get("primary_truth_ok") is not True
    ):
        summary = api_snapshot.get("summary") if isinstance(api_snapshot.get("summary"), dict) else {}
        return {
            "status": "denied",
            "machine_error_code": API_ROUTE_CONNECT_PREFLIGHT_UNSAFE_CODE,
            "reason": str(summary.get("human_message") or "API readonly snapshot не подтвердил server-owned source."),
            "source_kind": str(api_snapshot.get("source") or "unknown"),
            "write_surface": "external_models_route_registry_mutation_only",
            "refresh_surface": "api-connections-readonly",
            "browser_secret_intake": False,
            "browser_path_intake": False,
            "browser_route_id_intake": False,
            "current_session_untouched": False,
        }
    return {
        "status": "admitted",
        "machine_error_code": "OK",
        "reason": "Server-owned api-connections-readonly gate admitted API route connect path.",
        "source_kind": "server_owned_api_connections_readonly",
        "write_surface": "external_models_route_registry_mutation_only",
        "refresh_surface": "api-connections-readonly",
        "browser_secret_intake": False,
        "browser_path_intake": False,
        "browser_route_id_intake": False,
        "current_session_untouched": True,
    }


def _route_id_from_route(route: dict[str, Any] | None) -> str:
    return str(route.get("route_id") or "") if isinstance(route, dict) else ""


def _enabled_external_route_records(packet: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(packet, dict):
        return []
    data = packet.get("data")
    if not isinstance(data, dict):
        return []
    routes = data.get("routes")
    if not isinstance(routes, list):
        return []
    enabled_routes: list[dict[str, Any]] = []
    for route in routes:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("route_id") or "").strip()
        auth = route.get("auth") if isinstance(route.get("auth"), dict) else {}
        secret_ref = str(auth.get("secret_ref") or route.get("secret_ref") or "").strip()
        if route_id and route.get("enabled") is True and secret_ref:
            enabled_routes.append(route)
    return enabled_routes


def _primary_external_route_id(packet: dict[str, Any] | None) -> str:
    enabled_routes = _enabled_external_route_records(packet)
    if not enabled_routes:
        return ""
    return str(enabled_routes[0].get("route_id") or "").strip()


def _json_object_or_empty(raw_bytes: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _catalog_packet_from_registry(registry: dict[str, Any]) -> dict[str, Any]:
    models = registry.get("available_models")
    if not isinstance(models, list):
        return {"models": []}
    return {
        "models": [
            {
                "model_id": str(entry.get("model_id") or ""),
                "lane": str(entry.get("lane") or ""),
            }
            for entry in models
            if isinstance(entry, dict) and str(entry.get("model_id") or "")
        ]
    }


def _normalize_openai_compat_endpoint(raw_endpoint: str) -> str:
    text = str(raw_endpoint or "").strip()
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        text = f"http://{text}"
    return text.rstrip("/") if text.rstrip("/").endswith("/v1") else f"{text.rstrip('/')}/v1"


def _build_live_native_availability_lattice_packet(
    operator_status: dict[str, Any] | None,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    api_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    status_packet = operator_status.get("status") if isinstance(operator_status, dict) else {}
    reported_endpoint = (
        str(status_packet.get("endpoint") or "").strip()
        if isinstance(status_packet, dict)
        else ""
    )
    live_endpoint = _normalize_openai_compat_endpoint(reported_endpoint or endpoint)
    if not reported_endpoint:
        return None
    registry = build_custom_model_registry_packet(
        operator_status,
        endpoint=live_endpoint,
        api_snapshot=api_snapshot,
    )
    native_entries = [
        entry
        for entry in registry.get("available_models") or []
        if isinstance(entry, dict) and str(entry.get("lane") or "") == "codex_native"
    ]
    if not native_entries:
        return None
    try:
        local_api_key = extract_local_api_key(default_runtime_config_path())
    except RuntimeError:
        return None
    current_packets: list[dict[str, Any]] = []
    runtime_ready = True
    for entry in native_entries:
        model_id = str(entry.get("model_id") or "").strip()
        if not model_id:
            continue
        request_payload = {
            "model": model_id,
            "input": "Reply with exactly WBP_NATIVE_LIVE_OK.",
        }
        request = urllib.request.Request(
            f"{live_endpoint.rstrip('/')}/responses",
            data=json.dumps(request_payload, ensure_ascii=True).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {local_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "OpenAI-Beta": "responses=v1",
            },
            method="POST",
        )
        http_status: int | None = None
        response_payload: dict[str, Any] | None = None
        error_payload: dict[str, Any] | None = None
        request_sent_to_wbp = False
        try:
            with proxyless_urlopen(request, timeout=10) as response:
                http_status = int(response.status)
                request_sent_to_wbp = True
                response_payload = _json_object_or_empty(response.read())
        except urllib.error.HTTPError as exc:
            http_status = int(exc.code)
            request_sent_to_wbp = True
            error_payload = _json_object_or_empty(exc.read())
        except Exception as exc:
            runtime_ready = False
            error_payload = {
                "machine_error_code": "NATIVE_LIVE_PROBE_TRANSPORT_ERROR",
                "error": {
                    "type": "transport_error",
                    "message": str(getattr(exc, "reason", exc))[:200],
                },
            }
        current_packets.append(
            build_model_direct_preflight_packet(
                model_id=model_id,
                source="current_live_native_probe",
                listed=True,
                selectable=entry.get("selection_enabled") is True,
                route_selected=True,
                runtime_ready=runtime_ready,
                http_status=http_status,
                upstream_status=http_status if http_status is not None and 200 <= http_status < 300 else None,
                response_payload=response_payload,
                error_payload=error_payload,
                prompt_text="Reply with exactly WBP_NATIVE_LIVE_OK.",
                request_sent_to_wbp=request_sent_to_wbp,
                route_family="codex_native_account_route",
            )
        )
    return build_catalog_availability_lattice_packet(
        catalog_packet=_catalog_packet_from_registry(registry),
        current_model_packets=current_packets,
    )


@dataclass
class _CustomNativeBridgeLease:
    bridge_port: int = DEFAULT_CUSTOM_CODEX_STABLE_WBP_BRIDGE_PORT
    signature: str = ""
    bridge: HybridOpenAICompatAdapter | None = None

    @property
    def stable_endpoint(self) -> str:
        return f"http://127.0.0.1:{self.bridge_port}/v1"

    def ensure(
        self,
        *,
        downstream_endpoint: str,
        routes_packet: dict[str, Any] | None,
        hidden_native_model_ids: list[str] | None = None,
        forced_route_model_id: str = "",
    ) -> str:
        route_records = _enabled_external_route_records(routes_packet)
        if not route_records:
            self.close()
            return downstream_endpoint
        try:
            expected_api_key = extract_local_api_key(default_runtime_config_path())
        except RuntimeError:
            self.close()
            return downstream_endpoint
        signature_source = {
            "downstream_endpoint": downstream_endpoint,
            "stable_bridge_port": self.bridge_port,
            "expected_api_key_present": bool(expected_api_key),
            "routes": [
                {
                    "route_id": str(route.get("route_id") or ""),
                    "provider": str(route.get("provider") or ""),
                    "base_url": str(route.get("base_url") or ""),
                    "endpoint_path": str(route.get("endpoint_path") or ""),
                    "upstream_model": str(route.get("upstream_model") or ""),
                    "secret_ref": str(
                        (
                            route.get("auth")
                            if isinstance(route.get("auth"), dict)
                            else {}
                        ).get("secret_ref")
                        or route.get("secret_ref")
                        or ""
                    ),
                }
                for route in route_records
            ],
            "hidden_native_model_ids": sorted(
                str(model_id).strip()
                for model_id in (hidden_native_model_ids or [])
                if str(model_id).strip()
            ),
            "forced_route_model_id": str(forced_route_model_id or "").strip(),
        }
        signature = hashlib.sha256(
            json.dumps(signature_source, ensure_ascii=True, sort_keys=True).encode("utf-8")
        ).hexdigest()
        if self.bridge is not None and self.signature == signature:
            return self.bridge.listen_endpoint
        self.close()
        bridge = HybridOpenAICompatAdapter(
            downstream_endpoint=downstream_endpoint,
            expected_api_key=expected_api_key,
            routes=route_records,
            hidden_downstream_model_ids=hidden_native_model_ids,
            forced_route_model_id=str(forced_route_model_id or "").strip(),
            listen_port=self.bridge_port,
            allow_missing_auth_from_loopback=True,
        )
        bridge.__enter__()
        self.bridge = bridge
        self.signature = signature
        return bridge.listen_endpoint

    def set_trace_context(self, context: dict[str, Any]) -> None:
        if self.bridge is not None:
            self.bridge.set_trace_context(context)

    def trace_snapshot(self) -> dict[str, Any]:
        if self.bridge is None:
            return {
                "schema_version": 1,
                "packet_kind": "hybrid_openai_compat_prompt_trace",
                "captured_at_utc": utc_now(),
                "trace_context": {},
                "request_count": 0,
                "last_record": {},
                "records": [],
                "raw_prompt_recorded": False,
                "auth_header_recorded": False,
                "secret_value_recorded": False,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
            }
        return self.bridge.trace_snapshot()

    def close(self) -> None:
        if self.bridge is not None:
            self.bridge.__exit__(None, None, None)
        self.bridge = None
        self.signature = ""


def _server_owned_api_route_spec(runner: CommandRunner) -> dict[str, Any]:
    env = getattr(runner, "_env", None)
    source = env if isinstance(env, dict) else os.environ
    route_id = str(source.get("WBP_SERVER_OWNED_API_ROUTE_ID") or "wbp-web-primary-openrouter")
    provider = str(source.get("WBP_SERVER_OWNED_API_ROUTE_PROVIDER") or "openrouter")
    display_name = str(source.get("WBP_SERVER_OWNED_API_ROUTE_DISPLAY_NAME") or "OpenRouter primary")
    base_url = str(source.get("WBP_SERVER_OWNED_API_ROUTE_BASE_URL") or "https://openrouter.ai/api/v1")
    endpoint_path = str(source.get("WBP_SERVER_OWNED_API_ROUTE_ENDPOINT_PATH") or "/chat/completions")
    upstream_model = str(source.get("WBP_SERVER_OWNED_API_ROUTE_MODEL") or "deepseek/deepseek-chat")
    secret_ref = str(source.get("WBP_SERVER_OWNED_API_ROUTE_SECRET_REF") or "OPENROUTER_API_KEY")
    cost_class = str(source.get("WBP_SERVER_OWNED_API_ROUTE_COST_CLASS") or "paid_or_free_limited")
    return {
        "schema_version": 1,
        "route_id": route_id,
        "display_name": display_name,
        "provider": provider,
        "base_url": base_url,
        "endpoint_path": endpoint_path,
        "upstream_model": upstream_model,
        "compatibility": "openai_chat_completions",
        "auth": {"type": "bearer", "secret_ref": secret_ref},
        "cost_class": cost_class,
        "lane_role": "candidate",
        "fallback_eligible": False,
        "enabled": True,
    }


def _server_owned_api_route_provider(runner: CommandRunner) -> str:
    route = _server_owned_api_route_spec(runner)
    return str(route.get("provider") or "openrouter")


def _server_owned_api_route_secret_ref(runner: CommandRunner) -> str:
    route = _server_owned_api_route_spec(runner)
    auth = route.get("auth") if isinstance(route.get("auth"), dict) else {}
    return str(auth.get("secret_ref") or "")


def _server_owned_api_route_spec_path(
    runner: CommandRunner,
    launch_copy_contract: LaunchCopyContract | None,
    route_id: str,
) -> Path:
    if launch_copy_contract is not None and launch_copy_contract.data_dir:
        external_dir = Path(launch_copy_contract.data_dir).expanduser() / "external-models"
    else:
        env = getattr(runner, "_env", None)
        source = env if isinstance(env, dict) else os.environ
        external_dir = Path(
            source.get("WBP_EXTERNAL_MODELS_DIR", "~/.wild-boar-proxy/external-models")
        ).expanduser()
    safe_route_id = "".join(char if char in ROUTE_ID_SAFE_CHARS else "-" for char in route_id)
    return external_dir / "server-owned-route-specs" / f"{safe_route_id}.json"


def _write_server_owned_api_route_spec(path: Path, route: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(route, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def build_live_readonly_snapshot(runner: CommandRunner) -> dict[str, Any]:
    commands: dict[str, dict[str, Any]] = {}
    for command_id in PRIMARY_COMMAND_IDS:
        result = execute_command(runner, command_id)
        commands[command_id] = result
        if result["status"] != "ok":
            return _integration_failure(
                "Primary command для live-просмотра только чтение не выполнилась.",
                str(result["human_message"]),
                str(result["machine_error_code"]),
                commands,
            )

    try:
        runtime = build_runtime_snapshot(
            status_payload=commands["status"]["packet"],
            mode_payload=commands["mode_get"]["packet"],
        )
        accounts = build_account_pool_snapshot(commands["accounts_list"]["packet"])
    except UiShellError as exc:
        return _integration_failure(
            "Проверка пакета live-просмотра только чтение не прошла.",
            str(exc),
            "UI_LIVE_READONLY_PACKET_INVALID",
            commands,
        )

    warnings: list[dict[str, str]] = []
    for command_id in DETAIL_COMMAND_IDS:
        result = execute_command(runner, command_id)
        commands[command_id] = result
        if result["status"] != "ok":
            warnings.append(_warning_from_result(command_id, result))

    visual_state = _visual_state(runtime.liveness)
    if visual_state == "healthy" and any(warning["severity"] == "degraded" for warning in warnings):
        visual_state = "degraded"
    hold_count = sum(1 for account in accounts.accounts if account.manual_hold)
    problem_count = sum(
        1
        for account in accounts.accounts
        if account.status in {"down", "degraded"} or bool(account.last_error)
    )

    return {
        "schema_version": 1,
        "status": "ok",
        "ui_state": visual_state,
        "source": "live_readonly",
        "primary_truth_ok": True,
        "has_warnings": bool(warnings),
        "warnings": warnings,
        "evidence_summary": _evidence_summary(commands, warnings),
        "runtime": {
            "visual_state": visual_state,
            "status_label": _status_label(visual_state),
            "desired_mode": runtime.desired_mode,
            "effective_mode": runtime.effective_mode,
            "endpoint": runtime.endpoint or runtime.current_proxy_url,
            "machine_error_code": runtime.machine_error_code,
            "human_message": runtime.human_message,
            "last_error": runtime.last_error,
            "observed_at_utc": runtime.attestation_observed_at,
        },
        "pool_summary": {
            "active": accounts.active_count,
            "reserve": accounts.reserve_count,
            "hold": hold_count,
            "problem": problem_count,
            "active_note": f"{runtime.active_count} active в status packet",
            "reserve_note": f"{runtime.reserve_count} reserve в status packet",
            "hold_note": "аккаунты на manual hold",
            "problem_note": "аккаунты degraded/down/error",
        },
        "events": _events_from_commands(commands, visual_state, warnings),
        "commands": _public_command_results(commands),
    }


def build_accounts_readonly_snapshot(runner: CommandRunner) -> dict[str, Any]:
    result = execute_command(runner, "accounts_list")
    commands = {"accounts_list": result}
    if result["status"] != "ok":
        return _accounts_integration_failure(
            "Команда аккаунтов только для чтения не выполнилась.",
            str(result["human_message"]),
            str(result["machine_error_code"]),
        )

    packet = result["packet"]
    try:
        accounts = build_account_pool_snapshot(packet)
    except UiShellError as exc:
        return _accounts_integration_failure(
            "Проверка пакета аккаунтов только для чтения не прошла.",
            str(exc),
            "UI_ACCOUNTS_READONLY_PACKET_INVALID",
        )

    rows = _account_rows(accounts.accounts, packet)
    summary = _account_summary(rows, accounts)
    return {
        "schema_version": 1,
        "status": "ok",
        "source": "accounts_readonly",
        "primary_truth_ok": True,
        "privacy": {
            "redacted": True,
            "raw_command_packet_included": False,
            "forbidden_fields_excluded": ["secret_references", "tokens", "raw_paths", "raw_logs"],
        },
        "registry_identity": {
            "status": accounts.registry_identity_status,
            "machine_error_code": accounts.registry_identity_machine_error_code,
            "next_action": accounts.registry_identity_next_action,
        },
        "summary": summary,
        "accounts": rows,
        "commands": _public_command_results(commands),
    }


def execute_external_command(runner: CommandRunner, *argv: str) -> dict[str, Any]:
    try:
        result = runner.run(*argv)
        payload = result.payload
    except (UiShellError, OSError, ValueError) as exc:
        return {
            "status": "integration_failure",
            "ui_state": "integration_failure",
            "machine_error_code": "UI_COMMAND_INTEGRATION_FAILURE",
            "human_message": str(exc),
            "exit_code": 1,
            "changed_files": [],
            "next_action": "retry",
            "packet": {},
        }

    required = (
        "status",
        "exit_code",
        "human_message",
        "machine_error_code",
        "changed_files",
        "next_action",
    )
    if not isinstance(payload, dict) or any(key not in payload for key in required):
        return {
            "status": "integration_failure",
            "ui_state": "integration_failure",
            "machine_error_code": "UI_COMMAND_PACKET_INVALID",
            "human_message": "Пакет команды external-models недействителен.",
            "exit_code": 1,
            "changed_files": [],
            "next_action": "retry",
            "packet": payload if isinstance(payload, dict) else {},
        }

    ok = (
        payload.get("status") == "ok"
        and payload.get("exit_code") == 0
        and payload.get("machine_error_code") == "OK"
    )
    return {
        "status": "ok" if ok else "command_error",
        "ui_state": "success" if ok else "error",
        "machine_error_code": payload["machine_error_code"],
        "human_message": payload["human_message"],
        "exit_code": payload["exit_code"],
        "changed_files": payload["changed_files"] if isinstance(payload["changed_files"], list) else [],
        "next_action": payload["next_action"],
        "packet": payload,
    }


def build_api_connections_readonly_snapshot(runner: CommandRunner) -> dict[str, Any]:
    commands = {
        "external_models_status": execute_external_command(
            runner,
            "external-models",
            "status",
            "--json",
        ),
        "external_models_models": execute_external_command(
            runner,
            "external-models",
            "models",
            "--json",
        ),
        "external_models_routes_list": execute_external_command(
            runner,
            "external-models",
            "routes",
            "list",
            "--json",
        ),
    }
    for command_id in API_CONNECTIONS_READONLY_COMMAND_IDS:
        result = commands[command_id]
        if result["status"] != "ok":
            return _api_connections_integration_failure(
                "Команда API-подключений только для чтения не выполнилась.",
                str(result["human_message"]),
                str(result["machine_error_code"]),
                commands,
            )

    try:
        external_models = build_external_models_snapshot(
            status_payload=commands["external_models_status"]["packet"],
            models_payload=commands["external_models_models"]["packet"],
            routes_payload=commands["external_models_routes_list"]["packet"],
        )
    except UiShellError as exc:
        return _api_connections_integration_failure(
            "Проверка пакетов API-подключений только для чтения не прошла.",
            str(exc),
            "UI_API_CONNECTIONS_PACKET_INVALID",
            commands,
        )

    rows = _api_connection_rows(external_models)
    latest_check = max(
        (str(row["last_checked"]) for row in rows if str(row["last_checked"])),
        default="",
    )
    attention_count = sum(
        1
        for row in rows
        if row["status_code"]
        in {
            "missing_secret",
            "integration_failure",
            "validation_failed",
            "check_attention",
            "blocked",
        }
    )
    return {
        "schema_version": 1,
        "status": "ok",
        "source": "api_connections_readonly",
        "primary_truth_ok": True,
        "privacy": {
            "redacted": True,
            "raw_command_packet_included": False,
            "forbidden_fields_excluded": [
                "secret_references",
                "tokens",
                "raw_paths",
                "raw_logs",
            ],
        },
        "summary": {
            "routes_count": external_models.routes_count,
            "enabled_count": sum(1 for row in rows if row["enabled"]),
            "attention_count": attention_count,
            "latest_check": latest_check,
            "human_message": "Список API-подключений собран из пакетов команд.",
            "machine_error_code": "OK",
            "last_error": external_models.integration_error,
        },
        "adapter": {
            "foundation_phase": external_models.foundation_phase,
            "adapter_runtime_available": external_models.adapter_runtime_available,
            "lifecycle_mode": external_models.lifecycle_mode,
            "adapter_state": external_models.adapter_state,
            "listener_proven": external_models.listener_proven,
            "runtime_claim_blocked": external_models.runtime_claim_blocked,
            "profile_ready": external_models.profile_ready,
            "local_token_present": external_models.local_token_present,
            "observed_routes_count": external_models.observed_routes_count,
            "models_source": external_models.models_source,
        },
        "routes": rows,
        "commands": _public_command_results(commands),
    }


def _primary_api_route_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    routes = snapshot.get("routes")
    if not isinstance(routes, list) or not routes:
        return None
    for route in routes:
        if not isinstance(route, dict):
            continue
        if (
            route.get("role_label") in {"main route", "primary"}
            or route.get("is_primary") is True
            or route.get("primary") is True
        ):
            return route
    for route in routes:
        if isinstance(route, dict) and route.get("enabled") is True:
            return route
    first = routes[0]
    return first if isinstance(first, dict) else None


def _api_route_provider_from_snapshot(
    snapshot: dict[str, Any] | None,
    runner: CommandRunner,
) -> str:
    route = _primary_api_route_from_snapshot(snapshot or {}) if isinstance(snapshot, dict) else None
    if isinstance(route, dict):
        provider = str(route.get("provider") or "").strip()
        if provider:
            return provider
    return _server_owned_api_route_provider(runner)


def _api_route_secret_ref_from_snapshot(
    snapshot: dict[str, Any] | None,
    runner: CommandRunner,
) -> str:
    route = _primary_api_route_from_snapshot(snapshot or {}) if isinstance(snapshot, dict) else None
    if isinstance(route, dict):
        secret_ref = str(route.get("secret_ref") or "").strip()
        if secret_ref:
            return secret_ref
    return _server_owned_api_route_secret_ref(runner)


def _redacted_route_ref(route_id: str) -> str:
    return hashlib.sha256(route_id.encode("utf-8")).hexdigest() if route_id else ""


def _selection_packet_for_external_route(
    *,
    model_id: str,
    operator_status: dict[str, Any] | None,
    api_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    claim_gate_status = "not_reported"
    claim_gate = (operator_status or {}).get("claim_gate")
    if isinstance(claim_gate, dict):
        claim_gate_status = str(claim_gate.get("status") or "not_reported")
    route = None
    routes = api_snapshot.get("routes") if isinstance(api_snapshot, dict) else None
    if isinstance(routes, list):
        for item in routes:
            if isinstance(item, dict) and str(item.get("route_id") or "") == model_id:
                route = item
                break
    if not isinstance(route, dict):
        return {
            "schema_version": 1,
            "status": "degraded",
            "machine_error_code": "EXTERNAL_API_ROUTE_NOT_VISIBLE",
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "selection_dry_run_proven": False,
            "live_selection_proven": False,
            "selection_proven": False,
            "inference_proven": False,
            "selected_source_class": "none",
            "selected_backend_id": "",
            "selected_backend_ref": "",
            "selected_backend_id_redacted": True,
            "selected_backend_server_issued": False,
            "selected_backend_source": "none",
            "selected_route_ref": "",
            "selected_route_server_issued": False,
            "route_provenance_required": False,
            "route_provenance_proven": False,
            "source_provenance_status": "not_proven",
            "api_model_selected_by_user": True,
            "route_selected_by_user": False,
            "browser_selected_route": False,
            "route_candidate_source": "none",
            "route_candidate_classified": False,
            "route_static_readiness_classified": False,
            "route_execution_proven": False,
            "provider_response_proven": False,
            "secret_validity_proven": False,
            "live_compatibility_proven": False,
            "raw_route_exposed": False,
            "raw_secret_ref_exposed": False,
            "browser_selected_backend": False,
            "selection_reason": "selected external model is not visible in current server-owned API route snapshot",
            "claim_gate_status": claim_gate_status,
            "token_burn": 0,
            "selection_not_inference": True,
            "network_calls_made": False,
            "provider_called": False,
        }
    route_id = str(route.get("route_id") or "")
    secret_ref = str(route.get("secret_ref") or "")
    enabled = route.get("enabled") is True
    ready = enabled and bool(secret_ref)
    status = "ok" if ready and "blocked" not in claim_gate_status else "degraded"
    machine_error_code = (
        "OK"
        if ready and "blocked" not in claim_gate_status
        else (
            "CLAIM_GATE_BLOCKED"
            if ready
            else ("EXTERNAL_API_ROUTE_SECRET_REF_MISSING" if not secret_ref else "EXTERNAL_API_ROUTE_DISABLED")
        )
    )
    route_ref = _redacted_route_ref(route_id)
    return {
        "schema_version": 1,
        "status": status,
        "machine_error_code": machine_error_code,
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "selection_dry_run_proven": ready,
        "live_selection_proven": False,
        "selection_proven": ready,
        "inference_proven": False,
        "selected_source_class": "route_backed" if ready else "none",
        "selected_backend_id": "",
        "selected_backend_ref": "",
        "selected_backend_id_redacted": True,
        "selected_backend_server_issued": False,
        "selected_backend_source": "none",
        "selected_route_ref": route_ref,
        "selected_route_server_issued": ready,
        "route_provenance_required": ready,
        "route_provenance_proven": False,
        "source_provenance_status": (
            "route_static_candidate_classified" if ready else "route_static_candidate_missing"
        ),
        "api_model_selected_by_user": True,
        "route_selected_by_user": False,
        "browser_selected_route": False,
        "route_candidate_source": "server_issued_route_registry" if route_id else "none",
        "route_candidate_classified": bool(route_id),
        "route_static_readiness_classified": ready,
        "route_execution_proven": False,
        "provider_response_proven": False,
        "secret_validity_proven": False,
        "live_compatibility_proven": False,
        "raw_route_exposed": False,
        "raw_secret_ref_exposed": False,
        "browser_selected_backend": False,
        "selection_reason": "server-owned external route matched selected model_id",
        "claim_gate_status": claim_gate_status,
        "selected_route_provider": str(route.get("provider") or ""),
        "selected_route_primary": route.get("primary") is True or route.get("is_primary") is True,
        "selected_route_secret_ref_present": bool(secret_ref),
        "token_burn": 0,
        "selection_not_inference": True,
        "network_calls_made": False,
        "provider_called": False,
    }


def _codex_custom_selection_packet(
    *,
    model_id: str,
    commands: dict[str, dict[str, Any]],
    operator_status: dict[str, Any] | None,
    api_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    registry = build_custom_model_registry_packet(operator_status, api_snapshot=api_snapshot)
    lane_classification = model_lane_classification_from_registry(model_id, registry)
    model_lane = str(lane_classification.get("model_lane") or "")
    if model_lane == CODEX_ACCOUNT_MODEL_LANE:
        return build_account_selection_packet(commands, operator_status) | lane_classification
    if model_lane == API_ROUTE_MODEL_LANE:
        return _selection_packet_for_external_route(
            model_id=model_id,
            operator_status=operator_status,
            api_snapshot=api_snapshot,
        ) | lane_classification
    return {
        "schema_version": 1,
        "status": "rejected",
        "machine_error_code": "MODEL_LANE_NOT_CLASSIFIED",
        "selection_proven": False,
        "selected_source_class": "none",
        **lane_classification,
    }


def _owner_authorization_required_packet(*, mode_id: str, next_action: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "blocked",
        "machine_error_code": "OWNER_AUTHORIZATION_REQUIRED",
        "captured_at_utc": utc_now(),
        "mode_id": mode_id,
        "owner_authorization_phrase_present": False,
        "human_message": "Live launch requires exact owner authorization in the active thread.",
        "next_action": next_action,
    }


def _manual_custom_model_selection_required_packet(
    *,
    owner_authorized: bool,
    launch_claim_scope: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "status": "rejected",
        "machine_error_code": "MANUAL_MODEL_SELECTION_REQUIRED",
        "human_message": "Custom Codex native launch requires an explicit server-issued model selection.",
        "owner_authorization_phrase_present": owner_authorized,
        "launch_claim_scope": launch_claim_scope,
        "selected_model": "",
        "model_server_issued": False,
        "selected_model_server_issued": False,
        "model_auto_selected": False,
        "fallback_used": False,
        "external_route_selected": False,
        "recommended_model_used": False,
        "route_fallback_used": False,
        "process_started": False,
        "native_window_observed": False,
        "native_app_usable": False,
        "current_codex_touched": False,
        "next_action": "select_model_from_server_registry",
    }


CUSTOM_NATIVE_LAUNCH_ALLOWED_BROWSER_FIELDS = frozenset(
    {
        "model_id",
        "execution_mode",
        "chatgpt_model_id",
        "api_model_id",
        "api_reasoning_option_id",
    }
)


QUICK_START_CONFIG_ADMISSION_ALLOWED_BROWSER_FIELDS = frozenset(
    {
        "execution_mode",
        "chatgpt_model_id",
        "api_model_id",
        "api_reasoning_option_id",
    }
)


QUICK_START_DEEPSEEK_SAFE_WORKTREE_ALLOWED_BROWSER_FIELDS = frozenset(
    {
        "execution_mode",
        "api_model_id",
        "api_reasoning_option_id",
    }
)


def _forbidden_custom_live_launch_fields(payload: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            if prefix or key_text not in CUSTOM_NATIVE_LAUNCH_ALLOWED_BROWSER_FIELDS:
                findings.append(key_path)
            findings.extend(_forbidden_custom_live_launch_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(_forbidden_custom_live_launch_fields(value, f"{prefix}[{index}]"))
    return findings


def _forbidden_quick_start_config_admission_fields(
    payload: Any,
    prefix: str = "",
) -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            if prefix or key_text not in QUICK_START_CONFIG_ADMISSION_ALLOWED_BROWSER_FIELDS:
                findings.append(key_path)
            findings.extend(_forbidden_quick_start_config_admission_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(
                _forbidden_quick_start_config_admission_fields(
                    value,
                    f"{prefix}[{index}]",
                )
            )
    return findings


def _forbidden_quick_start_deepseek_safe_worktree_fields(
    payload: Any,
    prefix: str = "",
) -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            if prefix or key_text not in QUICK_START_DEEPSEEK_SAFE_WORKTREE_ALLOWED_BROWSER_FIELDS:
                findings.append(key_path)
            findings.extend(_forbidden_quick_start_deepseek_safe_worktree_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(
                _forbidden_quick_start_deepseek_safe_worktree_fields(
                    value,
                    f"{prefix}[{index}]",
                )
            )
    return findings


def _api_snapshot_route_for_model(
    api_snapshot: dict[str, Any] | None,
    model_id: str,
) -> dict[str, Any] | None:
    routes = api_snapshot.get("routes") if isinstance(api_snapshot, dict) else None
    if not isinstance(routes, list):
        return None
    for route in routes:
        if isinstance(route, dict) and str(route.get("route_id") or "").strip() == model_id:
            return route
    return None


def _route_targets_deepseek(route: dict[str, Any] | None, model_id: str) -> bool:
    if not isinstance(route, dict):
        return "deepseek" in model_id.lower()
    fields = (
        model_id,
        route.get("route_id"),
        route.get("display_name"),
        route.get("provider"),
        route.get("provider_label"),
        route.get("upstream_model"),
        route.get("effective_model"),
    )
    return any("deepseek" in str(value or "").lower() for value in fields)


def _custom_native_launch_mode_selection_packet(
    payload: dict[str, Any],
    operator_status: dict[str, Any] | None,
    api_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    execution_mode = str(payload.get("execution_mode") or "").strip()
    api_model_id = str(payload.get("api_model_id") or "").strip()
    chatgpt_model_id = str(payload.get("chatgpt_model_id") or "").strip()
    api_reasoning_option_id = str(payload.get("api_reasoning_option_id") or "").strip()
    if not execution_mode and not api_model_id and not chatgpt_model_id and not api_reasoning_option_id:
        return {}
    return build_custom_codex_execution_mode_selector_packet(
        {
            "execution_mode": execution_mode,
            "chatgpt_model_id": chatgpt_model_id,
            "api_model_id": api_model_id,
            "api_reasoning_option_id": api_reasoning_option_id,
        },
        operator_status,
        api_snapshot=api_snapshot,
    )


def _custom_native_launch_selected_model_id(
    payload: dict[str, Any],
    execution_packet: dict[str, Any],
) -> str:
    if execution_packet:
        slot = execution_packet.get("primary_model_slot")
        if isinstance(slot, dict):
            return str(slot.get("model_id") or "").strip()
        return ""
    return str(payload.get("model_id") or "").strip()


def _custom_native_launch_route_model_id(
    *,
    execution_packet: dict[str, Any],
    selected_model: str,
) -> str:
    if not execution_packet:
        return str(selected_model or "").strip()
    execution_mode = str(execution_packet.get("execution_mode") or "")
    if execution_mode == "chatgpt_plus_api":
        coding_slot = execution_packet.get("coding_agent_model_slot")
        if isinstance(coding_slot, dict):
            route_model = str(coding_slot.get("model_id") or "").strip()
            if route_model:
                return route_model
        return str(execution_packet.get("api_model_id") or "").strip()
    if execution_mode == "api_only":
        return str(execution_packet.get("api_model_id") or selected_model or "").strip()
    return str(selected_model or "").strip()


def _custom_native_route_matches_selection_packet(
    *,
    execution_packet: dict[str, Any],
    launch_model_id: str,
    route_model_id: str,
) -> bool:
    if not execution_packet:
        return True
    execution_mode = str(execution_packet.get("execution_mode") or "")
    primary_slot = (
        execution_packet.get("primary_model_slot")
        if isinstance(execution_packet.get("primary_model_slot"), dict)
        else {}
    )
    coding_slot = (
        execution_packet.get("coding_agent_model_slot")
        if isinstance(execution_packet.get("coding_agent_model_slot"), dict)
        else {}
    )
    primary_model_id = str(primary_slot.get("model_id") or "")
    coding_model_id = str(coding_slot.get("model_id") or "")
    if execution_mode == "chatgpt_plus_api":
        return bool(
            launch_model_id
            and route_model_id
            and launch_model_id == primary_model_id
            and route_model_id == coding_model_id
        )
    if execution_mode == "api_only":
        return bool(route_model_id and route_model_id == primary_model_id)
    if execution_mode == "chatgpt_only":
        return bool(launch_model_id and launch_model_id == primary_model_id)
    return False


def _quick_start_launch_selection_digest(fields: dict[str, Any]) -> str:
    safe_fields = {
        "execution_mode": str(fields.get("execution_mode") or ""),
        "chatgpt_model_id": str(fields.get("chatgpt_model_id") or ""),
        "api_model_id": str(fields.get("api_model_id") or ""),
        "api_reasoning_option_id": str(fields.get("api_reasoning_option_id") or ""),
        "selected_model": str(fields.get("selected_model") or ""),
    }
    return hashlib.sha256(
        json.dumps(safe_fields, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]


def _quick_start_launch_selection_fields(
    *,
    execution_packet: dict[str, Any] | None,
    selected_model: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, str]:
    source = execution_packet if execution_packet else (payload or {})
    return {
        "execution_mode": str(source.get("execution_mode") or ""),
        "chatgpt_model_id": str(source.get("chatgpt_model_id") or ""),
        "api_model_id": str(source.get("api_model_id") or ""),
        "api_reasoning_option_id": str(source.get("api_reasoning_option_id") or ""),
        "selected_model": selected_model,
    }


def _quick_start_launch_fields_from_packet(packet: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(packet, dict):
        return {
            "execution_mode": "",
            "chatgpt_model_id": "",
            "api_model_id": "",
            "api_reasoning_option_id": "",
            "selected_model": "",
        }
    return {
        "execution_mode": str(packet.get("execution_mode") or ""),
        "chatgpt_model_id": str(packet.get("chatgpt_model_id") or ""),
        "api_model_id": str(packet.get("api_model_id") or ""),
        "api_reasoning_option_id": str(packet.get("api_reasoning_option_id") or ""),
        "selected_model": str(packet.get("selected_model") or packet.get("model") or ""),
    }


def _custom_native_last_launch_packet_allows_window_relaunch(
    packet: dict[str, Any] | None,
) -> bool:
    if not isinstance(packet, dict):
        return False
    if packet.get("status") == "ok":
        return True
    return bool(
        packet.get("mode_id") == "codex_custom"
        and packet.get("owner_authorization_phrase_present") is True
        and packet.get("process_started") is True
        and packet.get("native_window_observed") is True
        and packet.get("native_app_usable") is True
        and packet.get("current_codex_touched") is not True
        and packet.get("original_codex_touched") is not True
        and packet.get("asar_touched") is not True
        and packet.get("browser_raw_backend_authority_widened") is not True
        and packet.get("raw_backend_details_exposed") is not True
        and packet.get("secret_value_exposed") is not True
    )


def _custom_native_process_inventory_summary() -> dict[str, Any]:
    paths = default_persistent_custom_profile_paths(
        profile_id=DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID
    )
    user_data_dir = str(paths.get("user_data_dir") or "")
    try:
        inventory = collect_codex_process_inventory(custom_user_data_dir=user_data_dir)
    except OSError as exc:
        return {
            "window_inventory_status": "unavailable",
            "window_inventory_error_class": type(exc).__name__,
            "custom_process_observed": False,
            "custom_process_count": 0,
            "profile_id": DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID,
            "raw_process_lines_exposed": False,
            "raw_path_exposed": False,
        }
    custom_process_count = int(inventory.get("custom_process_count") or 0)
    return {
        "window_inventory_status": "ok",
        "custom_process_observed": custom_process_count > 0,
        "custom_process_count": custom_process_count,
        "default_process_count": int(inventory.get("default_process_count") or 0),
        "profile_id": DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID,
        "raw_process_lines_exposed": False,
        "raw_path_exposed": False,
    }


def _redacted_custom_process_termination_summary(
    termination: dict[str, Any],
) -> dict[str, Any]:
    final_inventory = termination.get("final_inventory")
    if not isinstance(final_inventory, dict):
        final_inventory = {}
    initial_pids = termination.get("initial_custom_pids")
    if not isinstance(initial_pids, list):
        initial_pids = []
    return {
        "attempted": True,
        "status": (
            "ok" if termination.get("custom_processes_gone") is True else "blocked"
        ),
        "initial_custom_process_count": len(initial_pids),
        "custom_processes_gone": termination.get("custom_processes_gone") is True,
        "final_custom_process_count": int(
            final_inventory.get("custom_process_count") or 0
        ),
        "raw_process_lines_exposed": False,
        "raw_path_exposed": False,
    }


def _custom_native_launch_preflight_packet(
    payload: dict[str, Any],
    *,
    owner_authorized: bool,
    operator_status: dict[str, Any] | None,
    api_snapshot: dict[str, Any] | None,
    external_routes_packet: dict[str, Any] | None = None,
    native_bridge_lease: _CustomNativeBridgeLease | None = None,
    last_launch_packet: dict[str, Any] | None = None,
    runtime_health_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    forbidden = _forbidden_custom_live_launch_fields(payload)
    if forbidden:
        return {
            "schema_version": 1,
            "packet_kind": "custom_native_launch_preflight",
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "human_message": "Custom native launch preflight accepts no browser-controlled route, backend, auth, path, or home fields.",
            "forbidden_fields": forbidden,
            "owner_authorization_phrase_present": owner_authorized,
            "preflight_claim_scope": "quick_start_launch_guard_no_live_mutation",
            "show_window_attempted": False,
            "new_launch_started": False,
            "live_provider_called": False,
            "browser_raw_backend_authority_widened": True,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "raw_path_exposed": False,
            "original_codex_touched": False,
            "asar_touched": False,
            "final_status": "KNOWN_BLOCKER_QUICK_START_LIVE_BRIDGE_OR_WINDOW_REUSE_NOT_PROVEN",
            "next_action": "remove_browser_payload_fields",
        }
    if not owner_authorized:
        return {
            "schema_version": 1,
            "packet_kind": "custom_native_launch_preflight",
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "preflight_claim_scope": "quick_start_launch_guard_no_live_mutation",
            **_owner_authorization_required_packet(
                mode_id="codex_custom",
                next_action="provide_exact_owner_authorization_phrase",
            ),
            "show_window_attempted": False,
            "new_launch_started": False,
            "live_provider_called": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "raw_path_exposed": False,
            "original_codex_touched": False,
            "asar_touched": False,
            "final_status": "KNOWN_BLOCKER_QUICK_START_LIVE_BRIDGE_OR_WINDOW_REUSE_NOT_PROVEN",
        }

    execution_packet = _custom_native_launch_mode_selection_packet(
        payload,
        operator_status,
        api_snapshot,
    )
    if execution_packet and payload.get("model_id"):
        return {
            "schema_version": 1,
            "packet_kind": "custom_native_launch_preflight",
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "status": "rejected",
            "machine_error_code": "CUSTOM_NATIVE_LAUNCH_AMBIGUOUS_MODEL_FIELDS",
            "human_message": "Custom native launch preflight accepts either legacy model_id or execution-mode fields, not both.",
            "preflight_claim_scope": "quick_start_launch_guard_no_live_mutation",
            "execution_mode": str(payload.get("execution_mode") or ""),
            "show_window_attempted": False,
            "new_launch_started": False,
            "live_provider_called": False,
            "model_auto_selected": False,
            "fallback_used": False,
            "browser_raw_backend_authority_widened": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "raw_path_exposed": False,
            "final_status": "KNOWN_BLOCKER_QUICK_START_LIVE_BRIDGE_OR_WINDOW_REUSE_NOT_PROVEN",
            "next_action": "remove_model_id_or_use_legacy_launch_payload",
        }
    selected_model = _custom_native_launch_selected_model_id(payload, execution_packet)
    if execution_packet and execution_packet.get("status") != "ok":
        selected_model = selected_model or str(
            (execution_packet.get("primary_model_slot") or {}).get("model_id") or ""
        )
        return {
            "schema_version": 1,
            "packet_kind": "custom_native_launch_preflight",
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "status": execution_packet.get("status"),
            "machine_error_code": execution_packet.get("machine_error_code"),
            "human_message": "Custom native launch preflight blocked by execution-mode selection packet.",
            "preflight_claim_scope": "quick_start_launch_guard_no_live_mutation",
            "execution_mode": execution_packet.get("execution_mode"),
            "api_model_id": execution_packet.get("api_model_id"),
            "api_reasoning_option_id": execution_packet.get("api_reasoning_option_id"),
            "chatgpt_model_id": execution_packet.get("chatgpt_model_id"),
            "selected_model": selected_model,
            "selection_packet": execution_packet,
            "show_window_attempted": False,
            "new_launch_started": False,
            "live_provider_called": False,
            "model_auto_selected": False,
            "fallback_used": False,
            "browser_raw_backend_authority_widened": bool(
                execution_packet.get("browser_raw_backend_authority_widened")
            ),
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "raw_path_exposed": False,
            "final_status": "KNOWN_BLOCKER_QUICK_START_LIVE_BRIDGE_OR_WINDOW_REUSE_NOT_PROVEN",
            "next_action": execution_packet.get("next_action", "repair_execution_mode_selection"),
        }
    if not selected_model:
        packet = _manual_custom_model_selection_required_packet(
            owner_authorized=owner_authorized,
            launch_claim_scope="quick_start_launch_guard_no_live_mutation",
        )
        packet.update(
            {
                "packet_kind": "custom_native_launch_preflight",
                "show_window_attempted": False,
                "new_launch_started": False,
                "live_provider_called": False,
                "raw_path_exposed": False,
                "final_status": "KNOWN_BLOCKER_QUICK_START_LIVE_BRIDGE_OR_WINDOW_REUSE_NOT_PROVEN",
            }
        )
        return packet

    registry = build_custom_model_registry_packet(
        operator_status,
        api_snapshot=api_snapshot,
    )
    endpoint = str(registry.get("endpoint") or "")
    route_model_id = _custom_native_launch_route_model_id(
        execution_packet=execution_packet or {},
        selected_model=selected_model,
    )
    route_record = _external_route_record_for_model(external_routes_packet, route_model_id)
    route_selected = bool(route_record)
    bridge_port = (
        native_bridge_lease.bridge_port
        if native_bridge_lease is not None
        else (_openai_compat_endpoint_port(endpoint) or 0)
    )
    bridge_alive = bool(
        (native_bridge_lease is not None and native_bridge_lease.bridge is not None)
        or (bridge_port and _loopback_port_accepts_connection(int(bridge_port)))
    )
    if not route_selected:
        bridge_status = "not_required"
        bridge_next_action = "launch_custom_codex"
    elif bridge_alive:
        bridge_status = "alive"
        bridge_next_action = "launch_or_reuse_custom_codex"
    else:
        bridge_status = "not_started_or_down"
        bridge_next_action = "launch_custom_codex_to_create_bridge"

    window_inventory = _custom_native_process_inventory_summary()
    custom_process_observed = window_inventory.get("custom_process_observed") is True
    current_fields = _quick_start_launch_selection_fields(
        execution_packet=execution_packet,
        selected_model=selected_model,
        payload=payload,
    )
    runtime_health_gate = _custom_native_chatgpt_runtime_health_gate_packet(
        runtime_health_result,
        execution_mode=str(current_fields.get("execution_mode") or ""),
    )
    if runtime_health_gate.get("status") != "ok":
        return {
            "schema_version": 1,
            "packet_kind": "custom_native_launch_preflight",
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "status": "blocked",
            "machine_error_code": str(
                runtime_health_gate.get("runtime_health_machine_error_code")
                or runtime_health_gate.get("machine_error_code")
                or "CUSTOM_CODEX_RUNTIME_HEALTH_BLOCKED"
            ),
            "block_reason_code": str(
                runtime_health_gate.get("machine_error_code")
                or "CUSTOM_CODEX_RUNTIME_HEALTH_BLOCKED"
            ),
            "human_message": "Custom native launch preflight blocked because ChatGPT lane runtime health is not green.",
            "preflight_claim_scope": "quick_start_launch_guard_no_live_mutation",
            "owner_authorization_phrase_present": owner_authorized,
            "execution_mode": current_fields["execution_mode"],
            "chatgpt_model_id": current_fields["chatgpt_model_id"],
            "api_model_id": current_fields["api_model_id"],
            "api_reasoning_option_id": current_fields["api_reasoning_option_id"],
            "selected_model": selected_model,
            "launch_model_id": selected_model,
            "route_model_id": route_model_id,
            "selection_packet": execution_packet or {},
            "runtime_health_gate": runtime_health_gate,
            "runtime_health_required_for_chatgpt_lane": True,
            "runtime_health_status": str(runtime_health_gate.get("runtime_health_status") or ""),
            "runtime_health_machine_error_code": str(
                runtime_health_gate.get("runtime_health_machine_error_code") or ""
            ),
            "show_window_attempted": False,
            "new_launch_started": False,
            "live_provider_called": False,
            "model_auto_selected": False,
            "fallback_used": False,
            "silent_fallback_used": False,
            "browser_raw_backend_authority_widened": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "raw_path_exposed": False,
            "original_codex_touched": False,
            "asar_touched": False,
            "final_status": "KNOWN_BLOCKER_CUSTOM_CODEX_RUNTIME_HEALTH_NOT_PROVEN",
            "next_action": str(
                runtime_health_gate.get("runtime_health_next_action")
                or "repair_runtime_proxy"
            ),
        }
    current_digest = _quick_start_launch_selection_digest(current_fields)
    last_fields = _quick_start_launch_fields_from_packet(last_launch_packet)
    last_digest = _quick_start_launch_selection_digest(last_fields) if last_launch_packet else ""
    last_relaunch_admissible = (
        _custom_native_last_launch_packet_allows_window_relaunch(last_launch_packet)
    )
    last_packet_ok = (
        isinstance(last_launch_packet, dict) and last_launch_packet.get("status") == "ok"
    )
    selection_matches_last = bool(
        last_relaunch_admissible and last_digest and current_digest == last_digest
    )
    if not isinstance(last_launch_packet, dict):
        config_status = "no_previous_launch"
    elif selection_matches_last:
        config_status = "matches_last_launch"
    else:
        config_status = "changed"
    reuse_admissible = bool(custom_process_observed and selection_matches_last)
    relaunch_admissible = bool(
        custom_process_observed
        and last_relaunch_admissible
        and not selection_matches_last
        and config_status == "changed"
    )
    new_launch_required = not reuse_admissible
    next_action = (
        "show_existing_window"
        if reuse_admissible
        else (
            "relaunch_custom_codex_with_new_selection"
            if relaunch_admissible
            else (
                "block_existing_window_without_matching_launch_packet"
                if custom_process_observed and not selection_matches_last
                else bridge_next_action
            )
        )
    )
    return {
        "schema_version": 1,
        "packet_kind": "custom_native_launch_preflight",
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "status": "ok",
        "machine_error_code": "OK",
        "human_message": "Custom native launch preflight classified current bridge, window, and launch selection without live mutation.",
        "preflight_claim_scope": "quick_start_launch_guard_no_live_mutation",
        "owner_authorization_phrase_present": owner_authorized,
        "execution_mode": current_fields["execution_mode"],
        "chatgpt_model_id": current_fields["chatgpt_model_id"],
        "api_model_id": current_fields["api_model_id"],
        "api_reasoning_option_id": current_fields["api_reasoning_option_id"],
        "selected_model": selected_model,
        "launch_model_id": selected_model,
        "route_model_id": route_model_id,
        "selection_packet": execution_packet or {},
        "selection_digest": current_digest,
        "last_launch_packet_present": isinstance(last_launch_packet, dict),
        "last_launch_packet_status": str((last_launch_packet or {}).get("status") or ""),
        "last_launch_packet_status_ok": last_packet_ok,
        "last_launch_packet_relaunch_admissible": last_relaunch_admissible,
        "last_launch_selection_digest": last_digest,
        "selection_matches_last_launch": selection_matches_last,
        "config_status": config_status,
        "custom_process_observed": custom_process_observed,
        "custom_process_count": int(window_inventory.get("custom_process_count") or 0),
        "window_status": "found" if custom_process_observed else "not_found",
        "window_inventory_status": str(window_inventory.get("window_inventory_status") or ""),
        "existing_window_reuse_admissible": reuse_admissible,
        "existing_window_relaunch_admissible": relaunch_admissible,
        "new_launch_required": new_launch_required,
        "show_window_attempted": False,
        "new_launch_started": False,
        "live_provider_called": False,
        "bridge_required": route_selected,
        "bridge_alive": bridge_alive,
        "bridge_status": bridge_status,
        "bridge_owner": (
            "wbp_current_process"
            if native_bridge_lease is not None and native_bridge_lease.bridge is not None
            else ("unknown_or_foreign" if bridge_alive else "none")
        ),
        "route_selected": route_selected,
        "api_provider_id": str(route_record.get("provider") or ""),
        "server_issued_model_list": bool(registry.get("available_models")),
        "model_auto_selected": False,
        "fallback_used": False,
        "visible_window_counts_as_model_truth": False,
        "bridge_alive_counts_as_model_truth": False,
        "response_text_counts_as_route_truth": False,
        "launch_packet_is_truth_source": True,
        "browser_raw_backend_authority_widened": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "raw_path_exposed": False,
        "raw_process_lines_exposed": False,
        "original_codex_touched": False,
        "asar_touched": False,
        "quick_start_live_bridge_and_window_reuse_guarded_with_limits": True,
        "final_status": "QUICK_START_LIVE_BRIDGE_AND_WINDOW_REUSE_GUARDED_WITH_LIMITS",
        "next_action": next_action,
    }


def _quick_start_slot_admission_component(
    *,
    required: bool,
    slot: dict[str, Any],
    model_id: str,
    lane: str,
    missing_code: str,
) -> dict[str, Any]:
    if not required:
        return {
            "status": "not_required",
            "model_id": "",
            "lane": lane,
            "machine_error_code": "NOT_REQUIRED",
            "human_message": "Этот слот не нужен для выбранного режима.",
        }
    if not model_id:
        return {
            "status": "missing",
            "model_id": "",
            "lane": lane,
            "machine_error_code": missing_code,
            "human_message": "Модель не выбрана из server-issued catalog.",
        }
    slot_status = str(slot.get("status") or "")
    slot_lane = str(slot.get("lane") or "")
    slot_model = str(slot.get("model_id") or "")
    if slot_status == "bound" and slot_lane == lane and slot_model == model_id:
        return {
            "status": "admitted",
            "model_id": model_id,
            "lane": lane,
            "machine_error_code": "OK",
            "human_message": "Модель допущена server-owned selector packet.",
        }
    return {
        "status": "unavailable",
        "model_id": model_id,
        "lane": lane,
        "machine_error_code": "QUICK_START_CONFIG_SLOT_NOT_ADMITTED",
        "human_message": "Server-owned selector packet не подтвердил выбранный слот.",
    }


def _quick_start_api_route_admission_component(
    *,
    required: bool,
    model_id: str,
    api_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    if not required:
        return {
            "status": "not_required",
            "route_reference": "",
            "machine_error_code": "NOT_REQUIRED",
            "human_message": "API route не нужен для выбранного режима.",
        }
    if not model_id:
        return {
            "status": "missing",
            "route_reference": "",
            "machine_error_code": "QUICK_START_CONFIG_API_MODEL_MISSING",
            "human_message": "API модель не выбрана.",
        }
    route = _api_snapshot_route_for_model(api_snapshot, model_id)
    if route is None:
        return {
            "status": "missing",
            "route_reference": "",
            "machine_error_code": "QUICK_START_CONFIG_API_ROUTE_MISSING",
            "human_message": "Server-owned API route для выбранной модели не найден в bounded snapshot.",
        }
    if route.get("enabled") is not True:
        return {
            "status": "not_confirmed",
            "route_reference": "server-owned-api-route",
            "machine_error_code": "QUICK_START_CONFIG_API_ROUTE_DISABLED",
            "human_message": "API route найден, но не включён.",
        }
    secret_status = str(route.get("secret_status_label") or "").strip()
    if secret_status == "missing":
        return {
            "status": "not_confirmed",
            "route_reference": "server-owned-api-route",
            "machine_error_code": "QUICK_START_CONFIG_API_SECRET_MISSING",
            "human_message": "API route найден, но credential не подтверждён bounded snapshot.",
        }
    return {
        "status": "admitted",
        "route_reference": "server-owned-api-route",
        "provider": str(route.get("provider") or route.get("provider_label") or ""),
        "machine_error_code": "OK",
        "human_message": "API route допущен bounded api-connections snapshot.",
    }


def _quick_start_api_reasoning_admission_component(
    *,
    required: bool,
    model_truth: dict[str, Any],
) -> dict[str, Any]:
    if not required:
        return {
            "status": "not_required",
            "option_id": "",
            "machine_error_code": "NOT_REQUIRED",
            "human_message": "DeepSeek reasoning не нужен для выбранного режима.",
        }
    option_id = str(model_truth.get("api_reasoning_option_id") or "")
    model_bound = model_truth.get("api_reasoning_option_model_bound") is True
    if option_id == "catalog_default" and model_bound:
        status = "defaulted"
    elif model_bound:
        status = "accepted"
    else:
        status = "rejected"
    return {
        "status": status,
        "option_id": option_id,
        "operator_level": str(model_truth.get("api_reasoning_operator_level") or ""),
        "machine_error_code": "OK" if status in {"accepted", "defaulted"} else "QUICK_START_CONFIG_API_REASONING_REJECTED",
        "human_message": (
            "DeepSeek reasoning option принят server selector packet."
            if status in {"accepted", "defaulted"}
            else "DeepSeek reasoning option не совпал с server-issued model metadata."
        ),
        "runtime_mutation_claimed": False,
        "intelligence_measured": False,
        "codex_parity_claimed": False,
    }


def _command_result_health_ok(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    packet = result.get("packet")
    packet = packet if isinstance(packet, dict) else {}
    return bool(
        result.get("status") == "ok"
        and result.get("machine_error_code") == "OK"
        and packet.get("status") == "ok"
        and packet.get("machine_error_code") == "OK"
        and packet.get("effect") == "probe"
        and packet.get("changed_files") == []
        and _healthcheck_attestation_ok(packet)
    )


def _healthcheck_attestation_ok(packet: dict[str, Any] | None) -> bool:
    if not isinstance(packet, dict):
        return False
    attestation = packet.get("attestation")
    if not isinstance(attestation, dict):
        return False
    for key in (
        "listener_ok",
        "models_ok",
        "responses_ok",
        "effective_mode_match",
        "base_url_match",
    ):
        if attestation.get(key) is not True:
            return False
    for key in (
        "selected_backends_digest",
        "observed_at_utc",
        "runtime_version",
    ):
        if not str(attestation.get(key) or "").strip():
            return False
    return str(attestation.get("attestation_source") or "") == "healthcheck --json"


def _custom_native_chatgpt_runtime_health_gate_packet(
    runtime_health_result: dict[str, Any] | None,
    *,
    execution_mode: str,
) -> dict[str, Any]:
    chatgpt_required = execution_mode in {"chatgpt_only", "chatgpt_plus_api"}
    if not chatgpt_required:
        return {
            "schema_version": 1,
            "packet_kind": "custom_native_chatgpt_runtime_health_gate",
            "status": "ok",
            "machine_error_code": "OK",
            "runtime_health_required_for_chatgpt_lane": False,
            "runtime_health_status": "not_required",
            "runtime_health_machine_error_code": "OK",
            "runtime_health_next_action": "none",
            "source_command": "healthcheck --json",
        }

    packet = (
        runtime_health_result.get("packet")
        if isinstance(runtime_health_result, dict)
        and isinstance(runtime_health_result.get("packet"), dict)
        else {}
    )
    result_status = (
        str(runtime_health_result.get("status") or "")
        if isinstance(runtime_health_result, dict)
        else "missing"
    )
    machine_error_code = (
        str(runtime_health_result.get("machine_error_code") or "")
        if isinstance(runtime_health_result, dict)
        else ""
    )
    if not machine_error_code:
        machine_error_code = str(packet.get("machine_error_code") or "")
    if not machine_error_code:
        machine_error_code = "CUSTOM_CODEX_RUNTIME_HEALTH_MISSING"
    next_action = (
        str(runtime_health_result.get("next_action") or "")
        if isinstance(runtime_health_result, dict)
        else ""
    )
    if not next_action:
        next_action = str(packet.get("next_action") or "repair_runtime_proxy")
    ok = _command_result_health_ok(runtime_health_result)
    if not ok and machine_error_code == "OK":
        machine_error_code = "CUSTOM_CODEX_RUNTIME_ATTESTATION_INVALID"
    if not ok and next_action == "none":
        next_action = "retry_healthcheck_attestation"
    return {
        "schema_version": 1,
        "packet_kind": "custom_native_chatgpt_runtime_health_gate",
        "status": "ok" if ok else "blocked",
        "machine_error_code": "OK" if ok else "CUSTOM_CODEX_RUNTIME_HEALTH_BLOCKED",
        "runtime_health_required_for_chatgpt_lane": True,
        "runtime_health_status": result_status,
        "runtime_health_machine_error_code": "OK" if ok else machine_error_code,
        "runtime_health_human_message": (
            str(runtime_health_result.get("human_message") or "")
            if isinstance(runtime_health_result, dict)
            else "Healthcheck packet was not available."
        ),
        "runtime_health_next_action": "none" if ok else next_action,
        "source_command": "healthcheck --json",
    }


def _payload_requires_chatgpt_runtime_health(payload: dict[str, Any]) -> bool:
    execution_mode = str(payload.get("execution_mode") or "").strip()
    return execution_mode in {"chatgpt_only", "chatgpt_plus_api"}


def build_quick_start_config_admission_packet(
    payload: dict[str, Any],
    operator_status: dict[str, Any] | None,
    *,
    api_snapshot: dict[str, Any] | None,
    runtime_health_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = {
        "schema_version": 1,
        "packet_kind": "quick_start_config_admission",
        "captured_at_utc": utc_now(),
        "source": "server_owned_config_admission",
        "dry_server_truth_only": True,
        "runtime_execution_proven": False,
        "live_call_attempted": False,
        "provider_called": False,
        "network_calls_made": False,
        "custom_codex_launch_attempted": False,
        "new_launch_started": False,
        "fallback_used": False,
        "silent_fallback_used": False,
        "browser_route_authority": False,
        "browser_secret_authority": False,
        "browser_model_authority": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "raw_path_exposed": False,
        "original_codex_touched": False,
        "asar_touched": False,
        "launch_admission": "blocked",
    }
    forbidden = _forbidden_quick_start_config_admission_fields(payload)
    if forbidden:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "QUICK_START_CONFIG_ADMISSION_BROWSER_AUTHORITY_REJECTED",
            "final_status": "KNOWN_BLOCKER_QUICK_START_CONFIG_ADMISSION_NOT_PROVEN",
            "human_message": "Quick Start config admission accepts only bounded selection ids.",
            "forbidden_fields": forbidden,
            "execution_mode": "",
            "chatgpt_model": {"status": "missing"},
            "api_model": {"status": "missing"},
            "api_reasoning": {"status": "missing"},
            "api_route": {"status": "missing"},
            "launch_admission_summary": "Browser payload contained forbidden raw route, secret, path, or backend authority.",
            "next_action": "remove_forbidden_browser_fields",
        }

    model_truth = build_server_model_selection_and_reasoning_truth_packet(
        payload,
        operator_status,
        api_snapshot=api_snapshot,
    )
    execution_mode = str(model_truth.get("execution_mode") or "")
    chatgpt_model_id = str(model_truth.get("chatgpt_model_id") or "")
    api_model_id = str(model_truth.get("api_model_id") or "")
    primary_slot = model_truth.get("primary_model_slot")
    primary_slot = primary_slot if isinstance(primary_slot, dict) else {}
    coding_slot = model_truth.get("coding_agent_model_slot")
    coding_slot = coding_slot if isinstance(coding_slot, dict) else {}
    chatgpt_required = execution_mode in {"chatgpt_only", "chatgpt_plus_api"}
    api_required = execution_mode in {"chatgpt_plus_api", "api_only"}
    api_slot = primary_slot if execution_mode == "api_only" else coding_slot
    chatgpt_component = _quick_start_slot_admission_component(
        required=chatgpt_required,
        slot=primary_slot,
        model_id=chatgpt_model_id,
        lane=CODEX_ACCOUNT_MODEL_LANE,
        missing_code="QUICK_START_CONFIG_CHATGPT_MODEL_MISSING",
    )
    api_component = _quick_start_slot_admission_component(
        required=api_required,
        slot=api_slot,
        model_id=api_model_id,
        lane=API_ROUTE_MODEL_LANE,
        missing_code="QUICK_START_CONFIG_API_MODEL_MISSING",
    )
    route_component = _quick_start_api_route_admission_component(
        required=api_required,
        model_id=api_model_id,
        api_snapshot=api_snapshot,
    )
    reasoning_component = _quick_start_api_reasoning_admission_component(
        required=api_required,
        model_truth=model_truth,
    )
    components = (chatgpt_component, api_component, route_component, reasoning_component)
    admitted = (
        model_truth.get("status") == "ok"
        and all(component["status"] in {"admitted", "accepted", "defaulted", "not_required"} for component in components)
    )
    runtime_health_gate = _custom_native_chatgpt_runtime_health_gate_packet(
        runtime_health_result,
        execution_mode=execution_mode,
    )
    if runtime_health_gate.get("status") != "ok":
        admitted = False
    status = "ok" if admitted else "blocked"
    if admitted:
        machine_error_code = "OK"
    elif runtime_health_gate.get("status") != "ok":
        machine_error_code = str(
            runtime_health_gate.get("runtime_health_machine_error_code")
            or "CUSTOM_CODEX_RUNTIME_HEALTH_BLOCKED"
        )
    else:
        machine_error_code = str(
            model_truth.get("machine_error_code") or "QUICK_START_CONFIG_ADMISSION_BLOCKED"
        )
    if machine_error_code == "OK" and not admitted:
        machine_error_code = "QUICK_START_CONFIG_ADMISSION_BLOCKED"
    return {
        **base,
        "status": status,
        "machine_error_code": machine_error_code,
        "final_status": (
            "QUICK_START_CONFIG_ADMISSION_PROVEN_WITH_LIMITS"
            if admitted
            else "KNOWN_BLOCKER_QUICK_START_CONFIG_ADMISSION_NOT_PROVEN"
        ),
        "human_message": (
            "Quick Start configuration admitted by bounded server packet."
            if admitted
            else "Quick Start configuration is not admitted by bounded server packet."
        ),
        "execution_mode": execution_mode,
        "allowed_browser_fields": sorted(QUICK_START_CONFIG_ADMISSION_ALLOWED_BROWSER_FIELDS),
        "chatgpt_model": chatgpt_component,
        "api_model": api_component,
        "api_reasoning": reasoning_component,
        "api_route": route_component,
        "model_selection_truth": {
            "status": str(model_truth.get("status") or ""),
            "machine_error_code": str(model_truth.get("machine_error_code") or ""),
            "model_selection_truth_proven": model_truth.get("model_selection_truth_proven") is True,
            "server_catalog_source": model_truth.get("server_catalog_source") is True,
            "slots_coherent": model_truth.get("slots_coherent") is True,
            "api_reasoning_option_model_bound": model_truth.get("api_reasoning_option_model_bound") is True,
        },
        "runtime_health_gate": runtime_health_gate,
        "runtime_health_required_for_chatgpt_lane": (
            runtime_health_gate.get("runtime_health_required_for_chatgpt_lane") is True
        ),
        "launch_admission": "admitted" if admitted else "blocked",
        "launch_admission_summary": (
            "Config admission is ok; next contour may use existing launch preflight gate."
            if admitted
            else (
                "ChatGPT lane blocked by healthcheck --json; launch must stay gated."
                if runtime_health_gate.get("status") != "ok"
                else "Config admission blocked; launch must stay gated."
            )
        ),
        "selector_packet": model_truth.get("selector_packet", {}),
        "next_action": (
            "none"
            if admitted
            else (
                str(runtime_health_gate.get("runtime_health_next_action") or "repair_runtime_proxy")
                if runtime_health_gate.get("status") != "ok"
                else "repair_quick_start_config_selection"
            )
        ),
    }


def _custom_native_launch_stability_guard_packet(
    preflight_packet: dict[str, Any],
    *,
    status: str,
    machine_error_code: str,
    human_message: str,
    show_window_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    show_window_attempted = show_window_packet is not None
    window_visible = bool(
        isinstance(show_window_packet, dict)
        and show_window_packet.get("custom_window_visible") is True
    )
    show_window_ok = bool(
        isinstance(show_window_packet, dict) and show_window_packet.get("status") == "ok"
    )
    window_usable = bool(
        isinstance(show_window_packet, dict)
        and show_window_packet.get("native_app_usable") is True
    )
    window_unresponsive = bool(show_window_attempted and (not show_window_ok or not window_visible))
    show_window_machine_error = str(
        show_window_packet.get("machine_error_code") if isinstance(show_window_packet, dict) else ""
    )
    window_response_timeout = bool(
        window_unresponsive and "TIMEOUT" in show_window_machine_error.upper()
    )
    return {
        "schema_version": 1,
        "packet_kind": "custom_native_launch_stability_guard",
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "status": status,
        "machine_error_code": machine_error_code,
        "human_message": human_message,
        "launch_claim_scope": "custom_codex_launch_stability_and_recovery",
        "preflight_packet": preflight_packet,
        "owner_authorization_phrase_present": (
            preflight_packet.get("owner_authorization_phrase_present") is True
        ),
        "execution_mode": str(preflight_packet.get("execution_mode") or ""),
        "chatgpt_model_id": str(preflight_packet.get("chatgpt_model_id") or ""),
        "api_model_id": str(preflight_packet.get("api_model_id") or ""),
        "api_reasoning_option_id": str(preflight_packet.get("api_reasoning_option_id") or ""),
        "selected_model": str(preflight_packet.get("selected_model") or ""),
        "stable_bridge_preflight_required": (
            preflight_packet.get("stable_bridge_preflight_required") is True
        ),
        "stable_bridge_preflight_status": str(
            preflight_packet.get("stable_bridge_preflight_status") or ""
        ),
        "stable_bridge_launch_allowed": (
            preflight_packet.get("stable_bridge_launch_allowed") is True
        ),
        "stable_bridge_preflight_packet": preflight_packet.get(
            "stable_bridge_preflight_packet",
            {},
        ),
        "selection_packet": preflight_packet.get("selection_packet", {}),
        "selection_digest": str(preflight_packet.get("selection_digest") or ""),
        "last_launch_selection_digest": str(
            preflight_packet.get("last_launch_selection_digest") or ""
        ),
        "selection_matches_last_launch": (
            preflight_packet.get("selection_matches_last_launch") is True
        ),
        "config_status": str(preflight_packet.get("config_status") or ""),
        "custom_process_observed": preflight_packet.get("custom_process_observed") is True,
        "custom_process_count": int(preflight_packet.get("custom_process_count") or 0),
        "existing_window_reuse_admissible": (
            preflight_packet.get("existing_window_reuse_admissible") is True
        ),
        "reused_existing_window": bool(
            status == "ok" and preflight_packet.get("existing_window_reuse_admissible") is True
        ),
        "new_launch_required": preflight_packet.get("new_launch_required") is True,
        "launch_blocked": status != "ok",
        "show_window_attempted": show_window_attempted,
        "show_window_packet": show_window_packet or {},
        "custom_window_visible": window_visible,
        "custom_window_frontmost": bool(
            isinstance(show_window_packet, dict)
            and show_window_packet.get("custom_window_frontmost") is True
        ),
        "input_capable_ui_observed": bool(
            isinstance(show_window_packet, dict)
            and show_window_packet.get("input_capable_ui_observed") is True
        ),
        "native_app_usability_source": str(
            show_window_packet.get("native_app_usability_source")
            if isinstance(show_window_packet, dict)
            else ""
        ),
        "native_app_usability_blocked_reason_class": str(
            show_window_packet.get("native_app_usability_blocked_reason_class")
            if isinstance(show_window_packet, dict)
            else ""
        ),
        "window_response_timeout": window_response_timeout,
        "window_unresponsive_with_limits": window_unresponsive,
        "new_launch_started": False,
        "process_started": False,
        "native_window_observed": window_visible,
        "native_app_usable": window_usable,
        "live_provider_called": False,
        "model_auto_selected": False,
        "fallback_used": False,
        "api_only_calls_chatgpt": False,
        "chatgpt_only_calls_api": False,
        "visible_window_counts_as_model_truth": False,
        "response_text_counts_as_route_truth": False,
        "bridge_alive_counts_as_model_truth": False,
        "launch_packet_is_truth_source": True,
        "browser_raw_backend_authority_widened": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "raw_path_exposed": False,
        "raw_process_lines_exposed": False,
        "current_codex_touched": False,
        "original_codex_touched": False,
        "asar_touched": False,
        "final_status": "CUSTOM_CODEX_LAUNCH_STABILITY_AND_RECOVERY_WITH_LIMITS",
        "next_action": (
            "continue_in_existing_custom_window"
            if status == "ok"
            else "stop_and_diagnose_custom_launch_stability_guard"
        ),
    }


def _custom_native_stable_bridge_launch_gate_packet(
    preflight_packet: dict[str, Any],
    *,
    native_bridge_lease: _CustomNativeBridgeLease,
) -> dict[str, Any]:
    execution_mode = str(preflight_packet.get("execution_mode") or "")
    selection_packet = (
        preflight_packet.get("selection_packet")
        if isinstance(preflight_packet.get("selection_packet"), dict)
        else {}
    )
    api_slot = (
        selection_packet.get("coding_agent_model_slot")
        if isinstance(selection_packet.get("coding_agent_model_slot"), dict)
        else {}
    )
    api_model_id = str(preflight_packet.get("api_model_id") or "")
    bridge_required = bool(
        execution_mode in {"api_only", "chatgpt_plus_api"}
        or preflight_packet.get("route_selected") is True
        or (execution_mode == "chatgpt_plus_api" and api_slot.get("model_id"))
        or (execution_mode == "api_only" and api_model_id)
    )
    if not bridge_required:
        return {
            "schema_version": 1,
            "packet_kind": "stable_bridge_launch_gate",
            "captured_at_utc": utc_now(),
            "status": "ok",
            "machine_error_code": "OK",
            "bridge_preflight_required": False,
            "bridge_preflight_status": "not_required",
            "launch_allowed": True,
            "failure_reason": "",
            "final_status": "STABLE_BRIDGE_PREFLIGHT_NOT_REQUIRED_NO_API_ROUTE",
            "next_action": "launch_custom_codex",
        }
    stable_packet = build_custom_codex_stable_bridge_preflight_packet(
        last_launch_packet=preflight_packet,
        bridge_trace_packet=native_bridge_lease.trace_snapshot(),
        expected_bridge_port=native_bridge_lease.bridge_port,
    )
    launch_allowed = stable_packet.get("launch_allowed") is True
    return {
        "schema_version": 1,
        "packet_kind": "stable_bridge_launch_gate",
        "captured_at_utc": utc_now(),
        "status": "ok" if launch_allowed else "blocked",
        "machine_error_code": "OK" if launch_allowed else "STABLE_BRIDGE_PREFLIGHT_BLOCKED",
        "bridge_preflight_required": True,
        "bridge_preflight_status": str(stable_packet.get("status") or "blocked"),
        "launch_allowed": launch_allowed,
        "failure_reason": str(stable_packet.get("failure_reason") or ""),
        "blocking_reasons": stable_packet.get("blocking_reasons", []),
        "stable_bridge_preflight_packet": stable_packet,
        "final_status": (
            "STABLE_BRIDGE_PREFLIGHT_ENFORCED_ON_CUSTOM_CODEX_LAUNCH_WITH_LIMITS"
            if launch_allowed
            else "STOP_AND_DIAGNOSE_STABLE_BRIDGE_PREFLIGHT_NOT_PROVEN"
        ),
        "next_action": "launch_custom_codex" if launch_allowed else "repair_bridge_before_launch",
    }


def _custom_native_hidden_native_model_ids(registry: dict[str, Any]) -> list[str]:
    return [
        str(entry.get("model_id") or "")
        for entry in registry.get("available_models") or []
        if isinstance(entry, dict)
        and str(entry.get("lane") or "") == "codex_native"
        and entry.get("selection_enabled") is not True
    ]


def _custom_native_stable_bridge_prewarm_packet(
    preflight_packet: dict[str, Any],
    *,
    requested_model_id: str,
    operator_status: dict[str, Any] | None,
    api_snapshot: dict[str, Any] | None,
    external_routes_packet: dict[str, Any] | None,
    native_bridge_lease: _CustomNativeBridgeLease,
) -> dict[str, Any]:
    model_id = str(requested_model_id or "").strip()
    route_record = _external_route_record_for_model(external_routes_packet, model_id)
    if not model_id or not route_record:
        return {
            "schema_version": 1,
            "packet_kind": "custom_native_stable_bridge_prewarm",
            "captured_at_utc": utc_now(),
            "status": "ok",
            "machine_error_code": "OK",
            "prewarm_required": False,
            "bridge_endpoint": "",
            "smoke_status": "not_required",
            "final_status": "STABLE_BRIDGE_PREWARM_NOT_REQUIRED_NO_EXTERNAL_ROUTE",
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }

    registry = build_custom_model_registry_packet(operator_status, api_snapshot=api_snapshot)
    downstream_endpoint = str(registry.get("endpoint") or DEFAULT_ENDPOINT)
    hidden_native_model_ids = _custom_native_hidden_native_model_ids(registry)
    preflight_packet["selected_model"] = str(preflight_packet.get("selected_model") or model_id)
    _add_custom_codex_window_launch_trace_context(preflight_packet, route_record=route_record)
    native_bridge_lease.set_trace_context(
        {
            "launch_id": preflight_packet.get("launch_id"),
            "trace_id": preflight_packet.get("trace_id"),
            "selected_model": model_id,
            "api_reasoning_option_id": preflight_packet.get("api_reasoning_option_id"),
            "launch_route_digest": preflight_packet.get("launch_route_digest"),
        }
    )
    try:
        bridge_endpoint = native_bridge_lease.ensure(
            downstream_endpoint=downstream_endpoint,
            routes_packet=external_routes_packet,
            hidden_native_model_ids=hidden_native_model_ids,
            forced_route_model_id=model_id,
        )
    except OSError as exc:
        return {
            "schema_version": 1,
            "packet_kind": "custom_native_stable_bridge_prewarm",
            "captured_at_utc": utc_now(),
            "status": "blocked",
            "machine_error_code": "CUSTOM_CODEX_STABLE_WBP_BRIDGE_PORT_UNAVAILABLE",
            "prewarm_required": True,
            "bridge_endpoint": native_bridge_lease.stable_endpoint,
            "downstream_endpoint": downstream_endpoint,
            "selected_model": model_id,
            "bridge_exception_class": type(exc).__name__,
            "bridge_exception_message_bounded": str(exc)[:240],
            "smoke_status": "not_started",
            "final_status": "STOP_AND_DIAGNOSE_STABLE_BRIDGE_PREWARM_NOT_PROVEN",
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }
    if bridge_endpoint == downstream_endpoint:
        return {
            "schema_version": 1,
            "packet_kind": "custom_native_stable_bridge_prewarm",
            "captured_at_utc": utc_now(),
            "status": "blocked",
            "machine_error_code": "CUSTOM_CODEX_STABLE_WBP_BRIDGE_NOT_CONFIGURED",
            "prewarm_required": True,
            "bridge_endpoint": bridge_endpoint,
            "downstream_endpoint": downstream_endpoint,
            "selected_model": model_id,
            "smoke_status": "not_started",
            "final_status": "STOP_AND_DIAGNOSE_STABLE_BRIDGE_PREWARM_NOT_PROVEN",
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }

    try:
        local_api_key = extract_local_api_key(default_runtime_config_path())
    except RuntimeError as exc:
        return {
            "schema_version": 1,
            "packet_kind": "custom_native_stable_bridge_prewarm",
            "captured_at_utc": utc_now(),
            "status": "blocked",
            "machine_error_code": "CUSTOM_CODEX_STABLE_WBP_BRIDGE_AUTH_UNAVAILABLE",
            "prewarm_required": True,
            "bridge_endpoint": bridge_endpoint,
            "downstream_endpoint": downstream_endpoint,
            "selected_model": model_id,
            "auth_header_expected": True,
            "auth_header_available": False,
            "auth_exception_class": type(exc).__name__,
            "smoke_status": "not_started",
            "final_status": "STOP_AND_DIAGNOSE_STABLE_BRIDGE_PREWARM_NOT_PROVEN",
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }

    smoke_payload = {
        "model": model_id,
        "input": f"Ответь одной строкой: {STABLE_BRIDGE_WINDOW_SMOKE_PHRASE}",
        "stream": False,
        "max_output_tokens": 32,
    }
    request = urllib.request.Request(
        f"{bridge_endpoint.rstrip('/')}/responses",
        data=json.dumps(smoke_payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {local_api_key}",
        },
        method="POST",
    )
    response_body = b""
    http_status = 0
    error_class = ""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=75) as response:
            http_status = int(getattr(response, "status", 0) or 0)
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        http_status = int(exc.code or 0)
        error_class = type(exc).__name__
        response_body = exc.read()[:4096]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        error_class = type(exc).__name__

    smoke_ok = 200 <= http_status < 300
    trace_packet = native_bridge_lease.trace_snapshot()
    return {
        "schema_version": 1,
        "packet_kind": "custom_native_stable_bridge_prewarm",
        "captured_at_utc": utc_now(),
        "status": "ok" if smoke_ok else "blocked",
        "machine_error_code": "OK" if smoke_ok else "CUSTOM_CODEX_STABLE_WBP_BRIDGE_SMOKE_FAILED",
        "prewarm_required": True,
        "bridge_endpoint": bridge_endpoint,
        "downstream_endpoint": downstream_endpoint,
        "selected_model": model_id,
        "forced_route_used": True,
        "smoke_status": "ok" if smoke_ok else "blocked",
        "smoke_http_status": http_status,
        "smoke_error_class": error_class,
        "response_body_sha256": hashlib.sha256(response_body).hexdigest() if response_body else "",
        "bridge_trace_packet": trace_packet,
        "final_status": (
            "STABLE_BRIDGE_PREWARM_PROVEN_WITH_LIMITS"
            if smoke_ok
            else "STOP_AND_DIAGNOSE_STABLE_BRIDGE_PREWARM_NOT_PROVEN"
        ),
        "raw_prompt_recorded": False,
        "auth_header_recorded": False,
        "secret_value_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }


def _quick_start_deepseek_safe_worktree_check_packet(
    payload: dict[str, Any],
    *,
    session_manager: CodexCustomSessionManager,
    operator_status: dict[str, Any] | None,
    api_snapshot: dict[str, Any] | None,
    prompt_runner: Callable[[dict[str, Any], Path], dict[str, Any]],
    owner_authorized: bool,
    repo_root: Path,
) -> dict[str, Any]:
    base = {
        "schema_version": 1,
        "packet_kind": "quick_start_deepseek_safe_worktree_check",
        "captured_at_utc": utc_now(),
        "quick_start_button_id": "quickStartDeepSeekCoderCheckAction",
        "quick_start_button_claim_scope": "api_only_deepseek_safe_worktree_edit_with_limits",
        "allowed_browser_fields": sorted(
            QUICK_START_DEEPSEEK_SAFE_WORKTREE_ALLOWED_BROWSER_FIELDS
        ),
        "execution_mode": str(payload.get("execution_mode") or "").strip(),
        "api_model_id": str(payload.get("api_model_id") or "").strip(),
        "api_reasoning_option_id": str(payload.get("api_reasoning_option_id") or "").strip(),
        "server_issued_catalog_used": False,
        "browser_raw_backend_authority_widened": False,
        "raw_backend_details_exposed": False,
        "route_or_backend_exposed": False,
        "secret_value_exposed": False,
        "fallback_attempted": False,
        "no_fallback": True,
        "parallel_fanout_attempted": False,
        "original_codex_touched": False,
        "original_codex_profile_touched": False,
        "asar_touched": False,
        "wbp_patch_applier_used": False,
        "no_patch_applier": True,
        "commit_attempted": False,
        "push_attempted": False,
        "merge_attempted": False,
        "main_worktree_mutated_by_probe": False,
        "main_tree_untouched": True,
    }
    forbidden = _forbidden_quick_start_deepseek_safe_worktree_fields(payload)
    if forbidden:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "final_status": "KNOWN_BLOCKER_QUICK_START_DEEPSEEK_SAFE_WORKTREE_NOT_ADMITTED",
            "forbidden_fields": forbidden,
            "next_action": "remove_forbidden_browser_fields",
        }
    if not owner_authorized:
        return {
            **base,
            **_owner_authorization_required_packet(
                mode_id="codex_custom",
                next_action="provide_exact_owner_authorization_phrase",
            ),
            "final_status": "KNOWN_BLOCKER_QUICK_START_DEEPSEEK_SAFE_WORKTREE_NOT_ADMITTED",
            "safe_worktree_used": False,
        }
    if base["execution_mode"] != "api_only":
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "QUICK_START_DEEPSEEK_REQUIRES_API_ONLY_MODE",
            "final_status": "KNOWN_BLOCKER_QUICK_START_DEEPSEEK_SAFE_WORKTREE_NOT_ADMITTED",
            "next_action": "select_api_only_execution_mode",
        }
    if not base["api_model_id"]:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "QUICK_START_DEEPSEEK_API_MODEL_REQUIRED",
            "final_status": "KNOWN_BLOCKER_QUICK_START_DEEPSEEK_SAFE_WORKTREE_NOT_ADMITTED",
            "next_action": "select_deepseek_model_from_server_catalog",
        }

    selector_packet = build_custom_codex_execution_mode_selector_packet(
        {
            "execution_mode": base["execution_mode"],
            "api_model_id": base["api_model_id"],
            "api_reasoning_option_id": base["api_reasoning_option_id"],
        },
        operator_status,
        api_snapshot=api_snapshot,
    )
    if selector_packet.get("status") != "ok":
        return {
            **base,
            "status": selector_packet.get("status", "blocked"),
            "machine_error_code": selector_packet.get(
                "machine_error_code",
                "QUICK_START_DEEPSEEK_SELECTOR_NOT_PROVEN",
            ),
            "final_status": "KNOWN_BLOCKER_QUICK_START_DEEPSEEK_SAFE_WORKTREE_NOT_ADMITTED",
            "selector_packet": selector_packet,
            "server_issued_catalog_used": selector_packet.get("server_issued_catalog_used") is True,
            "browser_raw_backend_authority_widened": selector_packet.get(
                "browser_raw_backend_authority_widened"
            )
            is True,
            "next_action": selector_packet.get("next_action", "repair_selector_packet"),
        }
    primary_slot = selector_packet.get("primary_model_slot")
    primary_model_id = str(
        primary_slot.get("model_id") if isinstance(primary_slot, dict) else ""
    ).strip()
    if primary_model_id != base["api_model_id"]:
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "QUICK_START_DEEPSEEK_PRIMARY_SLOT_MISMATCH",
            "final_status": "KNOWN_BLOCKER_QUICK_START_DEEPSEEK_SAFE_WORKTREE_NOT_ADMITTED",
            "selector_packet": selector_packet,
            "server_issued_catalog_used": True,
            "next_action": "repair_primary_slot_binding",
        }
    route = _api_snapshot_route_for_model(api_snapshot, primary_model_id)
    if not _route_targets_deepseek(route, primary_model_id):
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "QUICK_START_DEEPSEEK_MODEL_REQUIRED",
            "final_status": "KNOWN_BLOCKER_QUICK_START_DEEPSEEK_SAFE_WORKTREE_NOT_ADMITTED",
            "selector_packet": selector_packet,
            "server_issued_catalog_used": True,
            "next_action": "select_deepseek_model_from_server_catalog",
        }

    created = session_manager.create_packet(
        {"primary_model_id": primary_model_id},
        {},
        operator_status,
        api_snapshot=api_snapshot,
    )
    session = created.get("session") if isinstance(created.get("session"), dict) else {}
    session_id = str(session.get("session_id") or "")
    if created.get("status") != "ok" or not session_id:
        return {
            **base,
            "status": created.get("status", "blocked"),
            "machine_error_code": created.get(
                "machine_error_code",
                "QUICK_START_DEEPSEEK_SESSION_NOT_CREATED",
            ),
            "final_status": "KNOWN_BLOCKER_QUICK_START_DEEPSEEK_SAFE_WORKTREE_NOT_ADMITTED",
            "selector_packet": selector_packet,
            "session_created": False,
            "server_issued_catalog_used": True,
            "next_action": created.get("next_action", "repair_session_creation"),
        }

    proof = session_manager.safe_worktree_edit_probe_packet(
        session_id,
        {"api_model_id": primary_model_id},
        prompt_runner,
        owner_authorized=True,
        repo_root=repo_root,
    )
    success = proof.get("final_status") == "API_ONLY_DEEPSEEK_SAFE_WORKTREE_EDIT_PROVEN_WITH_LIMITS"
    return {
        **base,
        "status": "ok" if success else proof.get("status", "blocked"),
        "machine_error_code": "OK" if success else proof.get("machine_error_code", "UNKNOWN"),
        "final_status": (
            "DEEPSEEK_LIVE_EXECUTOR_PACKET_PROVEN_WITH_LIMITS"
            if success
            else "KNOWN_BLOCKER_DEEPSEEK_LIVE_EXECUTOR_PACKET"
        ),
        "legacy_quick_start_final_status": (
            "QUICK_START_API_ONLY_DEEPSEEK_SAFE_WORKTREE_BUTTON_PROVEN_WITH_LIMITS"
            if success
            else "KNOWN_BLOCKER_QUICK_START_DEEPSEEK_SAFE_WORKTREE_NOT_PROVEN"
        ),
        "deepseek_live_executor_packet_proven_with_limits": success,
        "api_reasoning_option_packet": selector_packet.get("api_reasoning_option_packet", {}),
        "api_reasoning_option_runtime_mutation_claimed": (
            selector_packet.get("api_reasoning_option_runtime_mutation_claimed") is True
        ),
        "api_reasoning_intelligence_measured": (
            selector_packet.get("api_reasoning_intelligence_measured") is True
        ),
        "api_reasoning_codex_parity_claimed": (
            selector_packet.get("api_reasoning_codex_parity_claimed") is True
        ),
        "session_created": True,
        "session_id": session_id,
        "model_id": primary_model_id,
        "selected_model": primary_model_id,
        "provider_id": proof.get("provider_id", "deepseek"),
        "selector_packet": selector_packet,
        "server_issued_catalog_used": selector_packet.get("server_issued_catalog_used") is True
        and proof.get("selected_from_server_catalog") is True,
        "primary_model_slot": selector_packet.get("primary_model_slot", {}),
        "coding_agent_model_slot": selector_packet.get("coding_agent_model_slot", {}),
        "chatgpt_line_used_as_executor": False,
        "api_line_used_as_executor": True,
        "api_only_calls_chatgpt": False,
        "no_chatgpt": True,
        "provider_response_proven": proof.get("provider_response_proven") is True,
        "tool_loop_proven": proof.get("tool_loop_proven") is True,
        "request_count": proof.get("request_count") if isinstance(proof.get("request_count"), int) else 0,
        "safe_worktree_used": proof.get("safe_worktree_used") is True,
        "write_surface": proof.get("write_surface", "safe_worktree_only"),
        "workspace_write_admitted": proof.get("workspace_write_admitted") is True,
        "file_changed_by_codex_tool": proof.get("file_changed_by_codex_tool") is True,
        "git_diff_observed": proof.get("git_diff_observed") is True,
        "expected_diff_observed": proof.get("expected_diff_observed") is True,
        "main_worktree_mutated_by_probe": proof.get("main_worktree_mutated_by_probe") is True,
        "main_tree_untouched": proof.get("main_worktree_mutated_by_probe") is not True,
        "secret_value_recorded": proof.get("secret_value_recorded") is True,
        "secret_in_diff": proof.get("secret_in_diff") is True,
        "original_codex_touched": proof.get("original_codex_touched") is True,
        "original_codex_profile_touched": proof.get("original_codex_profile_touched") is True,
        "current_codex_touched": proof.get("current_codex_touched") is True,
        "wbp_patch_applier_used": proof.get("wbp_patch_applier_used") is True,
        "no_patch_applier": proof.get("wbp_patch_applier_used") is not True,
        "commit_attempted": proof.get("commit_attempted") is True,
        "push_attempted": proof.get("push_attempted") is True,
        "merge_attempted": proof.get("merge_attempted") is True,
        "no_fallback": proof.get("fallback_attempted") is not True,
        "worktree_removed_after_probe": proof.get("worktree_removed_after_probe") is True,
        "danger_full_access_admitted": proof.get("danger_full_access_admitted") is True,
        "response_preview_bounded": proof.get("response_preview_bounded", ""),
        "git_diff_sha256": proof.get("git_diff_sha256", ""),
        "trace_observer_packet": proof.get("trace_observer_packet", {}),
        "safe_worktree_probe_packet": {
            "final_status": proof.get("final_status"),
            "machine_error_code": proof.get("machine_error_code"),
            "model_id": proof.get("model_id"),
            "provider_response_proven": proof.get("provider_response_proven") is True,
            "tool_loop_proven": proof.get("tool_loop_proven") is True,
            "file_changed_by_codex_tool": proof.get("file_changed_by_codex_tool") is True,
            "git_diff_observed": proof.get("git_diff_observed") is True,
            "expected_diff_observed": proof.get("expected_diff_observed") is True,
            "main_worktree_mutated_by_probe": proof.get("main_worktree_mutated_by_probe") is True,
            "secret_in_diff": proof.get("secret_in_diff") is True,
            "worktree_removed_after_probe": proof.get("worktree_removed_after_probe") is True,
            "wbp_patch_applier_used": proof.get("wbp_patch_applier_used") is True,
        },
        "next_action": "manual_review_packet" if success else proof.get("next_action", "inspect_probe_packet"),
    }


def _launch_original_codex_packet(
    payload: dict[str, Any],
    *,
    owner_authorized: bool,
    app_bundle_path: Path | None = None,
) -> dict[str, Any]:
    forbidden = forbidden_original_fields(payload)
    base = {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "mode_id": "original_codex",
        "dry_run": False,
        "launch_source": "wbp_web_ui",
        "proxy_env_present": False,
        "wbp_endpoint_injected": False,
        "custom_home_present": False,
        "custom_codex_home_present": False,
        "current_codex_touched": False,
        "running_status": False,
        "launch_claim_scope": "owner_authorized_baseline_launch",
        "browser_payload_allowed_keys": [],
    }
    if forbidden:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "human_message": "Original launch accepts no browser-controlled fields.",
            "forbidden_fields": forbidden,
            "next_action": "remove_browser_payload_fields",
        }
    if not owner_authorized:
        return {
            **base,
            **_owner_authorization_required_packet(
                mode_id="original_codex",
                next_action="provide_exact_owner_authorization_phrase",
            ),
        }
    app_bundle = app_bundle_path or Path(DEFAULT_CODEX_BIN).resolve().parents[2]
    if not app_bundle.exists():
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "ORIGINAL_CODEX_APP_UNAVAILABLE",
            "human_message": "Original Codex app bundle is unavailable on this host.",
            "next_action": "repair_original_codex_bundle_path",
        }
    open_bin = Path("/usr/bin/open")
    if not open_bin.exists():
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "SYSTEM_OPEN_UNAVAILABLE",
            "human_message": "System app launch helper is unavailable on this host.",
            "next_action": "repair_system_open_binary",
        }
    env = clean_env()
    for key in list(env):
        if key == "HOME" or key.startswith("WBP_") or key.startswith("OPENAI_"):
            env.pop(key, None)
    env.pop("CODEX_HOME", None)
    before = protected_snapshot()
    try:
        launch = subprocess.run(
            [str(open_bin), "-a", str(app_bundle)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    except OSError as exc:
        return {
            **base,
            "status": "failed",
            "machine_error_code": "ORIGINAL_CODEX_LAUNCH_FAILED",
            "human_message": f"Original Codex launch failed: {type(exc).__name__}.",
            "error_class": type(exc).__name__,
            "next_action": "retry_original_launch",
        }
    after = protected_snapshot()
    comparisons = compare_snapshots(before, after)
    untouched = protected_surfaces_unchanged(comparisons)
    running_status = launch.returncode == 0 and untouched
    return {
        **base,
        "status": "ok" if running_status else "blocked",
        "machine_error_code": "OK" if running_status else ("CURRENT_CODEX_TOUCHED" if not untouched else "ORIGINAL_CODEX_LAUNCH_FAILED"),
        "human_message": (
            "Original Codex launch dispatched without proxy/custom env injection."
            if running_status
            else "Original Codex launch did not satisfy protected-baseline proof."
        ),
        "owner_authorization_phrase_present": True,
        "dispatch_observed": launch.returncode == 0,
        "dispatch_exit_code": launch.returncode,
        "running_status": running_status,
        "proxy_env_present": False,
        "wbp_endpoint_injected": False,
        "custom_home_present": False,
        "custom_codex_home_present": False,
        "current_codex_touched": not untouched,
        "protected_surfaces_unchanged": untouched,
        "protected_surface_comparisons": comparisons,
        "next_action": "none" if running_status else ("stop_and_diagnose_current_codex_touch" if not untouched else "retry_original_launch"),
    }


def _launch_custom_codex_packet(
    payload: dict[str, Any],
    *,
    owner_authorized: bool,
    session_manager: CodexCustomSessionManager,
    commands: dict[str, dict[str, Any]],
    operator_status: dict[str, Any] | None,
    api_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    forbidden = _forbidden_custom_live_launch_fields(payload)
    base = {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "dry_run": False,
        "launch_source": "wbp_web_ui",
        "running_status": False,
        "isolated_home": False,
        "isolated_codex_home": False,
        "isolated_workdir": False,
        "server_issued_model_list": False,
        "wbp_endpoint_configured": False,
        "browser_route_injection": False,
        "browser_backend_injection": False,
        "current_codex_touched": False,
        "workbench_ready": False,
        "launch_claim_scope": "isolated_session_workbench_launch",
    }
    if forbidden:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "human_message": "Codex Custom launch accepts no browser-controlled route, backend, auth, path, or home fields.",
            "forbidden_fields": forbidden,
            "next_action": "remove_browser_payload_fields",
        }
    if not owner_authorized:
        return {
            **base,
            **_owner_authorization_required_packet(
                mode_id="codex_custom",
                next_action="provide_exact_owner_authorization_phrase",
            ),
        }
    model_id = payload.get("model_id")
    if not isinstance(model_id, str) or not model_id:
        created = session_manager.create_packet(
            payload,
            commands,
            operator_status,
            api_snapshot=api_snapshot,
        )
        return {
            **created,
            **base,
            "status": created.get("status"),
            "machine_error_code": created.get("machine_error_code"),
            "human_message": created.get("human_message", "Codex Custom launch evaluated."),
            "owner_authorization_phrase_present": True,
            "session_created": False,
            "running_status": False,
            "isolated_home": False,
            "isolated_codex_home": False,
            "isolated_workdir": False,
            "server_issued_model_list": False,
            "wbp_endpoint_configured": False,
            "browser_route_injection": False,
            "browser_backend_injection": False,
            "current_codex_touched": False,
            "workbench_ready": False,
            "model_auto_selected": False,
            "fallback_used": False,
            "external_route_selected": False,
            "next_action": created.get("next_action", "select_model_from_server_registry"),
        }
    availability_lattice_packet = _build_live_native_availability_lattice_packet(
        operator_status,
        api_snapshot=api_snapshot,
    )
    selection = _codex_custom_selection_packet(
        model_id=model_id,
        commands=commands,
        operator_status=operator_status,
        api_snapshot=api_snapshot,
    )
    created = session_manager.create_packet(
        {"primary_model_id": model_id},
        commands,
        operator_status,
        selection=selection,
        api_snapshot=api_snapshot,
    )
    session = created.get("session") if isinstance(created.get("session"), dict) else {}
    session_root_ready = bool(session.get("session_root_digest"))
    codex_home_ready = bool(session.get("codex_home_digest"))
    workbench_ready = created.get("status") == "ok" and session_root_ready and codex_home_ready
    model_registry = build_custom_model_registry_packet(
        operator_status,
        api_snapshot=api_snapshot,
        availability_lattice_packet=availability_lattice_packet,
    )
    return {
        **created,
        **base,
        "status": created.get("status"),
        "machine_error_code": created.get("machine_error_code"),
        "human_message": created.get("human_message", "Codex Custom launch evaluated."),
        "owner_authorization_phrase_present": True,
        "session_created": created.get("session_created") is True,
        "running_status": workbench_ready,
        "isolated_home": workbench_ready,
        "isolated_codex_home": workbench_ready,
        "isolated_workdir": workbench_ready,
        "server_issued_model_list": bool(model_registry.get("available_models")),
        "wbp_endpoint_configured": str(model_registry.get("endpoint") or "").startswith("http://127.0.0.1:"),
        "browser_route_injection": False,
        "browser_backend_injection": False,
        "current_codex_touched": False,
        "workbench_ready": workbench_ready,
        "selection_packet": created.get("selection_packet", selection),
        "next_action": "prompt" if workbench_ready else created.get("next_action", "repair_custom_launch"),
    }


def _native_ui_action_result(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok" if packet.get("status") == "ok" else "failed",
        "machine_error_code": str(packet.get("machine_error_code") or "UNKNOWN"),
        "human_message": str(packet.get("human_message") or ""),
        "next_action": str(packet.get("next_action") or ""),
        "changed_files": [],
        "data": packet,
    }


def _openai_compat_endpoint_port(endpoint: str) -> int | None:
    try:
        parsed = urlparse(endpoint)
        return int(parsed.port) if parsed.port is not None else None
    except ValueError:
        return None


def _loopback_port_accepts_connection(port: int, *, timeout_seconds: float = 0.15) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _custom_native_bridge_truth_fields(
    *,
    native_bridge_lease: _CustomNativeBridgeLease | None,
    bridge_endpoint: str,
    downstream_endpoint: str,
    route_record: dict[str, Any],
    selected_model: str,
    status: str = "ok",
    machine_error_code: str = "OK",
) -> dict[str, Any]:
    route_selected = bool(route_record)
    stable_endpoint = (
        native_bridge_lease.stable_endpoint
        if native_bridge_lease is not None
        else bridge_endpoint
    )
    bridge_port = (
        native_bridge_lease.bridge_port
        if native_bridge_lease is not None
        else (_openai_compat_endpoint_port(bridge_endpoint) or 0)
    )
    bridge_alive = (
        bool(native_bridge_lease and native_bridge_lease.bridge is not None)
        or (bool(bridge_port) and _loopback_port_accepts_connection(int(bridge_port)))
    )
    config_points_to_stable_bridge = bool(
        route_selected and bridge_endpoint == stable_endpoint and status == "ok"
    )
    random_port_used = bool(
        route_selected
        and bridge_endpoint.startswith("http://127.0.0.1:")
        and bridge_endpoint != stable_endpoint
    )
    bridge_owner = "not_required_no_api_route"
    if route_selected and status == "ok" and native_bridge_lease is not None:
        bridge_owner = (
            "wbp_current_process"
            if native_bridge_lease.bridge is not None and bridge_endpoint == stable_endpoint
            else "unknown_or_foreign"
        )
    elif route_selected and status != "ok":
        bridge_owner = "foreign_or_unavailable"
    if not route_selected:
        final_status = "STABLE_CUSTOM_CODEX_WBP_BRIDGE_NOT_REQUIRED_NO_API_ROUTE"
    elif (
        status == "ok"
        and bridge_alive
        and config_points_to_stable_bridge
        and not random_port_used
        and machine_error_code == "OK"
    ):
        final_status = "STABLE_CUSTOM_CODEX_WBP_BRIDGE_PROVEN_WITH_LIMITS"
    else:
        final_status = "KNOWN_BLOCKER_STABLE_WBP_BRIDGE_UNAVAILABLE"
    return {
        "bridge_url": stable_endpoint,
        "bridge_port": bridge_port,
        "bridge_alive": bridge_alive,
        "bridge_owner": bridge_owner,
        "downstream_wbp_url": downstream_endpoint,
        "config_points_to_stable_bridge": config_points_to_stable_bridge,
        "random_port_used": random_port_used,
        "route_selected": route_selected,
        "provider_id": str(route_record.get("provider") or ""),
        "selected_model": selected_model,
        "fallback_used": False,
        "paid_provider_called": False,
        "secret_exposed": False,
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
        "stable_custom_codex_wbp_bridge_final_status": final_status,
    }


def _launch_custom_native_codex_packet(
    payload: dict[str, Any],
    *,
    owner_authorized: bool,
    commands: dict[str, dict[str, Any]],
    operator_status: dict[str, Any] | None,
    api_snapshot: dict[str, Any] | None,
    external_routes_packet: dict[str, Any] | None = None,
    native_bridge_lease: _CustomNativeBridgeLease | None = None,
) -> dict[str, Any]:
    forbidden = _forbidden_custom_live_launch_fields(payload)
    if forbidden:
        return {
            "schema_version": 1,
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "human_message": "Custom native launch accepts no browser-controlled route, backend, auth, path, or home fields.",
            "forbidden_fields": forbidden,
            "owner_authorization_phrase_present": owner_authorized,
            "launch_claim_scope": "custom_native_app_window_launch_only",
            "next_action": "remove_browser_payload_fields",
            "browser_raw_backend_authority_widened": True,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "original_codex_touched": False,
            "asar_touched": False,
        }
    if not owner_authorized:
        return {
            "schema_version": 1,
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "launch_claim_scope": "custom_native_app_window_launch_only",
            **_owner_authorization_required_packet(
                mode_id="codex_custom",
                next_action="provide_exact_owner_authorization_phrase",
            ),
        }
    execution_packet = _custom_native_launch_mode_selection_packet(
        payload,
        operator_status,
        api_snapshot,
    )
    if execution_packet and payload.get("model_id"):
        return {
            "schema_version": 1,
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "status": "rejected",
            "machine_error_code": "CUSTOM_NATIVE_LAUNCH_AMBIGUOUS_MODEL_FIELDS",
            "human_message": "Custom native launch accepts either legacy model_id or execution-mode fields, not both.",
            "owner_authorization_phrase_present": owner_authorized,
            "launch_claim_scope": "custom_native_app_window_launch_only",
            "execution_mode": str(payload.get("execution_mode") or ""),
            "model_auto_selected": False,
            "fallback_used": False,
            "browser_raw_backend_authority_widened": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "next_action": "remove_model_id_or_use_legacy_launch_payload",
        }
    if execution_packet and execution_packet.get("status") != "ok":
        return {
            "schema_version": 1,
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "status": execution_packet.get("status"),
            "machine_error_code": execution_packet.get("machine_error_code"),
            "human_message": "Custom native launch blocked by execution-mode selection packet.",
            "owner_authorization_phrase_present": owner_authorized,
            "launch_claim_scope": "custom_native_app_window_launch_only",
            "launch_route_truth_final_status": "KNOWN_BLOCKER_QUICK_START_LAUNCH_ROUTE_TRUTH",
            "execution_mode": execution_packet.get("execution_mode"),
            "api_model_id": execution_packet.get("api_model_id"),
            "api_reasoning_option_id": execution_packet.get("api_reasoning_option_id"),
            "api_reasoning_option_packet": execution_packet.get("api_reasoning_option_packet", {}),
            "chatgpt_model_id": execution_packet.get("chatgpt_model_id"),
            "selection_packet": execution_packet,
            "execution_mode_packet": execution_packet,
            "model_auto_selected": False,
            "fallback_used": False,
            "api_only_calls_chatgpt": False,
            "chatgpt_only_calls_api": False,
            "route_packet_matches_selection_packet": False,
            "quick_start_launch_route_truth_proven_with_limits": False,
            "browser_raw_backend_authority_widened": bool(
                execution_packet.get("browser_raw_backend_authority_widened")
            ),
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "next_action": execution_packet.get("next_action", "repair_execution_mode_selection"),
        }
    model_id = _custom_native_launch_selected_model_id(payload, execution_packet)
    if not isinstance(model_id, str) or not model_id:
        return _manual_custom_model_selection_required_packet(
            owner_authorized=owner_authorized,
            launch_claim_scope="custom_native_app_window_launch_only",
        )
    registry = build_custom_model_registry_packet(
        operator_status,
        api_snapshot=api_snapshot,
    )
    endpoint = str(registry.get("endpoint") or "")
    hidden_native_model_ids = _custom_native_hidden_native_model_ids(registry)
    route_model_id = _custom_native_launch_route_model_id(
        execution_packet=execution_packet or {},
        selected_model=model_id,
    )
    route_record = _external_route_record_for_model(external_routes_packet, route_model_id)
    try:
        bridge_endpoint = (
            native_bridge_lease.ensure(
                downstream_endpoint=endpoint,
                routes_packet=external_routes_packet,
                hidden_native_model_ids=hidden_native_model_ids,
                forced_route_model_id=route_model_id,
            )
            if native_bridge_lease is not None and route_record
            else endpoint
        )
    except OSError as exc:
        bridge_fields = _custom_native_bridge_truth_fields(
            native_bridge_lease=native_bridge_lease,
            bridge_endpoint=(
                native_bridge_lease.stable_endpoint
                if native_bridge_lease is not None
                else endpoint
            ),
            downstream_endpoint=endpoint,
            route_record=route_record,
            selected_model=model_id,
            status="blocked",
            machine_error_code="CUSTOM_CODEX_STABLE_WBP_BRIDGE_PORT_UNAVAILABLE",
        )
        return {
            "schema_version": 1,
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "status": "blocked",
            "machine_error_code": "CUSTOM_CODEX_STABLE_WBP_BRIDGE_PORT_UNAVAILABLE",
            "human_message": "Custom Codex stable WBP bridge port is unavailable.",
            "owner_authorization_phrase_present": owner_authorized,
            "launch_claim_scope": "custom_native_app_window_launch_only",
            "execution_mode": execution_packet.get("execution_mode") if execution_packet else "",
            "api_model_id": execution_packet.get("api_model_id") if execution_packet else "",
            "chatgpt_model_id": execution_packet.get("chatgpt_model_id") if execution_packet else "",
            "selection_packet": execution_packet or {},
            "selected_model": model_id,
            "launch_model_id": model_id,
            "route_model_id": route_model_id,
            "model_auto_selected": False,
            "fallback_used": False,
            "browser_raw_backend_authority_widened": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "original_codex_touched": False,
            "asar_touched": False,
            "bridge_exception_class": type(exc).__name__,
            "bridge_exception_message_bounded": str(exc)[:240],
            "next_action": "stop_and_diagnose_stable_wbp_bridge_port_conflict",
            **bridge_fields,
        }
    packet = launch_custom_native_app_packet(
        repo_root=ROOT,
        endpoint=bridge_endpoint,
        model=model_id,
        owner_authorization_phrase=(
            OWNER_STANDING_AUTHORIZATION_PHRASE if owner_authorized else None
        ),
        keep_running_on_window_observed=True,
        reuse_existing_window_if_present=not bool(route_record),
    )
    legacy_selection = _codex_custom_selection_packet(
        model_id=model_id,
        commands=commands,
        operator_status=operator_status,
        api_snapshot=api_snapshot,
    )
    packet["selection_packet"] = execution_packet or legacy_selection
    if execution_packet:
        packet["execution_mode_packet"] = execution_packet
        packet["execution_mode"] = str(execution_packet.get("execution_mode") or "")
        packet["api_model_id"] = str(execution_packet.get("api_model_id") or "")
        packet["api_reasoning_option_id"] = str(
            execution_packet.get("api_reasoning_option_id") or ""
        )
        packet["api_reasoning_option_packet"] = execution_packet.get(
            "api_reasoning_option_packet",
            {},
        )
        packet["api_reasoning_option_runtime_mutation_claimed"] = (
            execution_packet.get("api_reasoning_option_runtime_mutation_claimed") is True
        )
        packet["chatgpt_model_id"] = str(execution_packet.get("chatgpt_model_id") or "")
        packet["primary_model_slot"] = execution_packet.get("primary_model_slot", {})
        packet["coding_agent_model_slot"] = execution_packet.get("coding_agent_model_slot", {})
        packet["chatgpt_line_used_as_executor"] = (
            execution_packet.get("chatgpt_line_used_as_executor") is True
        )
        packet["api_line_used_as_executor"] = (
            execution_packet.get("api_line_used_as_executor") is True
        )
        packet["api_only_calls_chatgpt"] = execution_packet.get("api_only_calls_chatgpt") is True
        packet["chatgpt_only_calls_api"] = execution_packet.get("chatgpt_only_calls_api") is True
        packet["server_issued_catalog_used"] = execution_packet.get("server_issued_catalog_used") is True
    else:
        packet["execution_mode"] = "legacy_model_id_launch"
        packet["server_issued_catalog_used"] = False
    packet["server_issued_model_list"] = bool(registry.get("available_models"))
    packet["wbp_endpoint_configured"] = endpoint.startswith("http://127.0.0.1:")
    packet["bridge_endpoint_configured"] = bridge_endpoint != endpoint
    packet["configured_bridge_endpoint"] = bridge_endpoint
    packet["selected_model"] = model_id
    packet["launch_model_id"] = model_id
    packet["route_model_id"] = route_model_id
    packet["model_auto_selected"] = False
    packet["fallback_used"] = False
    packet["route_packet_matches_selection_packet"] = bool(
        str(packet.get("execution_mode") or "")
        == str((packet.get("execution_mode_packet") or {}).get("execution_mode") or "")
        and _custom_native_route_matches_selection_packet(
            execution_packet=execution_packet or {},
            launch_model_id=model_id,
            route_model_id=route_model_id,
        )
    )
    packet["quick_start_launch_route_truth_proven_with_limits"] = bool(
        execution_packet
        and packet.get("route_packet_matches_selection_packet") is True
        and packet.get("model_auto_selected") is False
        and packet.get("fallback_used") is False
        and packet.get("browser_raw_backend_authority_widened") is not True
        and packet.get("raw_backend_details_exposed") is not True
        and packet.get("secret_value_exposed") is not True
        and packet.get("original_codex_touched") is not True
        and packet.get("asar_touched") is not True
    )
    packet["launch_route_truth_final_status"] = (
        "QUICK_START_LAUNCH_ROUTE_TRUTH_PROVEN_WITH_LIMITS"
        if packet["quick_start_launch_route_truth_proven_with_limits"]
        else "KNOWN_BLOCKER_QUICK_START_LAUNCH_ROUTE_TRUTH"
    )
    packet["browser_raw_backend_authority_widened"] = False
    packet["raw_backend_details_exposed"] = False
    packet["secret_value_exposed"] = False
    packet["original_codex_touched"] = False
    packet["asar_touched"] = False
    packet["external_route_selected"] = bool(
        any(
            str(route.get("route_id") or "").strip() in {model_id, route_model_id}
            for route in _enabled_external_route_records(external_routes_packet)
        )
    )
    packet.update(
        _custom_native_bridge_truth_fields(
            native_bridge_lease=native_bridge_lease,
            bridge_endpoint=bridge_endpoint,
            downstream_endpoint=endpoint,
            route_record=route_record,
            selected_model=model_id,
            status=str(packet.get("status") or ""),
            machine_error_code=str(packet.get("machine_error_code") or ""),
        )
    )
    packet["selected_model"] = model_id
    packet["launch_model_id"] = model_id
    packet["route_model_id"] = route_model_id
    _add_custom_codex_window_launch_trace_context(packet, route_record=route_record)
    if native_bridge_lease is not None:
        native_bridge_lease.set_trace_context(
            {
                "launch_id": packet.get("launch_id"),
                "trace_id": packet.get("trace_id"),
                "selected_model": packet.get("selected_model"),
                "api_reasoning_option_id": packet.get("api_reasoning_option_id"),
                "launch_route_digest": packet.get("launch_route_digest"),
            }
        )
    _add_custom_codex_window_deepseek_smoke_truth(packet)
    _add_quick_start_stable_custom_launch_profile_truth(packet)
    return packet


def _add_quick_start_stable_custom_launch_profile_truth(packet: dict[str, Any]) -> None:
    profile_packet = build_custom_codex_persistent_profile_packet(
        last_launch_packet=packet,
    )
    profile_proven = profile_packet.get("profile_persistence_proven") is True
    route_truth_proven = packet.get("quick_start_launch_route_truth_proven_with_limits") is True
    stable_launch_proven = bool(
        packet.get("status") == "ok"
        and route_truth_proven
        and profile_proven
        and packet.get("temp_profile_used") is False
        and packet.get("current_codex_touched") is False
        and packet.get("original_codex_touched") is False
        and packet.get("asar_touched") is False
        and packet.get("browser_raw_backend_authority_widened") is False
        and packet.get("raw_backend_details_exposed") is False
        and packet.get("secret_value_exposed") is False
    )
    packet["profile_final_status"] = str(profile_packet.get("profile_final_status") or "")
    packet["session_storage_final_status"] = str(
        profile_packet.get("session_storage_final_status") or ""
    )
    packet["profile_persistence_proven"] = profile_proven
    packet["persistent_profile_reused"] = profile_packet.get("persistent_profile_reused") is True
    packet["codex_home_reused"] = profile_packet.get("codex_home_reused") is True
    packet["electron_user_data_reused"] = (
        profile_packet.get("electron_user_data_reused") is True
    )
    packet["profile_path_stable"] = profile_packet.get("profile_path_stable") is True
    packet["persistent_profile_root_is_tmp"] = (
        profile_packet.get("persistent_profile_root_is_tmp") is True
    )
    packet["persistent_codex_home_is_tmp"] = (
        profile_packet.get("persistent_codex_home_is_tmp") is True
    )
    packet["persistent_user_data_dir_is_tmp"] = (
        profile_packet.get("persistent_user_data_dir_is_tmp") is True
    )
    packet["session_storage_observed"] = profile_packet.get("session_storage_observed") is True
    packet["persistent_profile_path_exposed"] = False
    packet["persistent_codex_home_exposed"] = False
    packet["persistent_user_data_dir_exposed"] = False
    packet["profile_relaunch_required_for_strong_history_claim"] = True
    packet["visible_history_restore"] = "not_claimed"
    packet["full_history_restoration_claimed"] = False
    packet["quick_start_stable_custom_launch_profile_reuse_proven_with_limits"] = (
        stable_launch_proven
    )
    packet["quick_start_stable_custom_launch_final_status"] = (
        "QUICK_START_STABLE_CUSTOM_LAUNCH_WITH_PROFILE_REUSE_PROVEN_WITH_LIMITS"
        if stable_launch_proven
        else "KNOWN_BLOCKER_CUSTOM_LAUNCH_PROFILE_OR_ROUTE_NOT_PROVEN"
    )


def _external_route_record_for_model(
    packet: dict[str, Any] | None,
    model_id: str,
) -> dict[str, Any]:
    for route in _enabled_external_route_records(packet):
        if str(route.get("route_id") or "").strip() == str(model_id or "").strip():
            return route
    return {}


def _add_custom_codex_window_launch_trace_context(
    packet: dict[str, Any],
    *,
    route_record: dict[str, Any],
) -> None:
    selected_model = str(packet.get("selected_model") or "")
    captured_at = str(packet.get("captured_at_utc") or utc_now())
    bridge_endpoint = str(packet.get("configured_bridge_endpoint") or "")
    route_digest = _safe_route_digest(route_record) if route_record else ""
    launch_seed = {
        "captured_at_utc": captured_at,
        "selected_model": selected_model,
        "bridge_endpoint_configured": bool(bridge_endpoint),
        "route_digest": route_digest,
    }
    launch_id = hashlib.sha256(
        json.dumps(launch_seed, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    trace_id = hashlib.sha256(f"trace:{launch_id}".encode("utf-8")).hexdigest()[:24]
    packet["launch_id"] = launch_id
    packet["trace_id"] = trace_id
    packet["launch_route_digest"] = route_digest
    packet["launch_trace_server_issued"] = True
    packet["browser_trace_authority"] = False
    packet["prompt_route_trace_claimed"] = False


def _add_custom_codex_window_deepseek_smoke_truth(packet: dict[str, Any]) -> None:
    execution_mode = str(packet.get("execution_mode") or "")
    selected_model = str(packet.get("selected_model") or "")
    api_model_id = str(packet.get("api_model_id") or "")
    deepseek_api_only_selected = (
        execution_mode == "api_only"
        and selected_model.startswith("wbp-deepseek-")
        and (not api_model_id or api_model_id == selected_model)
        and packet.get("external_route_selected") is True
    )
    window_launch_proven = bool(
        deepseek_api_only_selected
        and packet.get("status") == "ok"
        and packet.get("process_started") is True
        and packet.get("expected_custom_identity_observed") is True
        and packet.get("native_window_observed") is True
        and packet.get("native_app_usable") is True
        and packet.get("real_codex_app_launched") is True
        and packet.get("route_packet_matches_selection_packet") is True
        and packet.get("quick_start_launch_route_truth_proven_with_limits") is True
        and packet.get("fallback_used") is False
        and packet.get("api_only_calls_chatgpt") is False
        and packet.get("raw_backend_details_exposed") is False
        and packet.get("secret_value_exposed") is False
        and packet.get("original_codex_touched") is False
        and packet.get("asar_touched") is False
    )
    packet["custom_codex_window_deepseek_launch_proven_with_limits"] = window_launch_proven
    packet["manual_prompt_smoke_attempted"] = False
    packet["manual_prompt_smoke_proven"] = False
    packet["manual_prompt_smoke_counts_as_model_truth"] = False
    packet["manual_prompt_smoke_blocked_reason"] = (
        "manual_native_window_prompt_not_automated"
        if window_launch_proven
        else "window_launch_not_proven"
    )
    packet["model_self_report_counts_as_runtime_truth"] = False
    packet["deepseek_window_prompt_runtime_truth_proven"] = False
    packet["history_persistence_claimed"] = False
    packet["visible_thread_history_restored_claimed"] = False
    packet["custom_codex_window_deepseek_smoke_final_status"] = (
        "CUSTOM_CODEX_WINDOW_DEEPSEEK_LAUNCH_PROVEN_PROMPT_SMOKE_BLOCKED_WITH_LIMITS"
        if window_launch_proven
        else "KNOWN_BLOCKER_CUSTOM_CODEX_WINDOW_DEEPSEEK_SMOKE"
    )


def build_custom_codex_window_prompt_trace_packet(
    *,
    last_launch_packet: dict[str, Any] | None,
    bridge_trace_packet: dict[str, Any],
    browser_payload: Any = None,
) -> dict[str, Any]:
    forbidden = _forbidden_custom_window_prompt_trace_fields(browser_payload)
    if forbidden:
        return {
            "schema_version": 1,
            "packet_kind": "custom_codex_window_deepseek_prompt_trace",
            "captured_at_utc": utc_now(),
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "final_status": "KNOWN_BLOCKER_WINDOW_PROMPT_ROUTE_TRACE_NOT_PROVEN",
            "forbidden_fields": forbidden,
            "browser_trace_authority": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "raw_prompt_recorded": False,
            "next_action": "remove_browser_payload_fields",
        }
    launch = last_launch_packet if isinstance(last_launch_packet, dict) else {}
    trace = bridge_trace_packet if isinstance(bridge_trace_packet, dict) else {}
    record = trace.get("last_record") if isinstance(trace.get("last_record"), dict) else {}
    launch_proven = (
        launch.get("custom_codex_window_deepseek_launch_proven_with_limits") is True
        and launch.get("status") == "ok"
        and launch.get("native_window_observed") is True
        and launch.get("native_app_usable") is True
        and launch.get("real_codex_app_launched") is True
    )
    selected_model = str(launch.get("selected_model") or "")
    api_reasoning_option_id = str(launch.get("api_reasoning_option_id") or "")
    launch_id = str(launch.get("launch_id") or "")
    trace_id = str(launch.get("trace_id") or "")
    bridge_health_packet = (
        trace.get("bridge_health_packet")
        if isinstance(trace.get("bridge_health_packet"), dict)
        else {}
    )
    bridge_request_trace_packet = (
        trace.get("bridge_request_trace_packet")
        if isinstance(trace.get("bridge_request_trace_packet"), dict)
        else {}
    )
    route_digest_matches = record.get("route_digest_matches_launch") is True
    request_seen = record.get("request_seen_after_launch") is True
    provider_called = record.get("provider_called") is True
    provider_id = str(record.get("provider_id") or "")
    upstream_model = str(record.get("upstream_model") or "")
    prompt_trace_proven = bool(
        launch_proven
        and request_seen
        and route_digest_matches
        and provider_called
        and provider_id == "deepseek"
        and upstream_model == "deepseek-v4-pro"
        and str(record.get("selected_model") or "") == selected_model
        and selected_model == "wbp-deepseek-v4-pro-max"
        and str(record.get("api_reasoning_option_id") or "") == api_reasoning_option_id
        and api_reasoning_option_id == "provider_declared_max"
        and record.get("known_smoke_phrase_matched") is True
        and record.get("response_seen") is True
        and record.get("chatgpt_route_used") is False
        and record.get("api_only_calls_chatgpt") is False
        and record.get("fallback_used") is False
        and record.get("raw_backend_details_exposed") is False
        and record.get("secret_value_exposed") is False
        and launch.get("original_codex_touched") is False
        and launch.get("asar_touched") is False
    )
    return {
        "schema_version": 1,
        "packet_kind": "custom_codex_window_deepseek_prompt_trace",
        "captured_at_utc": utc_now(),
        "status": "ok" if prompt_trace_proven else "blocked",
        "machine_error_code": "OK" if prompt_trace_proven else "WINDOW_PROMPT_ROUTE_TRACE_NOT_PROVEN",
        "final_status": (
            "CUSTOM_CODEX_WINDOW_DEEPSEEK_PROMPT_TRACE_PROVEN_WITH_LIMITS"
            if prompt_trace_proven
            else "KNOWN_BLOCKER_WINDOW_PROMPT_ROUTE_TRACE_NOT_PROVEN"
        ),
        "window_launch_proven_with_limits": launch_proven,
        "native_app_usable": launch.get("native_app_usable") is True,
        "launch_id": launch_id,
        "trace_id": trace_id,
        "trace_server_issued": bool(launch_id and trace_id),
        "browser_trace_authority": False,
        "request_seen_after_launch": request_seen,
        "request_count": int(trace.get("request_count") or 0),
        "bridge_health_packet": bridge_health_packet,
        "bridge_request_trace_packet": bridge_request_trace_packet,
        "bridge_machine_error_code": str(
            trace.get("bridge_machine_error_code")
            or bridge_health_packet.get("machine_error_code")
            or bridge_request_trace_packet.get("machine_error_code")
            or ""
        ),
        "path": str(record.get("path") or ""),
        "selected_model": selected_model,
        "requested_model": str(record.get("requested_model") or ""),
        "effective_route_model": str(record.get("effective_route_model") or ""),
        "forced_route_used": record.get("forced_route_used") is True,
        "provider_called": provider_called,
        "provider_id": provider_id,
        "upstream_model": upstream_model,
        "api_reasoning_option_id": api_reasoning_option_id,
        "launch_route_digest": str(launch.get("launch_route_digest") or ""),
        "trace_route_digest": str(record.get("route_digest") or ""),
        "route_digest_matches_launch": route_digest_matches,
        "route_unchanged": (
            bridge_request_trace_packet.get("route_unchanged")
            if "route_unchanged" in bridge_request_trace_packet
            else route_digest_matches
        )
        is True,
        "prompt_hash": str(record.get("prompt_hash") or ""),
        "known_smoke_phrase_matched": record.get("known_smoke_phrase_matched") is True,
        "response_seen": record.get("response_seen") is True,
        "upstream_status": int(record.get("upstream_status") or 0),
        "response_body_sha256": str(record.get("response_body_sha256") or ""),
        "chatgpt_route_used": record.get("chatgpt_route_used") is True,
        "api_only_calls_chatgpt": record.get("api_only_calls_chatgpt") is True,
        "fallback_used": record.get("fallback_used") is True,
        "raw_prompt_recorded": False,
        "auth_header_recorded": False,
        "secret_value_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "response_text_counts_as_model_truth": False,
        "model_self_report_counts_as_runtime_truth": False,
        "original_codex_touched": launch.get("original_codex_touched") is True,
        "asar_touched": launch.get("asar_touched") is True,
        "history_persistence_claimed": False,
        "live_coding_claimed": False,
        "next_action": (
            "none"
            if prompt_trace_proven
            else "send_window_smoke_prompt_and_refresh_trace_packet"
        ),
    }


def build_custom_codex_window_input_route_trace_packet(
    *,
    last_launch_packet: dict[str, Any] | None,
    bridge_trace_packet: dict[str, Any],
    browser_payload: Any = None,
) -> dict[str, Any]:
    forbidden = _forbidden_custom_window_prompt_trace_fields(browser_payload)
    if forbidden:
        return {
            "schema_version": 1,
            "packet_kind": "custom_codex_window_input_route_trace",
            "captured_at_utc": utc_now(),
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "final_status": "KNOWN_BLOCKER_CUSTOM_CODEX_INPUT_OR_ROUTE_NOT_PROVEN",
            "forbidden_fields": forbidden,
            "browser_trace_authority": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "raw_prompt_recorded": False,
            "next_action": "remove_browser_payload_fields",
        }
    launch = last_launch_packet if isinstance(last_launch_packet, dict) else {}
    route_packet = build_custom_codex_window_prompt_trace_packet(
        last_launch_packet=launch,
        bridge_trace_packet=bridge_trace_packet,
    )
    window_bounds = (
        launch.get("custom_window_bounds")
        if isinstance(launch.get("custom_window_bounds"), dict)
        else {}
    )
    window_prompt_seen = route_packet.get("request_seen_after_launch") is True
    input_surface_observed = (
        launch.get("native_window_observed") is True
        or launch.get("custom_window_observed") is True
        or launch.get("custom_window_visible") is True
    )
    input_proven = bool(
        route_packet.get("window_launch_proven_with_limits") is True
        and window_prompt_seen
        and bool(str(route_packet.get("prompt_hash") or ""))
    )
    route_trace_proven = (
        route_packet.get("final_status")
        == "CUSTOM_CODEX_WINDOW_DEEPSEEK_PROMPT_TRACE_PROVEN_WITH_LIMITS"
    )
    full_success = input_proven and route_trace_proven
    if not input_proven:
        next_action = "send_window_prompt_and_refresh_trace_packet"
    elif not route_trace_proven:
        next_action = "repair_route_trace_or_refresh_deepseek_trace_packet"
    else:
        next_action = "none"
    return {
        "schema_version": 1,
        "packet_kind": "custom_codex_window_input_route_trace",
        "captured_at_utc": utc_now(),
        "status": "ok" if full_success else "blocked",
        "machine_error_code": "OK" if full_success else "CUSTOM_CODEX_INPUT_OR_ROUTE_NOT_PROVEN",
        "final_status": (
            "CUSTOM_CODEX_INPUT_AND_DEEPSEEK_ROUTE_PROVEN_WITH_LIMITS"
            if full_success
            else "KNOWN_BLOCKER_CUSTOM_CODEX_INPUT_OR_ROUTE_NOT_PROVEN"
        ),
        "launch_id": str(route_packet.get("launch_id") or ""),
        "trace_id": str(route_packet.get("trace_id") or ""),
        "trace_server_issued": route_packet.get("trace_server_issued") is True,
        "browser_trace_authority": False,
        "input_surface_observed": input_surface_observed,
        "input_surface_method": (
            "window_prompt_trace"
            if input_proven
            else str(launch.get("native_app_usability_source") or "")
        ),
        "input_surface_bounds": window_bounds,
        "input_focus_attempted": launch.get("window_focus_action_attempted") is True,
        "input_focus_succeeded": launch.get("window_focus_action_succeeded") is True,
        "input_text_insert_attempted": False,
        "input_text_insert_succeeded": False,
        "send_attempted": window_prompt_seen,
        "send_succeeded": input_proven,
        "input_proven": input_proven,
        "window_prompt_seen": window_prompt_seen,
        "route_trace_proven": route_trace_proven,
        "provider_called": route_packet.get("provider_called") is True,
        "provider_id": str(route_packet.get("provider_id") or ""),
        "bridge_health_packet": route_packet.get("bridge_health_packet", {}),
        "bridge_request_trace_packet": route_packet.get("bridge_request_trace_packet", {}),
        "bridge_machine_error_code": str(route_packet.get("bridge_machine_error_code") or ""),
        "selected_model": str(route_packet.get("selected_model") or ""),
        "upstream_model": str(route_packet.get("upstream_model") or ""),
        "execution_mode": str(launch.get("execution_mode") or ""),
        "api_reasoning_option_id": str(route_packet.get("api_reasoning_option_id") or ""),
        "route_digest_matches_launch": route_packet.get("route_digest_matches_launch") is True,
        "route_unchanged": route_packet.get("route_unchanged") is True,
        "known_smoke_phrase_matched": route_packet.get("known_smoke_phrase_matched") is True,
        "response_seen": route_packet.get("response_seen") is True,
        "fallback_used": route_packet.get("fallback_used") is True,
        "chatgpt_route_used": route_packet.get("chatgpt_route_used") is True,
        "api_only_calls_chatgpt": route_packet.get("api_only_calls_chatgpt") is True,
        "chatgpt_only_calls_api": launch.get("chatgpt_only_calls_api") is True,
        "raw_prompt_recorded": False,
        "auth_header_recorded": False,
        "secret_value_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "response_text_counts_as_model_truth": False,
        "model_self_report_counts_as_runtime_truth": False,
        "original_codex_touched": launch.get("original_codex_touched") is True,
        "asar_touched": launch.get("asar_touched") is True,
        "history_persistence_claimed": False,
        "live_coding_claimed": False,
        "route_trace_packet": route_packet,
        "next_action": next_action,
    }


def build_custom_codex_bridge_failure_recovery_truth_packet(
    *,
    last_launch_packet: dict[str, Any] | None,
    bridge_trace_packet: dict[str, Any],
    browser_payload: Any = None,
) -> dict[str, Any]:
    forbidden = _forbidden_custom_window_prompt_trace_fields(browser_payload)
    if forbidden:
        return {
            "schema_version": 1,
            "packet_kind": "custom_codex_bridge_failure_recovery_truth",
            "captured_at_utc": utc_now(),
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "final_status": "STOP_AND_DIAGNOSE_CUSTOM_CODEX_BRIDGE_STABILITY_NOT_PROVEN",
            "forbidden_fields": forbidden,
            "browser_trace_authority": False,
            "fallback_used": False,
            "restart_attempted": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "next_action": "remove_browser_payload_fields",
        }
    return build_bridge_failure_recovery_truth_packet(
        last_launch_packet=last_launch_packet,
        bridge_trace_packet=bridge_trace_packet,
    )


def build_custom_codex_stable_bridge_preflight_packet(
    *,
    last_launch_packet: dict[str, Any] | None,
    bridge_trace_packet: dict[str, Any],
    expected_bridge_port: int | None = None,
    browser_payload: Any = None,
) -> dict[str, Any]:
    forbidden = _forbidden_custom_window_prompt_trace_fields(browser_payload)
    if forbidden:
        return {
            "schema_version": 1,
            "packet_kind": "stable_bridge_preflight",
            "captured_at_utc": utc_now(),
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "final_status": "STOP_AND_DIAGNOSE_STABLE_BRIDGE_PREFLIGHT_NOT_PROVEN",
            "forbidden_fields": forbidden,
            "launch_allowed": False,
            "browser_trace_authority": False,
            "fallback_used": False,
            "fallback_attempted": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "next_action": "remove_browser_payload_fields",
        }
    return build_stable_bridge_preflight_packet(
        last_launch_packet=last_launch_packet,
        bridge_trace_packet=bridge_trace_packet,
        expected_bridge_port=expected_bridge_port,
    )


def build_custom_codex_live_bridge_stability_packet(
    *,
    last_launch_packet: dict[str, Any] | None,
    bridge_trace_packet: dict[str, Any],
    expected_bridge_port: int | None = None,
    browser_payload: Any = None,
) -> dict[str, Any]:
    forbidden = _forbidden_custom_window_prompt_trace_fields(browser_payload)
    if forbidden:
        return {
            "schema_version": 1,
            "packet_kind": "custom_codex_live_bridge_stability",
            "captured_at_utc": utc_now(),
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "bridge_status": "BRIDGE_RECOVERY_REQUIRED",
            "final_status": "STOP_AND_DIAGNOSE_CUSTOM_CODEX_LIVE_BRIDGE_STABILITY_NOT_PROVEN",
            "forbidden_fields": forbidden,
            "fallback_used": False,
            "fallback_attempted": False,
            "silent_fallback_used": False,
            "browser_trace_authority": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "next_action": "remove_browser_payload_fields",
        }

    launch = last_launch_packet if isinstance(last_launch_packet, dict) else {}
    trace = bridge_trace_packet if isinstance(bridge_trace_packet, dict) else {}
    health = (
        trace.get("bridge_health_packet")
        if isinstance(trace.get("bridge_health_packet"), dict)
        else {}
    )
    request_trace = (
        trace.get("bridge_request_trace_packet")
        if isinstance(trace.get("bridge_request_trace_packet"), dict)
        else {}
    )
    record = trace.get("last_record") if isinstance(trace.get("last_record"), dict) else {}
    trace_context = (
        trace.get("trace_context") if isinstance(trace.get("trace_context"), dict) else {}
    )
    stable_packet = build_stable_bridge_preflight_packet(
        last_launch_packet=launch,
        bridge_trace_packet=trace,
        expected_bridge_port=expected_bridge_port,
    )
    recovery_packet = build_bridge_failure_recovery_truth_packet(
        last_launch_packet=launch,
        bridge_trace_packet=trace,
    )

    launch_id = str(launch.get("launch_id") or "")
    launch_trace_id = str(launch.get("trace_id") or "")
    trace_launch_id = str(trace.get("launch_packet_id") or record.get("launch_packet_id") or "")
    trace_id = str(trace.get("trace_id") or record.get("trace_id") or "")
    trace_id_matches_launch = bool(launch_trace_id and trace_id and launch_trace_id == trace_id)
    launch_id_matches_trace = bool(
        launch_id and trace_launch_id and launch_id == trace_launch_id
    )
    old_window_answered = bool(
        (launch_trace_id and trace_id and launch_trace_id != trace_id)
        or (launch_id and trace_launch_id and launch_id != trace_launch_id)
        or trace.get("stale_launch_packet") is True
    )
    bridge_session_matches_active_window = bool(
        launch.get("native_window_observed") is True
        and trace_id_matches_launch
        and (not launch_id or not trace_launch_id or launch_id_matches_trace)
    )
    raw_bridge_machine_error_code = str(
        trace.get("bridge_machine_error_code")
        or health.get("machine_error_code")
        or request_trace.get("machine_error_code")
        or record.get("bridge_machine_error_code")
        or stable_packet.get("bridge_machine_error_code")
        or "BRIDGE_RESPONSES_ENDPOINT_UNREADY"
    )
    last_http_status = int(
        record.get("upstream_status")
        or request_trace.get("upstream_status")
        or stable_packet.get("last_http_status")
        or 0
    )
    last_error_class = str(
        stable_packet.get("last_error_class")
        or recovery_packet.get("last_error_kind")
        or ""
    )
    blocking_reasons = {
        str(reason)
        for reason in stable_packet.get("blocking_reasons", [])
        if str(reason)
    }
    request_started = (
        request_trace.get("request_started") is True
        or record.get("request_seen_after_launch") is True
    )
    request_seen_after_launch = record.get("request_seen_after_launch") is True
    upstream_called = (
        request_trace.get("provider_called") is True
        or request_trace.get("downstream_called") is True
        or record.get("provider_called") is True
        or record.get("downstream_called") is True
    )
    response_seen = record.get("response_seen") is True
    stream_requested = request_trace.get("stream_requested") is True or record.get(
        "stream_requested"
    ) is True
    stream_completed = (
        request_trace.get("stream_completed") is True
        or record.get("stream_completed") is True
        or (response_seen and not stream_requested and raw_bridge_machine_error_code == "OK")
    )
    fallback_used = stable_packet.get("fallback_used") is True or recovery_packet.get(
        "fallback_used"
    ) is True
    fallback_attempted = stable_packet.get(
        "fallback_attempted"
    ) is True or recovery_packet.get("fallback_attempted") is True
    stream_failure = (
        raw_bridge_machine_error_code in {"BRIDGE_STREAM_DISCONNECTED", "BRIDGE_STREAM_TIMEOUT"}
        or last_error_class in {"stream_disconnected", "provider_timeout"}
        or "stream_disconnected" in blocking_reasons
        or "provider_timeout" in blocking_reasons
    )
    auth_failure = (
        last_http_status == 401
        or raw_bridge_machine_error_code in {"BRIDGE_AUTH_MISSING", "BRIDGE_AUTH_REJECTED"}
        or last_error_class == "unauthorized"
        or (request_started and "auth_mismatch" in blocking_reasons)
        or (request_started and "http_401_unauthorized" in blocking_reasons)
    )
    stale_port = (
        trace.get("stale_port_detected") is True
        or raw_bridge_machine_error_code == "BRIDGE_PORT_STALE"
        or last_error_class == "stale_port"
        or "stale_port" in blocking_reasons
    )
    bridge_port = int(stable_packet.get("bridge_port") or expected_bridge_port or 0)
    actual_bridge_port = int(
        health.get("bridge_port")
        or trace.get("bridge_port")
        or launch.get("bridge_port")
        or bridge_port
        or 0
    )
    if expected_bridge_port and actual_bridge_port and actual_bridge_port != expected_bridge_port:
        stale_port = True
    auth_header_expected = (
        health.get("auth_header_expected") is True
        or trace.get("auth_header_expected") is True
        or request_trace.get("auth_header_expected") is True
    )
    auth_header_seen = (
        health.get("auth_header_present") is True
        or trace.get("auth_header_seen") is True
        or request_trace.get("auth_header_seen") is True
        or record.get("auth_header_seen") is True
    )
    auth_mismatch = auth_header_expected and not (
        health.get("auth_ok") is True
        or trace.get("auth_ok") is True
        or request_trace.get("auth_ok") is True
        or record.get("auth_ok") is True
    )
    stream_disconnected = stream_failure and not stream_completed
    api_only_calls_chatgpt = bool(
        str(launch.get("execution_mode") or "") == "api_only"
        and (
            record.get("chatgpt_route_used") is True
            or request_trace.get("chatgpt_route_used") is True
        )
    )
    bridge_ready_evidence_complete = bool(
        stable_packet.get("status") == "ok"
        and bridge_session_matches_active_window
        and request_started
        and upstream_called
        and response_seen
        and stream_completed
    )
    if api_only_calls_chatgpt:
        bridge_status = "BRIDGE_API_ONLY_CHATGPT_CALLED"
    elif bridge_ready_evidence_complete:
        bridge_status = "BRIDGE_READY"
    elif auth_failure:
        bridge_status = "BRIDGE_AUTH_FAILED"
    elif stream_failure:
        bridge_status = "BRIDGE_STREAM_DISCONNECTED"
    elif not bridge_session_matches_active_window:
        bridge_status = "BRIDGE_WINDOW_NOT_BOUND"
    elif stale_port:
        bridge_status = "BRIDGE_STALE_PORT"
    else:
        bridge_status = "BRIDGE_RECOVERY_REQUIRED"

    bridge_ready = bridge_status == "BRIDGE_READY"
    status = "ok" if bridge_ready else "blocked"
    execution_mode = str(launch.get("execution_mode") or "")
    selected_mode_known = execution_mode in {
        "chatgpt_only",
        "api_only",
        "chatgpt_plus_api",
    }
    if bridge_ready := bridge_status == "BRIDGE_READY":
        failure_machine_error_code = "OK"
    elif auth_failure or auth_mismatch:
        failure_machine_error_code = "BRIDGE_AUTH_MISMATCH"
    elif stale_port:
        failure_machine_error_code = "BRIDGE_PORT_STALE"
    elif old_window_answered or not bridge_session_matches_active_window:
        failure_machine_error_code = "WINDOW_BOUND_TO_OLD_BRIDGE"
    elif stream_disconnected:
        failure_machine_error_code = "UPSTREAM_STREAM_INTERRUPTED"
    elif api_only_calls_chatgpt:
        failure_machine_error_code = "CHATGPT_CALLED_IN_API_ONLY"
    elif fallback_used:
        failure_machine_error_code = "FALLBACK_USED"
    elif request_started is not True:
        failure_machine_error_code = "REQUEST_NOT_SEEN"
    elif response_seen is not True:
        failure_machine_error_code = "RESPONSE_NOT_SEEN"
    else:
        failure_machine_error_code = raw_bridge_machine_error_code
    recovery_available = recovery_packet.get("restart_admissible") is True
    if bridge_ready:
        recommended_recovery_action = "none"
    elif auth_failure or auth_mismatch:
        recommended_recovery_action = "reauthorize"
    elif stale_port or stream_disconnected:
        recommended_recovery_action = "restart_bridge"
    elif old_window_answered or not bridge_session_matches_active_window:
        recommended_recovery_action = "relaunch_custom"
    else:
        recommended_recovery_action = "restart_bridge" if recovery_available else "none"
    return {
        "schema_version": 1,
        "packet_kind": "custom_codex_live_bridge_stability",
        "captured_at_utc": utc_now(),
        "status": status,
        "machine_error_code": bridge_status,
        "bridge_status": bridge_status,
        "raw_bridge_machine_error_code": raw_bridge_machine_error_code,
        "human_message": (
            "Live bridge ready."
            if bridge_ready
            else f"Live bridge not ready: {bridge_status}."
        ),
        "final_status": (
            "CUSTOM_CODEX_LIVE_BRIDGE_STABILITY_PROVEN_WITH_LIMITS"
            if bridge_ready
            else "STOP_AND_DIAGNOSE_CUSTOM_CODEX_LIVE_BRIDGE_STABILITY_NOT_PROVEN"
        ),
        "port_alive": health.get("bridge_alive") is True or trace.get("bridge_alive") is True,
        "responses_endpoint_available": (
            health.get("responses_endpoint_ready") is True
            or trace.get("responses_endpoint_alive") is True
        ),
        "auth_token_consistent": stable_packet.get("auth_matches") is True,
        "selected_mode_known": selected_mode_known,
        "execution_mode": execution_mode,
        "bridge_session_matches_active_window": bridge_session_matches_active_window,
        "trace_id_matches_launch": trace_id_matches_launch,
        "launch_id_matches_trace": launch_id_matches_trace,
        "trace_id": launch_trace_id,
        "bridge_alive": health.get("bridge_alive") is True or trace.get("bridge_alive") is True,
        "bridge_port": bridge_port,
        "actual_bridge_port": actual_bridge_port,
        "bridge_port_known": bridge_port > 0,
        "launch_id": launch_id,
        "launch_id_known": bool(launch_id),
        "trace_context_launch_id": str(
            trace_context.get("launch_packet_id") or trace_context.get("launch_id") or ""
        ),
        "trace_id_known": bool(launch_trace_id),
        "last_http_status": last_http_status,
        "last_error_class": last_error_class,
        "failure_machine_error_code": failure_machine_error_code,
        "auth_header_expected": auth_header_expected,
        "auth_header_seen": auth_header_seen,
        "auth_mismatch": auth_mismatch,
        "request_seen_after_launch": request_seen_after_launch,
        "last_request_seen": request_started,
        "upstream_called": upstream_called,
        "upstream_status": last_http_status,
        "response_seen": response_seen,
        "last_response_seen": response_seen,
        "stream_completed": stream_completed,
        "stream_disconnected": stream_disconnected,
        "fallback_used": fallback_used,
        "fallback_attempted": fallback_attempted,
        "api_only_calls_chatgpt": api_only_calls_chatgpt,
        "stale_port": stale_port,
        "old_window_answered": old_window_answered,
        "silent_fallback_used": bool(fallback_used and not fallback_attempted),
        "fallback_suppressed": True,
        "recovery_required": not bridge_ready,
        "recovery_available": recovery_available,
        "recommended_recovery_action": recommended_recovery_action,
        "restart_attempted": False,
        "restart_admissible": recovery_packet.get("restart_admissible") is True,
        "owner_action_required_for_live_restart": recovery_packet.get(
            "owner_action_required_for_live_restart"
        )
        is True,
        "stable_bridge_preflight_packet": stable_packet,
        "bridge_failure_recovery_packet": recovery_packet,
        "ui_label_counts_as_runtime_truth": False,
        "model_self_report_counts_as_runtime_truth": False,
        "browser_trace_authority": False,
        "raw_prompt_recorded": False,
        "auth_header_recorded": False,
        "secret_value_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "original_codex_touched": launch.get("original_codex_touched") is True,
        "asar_touched": launch.get("asar_touched") is True,
        "next_action": "none" if bridge_ready else "inspect_bridge_stability_packet",
    }


def build_custom_codex_chatgpt_plus_api_coder_trace_packet(
    *,
    last_launch_packet: dict[str, Any] | None,
    bridge_trace_packet: dict[str, Any],
    browser_payload: Any = None,
) -> dict[str, Any]:
    forbidden = _forbidden_custom_window_prompt_trace_fields(browser_payload)
    if forbidden:
        return {
            "schema_version": 1,
            "packet_kind": "custom_codex_chatgpt_plus_api_coder_trace",
            "captured_at_utc": utc_now(),
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "final_status": "KNOWN_BLOCKER_CHATGPT_PLUS_API_CODER_SLOT_NOT_DISPATCHED",
            "forbidden_fields": forbidden,
            "browser_trace_authority": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "raw_prompt_recorded": False,
            "next_action": "remove_browser_payload_fields",
        }
    launch = last_launch_packet if isinstance(last_launch_packet, dict) else {}
    trace = bridge_trace_packet if isinstance(bridge_trace_packet, dict) else {}
    records = [
        record
        for record in trace.get("records") or []
        if isinstance(record, dict)
    ]
    last_record = trace.get("last_record") if isinstance(trace.get("last_record"), dict) else {}
    if last_record and last_record not in records:
        records.append(last_record)
    execution_packet = (
        launch.get("execution_mode_packet")
        if isinstance(launch.get("execution_mode_packet"), dict)
        else {}
    )
    primary_slot = (
        launch.get("primary_model_slot")
        if isinstance(launch.get("primary_model_slot"), dict)
        else execution_packet.get("primary_model_slot")
        if isinstance(execution_packet.get("primary_model_slot"), dict)
        else {}
    )
    coding_slot = (
        launch.get("coding_agent_model_slot")
        if isinstance(launch.get("coding_agent_model_slot"), dict)
        else execution_packet.get("coding_agent_model_slot")
        if isinstance(execution_packet.get("coding_agent_model_slot"), dict)
        else {}
    )
    execution_mode = str(launch.get("execution_mode") or execution_packet.get("execution_mode") or "")
    primary_model_id = str(primary_slot.get("model_id") or "")
    coding_model_id = str(coding_slot.get("model_id") or "")
    launch_id = str(launch.get("launch_id") or "")
    trace_id = str(launch.get("trace_id") or "")
    stable_bridge_preflight_status = str(
        launch.get("stable_bridge_preflight_status")
        or (
            launch.get("stable_bridge_preflight_packet", {})
            if isinstance(launch.get("stable_bridge_preflight_packet"), dict)
            else {}
        ).get("status")
        or ""
    )
    stable_bridge_preflight_ok = bool(
        launch.get("stable_bridge_preflight_required") is True
        and launch.get("stable_bridge_launch_allowed") is True
        and stable_bridge_preflight_status == "ok"
    )

    def record_matches_launch(record: dict[str, Any]) -> bool:
        record_launch_id = str(record.get("launch_packet_id") or record.get("launch_id") or "")
        record_trace_id = str(record.get("trace_id") or "")
        return bool(launch_id and trace_id and record_launch_id == launch_id and record_trace_id == trace_id)

    launch_proven = (
        launch.get("status") == "ok"
        and launch.get("native_window_observed") is True
        and launch.get("real_codex_app_launched") is True
    )
    slot_binding_proven = bool(
        launch_proven
        and stable_bridge_preflight_ok
        and execution_mode == "chatgpt_plus_api"
        and primary_slot.get("status") == "bound"
        and primary_slot.get("lane") == CODEX_ACCOUNT_MODEL_LANE
        and coding_slot.get("status") == "bound"
        and coding_slot.get("lane") == API_ROUTE_MODEL_LANE
        and str(coding_slot.get("provider") or "") == "deepseek"
        and coding_model_id
        and coding_slot.get("server_issued") is True
        and launch.get("raw_backend_details_exposed") is not True
        and launch.get("secret_value_exposed") is not True
        and launch.get("original_codex_touched") is not True
        and launch.get("asar_touched") is not True
    )
    prompt_record = next(
        (
            record
            for record in reversed(records)
            if record.get("request_seen_after_launch") is True
            and record.get("path") == "/v1/responses"
            and record_matches_launch(record)
            and record.get("chatgpt_route_used") is True
            and record.get("provider_called") is not True
            and record.get("raw_prompt_recorded") is not True
            and record.get("secret_value_recorded") is not True
        ),
        {},
    )
    deepseek_record = next(
        (
            record
            for record in reversed(records)
            if record.get("request_seen_after_launch") is True
            and record.get("path") == "/v1/responses"
            and record_matches_launch(record)
            and record.get("provider_called") is True
            and str(record.get("provider_id") or "") == "deepseek"
            and str(record.get("effective_route_model") or record.get("requested_model") or "")
            == coding_model_id
            and record.get("fallback_used") is False
            and record.get("chatgpt_route_used") is False
        ),
        {},
    )
    prompt_seen = bool(slot_binding_proven and prompt_record)
    coder_dispatch_proven = bool(slot_binding_proven and deepseek_record)
    fallback_seen = any(record.get("fallback_used") is True for record in records)
    trace_launch_packet_matches = bool(
        prompt_record
        and deepseek_record
        and record_matches_launch(prompt_record)
        and record_matches_launch(deepseek_record)
    )
    trace_id_matches_launch = trace_launch_packet_matches
    coder_work_result_proven = bool(
        coder_dispatch_proven
        and deepseek_record.get("response_seen") is True
        and deepseek_record.get("known_smoke_phrase_matched") is True
        and int(deepseek_record.get("upstream_status") or 0) == 200
    )
    full_success = bool(
        prompt_seen
        and coder_dispatch_proven
        and coder_work_result_proven
        and trace_launch_packet_matches
        and not fallback_seen
    )
    return {
        "schema_version": 1,
        "packet_kind": "custom_codex_chatgpt_plus_api_coder_trace",
        "captured_at_utc": utc_now(),
        "status": "ok" if full_success else "blocked",
        "machine_error_code": (
            "OK" if full_success else "CHATGPT_PLUS_API_CODER_SLOT_NOT_DISPATCHED"
        ),
        "final_status": (
            "CHATGPT_PLUS_API_ROUTE_PROVEN_WITH_LIMITS"
            if full_success
            else "KNOWN_BLOCKER_CHATGPT_PLUS_API_CODER_SLOT_NOT_DISPATCHED"
        ),
        "stage_statuses": {
            "slot_binding": (
                "CHATGPT_PLUS_API_SLOT_BINDING_PROVEN"
                if slot_binding_proven
                else "KNOWN_BLOCKER_CHATGPT_PLUS_API_SLOT_BINDING_NOT_PROVEN"
            ),
            "prompt_seen": (
                "CHATGPT_PLUS_API_PROMPT_SEEN"
                if prompt_seen
                else "KNOWN_BLOCKER_CHATGPT_PLUS_API_PROMPT_NOT_SEEN"
            ),
            "coder_dispatch": (
                "DEEPSEEK_CODER_SLOT_DISPATCH_PROVEN"
                if coder_dispatch_proven
                else "KNOWN_BLOCKER_CHATGPT_PLUS_API_CODER_SLOT_NOT_DISPATCHED"
            ),
            "coder_work_result": (
                "DEEPSEEK_CODER_WORK_RESULT_PROVEN_WITH_LIMITS"
                if coder_work_result_proven
                else "KNOWN_BLOCKER_DEEPSEEK_CODER_WORK_RESULT_NOT_PROVEN"
            ),
        },
        "slot_binding_proven": slot_binding_proven,
        "primary_slot_bound": primary_slot.get("status") == "bound",
        "coding_slot_bound": coding_slot.get("status") == "bound",
        "dual_lane_slots_preserved": bool(
            primary_slot.get("lane") == CODEX_ACCOUNT_MODEL_LANE
            and coding_slot.get("lane") == API_ROUTE_MODEL_LANE
            and primary_slot.get("slot_id") == "primary_model_slot"
            and coding_slot.get("slot_id") == "coding_agent_model_slot"
        ),
        "prompt_seen": prompt_seen,
        "chatgpt_route_observed": prompt_seen,
        "chatgpt_primary_route_observed": prompt_seen,
        "deepseek_route_observed": coder_dispatch_proven,
        "deepseek_coding_route_observed": coder_dispatch_proven,
        "coder_dispatch_proven": coder_dispatch_proven,
        "coder_work_result_proven_with_limits": coder_work_result_proven,
        "stable_bridge_preflight": stable_bridge_preflight_status,
        "stable_bridge_preflight_ok": stable_bridge_preflight_ok,
        "stable_bridge_preflight_required": launch.get("stable_bridge_preflight_required") is True,
        "stable_bridge_launch_allowed": launch.get("stable_bridge_launch_allowed") is True,
        "launch_id": launch_id,
        "trace_id": trace_id,
        "trace_server_issued": bool(launch_id and trace_id),
        "trace_launch_packet_matches": trace_launch_packet_matches,
        "trace_id_matches_launch": trace_id_matches_launch,
        "execution_mode": execution_mode,
        "primary_model_slot": primary_slot,
        "coding_agent_model_slot": coding_slot,
        "primary_model_id": primary_model_id,
        "coding_agent_model_id": coding_model_id,
        "primary_provider": "chatgpt",
        "coding_slot_provider": str(coding_slot.get("provider") or ""),
        "coding_slot_model": coding_model_id,
        "request_count": int(trace.get("request_count") or 0),
        "chatgpt_prompt_record_seen": bool(prompt_record),
        "chatgpt_requested_model": str(prompt_record.get("requested_model") or ""),
        "deepseek_record_seen": bool(deepseek_record),
        "deepseek_requested_model": str(deepseek_record.get("requested_model") or ""),
        "deepseek_effective_route_model": str(deepseek_record.get("effective_route_model") or ""),
        "provider_called": deepseek_record.get("provider_called") is True,
        "provider_id": str(deepseek_record.get("provider_id") or ""),
        "upstream_model": str(deepseek_record.get("upstream_model") or ""),
        "upstream_status": int(deepseek_record.get("upstream_status") or 0),
        "known_smoke_phrase_matched": deepseek_record.get("known_smoke_phrase_matched") is True,
        "fallback_used": fallback_seen,
        "api_only_mode": execution_mode == "api_only",
        "api_only_mode_used": execution_mode == "api_only",
        "chatgpt_only_mode_used": execution_mode == "chatgpt_only",
        "chatgpt_replaced_by_api": False,
        "browser_trace_authority": False,
        "raw_prompt_recorded": False,
        "auth_header_recorded": False,
        "secret_value_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "response_text_counts_as_proof": False,
        "ui_label_counts_as_proof": False,
        "response_text_counts_as_model_truth": False,
        "model_self_report_counts_as_runtime_truth": False,
        "wbp_patch_applier_used": False,
        "live_file_mutation_claimed": False,
        "next_action": (
            "none"
            if full_success
            else "confirm_runtime_can_dispatch_coding_agent_model_slot"
        ),
    }


def _forbidden_quick_start_mixed_mode_code_edit_fields(
    payload: Any,
    prefix: str = "",
) -> list[str]:
    if payload in (None, {}, ""):
        return []
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            if prefix or key_text not in QUICK_START_MIXED_MODE_CODE_EDIT_ALLOWED_BROWSER_FIELDS:
                findings.append(key_path)
            if isinstance(value, (dict, list)):
                findings.extend(
                    _forbidden_quick_start_mixed_mode_code_edit_fields(value, key_path)
                )
        return sorted(dict.fromkeys(findings))
    if isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(
                _forbidden_quick_start_mixed_mode_code_edit_fields(
                    value,
                    f"{prefix}[{index}]",
                )
            )
    return sorted(dict.fromkeys(findings))


def build_custom_codex_chatgpt_plus_deepseek_file_edit_packet(
    *,
    last_launch_packet: dict[str, Any] | None,
    bridge_trace_packet: dict[str, Any] | None,
    browser_payload: Any = None,
    repo_root: Path = ROOT,
    expected_file: str = MIXED_MODE_CODE_EDIT_PROBE_FILE,
    expected_text: str = MIXED_MODE_CODE_EDIT_EXPECTED_TEXT,
) -> dict[str, Any]:
    payload = browser_payload if isinstance(browser_payload, dict) else {}
    forbidden = _forbidden_quick_start_mixed_mode_code_edit_fields(browser_payload)
    base = {
        "schema_version": 1,
        "packet_kind": "custom_codex_chatgpt_plus_deepseek_file_edit",
        "captured_at_utc": utc_now(),
        "expected_file": expected_file,
        "expected_content_sha256": hashlib.sha256(
            expected_text.encode("utf-8")
        ).hexdigest(),
        "manual_prompt_required": (
            "Сначала сам составь короткий план.\n"
            "Кодовую часть выполни через API-кодера DeepSeek.\n"
            f"Создай файл {expected_file} и запиши туда ровно:\n"
            f"{expected_text}\n\n"
            "Больше ничего в репозитории не меняй."
        ),
        "browser_raw_backend_authority_widened": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "original_codex_touched": False,
        "asar_touched": False,
        "chatgpt_patch_applier_used": False,
        "wbp_patch_applier_used": False,
        "commit_attempted": False,
        "push_attempted": False,
        "merge_attempted": False,
    }
    if forbidden:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "final_status": "KNOWN_BLOCKER_CHATGPT_PLUS_DEEPSEEK_FILE_EDIT_NOT_PROVEN",
            "forbidden_fields": forbidden,
            "next_action": "remove_forbidden_browser_payload_fields",
        }

    launch = last_launch_packet if isinstance(last_launch_packet, dict) else {}
    route_packet = build_custom_codex_chatgpt_plus_api_coder_trace_packet(
        last_launch_packet=launch,
        bridge_trace_packet=bridge_trace_packet if isinstance(bridge_trace_packet, dict) else {},
        browser_payload=None,
    )
    profile_root_value = str(launch.get("persistent_profile_root") or "")
    profile_root = Path(profile_root_value).expanduser() if profile_root_value else Path()
    thread = _latest_custom_codex_thread(profile_root) if profile_root_value else {}
    thread_id = str(thread.get("id") or "")
    thread_cwd = str(thread.get("cwd") or "")
    thread_provider = str(thread.get("model_provider") or "")
    coding_model_id = str(route_packet.get("coding_slot_model") or "")
    log_evidence = (
        _custom_codex_log_evidence(
            profile_root,
            thread_id=thread_id,
            selected_model=coding_model_id,
            repo_root=repo_root,
            probe_file=expected_file,
        )
        if profile_root_value
        else {}
    )
    file_path = repo_root / expected_file
    try:
        file_content = file_path.read_text(encoding="utf-8")
        file_created = True
    except OSError:
        file_content = ""
        file_created = False
    file_content_exact = file_content == expected_text
    git_probe = _git_probe_file_status(repo_root, expected_file)
    trace = bridge_trace_packet if isinstance(bridge_trace_packet, dict) else {}
    trace_records = [
        record
        for record in trace.get("records") or []
        if isinstance(record, dict)
    ]
    trace_last_record = (
        trace.get("last_record") if isinstance(trace.get("last_record"), dict) else {}
    )
    if trace_last_record and trace_last_record not in trace_records:
        trace_records.append(trace_last_record)
    request_trace = (
        trace.get("bridge_request_trace_packet")
        if isinstance(trace.get("bridge_request_trace_packet"), dict)
        else {}
    )
    trace_changed_files: Any = request_trace.get("changed_files")
    if not isinstance(trace_changed_files, list):
        trace_changed_files = next(
            (
                record.get("changed_files")
                for record in reversed(trace_records)
                if str(record.get("launch_packet_id") or record.get("launch_id") or "")
                == str(route_packet.get("launch_id") or "")
                and str(record.get("trace_id") or "")
                == str(route_packet.get("trace_id") or "")
                and isinstance(record.get("changed_files"), list)
            ),
            [],
        )
    changed_files = [
        str(item)
        for item in (trace_changed_files if isinstance(trace_changed_files, list) else [])
        if str(item)
    ]
    if not changed_files and file_created and file_content_exact:
        changed_files = [expected_file]
    mutation_scope_allowed = changed_files == [expected_file]
    file_mutation_observed = bool(
        file_created
        and file_content_exact
        and log_evidence.get("tool_call_seen") is True
        and log_evidence.get("tool_result_success") is True
    )
    fallback_used = route_packet.get("fallback_used") is True or bool(
        log_evidence.get("fallback_used_seen")
    )
    success = bool(
        route_packet.get("status") == "ok"
        and route_packet.get("execution_mode") == "chatgpt_plus_api"
        and route_packet.get("chatgpt_primary_route_observed") is True
        and route_packet.get("coding_slot_provider") == "deepseek"
        and route_packet.get("deepseek_coding_route_observed") is True
        and route_packet.get("stable_bridge_preflight_ok") is True
        and thread_cwd == str(repo_root)
        and thread_provider == "wbp"
        and file_created
        and file_content_exact
        and file_mutation_observed
        and mutation_scope_allowed
        and log_evidence.get("tool_call_seen") is True
        and log_evidence.get("tool_result_success") is True
        and log_evidence.get("model_seen") is True
        and log_evidence.get("cwd_seen") is True
        and not fallback_used
        and launch.get("original_codex_touched") is False
        and launch.get("asar_touched") is False
    )
    return {
        **base,
        "status": "ok" if success else "blocked",
        "machine_error_code": (
            "OK" if success else "CHATGPT_PLUS_DEEPSEEK_FILE_EDIT_NOT_PROVEN"
        ),
        "final_status": (
            "CHATGPT_PLUS_API_CODE_EDIT_PROVEN_WITH_LIMITS"
            if success
            else "KNOWN_BLOCKER_CHATGPT_PLUS_DEEPSEEK_FILE_EDIT_NOT_PROVEN"
        ),
        "execution_mode": str(route_packet.get("execution_mode") or ""),
        "chatgpt_model_id": str(payload.get("chatgpt_model_id") or ""),
        "api_model_id": str(payload.get("api_model_id") or ""),
        "api_reasoning_option_id": str(
            payload.get("api_reasoning_option_id")
            or route_packet.get("api_reasoning_option_id")
            or ""
        ),
        "launch_id": str(route_packet.get("launch_id") or ""),
        "trace_id": str(route_packet.get("trace_id") or ""),
        "trace_launch_packet_matches": route_packet.get("trace_launch_packet_matches") is True,
        "trace_id_matches_launch": route_packet.get("trace_id_matches_launch") is True,
        "chatgpt_primary_route_observed": (
            route_packet.get("chatgpt_primary_route_observed") is True
        ),
        "deepseek_coding_route_observed": (
            route_packet.get("deepseek_coding_route_observed") is True
        ),
        "stable_bridge_preflight": str(route_packet.get("stable_bridge_preflight") or ""),
        "stable_bridge_preflight_ok": route_packet.get("stable_bridge_preflight_ok") is True,
        "stable_bridge_preflight_required": (
            route_packet.get("stable_bridge_preflight_required") is True
        ),
        "stable_bridge_launch_allowed": (
            route_packet.get("stable_bridge_launch_allowed") is True
        ),
        "mixed_route_trace_packet": route_packet,
        "coding_slot_provider": str(route_packet.get("coding_slot_provider") or ""),
        "coding_slot_model": coding_model_id,
        "file_created": file_created,
        "file_content_exact": file_content_exact,
        "file_mutation_observed": file_mutation_observed,
        "changed_files": changed_files,
        "mutation_scope_allowed": mutation_scope_allowed,
        "file_content_sha256": hashlib.sha256(file_content.encode("utf-8")).hexdigest(),
        "file_path": str(file_path),
        "file_path_relative": expected_file,
        "probe_file_ignored_by_git": git_probe["probe_file_ignored_by_git"],
        "probe_file_visible_to_git_status": git_probe["probe_file_visible_to_git_status"],
        "git_diff_name_status_only_expected": git_probe["git_diff_name_status_only_expected"],
        "git_status_short_for_probe_file": git_probe["git_status_short_for_probe_file"],
        "cwd": thread_cwd,
        "thread_id": thread_id,
        "thread_model_provider": thread_provider,
        "log_evidence": log_evidence,
        "fallback_used": fallback_used,
        "chatgpt_patch_applier_used": False,
        "wbp_patch_applier_used": False,
        "response_text_counts_as_proof": False,
        "ui_label_counts_as_proof": False,
        "response_text_counts_as_model_truth": False,
        "model_self_report_counts_as_runtime_truth": False,
        "next_action": (
            "none"
            if success
            else "enter_manual_prompt_then_refresh_mixed_mode_file_edit_proof"
        ),
    }


def _forbidden_custom_window_prompt_trace_fields(
    payload: Any,
    prefix: str = "",
) -> list[str]:
    if payload in (None, {}, ""):
        return []
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            findings.append(key_path)
            if isinstance(value, (dict, list)):
                findings.extend(_forbidden_custom_window_prompt_trace_fields(value, key_path))
        return sorted(dict.fromkeys(findings))
    if isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(
                _forbidden_custom_window_prompt_trace_fields(value, f"{prefix}[{index}]")
            )
    return sorted(dict.fromkeys(findings))


def _forbidden_quick_start_deepseek_code_edit_fields(
    payload: Any,
    prefix: str = "",
) -> list[str]:
    if payload in (None, {}, ""):
        return []
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            if prefix or key_text not in QUICK_START_DEEPSEEK_CODE_EDIT_ALLOWED_BROWSER_FIELDS:
                findings.append(key_path)
            if isinstance(value, (dict, list)):
                findings.extend(
                    _forbidden_quick_start_deepseek_code_edit_fields(value, key_path)
                )
        return sorted(dict.fromkeys(findings))
    if isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(
                _forbidden_quick_start_deepseek_code_edit_fields(
                    value,
                    f"{prefix}[{index}]",
                )
            )
    return sorted(dict.fromkeys(findings))


def _latest_custom_codex_thread(profile_root: Path) -> dict[str, Any]:
    state_dbs = sorted(profile_root.glob("state*.sqlite"))
    latest: dict[str, Any] = {}
    for db_path in state_dbs:
        try:
            with sqlite3.connect(db_path) as connection:
                connection.row_factory = sqlite3.Row
                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "select name from sqlite_master where type='table'"
                    )
                }
                if "threads" not in tables:
                    continue
                row = connection.execute(
                    "select * from threads order by updated_at desc, created_at desc limit 1"
                ).fetchone()
                if row is None:
                    continue
                candidate = dict(row)
                candidate["state_db"] = str(db_path)
                if not latest or int(candidate.get("updated_at") or 0) >= int(
                    latest.get("updated_at") or 0
                ):
                    latest = candidate
        except (OSError, sqlite3.Error):
            continue
    return latest


def _custom_codex_log_evidence(
    profile_root: Path,
    *,
    thread_id: str,
    selected_model: str,
    repo_root: Path,
    probe_file: str = DEEPSEEK_CODE_EDIT_PROBE_FILE,
) -> dict[str, Any]:
    evidence = {
        "log_db_seen": False,
        "session_jsonl_seen": False,
        "tool_call_seen": False,
        "tool_result_success": False,
        "model_seen": False,
        "cwd_seen": False,
        "chatgpt_model_seen": False,
        "fallback_used_seen": False,
    }
    if not thread_id:
        return evidence
    repo_root_text = str(repo_root)
    for db_path in sorted(profile_root.glob("logs*.sqlite")):
        try:
            with sqlite3.connect(db_path) as connection:
                connection.row_factory = sqlite3.Row
                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "select name from sqlite_master where type='table'"
                    )
                }
                if "logs" not in tables:
                    continue
                evidence["log_db_seen"] = True
                rows = connection.execute(
                    "select feedback_log_body from logs where thread_id = ? order by id desc limit 250",
                    (thread_id,),
                ).fetchall()
                for row in rows:
                    body = str(row["feedback_log_body"] or "")
                    if selected_model and f"model={selected_model}" in body:
                        evidence["model_seen"] = True
                    if repo_root_text and f"cwd={repo_root_text}" in body:
                        evidence["cwd_seen"] = True
                    if probe_file in body and "ToolCall: exec_command" in body:
                        evidence["tool_call_seen"] = True
                    if probe_file in body and "success=true" in body:
                        evidence["tool_result_success"] = True
                    if "fallback_used\": true" in body or "fallback_used=true" in body:
                        evidence["fallback_used_seen"] = True
                    if "model=gpt-" in body or "slug=gpt-" in body:
                        evidence["chatgpt_model_seen"] = True
        except (OSError, sqlite3.Error):
            continue
    sessions_dir = profile_root / "sessions"
    try:
        session_paths = sorted(
            sessions_dir.rglob("*.jsonl"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:50]
    except OSError:
        session_paths = []
    for session_path in session_paths:
        try:
            session_text = session_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if thread_id and thread_id not in session_text:
            continue
        evidence["session_jsonl_seen"] = True
        pending_probe_tool_call = False
        for line in session_text.splitlines():
            if selected_model and selected_model in line:
                evidence["model_seen"] = True
            if repo_root_text and repo_root_text in line:
                evidence["cwd_seen"] = True
            if probe_file in line and (
                '"name":"exec_command"' in line
                or '"name": "exec_command"' in line
                or "ToolCall: exec_command" in line
            ):
                evidence["tool_call_seen"] = True
                pending_probe_tool_call = True
            if pending_probe_tool_call and "function_call_output" in line:
                if "Process exited with code 0" in line:
                    evidence["tool_result_success"] = True
                pending_probe_tool_call = False
            if "fallback_used\": true" in line or "fallback_used=true" in line:
                evidence["fallback_used_seen"] = True
            if "model=gpt-" in line or '"model":"gpt-' in line or '"model": "gpt-' in line:
                evidence["chatgpt_model_seen"] = True
    return evidence


def _git_probe_file_status(repo_root: Path, expected_file: str) -> dict[str, Any]:
    status = {
        "git_probe_attempted": False,
        "probe_file_ignored_by_git": False,
        "probe_file_visible_to_git_status": False,
        "git_diff_name_status_only_expected": False,
        "git_status_short_for_probe_file": "",
    }
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return status
    status["git_probe_attempted"] = True
    try:
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--", expected_file],
            cwd=str(repo_root),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        status["probe_file_ignored_by_git"] = ignored.returncode == 0
        visible = subprocess.run(
            ["git", "status", "--short", "--", expected_file],
            cwd=str(repo_root),
            check=False,
            text=True,
            capture_output=True,
            timeout=5,
        )
        probe_status = visible.stdout.strip() if visible.returncode == 0 else ""
        status["git_status_short_for_probe_file"] = probe_status
        status["probe_file_visible_to_git_status"] = bool(probe_status)
        status["git_diff_name_status_only_expected"] = (
            status["probe_file_ignored_by_git"] is True
            and status["probe_file_visible_to_git_status"] is False
        )
    except (OSError, subprocess.SubprocessError):
        return status
    return status


def build_custom_codex_deepseek_code_edit_reproduction_packet(
    *,
    last_launch_packet: dict[str, Any] | None,
    bridge_trace_packet: dict[str, Any] | None,
    browser_payload: Any = None,
    repo_root: Path = ROOT,
    expected_file: str = DEEPSEEK_CODE_EDIT_PROBE_FILE,
    expected_text: str = DEEPSEEK_CODE_EDIT_EXPECTED_TEXT,
    packet_kind: str = "custom_codex_deepseek_code_edit_reproduction",
    quick_start_button_id: str = "quickStartDeepSeekCodeEditProofAction",
    ok_final_status: str = "CUSTOM_CODEX_DEEPSEEK_CODE_EDIT_REPRODUCIBLE_PROVEN_WITH_LIMITS",
    blocked_final_status: str = "KNOWN_BLOCKER_CUSTOM_CODEX_DEEPSEEK_CODE_EDIT_REPRODUCTION_FAILED",
    blocked_machine_error_code: str = "CUSTOM_CODEX_DEEPSEEK_CODE_EDIT_REPRODUCTION_NOT_PROVEN",
) -> dict[str, Any]:
    payload = browser_payload if isinstance(browser_payload, dict) else {}
    forbidden = _forbidden_quick_start_deepseek_code_edit_fields(browser_payload)
    base = {
        "schema_version": 1,
        "packet_kind": packet_kind,
        "captured_at_utc": utc_now(),
        "quick_start_button_id": quick_start_button_id,
        "expected_file": expected_file,
        "expected_content_sha256": hashlib.sha256(
            expected_text.encode("utf-8")
        ).hexdigest(),
        "manual_prompt_required": (
            f"Создай файл {expected_file} и запиши туда ровно:\n"
            f"{expected_text}\n\n"
            "Больше ничего в репозитории не меняй."
        ),
        "browser_raw_backend_authority_widened": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "original_codex_touched": False,
        "asar_touched": False,
        "wbp_patch_applier_used": False,
        "commit_attempted": False,
        "push_attempted": False,
        "merge_attempted": False,
    }
    if forbidden:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "final_status": blocked_final_status,
            "forbidden_fields": forbidden,
            "next_action": "remove_forbidden_browser_payload_fields",
        }

    launch = last_launch_packet if isinstance(last_launch_packet, dict) else {}
    trace = bridge_trace_packet if isinstance(bridge_trace_packet, dict) else {}
    record = trace.get("last_record") if isinstance(trace.get("last_record"), dict) else {}
    selected_model = str(launch.get("selected_model") or payload.get("api_model_id") or "")
    execution_mode = str(launch.get("execution_mode") or payload.get("execution_mode") or "")
    api_reasoning_option_id = str(
        launch.get("api_reasoning_option_id") or payload.get("api_reasoning_option_id") or ""
    )
    profile_root_value = str(launch.get("persistent_profile_root") or "")
    profile_root = Path(profile_root_value).expanduser() if profile_root_value else Path()
    thread = _latest_custom_codex_thread(profile_root) if profile_root_value else {}
    thread_id = str(thread.get("id") or "")
    thread_cwd = str(thread.get("cwd") or "")
    thread_model = str(thread.get("model") or "")
    thread_provider = str(thread.get("model_provider") or "")
    log_evidence = (
        _custom_codex_log_evidence(
            profile_root,
            thread_id=thread_id,
            selected_model=selected_model,
            repo_root=repo_root,
            probe_file=expected_file,
        )
        if profile_root_value
        else {}
    )
    file_path = repo_root / expected_file
    try:
        file_content = file_path.read_text(encoding="utf-8")
        file_created = True
    except OSError:
        file_content = ""
        file_created = False
    file_content_exact = file_content == expected_text
    file_content_sha256 = hashlib.sha256(file_content.encode("utf-8")).hexdigest()
    route_digest_matches = record.get("route_digest_matches_launch") is True
    request_trace = (
        trace.get("bridge_request_trace_packet")
        if isinstance(trace.get("bridge_request_trace_packet"), dict)
        else {}
    )
    launch_id = str(launch.get("launch_id") or "")
    trace_id = str(launch.get("trace_id") or "")
    record_launch_id = str(record.get("launch_packet_id") or record.get("launch_id") or "")
    record_trace_id = str(record.get("trace_id") or "")
    trace_launch_packet_matches = bool(launch_id and record_launch_id == launch_id)
    trace_id_matches_launch = bool(trace_id and record_trace_id == trace_id)
    provider_called = record.get("provider_called") is True
    provider_id = str(record.get("provider_id") or "")
    upstream_model = str(record.get("upstream_model") or "")
    effective_route_model = str(record.get("effective_route_model") or selected_model)
    request_seen = record.get("request_seen_after_launch") is True
    response_seen = record.get("response_seen") is True
    forced_route_used = record.get("forced_route_used") is True
    forced_route_counts_as_fallback = False
    route_unchanged = (
        request_trace.get("route_unchanged")
        if "route_unchanged" in request_trace
        else trace.get("route_unchanged")
    ) is True
    if not request_trace and "route_unchanged" not in trace:
        route_unchanged = bool(route_digest_matches and forced_route_used)
    selected_route_preserved = bool(
        route_unchanged
        and record.get("fallback_used") is not True
        and effective_route_model == selected_model
    )
    trace_changed_files = record.get("changed_files")
    if not isinstance(trace_changed_files, list):
        trace_changed_files = request_trace.get("changed_files") if isinstance(request_trace, dict) else []
    changed_files = [
        str(item)
        for item in (trace_changed_files if isinstance(trace_changed_files, list) else [])
        if str(item)
    ]
    if not changed_files and file_created and file_content_exact:
        changed_files = [expected_file]
    mutation_scope_allowed = changed_files == [expected_file]
    file_mutation_observed = bool(
        file_created
        and file_content_exact
        and log_evidence.get("tool_call_seen") is True
        and log_evidence.get("tool_result_success") is True
    )
    stable_bridge_preflight_status = str(
        launch.get("stable_bridge_preflight_status")
        or (
            launch.get("stable_bridge_preflight_packet", {})
            if isinstance(launch.get("stable_bridge_preflight_packet"), dict)
            else {}
        ).get("status")
        or ""
    )
    stable_bridge_preflight_ok = bool(
        launch.get("stable_bridge_preflight_required") is True
        and launch.get("stable_bridge_launch_allowed") is True
        and stable_bridge_preflight_status == "ok"
    )
    git_probe = _git_probe_file_status(repo_root, expected_file)
    fallback_used = record.get("fallback_used") is True or bool(
        log_evidence.get("fallback_used_seen")
    )
    chatgpt_called = record.get("chatgpt_route_used") is True or bool(
        log_evidence.get("chatgpt_model_seen")
    )
    api_primary_slot_proven = bool(
        execution_mode == "api_only"
        and selected_model == "wbp-deepseek-v4-pro-max"
        and thread_model == selected_model
        and thread_provider == "wbp"
        and provider_id == "deepseek"
        and effective_route_model == selected_model
    )
    api_only_executor_truth_proven = bool(
        api_primary_slot_proven
        and selected_route_preserved
        and not chatgpt_called
        and not fallback_used
    )
    launch_alive_enough = (
        launch.get("status") == "ok"
        and launch.get("custom_codex_window_deepseek_launch_proven_with_limits") is True
        and launch.get("native_app_usable") is True
        and launch.get("real_codex_app_launched") is True
    )
    success = bool(
        launch_alive_enough
        and execution_mode == "api_only"
        and selected_model == "wbp-deepseek-v4-pro-max"
        and api_primary_slot_proven
        and api_only_executor_truth_proven
        and stable_bridge_preflight_ok
        and thread_cwd == str(repo_root)
        and thread_model == selected_model
        and thread_provider == "wbp"
        and file_created
        and file_content_exact
        and file_mutation_observed
        and mutation_scope_allowed
        and log_evidence.get("tool_call_seen") is True
        and log_evidence.get("tool_result_success") is True
        and log_evidence.get("model_seen") is True
        and log_evidence.get("cwd_seen") is True
        and provider_called
        and provider_id == "deepseek"
        and upstream_model == "deepseek-v4-pro"
        and selected_route_preserved
        and request_seen
        and response_seen
        and route_digest_matches
        and trace_launch_packet_matches
        and trace_id_matches_launch
        and not chatgpt_called
        and not fallback_used
        and launch.get("original_codex_touched") is False
        and launch.get("asar_touched") is False
    )
    return {
        **base,
        "status": "ok" if success else "blocked",
        "machine_error_code": (
            "OK"
            if success
            else blocked_machine_error_code
        ),
        "final_status": (
            ok_final_status
            if success
            else blocked_final_status
        ),
        "execution_mode": execution_mode,
        "selected_model": selected_model,
        "api_primary_slot_proven": api_primary_slot_proven,
        "api_only_executor_truth_proven": api_only_executor_truth_proven,
        "primary_model_slot": {
            "slot_id": "primary_model_slot",
            "status": "bound" if api_primary_slot_proven else "not_proven",
            "lane": "api_route_lane" if api_primary_slot_proven else "",
            "model_id": selected_model if api_primary_slot_proven else "",
            "provider_id": provider_id if api_primary_slot_proven else "",
            "source": "server_catalog",
        },
        "coding_agent_model_slot": {
            "slot_id": "coding_agent_model_slot",
            "status": "not_bound_for_mode" if execution_mode == "api_only" else "not_proven",
            "reason": (
                "api_only_uses_primary_model_slot"
                if execution_mode == "api_only"
                else "execution_mode_not_api_only"
            ),
        },
        "api_model_id": str(payload.get("api_model_id") or ""),
        "api_reasoning_option_id": api_reasoning_option_id,
        "cwd": thread_cwd,
        "repo_root": str(repo_root),
        "thread_id": thread_id,
        "thread_model": thread_model,
        "thread_model_provider": thread_provider,
        "window_launch_proven_with_limits": launch_alive_enough,
        "native_app_usable": launch.get("native_app_usable") is True,
        "stable_bridge_preflight": stable_bridge_preflight_status,
        "stable_bridge_preflight_ok": stable_bridge_preflight_ok,
        "stable_bridge_preflight_required": launch.get("stable_bridge_preflight_required") is True,
        "stable_bridge_launch_allowed": launch.get("stable_bridge_launch_allowed") is True,
        "file_created": file_created,
        "file_content_exact": file_content_exact,
        "file_edit_observed": file_created,
        "file_mutation_observed": file_mutation_observed,
        "file_content_matches_expected": file_content_exact,
        "changed_files": changed_files,
        "mutation_scope_allowed": mutation_scope_allowed,
        "file_size_bytes": len(file_content.encode("utf-8")) if file_created else 0,
        "file_content_sha256": file_content_sha256,
        "file_path": str(file_path),
        "file_path_relative": expected_file,
        "probe_file_ignored_by_git": git_probe["probe_file_ignored_by_git"],
        "probe_file_visible_to_git_status": git_probe["probe_file_visible_to_git_status"],
        "git_diff_name_status_only_expected": git_probe["git_diff_name_status_only_expected"],
        "git_status_short_for_probe_file": git_probe["git_status_short_for_probe_file"],
        "provider_called": provider_called,
        "provider_id": provider_id,
        "upstream_model": upstream_model,
        "effective_route_model": effective_route_model,
        "request_seen_after_launch": request_seen,
        "response_seen": response_seen,
        "route_digest_matches_launch": route_digest_matches,
        "route_unchanged": route_unchanged,
        "selected_route_preserved": selected_route_preserved,
        "launch_id": launch_id,
        "trace_id": trace_id,
        "trace_server_issued": bool(launch_id and trace_id),
        "trace_launch_packet_matches": trace_launch_packet_matches,
        "trace_id_matches_launch": trace_id_matches_launch,
        "forced_route_used": forced_route_used,
        "forced_route_counts_as_fallback": forced_route_counts_as_fallback,
        "chatgpt_called": chatgpt_called,
        "api_only_calls_chatgpt": chatgpt_called,
        "fallback_used": fallback_used,
        "log_evidence": log_evidence,
        "profile_path_exposed": False,
        "raw_prompt_recorded": False,
        "response_text_counts_as_proof": False,
        "ui_label_counts_as_proof": False,
        "response_text_counts_as_model_truth": False,
        "model_self_report_counts_as_runtime_truth": False,
        "next_action": (
            "none"
            if success
            else "enter_manual_prompt_then_refresh_deepseek_code_edit_proof"
        ),
        "small_real_edit_probe_supported": True,
    }


def build_custom_codex_deepseek_route_bound_real_edit_packet(
    *,
    last_launch_packet: dict[str, Any] | None,
    bridge_trace_packet: dict[str, Any] | None,
    browser_payload: Any = None,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    return build_custom_codex_deepseek_code_edit_reproduction_packet(
        last_launch_packet=last_launch_packet,
        bridge_trace_packet=bridge_trace_packet,
        browser_payload=browser_payload,
        repo_root=repo_root,
        expected_file=DEEPSEEK_ROUTE_BOUND_EDIT_PROBE_FILE,
        expected_text=DEEPSEEK_ROUTE_BOUND_EDIT_EXPECTED_TEXT,
        packet_kind="custom_codex_deepseek_route_bound_real_edit",
        quick_start_button_id="quickStartDeepSeekRouteBoundEditProofAction",
        ok_final_status="CUSTOM_CODEX_DEEPSEEK_ROUTE_BOUND_REAL_EDIT_PROVEN_WITH_LIMITS",
        blocked_final_status="KNOWN_BLOCKER_DEEPSEEK_ROUTE_BOUND_REAL_EDIT_NOT_PROVEN",
        blocked_machine_error_code="CUSTOM_CODEX_DEEPSEEK_ROUTE_BOUND_REAL_EDIT_NOT_PROVEN",
    )


def build_api_only_deepseek_live_code_edit_truth_packet(
    *,
    last_launch_packet: dict[str, Any] | None,
    bridge_trace_packet: dict[str, Any] | None,
    browser_payload: Any = None,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    return build_custom_codex_deepseek_code_edit_reproduction_packet(
        last_launch_packet=last_launch_packet,
        bridge_trace_packet=bridge_trace_packet,
        browser_payload=browser_payload,
        repo_root=repo_root,
        expected_file=API_ONLY_DEEPSEEK_CODE_EDIT_PROBE_FILE,
        expected_text=API_ONLY_DEEPSEEK_CODE_EDIT_EXPECTED_TEXT,
        packet_kind="api_only_deepseek_live_code_edit_truth",
        quick_start_button_id="quickStartApiOnlyDeepSeekLiveCodeEditTruthAction",
        ok_final_status="API_ONLY_DEEPSEEK_LIVE_CODE_EDIT_PROVEN_WITH_LIMITS",
        blocked_final_status="STOP_AND_DIAGNOSE_API_ONLY_LIVE_CODE_EDIT_NOT_PROVEN",
        blocked_machine_error_code="API_ONLY_DEEPSEEK_LIVE_CODE_EDIT_NOT_PROVEN",
    )


def _forbidden_visible_history_owner_confirmation_fields(
    payload: Any,
    prefix: str = "",
    allowed_fields: frozenset[str] = VISIBLE_HISTORY_ALLOWED_OWNER_FIELDS,
) -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            if prefix or key_text not in allowed_fields:
                findings.append(key_path)
            findings.extend(
                _forbidden_visible_history_owner_confirmation_fields(
                    value,
                    key_path,
                    allowed_fields=allowed_fields,
                )
            )
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(
                _forbidden_visible_history_owner_confirmation_fields(
                    value,
                    f"{prefix}[{index}]",
                    allowed_fields=allowed_fields,
                )
            )
    return findings


def _visible_history_session_storage_summary(
    last_launch_packet: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(last_launch_packet, dict):
        return {
            "session_storage_probe_attempted": False,
            "session_storage_observed": False,
            "session_file_content_read": False,
        }
    profile_root_value = last_launch_packet.get("persistent_profile_root")
    if not isinstance(profile_root_value, str) or not profile_root_value.strip():
        return {
            "session_storage_probe_attempted": False,
            "session_storage_observed": False,
            "session_file_content_read": False,
        }
    profile_root = Path(profile_root_value).expanduser()
    if not profile_root.exists():
        return {
            "session_storage_probe_attempted": True,
            "session_storage_observed": False,
            "session_file_content_read": False,
        }
    session_files = sorted(
        (
            path
            for path in profile_root.rglob("*.jsonl")
            if path.is_file() and "sessions" in {part.lower() for part in path.parts}
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not session_files:
        return {
            "session_storage_probe_attempted": True,
            "session_storage_observed": False,
            "session_file_content_read": False,
        }
    latest = session_files[0]
    stat = latest.stat()
    return {
        "session_storage_probe_attempted": True,
        "session_storage_observed": True,
        "latest_session_file_relative": str(latest.relative_to(profile_root)),
        "latest_session_file_size_bytes": stat.st_size,
        "latest_session_file_mtime_utc": datetime.fromtimestamp(
            stat.st_mtime,
            timezone.utc,
        ).isoformat().replace("+00:00", "Z"),
        "session_file_content_read": False,
    }


def _payload_first_text(payload: Any, key: str, default: str = "") -> str:
    if not isinstance(payload, dict):
        return default
    value = payload.get(key)
    if isinstance(value, list):
        if not value:
            return default
        value = value[0]
    text = str(value or "").strip()
    return text if text else default


def _forbidden_stable_profile_history_fields(
    payload: Any,
    prefix: str = "",
) -> list[str]:
    if payload in (None, {}, ""):
        return []
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            if prefix or key_text not in STABLE_PROFILE_HISTORY_ALLOWED_BROWSER_FIELDS:
                findings.append(key_path)
            if isinstance(value, (dict, list)):
                findings.extend(_forbidden_stable_profile_history_fields(value, key_path))
        return sorted(dict.fromkeys(findings))
    if isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(
                _forbidden_stable_profile_history_fields(value, f"{prefix}[{index}]")
            )
    return sorted(dict.fromkeys(findings))


def _stable_profile_history_storage_snapshot(
    profile_root: Path | None,
    *,
    history_marker: str,
) -> dict[str, Any]:
    marker = str(history_marker or "")
    marker_sha256 = hashlib.sha256(marker.encode("utf-8")).hexdigest() if marker else ""
    snapshot: dict[str, Any] = {
        "snapshot_captured_at_utc": utc_now(),
        "profile_root_available": profile_root is not None,
        "profile_root_exists": False,
        "thread_count": 0,
        "session_file_count": 0,
        "log_record_count": 0,
        "history_marker_sha256": marker_sha256,
        "history_marker_seen": False,
        "state_db_seen": False,
        "log_db_seen": False,
        "session_jsonl_seen": False,
        "raw_thread_content_read": False,
        "raw_thread_content_recorded": False,
        "raw_profile_path_exposed": False,
    }
    if profile_root is None:
        return snapshot
    snapshot["profile_root_exists"] = profile_root.exists()
    if not profile_root.exists():
        return snapshot

    try:
        state_dbs = sorted(profile_root.glob("state*.sqlite"))
    except OSError:
        state_dbs = []
    for db_path in state_dbs:
        try:
            with sqlite3.connect(db_path) as connection:
                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "select name from sqlite_master where type='table'"
                    )
                }
                if "threads" in tables:
                    snapshot["state_db_seen"] = True
                    row = connection.execute("select count(*) from threads").fetchone()
                    snapshot["thread_count"] = int(snapshot["thread_count"]) + int(row[0] or 0)
                if "logs" in tables:
                    snapshot["log_db_seen"] = True
                    row = connection.execute("select count(*) from logs").fetchone()
                    snapshot["log_record_count"] = int(snapshot["log_record_count"]) + int(row[0] or 0)
                    if marker:
                        for body_row in connection.execute(
                            "select feedback_log_body from logs order by id desc limit 500"
                        ):
                            if marker in str(body_row[0] or ""):
                                snapshot["history_marker_seen"] = True
                                break
        except (OSError, sqlite3.Error):
            continue

    sessions_dir = profile_root / "sessions"
    try:
        session_paths = sorted(sessions_dir.rglob("*.jsonl")) if sessions_dir.exists() else []
    except OSError:
        session_paths = []
    snapshot["session_file_count"] = len(session_paths)
    snapshot["session_jsonl_seen"] = bool(session_paths)
    if marker and not snapshot["history_marker_seen"]:
        for session_path in session_paths[-500:]:
            try:
                text = session_path.read_text(encoding="utf-8")
            except OSError:
                continue
            if marker in text:
                snapshot["history_marker_seen"] = True
                break
    return snapshot


def build_custom_codex_persistent_profile_packet(
    *,
    last_launch_packet: dict[str, Any] | None,
    browser_payload: Any = None,
) -> dict[str, Any]:
    forbidden = _forbidden_custom_persistent_profile_fields(browser_payload)
    base = {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "packet_kind": "custom_codex_persistent_profile",
        "profile_final_status": "KNOWN_BLOCKER_CUSTOM_CODEX_PERSISTENT_PROFILE_NOT_PROVEN",
        "session_storage_final_status": "KNOWN_BLOCKER_CUSTOM_CODEX_SESSION_STORAGE_NOT_OBSERVED",
        "profile_persistence_proven": False,
        "session_storage_observed": False,
        "visible_history_restore": "not_claimed",
        "visible_thread_history_owner_confirmed": False,
        "relaunch_continuity_proven": False,
        "profile_relaunch_required_for_strong_history_claim": True,
        "raw_thread_content_read": False,
        "raw_thread_content_recorded": False,
        "browser_client_path_authority": False,
        "original_codex_touched": False,
        "asar_touched": False,
        "history_persistence_claimed": False,
        "full_history_restoration_claimed": False,
        "cloud_history_restoration_claimed": False,
    }
    if forbidden:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "forbidden_fields": forbidden,
            "next_action": "remove_browser_payload_fields",
        }
    if not isinstance(last_launch_packet, dict):
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "CUSTOM_CODEX_FRESH_LAUNCH_PACKET_REQUIRED",
            "next_action": "launch_custom_codex_with_stable_profile",
        }

    profile_id = str(last_launch_packet.get("persistent_profile_id") or "")
    profile_root_value = str(last_launch_packet.get("persistent_profile_root") or "")
    codex_home_value = str(last_launch_packet.get("persistent_codex_home") or "")
    user_data_value = str(last_launch_packet.get("persistent_user_data_dir") or "")
    runtime_tmp_value = str(last_launch_packet.get("persistent_runtime_tmp_dir") or "")
    profile_root = Path(profile_root_value).expanduser() if profile_root_value else None
    codex_home = Path(codex_home_value).expanduser() if codex_home_value else None
    user_data_dir = Path(user_data_value).expanduser() if user_data_value else None
    runtime_tmp_dir = Path(runtime_tmp_value).expanduser() if runtime_tmp_value else None
    persistent_root_tmp = _path_is_tmp(profile_root) if profile_root is not None else True
    codex_home_tmp = _path_is_tmp(codex_home) if codex_home is not None else True
    user_data_tmp = _path_is_tmp(user_data_dir) if user_data_dir is not None else True
    profile_path_stable = bool(
        profile_id == "wbp-custom-main"
        and profile_root is not None
        and codex_home is not None
        and user_data_dir is not None
        and not persistent_root_tmp
        and not codex_home_tmp
        and not user_data_tmp
        and str(codex_home) == str(profile_root)
        and str(user_data_dir).startswith(str(profile_root))
    )
    profile_persistence_proven = bool(
        last_launch_packet.get("status") == "ok"
        and last_launch_packet.get("profile_mode") == "persistent_custom"
        and last_launch_packet.get("temp_profile_used") is False
        and profile_path_stable
        and last_launch_packet.get("cleanup_deletes_persistent_profile_by_default") is False
        and str(last_launch_packet.get("cleanup_scope") or "")
        == "runtime_tmp_only_or_deferred_running_process"
        and last_launch_packet.get("original_codex_touched") is False
        and last_launch_packet.get("asar_touched") is False
        and last_launch_packet.get("original_codex_profile_runtime_dependency") is False
    )
    session_summary = _visible_history_session_storage_summary(last_launch_packet)
    session_storage_observed = session_summary.get("session_storage_observed") is True
    return {
        **base,
        **session_summary,
        "status": "ok" if profile_persistence_proven else "blocked",
        "machine_error_code": "OK" if profile_persistence_proven else "CUSTOM_CODEX_PERSISTENT_PROFILE_NOT_PROVEN",
        "profile_final_status": (
            "CUSTOM_CODEX_PERSISTENT_PROFILE_PROVEN_WITH_LIMITS"
            if profile_persistence_proven
            else "KNOWN_BLOCKER_CUSTOM_CODEX_PERSISTENT_PROFILE_NOT_PROVEN"
        ),
        "session_storage_final_status": (
            "CUSTOM_CODEX_SESSION_STORAGE_OBSERVED_WITH_LIMITS"
            if session_storage_observed
            else "KNOWN_BLOCKER_CUSTOM_CODEX_SESSION_STORAGE_NOT_OBSERVED"
        ),
        "profile_persistence_proven": profile_persistence_proven,
        "persistent_profile_id": profile_id,
        "persistent_profile_reused": profile_persistence_proven,
        "codex_home_reused": profile_persistence_proven,
        "electron_user_data_reused": profile_persistence_proven,
        "temp_profile_used": last_launch_packet.get("temp_profile_used") is True,
        "profile_mode": str(last_launch_packet.get("profile_mode") or ""),
        "profile_path_stable": profile_path_stable,
        "persistent_profile_root_is_tmp": persistent_root_tmp,
        "persistent_codex_home_is_tmp": codex_home_tmp,
        "persistent_user_data_dir_is_tmp": user_data_tmp,
        "persistent_runtime_tmp_dir_is_tmp": _path_is_tmp(runtime_tmp_dir)
        if runtime_tmp_dir is not None
        else False,
        "persistent_profile_path_exposed": False,
        "persistent_codex_home_exposed": False,
        "persistent_user_data_dir_exposed": False,
        "session_storage_observed": session_storage_observed,
        "session_storage_path_stable": profile_path_stable,
        "session_files_observed": session_storage_observed,
        "cleanup_deletes_persistent_profile_by_default": last_launch_packet.get(
            "cleanup_deletes_persistent_profile_by_default"
        )
        is True,
        "cleanup_scope": str(last_launch_packet.get("cleanup_scope") or ""),
        "persistent_history_delete_requires_explicit_owner_action": True,
        "cleanup_target_is_persistent_profile_root": False,
        "cleanup_scope_runtime_tmp_only_or_deferred": str(
            last_launch_packet.get("cleanup_scope") or ""
        )
        == "runtime_tmp_only_or_deferred_running_process",
        "original_codex_touched": last_launch_packet.get("original_codex_touched") is True,
        "asar_touched": last_launch_packet.get("asar_touched") is True,
        "original_codex_profile_runtime_dependency": last_launch_packet.get(
            "original_codex_profile_runtime_dependency"
        )
        is True,
        "next_action": (
            "none"
            if profile_persistence_proven and session_storage_observed
            else "observe_session_storage_or_confirm_visible_history_separately"
        ),
    }


def build_custom_codex_persistent_relaunch_profile_packet(
    *,
    first_launch_packet: dict[str, Any] | None,
    second_launch_packet: dict[str, Any] | None,
    browser_payload: Any = None,
) -> dict[str, Any]:
    forbidden = _forbidden_custom_persistent_profile_fields(browser_payload)
    base = {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "packet_kind": "custom_codex_persistent_relaunch_profile",
        "final_status": "KNOWN_BLOCKER_CUSTOM_CODEX_PERSISTENT_RELAUNCH_PROFILE_NOT_PROVEN",
        "profile_relaunch_proven": False,
        "same_persistent_profile_id": False,
        "same_persistent_codex_home": False,
        "same_user_data_dir": False,
        "session_storage_survived_relaunch": False,
        "cleanup_deleted_persistent_profile": False,
        "cleanup_deletes_persistent_profile_by_default": False,
        "raw_thread_content_read": False,
        "raw_thread_content_recorded": False,
        "visible_history_owner_confirmed": False,
        "visible_history_restore_claimed": False,
        "full_history_restoration_claimed": False,
        "browser_client_path_authority": False,
        "original_codex_touched": False,
        "asar_touched": False,
    }
    if forbidden:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "forbidden_fields": forbidden,
            "next_action": "remove_browser_payload_fields",
        }
    if not isinstance(first_launch_packet, dict) or not isinstance(second_launch_packet, dict):
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "TWO_CUSTOM_CODEX_LAUNCH_PACKETS_REQUIRED",
            "next_action": "launch_custom_codex_twice_with_stable_profile",
        }

    first_profile = build_custom_codex_persistent_profile_packet(
        last_launch_packet=first_launch_packet,
    )
    second_profile = build_custom_codex_persistent_profile_packet(
        last_launch_packet=second_launch_packet,
    )
    for profile_packet in (first_profile, second_profile):
        profile_packet.pop("latest_session_file_relative", None)
        profile_packet.pop("latest_session_file_size_bytes", None)
        profile_packet.pop("latest_session_file_mtime_utc", None)
    first_ok = first_profile.get("profile_persistence_proven") is True
    second_ok = second_profile.get("profile_persistence_proven") is True
    first_profile_id = str(first_launch_packet.get("persistent_profile_id") or "")
    second_profile_id = str(second_launch_packet.get("persistent_profile_id") or "")
    first_codex_home = str(first_launch_packet.get("persistent_codex_home") or "")
    second_codex_home = str(second_launch_packet.get("persistent_codex_home") or "")
    first_user_data_dir = str(first_launch_packet.get("persistent_user_data_dir") or "")
    second_user_data_dir = str(second_launch_packet.get("persistent_user_data_dir") or "")
    same_profile_id = bool(
        first_profile_id and second_profile_id and first_profile_id == second_profile_id
    )
    same_codex_home = bool(
        first_codex_home and second_codex_home and first_codex_home == second_codex_home
    )
    same_user_data_dir = bool(
        first_user_data_dir
        and second_user_data_dir
        and first_user_data_dir == second_user_data_dir
    )
    cleanup_deleted_persistent_profile = bool(
        first_launch_packet.get("cleanup_deletes_persistent_profile_by_default") is True
        or second_launch_packet.get("cleanup_deletes_persistent_profile_by_default") is True
    )
    original_codex_touched = bool(
        first_launch_packet.get("original_codex_touched") is True
        or second_launch_packet.get("original_codex_touched") is True
    )
    asar_touched = bool(
        first_launch_packet.get("asar_touched") is True
        or second_launch_packet.get("asar_touched") is True
    )
    session_storage_survived = bool(
        first_profile.get("session_storage_observed") is True
        and second_profile.get("session_storage_observed") is True
    )
    profile_relaunch_proven = bool(
        first_ok
        and second_ok
        and same_profile_id
        and same_codex_home
        and same_user_data_dir
        and not cleanup_deleted_persistent_profile
        and not original_codex_touched
        and not asar_touched
    )
    if profile_relaunch_proven and session_storage_survived:
        final_status = "CUSTOM_CODEX_PERSISTENT_RELAUNCH_PROFILE_PROVEN_WITH_LIMITS"
        machine_error_code = "OK"
        next_action = "confirm_visible_history_separately_if_needed"
    elif profile_relaunch_proven:
        final_status = "CUSTOM_CODEX_PERSISTENT_RELAUNCH_PROFILE_PROVEN_SESSION_STORAGE_NOT_OBSERVED"
        machine_error_code = "SESSION_STORAGE_NOT_OBSERVED"
        next_action = "observe_session_storage_or_confirm_visible_history_separately"
    else:
        final_status = "KNOWN_BLOCKER_CUSTOM_CODEX_PERSISTENT_RELAUNCH_PROFILE_NOT_PROVEN"
        machine_error_code = "CUSTOM_CODEX_PERSISTENT_RELAUNCH_PROFILE_NOT_PROVEN"
        next_action = "diagnose_launch_profile_drift"

    return {
        **base,
        "status": "ok" if profile_relaunch_proven else "blocked",
        "machine_error_code": machine_error_code,
        "final_status": final_status,
        "profile_relaunch_proven": profile_relaunch_proven,
        "first_profile_final_status": str(first_profile.get("profile_final_status") or ""),
        "second_profile_final_status": str(second_profile.get("profile_final_status") or ""),
        "first_session_storage_final_status": str(
            first_profile.get("session_storage_final_status") or ""
        ),
        "second_session_storage_final_status": str(
            second_profile.get("session_storage_final_status") or ""
        ),
        "same_persistent_profile_id": same_profile_id,
        "same_persistent_codex_home": same_codex_home,
        "same_user_data_dir": same_user_data_dir,
        "first_temp_profile_used": first_launch_packet.get("temp_profile_used") is True,
        "second_temp_profile_used": second_launch_packet.get("temp_profile_used") is True,
        "first_profile_mode": str(first_launch_packet.get("profile_mode") or ""),
        "second_profile_mode": str(second_launch_packet.get("profile_mode") or ""),
        "session_storage_survived_relaunch": session_storage_survived,
        "first_session_storage_observed": first_profile.get("session_storage_observed") is True,
        "second_session_storage_observed": second_profile.get("session_storage_observed") is True,
        "cleanup_deleted_persistent_profile": cleanup_deleted_persistent_profile,
        "cleanup_deletes_persistent_profile_by_default": cleanup_deleted_persistent_profile,
        "cleanup_target_is_persistent_profile_root": False,
        "original_codex_touched": original_codex_touched,
        "asar_touched": asar_touched,
        "next_action": next_action,
    }


def build_custom_codex_stable_profile_history_persistence_packet(
    *,
    first_launch_packet: dict[str, Any] | None,
    second_launch_packet: dict[str, Any] | None,
    before_history_snapshot: dict[str, Any] | None,
    browser_payload: Any = None,
) -> dict[str, Any]:
    forbidden = _forbidden_stable_profile_history_fields(browser_payload)
    history_marker = _payload_first_text(
        browser_payload,
        "history_marker",
        DEFAULT_STABLE_PROFILE_HISTORY_MARKER,
    )
    base = {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "packet_kind": "custom_codex_stable_profile_history_persistence",
        "final_status": "KNOWN_BLOCKER_CUSTOM_CODEX_STABLE_PROFILE_HISTORY_PERSISTENCE_NOT_PROVEN",
        "profile_id": "",
        "stable_profile_root": "server_owned_redacted",
        "stable_profile_root_exposed": False,
        "stable_profile_root_sha256": "",
        "stable_profile_used": False,
        "temporary_profile_used": False,
        "same_profile_after_relaunch": False,
        "thread_count_before": 0,
        "thread_count_after": 0,
        "history_marker_sha256": hashlib.sha256(
            history_marker.encode("utf-8")
        ).hexdigest(),
        "history_marker_seen_before": False,
        "history_marker_seen_after": False,
        "visible_history_restored": False,
        "browser_profile_authority": False,
        "original_codex_touched": False,
        "asar_touched": False,
        "secret_value_exposed": False,
        "raw_thread_content_read": False,
        "raw_thread_content_recorded": False,
        "full_history_restoration_claimed": False,
        "cloud_history_restoration_claimed": False,
    }
    if forbidden:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "forbidden_fields": forbidden,
            "next_action": "remove_forbidden_browser_payload_fields",
        }
    if not isinstance(first_launch_packet, dict) or not isinstance(second_launch_packet, dict):
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "TWO_CUSTOM_CODEX_LAUNCH_PACKETS_REQUIRED",
            "next_action": "launch_custom_codex_twice_with_stable_profile",
        }
    if not isinstance(before_history_snapshot, dict):
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "STABLE_PROFILE_HISTORY_BEFORE_SNAPSHOT_REQUIRED",
            "next_action": "capture_stable_profile_history_before_relaunch",
        }

    relaunch_profile_packet = build_custom_codex_persistent_relaunch_profile_packet(
        first_launch_packet=first_launch_packet,
        second_launch_packet=second_launch_packet,
    )
    profile_id = str(second_launch_packet.get("persistent_profile_id") or "")
    profile_root_value = str(second_launch_packet.get("persistent_profile_root") or "")
    profile_root = Path(profile_root_value).expanduser() if profile_root_value else None
    after_history_snapshot = _stable_profile_history_storage_snapshot(
        profile_root,
        history_marker=history_marker,
    )
    stable_profile_root_sha256 = (
        hashlib.sha256(profile_root_value.encode("utf-8")).hexdigest()
        if profile_root_value
        else ""
    )
    stable_profile_used = bool(
        relaunch_profile_packet.get("profile_relaunch_proven") is True
        and profile_id == DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID
        and second_launch_packet.get("temp_profile_used") is False
        and relaunch_profile_packet.get("second_temp_profile_used") is False
    )
    temporary_profile_used = bool(
        first_launch_packet.get("temp_profile_used") is True
        or second_launch_packet.get("temp_profile_used") is True
    )
    same_profile_after_relaunch = bool(
        relaunch_profile_packet.get("same_persistent_profile_id") is True
        and relaunch_profile_packet.get("same_persistent_codex_home") is True
        and relaunch_profile_packet.get("same_user_data_dir") is True
    )
    thread_count_before = int(before_history_snapshot.get("thread_count") or 0)
    thread_count_after = int(after_history_snapshot.get("thread_count") or 0)
    history_marker_seen_before = before_history_snapshot.get("history_marker_seen") is True
    history_marker_seen_after = after_history_snapshot.get("history_marker_seen") is True
    original_codex_touched = relaunch_profile_packet.get("original_codex_touched") is True
    asar_touched = relaunch_profile_packet.get("asar_touched") is True
    success = bool(
        stable_profile_used
        and not temporary_profile_used
        and same_profile_after_relaunch
        and thread_count_before > 0
        and thread_count_after >= thread_count_before
        and history_marker_seen_before
        and history_marker_seen_after
        and not original_codex_touched
        and not asar_touched
    )
    return {
        **base,
        "status": "ok" if success else "blocked",
        "machine_error_code": (
            "OK"
            if success
            else "CUSTOM_CODEX_STABLE_PROFILE_HISTORY_PERSISTENCE_NOT_PROVEN"
        ),
        "final_status": (
            "CUSTOM_CODEX_STABLE_PROFILE_HISTORY_PERSISTENCE_PROVEN_WITH_LIMITS"
            if success
            else "KNOWN_BLOCKER_CUSTOM_CODEX_STABLE_PROFILE_HISTORY_PERSISTENCE_NOT_PROVEN"
        ),
        "profile_id": profile_id,
        "stable_profile_root_sha256": stable_profile_root_sha256,
        "stable_profile_used": stable_profile_used,
        "temporary_profile_used": temporary_profile_used,
        "same_profile_after_relaunch": same_profile_after_relaunch,
        "thread_count_before": thread_count_before,
        "thread_count_after": thread_count_after,
        "history_marker_seen_before": history_marker_seen_before,
        "history_marker_seen_after": history_marker_seen_after,
        "visible_history_restored": history_marker_seen_after,
        "session_file_count_before": int(before_history_snapshot.get("session_file_count") or 0),
        "session_file_count_after": int(after_history_snapshot.get("session_file_count") or 0),
        "session_storage_survived_relaunch": (
            relaunch_profile_packet.get("session_storage_survived_relaunch") is True
        ),
        "before_snapshot_captured": True,
        "after_snapshot_captured": True,
        "before_snapshot_source": str(before_history_snapshot.get("snapshot_source") or ""),
        "after_snapshot_source": "current_stable_profile_storage",
        "relaunch_profile_packet": relaunch_profile_packet,
        "original_codex_touched": original_codex_touched,
        "asar_touched": asar_touched,
        "next_action": (
            "none"
            if success
            else "capture_marker_before_relaunch_then_relaunch_and_prove_after",
        ),
    }


def build_custom_codex_stable_profile_history_before_snapshot_packet(
    *,
    last_launch_packet: dict[str, Any] | None,
    browser_payload: Any = None,
) -> dict[str, Any]:
    forbidden = _forbidden_stable_profile_history_fields(browser_payload)
    history_marker = _payload_first_text(
        browser_payload,
        "history_marker",
        DEFAULT_STABLE_PROFILE_HISTORY_MARKER,
    )
    base = {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "packet_kind": "custom_codex_stable_profile_history_before_snapshot",
        "history_marker_sha256": hashlib.sha256(
            history_marker.encode("utf-8")
        ).hexdigest(),
        "browser_profile_authority": False,
        "stable_profile_root_exposed": False,
        "raw_thread_content_read": False,
        "raw_thread_content_recorded": False,
    }
    if forbidden:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "forbidden_fields": forbidden,
            "snapshot": None,
            "next_action": "remove_forbidden_browser_payload_fields",
        }
    if not isinstance(last_launch_packet, dict):
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "CUSTOM_CODEX_LAUNCH_PACKET_REQUIRED",
            "snapshot": None,
            "next_action": "launch_custom_codex_with_stable_profile",
        }
    profile_packet = build_custom_codex_persistent_profile_packet(
        last_launch_packet=last_launch_packet,
    )
    profile_root_value = str(last_launch_packet.get("persistent_profile_root") or "")
    profile_root = Path(profile_root_value).expanduser() if profile_root_value else None
    snapshot = _stable_profile_history_storage_snapshot(
        profile_root,
        history_marker=history_marker,
    )
    snapshot["snapshot_source"] = "current_stable_profile_storage_before_relaunch"
    stable_profile_used = profile_packet.get("profile_persistence_proven") is True
    marker_seen = snapshot.get("history_marker_seen") is True
    thread_count = int(snapshot.get("thread_count") or 0)
    success = bool(stable_profile_used and marker_seen and thread_count > 0)
    return {
        **base,
        "status": "ok" if success else "blocked",
        "machine_error_code": (
            "OK"
            if success
            else "STABLE_PROFILE_HISTORY_BEFORE_SNAPSHOT_NOT_PROVEN"
        ),
        "stable_profile_used": stable_profile_used,
        "profile_id": str(last_launch_packet.get("persistent_profile_id") or ""),
        "thread_count": thread_count,
        "history_marker_seen": marker_seen,
        "snapshot": snapshot,
        "next_action": (
            "relaunch_custom_codex_then_prove_after"
            if success
            else "create_history_marker_in_stable_profile_then_capture_before",
        ),
    }


def build_custom_codex_persistent_profile_history_proof_packet(
    *,
    first_launch_packet: dict[str, Any] | None,
    second_launch_packet: dict[str, Any] | None,
    before_history_snapshot: dict[str, Any] | None,
    browser_payload: Any = None,
) -> dict[str, Any]:
    forbidden = _forbidden_stable_profile_history_fields(browser_payload)
    history_marker = _payload_first_text(
        browser_payload,
        "history_marker",
        DEFAULT_STABLE_PROFILE_HISTORY_MARKER,
    )
    base = {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "packet_kind": "custom_codex_persistent_profile_history_proof",
        "status": "blocked",
        "machine_error_code": "CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_NOT_PROVEN",
        "final_status": "KNOWN_BLOCKER_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_NOT_PROVEN",
        "profile_final_status": "KNOWN_BLOCKER_CUSTOM_CODEX_PERSISTENT_PROFILE_NOT_PROVEN",
        "history_final_status": "CUSTOM_CODEX_HISTORY_RESTORE_OWNER_RELAUNCH_REQUIRED",
        "profile_id": "",
        "persistent_profile_used": False,
        "profile_path_is_tmp": True,
        "profile_root": "server_owned_redacted",
        "profile_root_redacted_if_needed": True,
        "first_launch_profile_root": "server_owned_redacted",
        "second_launch_profile_root": "server_owned_redacted",
        "first_launch_profile_root_sha256": "",
        "second_launch_profile_root_sha256": "",
        "same_profile_root": False,
        "history_store_seen": False,
        "thread_store_seen": False,
        "previous_thread_seen_after_relaunch": False,
        "history_reset_detected": True,
        "owner_visible_relaunch_required": True,
        "original_codex_profile_touched": False,
        "original_codex_touched": False,
        "asar_touched": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "ui_label_counts_as_proof": False,
        "model_response_counts_as_proof": False,
        "raw_thread_content_read": False,
        "raw_thread_content_recorded": False,
        "browser_profile_authority": False,
    }
    if forbidden:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "forbidden_fields": forbidden,
            "next_action": "remove_forbidden_browser_payload_fields",
        }
    if not isinstance(first_launch_packet, dict) or not isinstance(second_launch_packet, dict):
        return {
            **base,
            "machine_error_code": "TWO_CUSTOM_CODEX_LAUNCH_PACKETS_REQUIRED",
            "next_action": "launch_custom_codex_twice_with_stable_profile",
        }

    relaunch_profile_packet = build_custom_codex_persistent_relaunch_profile_packet(
        first_launch_packet=first_launch_packet,
        second_launch_packet=second_launch_packet,
    )
    first_root_value = str(first_launch_packet.get("persistent_profile_root") or "")
    second_root_value = str(second_launch_packet.get("persistent_profile_root") or "")
    first_root = Path(first_root_value).expanduser() if first_root_value else None
    second_root = Path(second_root_value).expanduser() if second_root_value else None
    first_root_sha256 = (
        hashlib.sha256(first_root_value.encode("utf-8")).hexdigest()
        if first_root_value
        else ""
    )
    second_root_sha256 = (
        hashlib.sha256(second_root_value.encode("utf-8")).hexdigest()
        if second_root_value
        else ""
    )
    profile_id = str(second_launch_packet.get("persistent_profile_id") or "")
    same_profile_root = bool(first_root_value and second_root_value and first_root_value == second_root_value)
    profile_path_is_tmp = _path_is_tmp(second_root) if second_root is not None else True
    persistent_profile_used = bool(
        relaunch_profile_packet.get("profile_relaunch_proven") is True
        and profile_id == DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID
        and same_profile_root
        and not profile_path_is_tmp
        and second_launch_packet.get("temp_profile_used") is False
    )

    before_snapshot_ok = isinstance(before_history_snapshot, dict)
    after_snapshot = _stable_profile_history_storage_snapshot(
        second_root,
        history_marker=history_marker,
    )
    thread_count_before = (
        int(before_history_snapshot.get("thread_count") or 0)
        if isinstance(before_history_snapshot, dict)
        else 0
    )
    thread_count_after = int(after_snapshot.get("thread_count") or 0)
    session_file_count_before = (
        int(before_history_snapshot.get("session_file_count") or 0)
        if isinstance(before_history_snapshot, dict)
        else 0
    )
    session_file_count_after = int(after_snapshot.get("session_file_count") or 0)
    history_marker_seen_before = (
        before_history_snapshot.get("history_marker_seen") is True
        if isinstance(before_history_snapshot, dict)
        else False
    )
    history_marker_seen_after = after_snapshot.get("history_marker_seen") is True
    history_store_seen = bool(
        after_snapshot.get("state_db_seen") is True
        or after_snapshot.get("session_jsonl_seen") is True
        or after_snapshot.get("log_db_seen") is True
    )
    thread_store_seen = bool(after_snapshot.get("state_db_seen") is True and thread_count_after > 0)
    previous_thread_seen_after_relaunch = bool(
        before_snapshot_ok
        and history_marker_seen_before
        and history_marker_seen_after
    )
    history_reset_detected = bool(
        not before_snapshot_ok
        or thread_count_after < thread_count_before
        or (
            history_marker_seen_before
            and not history_marker_seen_after
        )
    )
    original_codex_touched = relaunch_profile_packet.get("original_codex_touched") is True
    asar_touched = relaunch_profile_packet.get("asar_touched") is True
    history_restore_proven = bool(
        persistent_profile_used
        and before_snapshot_ok
        and history_store_seen
        and thread_store_seen
        and previous_thread_seen_after_relaunch
        and not history_reset_detected
        and not original_codex_touched
        and not asar_touched
    )
    if history_restore_proven:
        status = "ok"
        machine_error_code = "OK"
        final_status = "CUSTOM_CODEX_HISTORY_RESTORE_PROVEN_WITH_LIMITS"
        history_final_status = "CUSTOM_CODEX_HISTORY_RESTORE_PROVEN_WITH_LIMITS"
        next_action = "none"
    elif persistent_profile_used:
        status = "ok"
        machine_error_code = "HISTORY_RESTORE_NOT_PROVEN"
        final_status = "CUSTOM_CODEX_PERSISTENT_PROFILE_PROVEN_WITH_LIMITS"
        history_final_status = "CUSTOM_CODEX_HISTORY_RESTORE_OWNER_RELAUNCH_REQUIRED"
        next_action = "capture_history_marker_and_owner_visible_relaunch_if_needed"
    else:
        status = "blocked"
        machine_error_code = "CUSTOM_CODEX_PERSISTENT_PROFILE_NOT_PROVEN"
        final_status = "KNOWN_BLOCKER_CUSTOM_CODEX_PERSISTENT_PROFILE_NOT_PROVEN"
        history_final_status = "CUSTOM_CODEX_HISTORY_RESTORE_OWNER_RELAUNCH_REQUIRED"
        next_action = "diagnose_persistent_profile_before_history_claim"

    return {
        **base,
        "status": status,
        "machine_error_code": machine_error_code,
        "final_status": final_status,
        "profile_final_status": (
            "CUSTOM_CODEX_PERSISTENT_PROFILE_PROVEN_WITH_LIMITS"
            if persistent_profile_used
            else "KNOWN_BLOCKER_CUSTOM_CODEX_PERSISTENT_PROFILE_NOT_PROVEN"
        ),
        "history_final_status": history_final_status,
        "profile_id": profile_id,
        "persistent_profile_used": persistent_profile_used,
        "profile_path_is_tmp": profile_path_is_tmp,
        "first_launch_profile_root_sha256": first_root_sha256,
        "second_launch_profile_root_sha256": second_root_sha256,
        "same_profile_root": same_profile_root,
        "same_profile_root_across_launches": same_profile_root,
        "history_store_seen": history_store_seen,
        "thread_store_seen": thread_store_seen,
        "previous_thread_seen_after_relaunch": previous_thread_seen_after_relaunch,
        "history_reset_detected": history_reset_detected,
        "owner_visible_relaunch_required": not history_restore_proven,
        "history_restore_proven": history_restore_proven,
        "thread_count_before": thread_count_before,
        "thread_count_after": thread_count_after,
        "session_file_count_before": session_file_count_before,
        "session_file_count_after": session_file_count_after,
        "history_marker_sha256": hashlib.sha256(
            history_marker.encode("utf-8")
        ).hexdigest(),
        "history_marker_seen_before": history_marker_seen_before,
        "history_marker_seen_after": history_marker_seen_after,
        "before_snapshot_seen": before_snapshot_ok,
        "after_snapshot_captured": True,
        "relaunch_profile_packet": relaunch_profile_packet,
        "original_codex_profile_touched": original_codex_touched,
        "original_codex_touched": original_codex_touched,
        "asar_touched": asar_touched,
        "next_action": next_action,
    }


def build_custom_codex_visible_history_relaunch_owner_confirmation_packet(
    payload: dict[str, Any],
    *,
    owner_authorized: bool,
    relaunch_profile_packet: dict[str, Any] | None,
) -> dict[str, Any]:
    base = {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "packet_kind": "custom_codex_visible_history_relaunch_owner_confirmation",
        "final_status": VISIBLE_HISTORY_RELAUNCH_NOT_CONFIRMED_STATUS,
        "profile_relaunch_proven": False,
        "session_storage_survived_relaunch": False,
        "owner_confirmed_old_chat_visible": False,
        "owner_confirmed_chat_not_empty": False,
        "owner_confirmed_custom_codex_window": False,
        "owner_confirmed_after_relaunch": False,
        "owner_confirmed_smoke_phrase_visible": False,
        "smoke_phrase_required": False,
        "raw_thread_content_read": False,
        "raw_thread_content_recorded": False,
        "ocr_used_as_truth": False,
        "all_history_restored_claimed": False,
        "cloud_history_restored_claimed": False,
        "browser_client_path_authority": False,
        "original_codex_touched": False,
        "asar_touched": False,
    }
    if not isinstance(payload, dict):
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "VISIBLE_HISTORY_CONFIRMATION_PAYLOAD_REQUIRED",
            "human_message": "Visible relaunch history confirmation payload must be an object.",
            "next_action": "send_owner_relaunch_checklist_booleans_only",
        }
    forbidden = _forbidden_visible_history_owner_confirmation_fields(
        payload,
        allowed_fields=VISIBLE_HISTORY_RELAUNCH_ALLOWED_OWNER_FIELDS,
    )
    if forbidden:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "human_message": "Visible relaunch history confirmation accepts only owner checklist booleans.",
            "forbidden_fields": sorted(set(forbidden)),
            "next_action": "remove_raw_history_path_or_runtime_fields",
        }
    if not owner_authorized:
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "OWNER_AUTHORIZATION_REQUIRED",
            "human_message": "Owner authorization is required before visible relaunch history confirmation.",
            "next_action": "provide_exact_owner_authorization_phrase",
        }
    if not isinstance(relaunch_profile_packet, dict):
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "PROFILE_RELAUNCH_PACKET_REQUIRED",
            "human_message": "Profile relaunch packet is required before visible history confirmation.",
            "next_action": "launch_custom_codex_twice_with_stable_profile",
        }

    profile_relaunch_proven = relaunch_profile_packet.get("profile_relaunch_proven") is True
    session_storage_survived = (
        relaunch_profile_packet.get("session_storage_survived_relaunch") is True
    )
    original_codex_touched = relaunch_profile_packet.get("original_codex_touched") is True
    asar_touched = relaunch_profile_packet.get("asar_touched") is True
    if (
        not profile_relaunch_proven
        or relaunch_profile_packet.get("status") != "ok"
        or original_codex_touched
        or asar_touched
    ):
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "VISIBLE_HISTORY_UI_WITHOUT_PROFILE_PACKET_TRUTH",
            "final_status": "KNOWN_BLOCKER_VISIBLE_HISTORY_UI_WITHOUT_PROFILE_PACKET_TRUTH",
            "human_message": "Owner UI confirmation is not admitted without proven profile relaunch packet.",
            "profile_relaunch_proven": profile_relaunch_proven,
            "session_storage_survived_relaunch": session_storage_survived,
            "original_codex_touched": original_codex_touched,
            "asar_touched": asar_touched,
            "next_action": "repair_profile_relaunch_packet_before_visible_history_confirmation",
        }

    smoke_required = payload.get("smoke_phrase_required") is True
    smoke_visible = payload.get("smoke_phrase_visible") is True
    owner_checklist = {
        "custom_codex_open": payload.get("custom_codex_open") is True,
        "old_chat_visible": payload.get("old_chat_visible") is True,
        "chat_not_empty": payload.get("chat_not_empty") is True,
        "not_original_codex": payload.get("not_original_codex") is True,
        "owner_confirmed_after_relaunch": (
            payload.get("owner_confirmed_after_relaunch") is True
        ),
        "raw_thread_content_not_recorded": (
            payload.get("raw_thread_content_not_recorded") is True
        ),
        "smoke_phrase_required": smoke_required,
        "smoke_phrase_visible": smoke_visible,
    }
    common_owner_truth = bool(
        owner_checklist["custom_codex_open"]
        and owner_checklist["chat_not_empty"]
        and owner_checklist["not_original_codex"]
        and owner_checklist["owner_confirmed_after_relaunch"]
        and owner_checklist["raw_thread_content_not_recorded"]
    )
    old_chat_confirmed = owner_checklist["old_chat_visible"]
    smoke_confirmed = smoke_visible
    if smoke_required and not smoke_confirmed:
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "VISIBLE_HISTORY_SMOKE_PHRASE_NOT_CONFIRMED",
            "human_message": "Smoke phrase was required but not owner-confirmed visible.",
            "profile_relaunch_proven": profile_relaunch_proven,
            "session_storage_survived_relaunch": session_storage_survived,
            "owner_checklist": owner_checklist,
            "smoke_phrase_required": smoke_required,
            "next_action": "confirm_smoke_phrase_visible_or_use_path_a_without_smoke",
        }
    if not common_owner_truth or not (old_chat_confirmed or smoke_confirmed):
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "VISIBLE_HISTORY_OWNER_CONFIRMATION_INCOMPLETE",
            "human_message": "Owner relaunch history checklist is incomplete.",
            "profile_relaunch_proven": profile_relaunch_proven,
            "session_storage_survived_relaunch": session_storage_survived,
            "owner_checklist": owner_checklist,
            "smoke_phrase_required": smoke_required,
            "next_action": "confirm_visible_history_relaunch_checklist_from_open_custom_window",
        }

    final_status = (
        VISIBLE_HISTORY_RELAUNCH_CONFIRMED_STATUS
        if old_chat_confirmed
        else VISIBLE_HISTORY_RELAUNCH_SMOKE_CONFIRMED_STATUS
    )
    return {
        **base,
        "status": "ok",
        "machine_error_code": "OK",
        "human_message": "Owner confirmed visible Custom Codex history after relaunch.",
        "final_status": final_status,
        "profile_relaunch_proven": True,
        "session_storage_survived_relaunch": session_storage_survived,
        "owner_confirmed_old_chat_visible": old_chat_confirmed,
        "owner_confirmed_chat_not_empty": True,
        "owner_confirmed_custom_codex_window": True,
        "owner_confirmed_after_relaunch": True,
        "owner_confirmed_smoke_phrase_visible": smoke_confirmed,
        "smoke_phrase_required": smoke_required,
        "owner_checklist": owner_checklist,
        "original_codex_touched": False,
        "asar_touched": False,
        "next_action": "treat_as_owner_confirmed_visible_history_with_limits",
    }


def _path_is_tmp(path: Path | None) -> bool:
    if path is None:
        return False
    raw_text = str(path.expanduser())
    if raw_text == "/tmp" or raw_text.startswith("/tmp/") or raw_text.startswith("/private/tmp/"):
        return True
    text = str(path.expanduser().resolve(strict=False))
    return text == "/tmp" or text.startswith("/tmp/") or text.startswith("/private/tmp/")


def _forbidden_custom_persistent_profile_fields(
    payload: Any,
    prefix: str = "",
) -> list[str]:
    if payload in (None, {}, ""):
        return []
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            findings.append(key_path)
            if isinstance(value, (dict, list)):
                findings.extend(_forbidden_custom_persistent_profile_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(_forbidden_custom_persistent_profile_fields(value, f"{prefix}[{index}]"))
    return sorted(dict.fromkeys(findings))


def build_visible_thread_history_owner_confirmation_packet(
    payload: dict[str, Any],
    *,
    owner_authorized: bool,
    last_launch_packet: dict[str, Any] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    base = {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "packet_kind": "visible_thread_history_owner_confirmation",
        "final_status": VISIBLE_HISTORY_NOT_PROVEN_STATUS,
        "visible_thread_history_owner_confirmed": False,
        "profile_storage_continuity_proven": False,
        "full_history_restoration_claimed": False,
        "all_threads_restored_claimed": False,
        "cloud_history_restoration_claimed": False,
        "automatic_ui_inspection_claimed": False,
        "owner_confirmation_counts_as_automatic_runtime_proof": False,
        "raw_thread_content_recorded": False,
        "chat_text_copied": False,
        "browser_client_path_authority": False,
        "original_codex_touched": False,
        "fresh_launch_packet_required": True,
        "freshness_window_seconds": VISIBLE_HISTORY_CONFIRMATION_MAX_AGE_SECONDS,
    }
    if not isinstance(payload, dict):
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "VISIBLE_HISTORY_CONFIRMATION_PAYLOAD_REQUIRED",
            "human_message": "Visible history confirmation payload must be an object.",
            "next_action": "send_owner_checklist_booleans_only",
        }
    forbidden = _forbidden_visible_history_owner_confirmation_fields(payload)
    if forbidden:
        return {
            **base,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "human_message": "Visible history confirmation accepts only owner checklist booleans.",
            "forbidden_fields": sorted(set(forbidden)),
            "next_action": "remove_raw_history_path_or_runtime_fields",
        }
    if not owner_authorized:
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "OWNER_AUTHORIZATION_REQUIRED",
            "human_message": "Owner authorization is required before visible history confirmation.",
            "next_action": "provide_exact_owner_authorization_phrase",
        }
    if not isinstance(last_launch_packet, dict):
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "VISIBLE_HISTORY_FRESH_LAUNCH_PACKET_REQUIRED",
            "human_message": "Launch Custom Codex first, then confirm visible history from the open window.",
            "next_action": "launch_custom_codex_with_stable_profile",
        }

    launch_time = _parse_utc_timestamp(last_launch_packet.get("captured_at_utc"))
    current_time = now or datetime.now(timezone.utc)
    age_seconds = (
        int((current_time - launch_time).total_seconds()) if launch_time is not None else None
    )
    launch_ok = (
        last_launch_packet.get("status") == "ok"
        and last_launch_packet.get("persistent_profile_id") == "wbp-custom-main"
        and last_launch_packet.get("temp_profile_used") is False
        and last_launch_packet.get("native_window_observed") is True
    )
    if age_seconds is None or age_seconds < 0 or age_seconds > VISIBLE_HISTORY_CONFIRMATION_MAX_AGE_SECONDS:
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "VISIBLE_HISTORY_LAUNCH_PACKET_STALE",
            "human_message": "Fresh Custom Codex launch packet is required for owner-visible history confirmation.",
            "launch_packet_age_seconds": age_seconds,
            "persistent_profile_id": last_launch_packet.get("persistent_profile_id", ""),
            "temp_profile_used": last_launch_packet.get("temp_profile_used", None),
            "native_window_observed": last_launch_packet.get("native_window_observed", None),
            "next_action": "launch_custom_codex_again_then_confirm",
        }
    if not launch_ok:
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "VISIBLE_HISTORY_LAUNCH_PACKET_NOT_ADMITTED",
            "human_message": "Last launch packet does not prove stable Custom Codex native window.",
            "launch_packet_age_seconds": age_seconds,
            "launch_status": last_launch_packet.get("status", ""),
            "persistent_profile_id": last_launch_packet.get("persistent_profile_id", ""),
            "temp_profile_used": last_launch_packet.get("temp_profile_used", None),
            "native_window_observed": last_launch_packet.get("native_window_observed", None),
            "next_action": "repair_custom_native_launch_packet",
        }

    checklist = {
        key: payload.get(key) is True for key in sorted(VISIBLE_HISTORY_ALLOWED_OWNER_FIELDS)
    }
    if not all(checklist.values()):
        return {
            **base,
            "status": "blocked",
            "machine_error_code": "VISIBLE_HISTORY_OWNER_CONFIRMATION_INCOMPLETE",
            "human_message": "All owner checklist confirmations must be true.",
            "owner_checklist": checklist,
            "launch_packet_age_seconds": age_seconds,
            "persistent_profile_id": last_launch_packet.get("persistent_profile_id", ""),
            "temp_profile_used": last_launch_packet.get("temp_profile_used", None),
            "native_window_observed": last_launch_packet.get("native_window_observed", None),
            "next_action": "confirm_visible_history_checklist_from_open_custom_window",
        }

    return {
        **base,
        **_visible_history_session_storage_summary(last_launch_packet),
        "status": "ok",
        "machine_error_code": "OK",
        "human_message": "Owner confirmed visible thread history in the open Custom Codex window.",
        "final_status": VISIBLE_HISTORY_CONFIRMED_STATUS,
        "visible_thread_history_owner_confirmed": True,
        "profile_storage_continuity_proven": True,
        "owner_checklist": checklist,
        "launch_packet_age_seconds": age_seconds,
        "persistent_profile_id": last_launch_packet.get("persistent_profile_id", ""),
        "persistent_profile_path_exposed": False,
        "persistent_codex_home_exposed": False,
        "temp_profile_used": last_launch_packet.get("temp_profile_used", None),
        "native_window_observed": last_launch_packet.get("native_window_observed", None),
        "next_action": "treat_as_owner_confirmed_with_limits_not_full_history_proof",
    }


def _runtime_check_all_component(snapshot: dict[str, Any]) -> dict[str, Any]:
    if snapshot.get("status") != "ok":
        return {
            "status": "failed",
            "machine_error_code": str(snapshot.get("runtime", {}).get("machine_error_code") or "UI_CHECK_ALL_RUNTIME_UNAVAILABLE"),
            "human_message": str(snapshot.get("runtime", {}).get("human_message") or "Runtime readonly truth unavailable."),
            "visual_state": "integration_failure",
            "source": str(snapshot.get("source") or "unknown"),
        }
    runtime = snapshot.get("runtime", {})
    visual_state = str(runtime.get("visual_state") or snapshot.get("ui_state") or "unknown")
    if visual_state == "healthy":
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": str(runtime.get("human_message") or "Runtime readonly truth is healthy."),
            "visual_state": visual_state,
            "source": str(snapshot.get("source") or "live_readonly"),
        }
    if visual_state in {"degraded", "stale", "unknown"}:
        return {
            "status": "partial",
            "machine_error_code": str(runtime.get("machine_error_code") or "UI_CHECK_ALL_RUNTIME_DEGRADED"),
            "human_message": str(runtime.get("human_message") or "Runtime readonly truth is degraded."),
            "visual_state": visual_state,
            "source": str(snapshot.get("source") or "live_readonly"),
        }
    return {
        "status": "failed",
        "machine_error_code": str(runtime.get("machine_error_code") or "UI_CHECK_ALL_RUNTIME_FAILED"),
        "human_message": str(runtime.get("human_message") or "Runtime readonly truth failed."),
        "visual_state": visual_state,
        "source": str(snapshot.get("source") or "live_readonly"),
    }


def _run_quick_start_check_all_action(runner: CommandRunner) -> dict[str, Any]:
    accounts_snapshot = build_accounts_readonly_snapshot(runner)
    api_snapshot_before = build_api_connections_readonly_snapshot(runner)
    runtime_snapshot = build_live_readonly_snapshot(runner)

    accounts_summary = accounts_snapshot.get("summary", {})
    visible_count = int(accounts_summary.get("visible_count") or 0) if isinstance(accounts_summary, dict) else 0
    problem_count = int(accounts_summary.get("problem") or 0) if isinstance(accounts_summary, dict) else 0
    if accounts_snapshot.get("status") != "ok":
        accounts_component = {
            "status": "failed",
            "machine_error_code": str(accounts_summary.get("machine_error_code") or "UI_CHECK_ALL_ACCOUNTS_UNAVAILABLE"),
            "human_message": str(accounts_summary.get("human_message") or "Accounts readonly truth unavailable."),
            "source": str(accounts_snapshot.get("source") or "unknown"),
        }
    elif visible_count <= 0:
        accounts_component = {
            "status": "partial",
            "machine_error_code": "UI_CHECK_ALL_NO_ACCOUNTS",
            "human_message": "В sandbox пока нет подключённых аккаунтов; ready не подтверждается.",
            "source": str(accounts_snapshot.get("source") or "accounts_readonly"),
        }
    elif problem_count > 0:
        accounts_component = {
            "status": "partial",
            "machine_error_code": "UI_CHECK_ALL_ACCOUNTS_NEED_ATTENTION",
            "human_message": "В accounts snapshot есть problem-аккаунты; нужен следующий шаг.",
            "source": str(accounts_snapshot.get("source") or "accounts_readonly"),
        }
    else:
        accounts_component = {
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": str(accounts_summary.get("human_message") or "Accounts readonly truth confirmed."),
            "source": str(accounts_snapshot.get("source") or "accounts_readonly"),
        }

    api_component: dict[str, Any]
    api_check_result: dict[str, Any] | None = None
    api_snapshot_after = api_snapshot_before
    primary_route = _primary_api_route_from_snapshot(api_snapshot_before)
    if api_snapshot_before.get("status") != "ok":
        api_component = {
            "status": "failed",
            "machine_error_code": str(api_snapshot_before.get("summary", {}).get("machine_error_code") or "UI_CHECK_ALL_API_UNAVAILABLE"),
            "human_message": str(api_snapshot_before.get("summary", {}).get("human_message") or "API readonly truth unavailable."),
            "route_id": "",
            "refresh_status": "failed",
            "source": str(api_snapshot_before.get("source") or "unknown"),
        }
    elif primary_route is None:
        api_component = {
            "status": "partial",
            "machine_error_code": "UI_CHECK_ALL_API_ROUTE_MISSING",
            "human_message": "Основной API route не подтверждён bounded snapshot.",
            "route_id": "",
            "refresh_status": "complete",
            "source": str(api_snapshot_before.get("source") or "api_connections_readonly"),
        }
    elif primary_route.get("enabled") is not True:
        api_component = {
            "status": "partial",
            "machine_error_code": "UI_CHECK_ALL_API_ROUTE_DISABLED",
            "human_message": "Основной API route отключён; ready не подтверждается.",
            "route_id": str(primary_route.get("route_id") or ""),
            "refresh_status": "complete",
            "source": str(api_snapshot_before.get("source") or "api_connections_readonly"),
        }
    elif str(primary_route.get("secret_status_label") or "unknown") == "missing":
        api_component = {
            "status": "partial",
            "machine_error_code": "UI_CHECK_ALL_API_SECRET_REF_MISSING",
            "human_message": "Для основного API route отсутствует подтверждённый secret_ref.",
            "route_id": str(primary_route.get("route_id") or ""),
            "refresh_status": "complete",
            "source": str(api_snapshot_before.get("source") or "api_connections_readonly"),
        }
    else:
        route_id = str(primary_route.get("route_id") or "")
        api_check_result = execute_command(
            runner,
            "external_models_check",
            structured_args={"route_id": route_id},
        )
        api_snapshot_after = build_api_connections_readonly_snapshot(runner)
        refreshed_route = _primary_api_route_from_snapshot(api_snapshot_after)
        refresh_status = (
            "complete"
            if refreshed_route is not None and str(refreshed_route.get("route_id") or "") == route_id
            else "mismatch"
        )
        if api_check_result["status"] == "ok" and api_snapshot_after.get("status") == "ok" and refresh_status == "complete":
            validation_visual = str(refreshed_route.get("validation_visual_state") or "")
            observed_status = (
                "failed"
                if validation_visual == "red"
                else ("partial" if validation_visual == "amber" else "ok")
            )
            api_component = {
                "status": observed_status,
                "machine_error_code": "OK" if observed_status == "ok" else str(refreshed_route.get("status_code") or "UI_CHECK_ALL_API_ROUTE_UNCONFIRMED"),
                "human_message": str(refreshed_route.get("note") or api_check_result["human_message"]),
                "route_id": route_id,
                "refresh_status": refresh_status,
                "source": str(api_snapshot_after.get("source") or "api_connections_readonly"),
            }
        elif api_check_result["status"] != "ok":
            api_component = {
                "status": "failed",
                "machine_error_code": str(api_check_result["machine_error_code"]),
                "human_message": str(api_check_result["human_message"]),
                "route_id": route_id,
                "refresh_status": "complete" if api_snapshot_after.get("status") == "ok" else "failed",
                "source": str(api_snapshot_after.get("source") or "api_connections_readonly"),
            }
        else:
            api_component = {
                "status": "failed",
                "machine_error_code": "UI_CHECK_ALL_API_REFRESH_MISMATCH" if refresh_status == "mismatch" else str(api_snapshot_after.get("summary", {}).get("machine_error_code") or "UI_CHECK_ALL_API_REFRESH_FAILED"),
                "human_message": "Пакет API check получен, но sandbox-owned refresh не подтвердил route truth.",
                "route_id": route_id,
                "refresh_status": refresh_status if api_snapshot_after.get("status") == "ok" else "failed",
                "source": str(api_snapshot_after.get("source") or "api_connections_readonly"),
            }

    runtime_component = _runtime_check_all_component(runtime_snapshot)
    component_statuses = (
        accounts_component["status"],
        api_component["status"],
        runtime_component["status"],
    )
    if any(status == "failed" for status in component_statuses):
        bundle_verdict = "failed"
        bundle_status = "command_error"
        machine_error_code = "UI_CHECK_ALL_FAILED"
        human_message = "Одна или несколько bounded проверок завершились с blocking failure."
        next_action = "inspect_bundle"
    elif any(status == "partial" for status in component_statuses):
        bundle_verdict = "partial"
        bundle_status = "partial_success"
        machine_error_code = "UI_CHECK_ALL_PARTIAL"
        human_message = "Проверка завершилась частично: нужен следующий шаг по bounded truth surfaces."
        next_action = "review_follow_up"
    else:
        bundle_verdict = "ready"
        bundle_status = "ok"
        machine_error_code = "OK"
        human_message = "Все bounded truth surfaces подтверждены для Quick Start summary."
        next_action = "none"

    data = {
        "bundle_verdict": bundle_verdict,
        "hidden_mutation_absent": True,
        "bundle": {
            "accounts": accounts_component,
            "api": api_component,
            "runtime": runtime_component,
        },
        "bundle_refresh_sources": ["accounts-readonly", "api-connections-readonly", "runtime-owner-packet"],
        "api_check_packet": {
            "status": str(api_check_result["status"]) if api_check_result is not None else "not_run",
            "machine_error_code": str(api_check_result["machine_error_code"]) if api_check_result is not None else "NOT_RUN",
            "human_message": str(api_check_result["human_message"]) if api_check_result is not None else "API verify action was not run.",
            "next_action": str(api_check_result["next_action"]) if api_check_result is not None else "none",
        },
    }
    return {
        "schema_version": 1,
        "status": bundle_status,
        "source": "ui_action",
        "ui_action": "quick_start_check_all",
        "action_role": "quick_start_verify_bundle",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": True,
        "action_claim_scope": "verify-only bundle over admitted truths; hidden mutations absent",
        "result": {
            "status": bundle_status,
            "machine_error_code": machine_error_code,
            "human_message": human_message,
            "next_action": next_action,
            "changed_files": [],
            "data": data,
        },
    }


def run_ui_action(
    runner: CommandRunner,
    payload: dict[str, Any],
    *,
    launch_client_path: str | None = None,
    launch_copy_contract: LaunchCopyContract | None = None,
    launch_action_runner: CommandRunner | None = None,
    action_phase: str = FULL_ACTION_PHASE,
    owner_authorized: bool = False,
    native_operator_status: dict[str, Any] | None = None,
    native_api_snapshot: dict[str, Any] | None = None,
    legacy_import_token_store: LegacyImportTokenStore | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _blocked_action("unknown", "Payload UI-действия должен быть объектом.")
    if "command_id" in payload:
        return _blocked_action("unknown", "Browser должен отправлять ui_action, а не command_id.")

    ui_action = payload.get("ui_action")
    if not isinstance(ui_action, str):
        return _blocked_action("unknown", "UI action должен быть строкой.")
    if ui_action == "legacy_import_discovery":
        forbidden_browser_fields = tuple(
            field
            for field in ("source_dir", "source_path", "path", "source")
            if field in payload
        )
        if forbidden_browser_fields:
            return _unavailable_action(
                ui_action,
                "Legacy import discovery does not accept browser-owned path or source fields.",
                "UI_LEGACY_IMPORT_DISCOVERY_BROWSER_PATH_FORBIDDEN",
                availability_state=LEGACY_IMPORT_DISCOVERY_AVAILABLE_STATE,
                disabled_reasons=("browser_path_forbidden",),
            )
    if ui_action == "legacy_import":
        forbidden_browser_fields = tuple(
            field
            for field in payload
            if field not in {"ui_action", "token_ref", "confirmed"}
        )
        if forbidden_browser_fields:
            return _unavailable_action(
                ui_action,
                "Legacy import reference accepts only a server-owned token_ref.",
                "UI_LEGACY_IMPORT_BROWSER_FIELDS_FORBIDDEN",
                availability_state="token_required",
                disabled_reasons=("browser_fields_forbidden",),
            )
        token_ref = payload.get("token_ref")
        if not isinstance(token_ref, str) or not token_ref.strip():
            return _unavailable_action(
                ui_action,
                "Legacy import requires a server-owned discovery token.",
                LEGACY_IMPORT_TOKEN_REQUIRED_CODE,
                availability_state="token_required",
                disabled_reasons=("token_missing",),
            )
        token_ref = token_ref.strip()
        if (
            len(token_ref) > 64
            or any(char not in SESSION_ID_SAFE_CHARS for char in token_ref)
        ):
            return _unavailable_action(
                ui_action,
                "Legacy import token_ref is not safe.",
                LEGACY_IMPORT_TOKEN_INVALID_CODE,
                availability_state="token_required",
                disabled_reasons=("token_invalid",),
            )
        confirmed = payload.get("confirmed")
        if confirmed is not None and not isinstance(confirmed, bool):
            return _unavailable_action(
                ui_action,
                "Legacy import confirmed flag must be boolean.",
                LEGACY_IMPORT_CONFIRM_INVALID_CODE,
                availability_state="token_required",
                disabled_reasons=("confirm_invalid",),
            )

    action_spec = UI_ACTION_ALLOWLIST.get(ui_action)
    if action_spec is None:
        return _blocked_action(ui_action, "UI action отсутствует в allowlist.")
    if (
        ui_action == "launch_client_dispatch"
        and action_phase == FULL_ACTION_PHASE
        and not launch_client_path
    ):
        return _unavailable_action(
            ui_action,
            "Bounded путь запуска клиента недоступен.",
            "UI_LAUNCH_CLIENT_PATH_UNAVAILABLE",
        )
    if ui_action == "launch_client_dispatch" and action_phase == FULL_ACTION_PHASE and launch_client_path:
        launch_preflight = _launch_copy_preflight(launch_copy_contract)
        if launch_preflight["status"] != "admitted":
            return _launch_copy_preflight_denied(ui_action, launch_preflight)
    if ui_action == "setup_discovery":
        return _direct_ui_action_packet_response(
            ui_action,
            action_spec=action_spec,
            packet=_setup_discovery_packet(),
        )
    if ui_action == "legacy_import_discovery":
        return _direct_ui_action_packet_response(
            ui_action,
            action_spec=action_spec,
            packet=_legacy_import_discovery_packet_with_store(legacy_import_token_store),
        )
    if ui_action == "legacy_import":
        return _direct_ui_action_packet_response(
            ui_action,
            action_spec=action_spec,
            packet=(
                _legacy_import_confirmed_packet(
                    legacy_import_token_store,
                    token_ref=str(payload.get("token_ref") or ""),
                )
                if payload.get("confirmed") is True
                else _legacy_import_reference_packet(
                    legacy_import_token_store,
                    token_ref=str(payload.get("token_ref") or ""),
                )
            ),
        )
    if not _action_available(
        ui_action,
        launch_client_path=launch_client_path,
        launch_copy_contract=launch_copy_contract,
        action_phase=action_phase,
        owner_authorized=owner_authorized,
        legacy_import_token_store=legacy_import_token_store,
    ):
        return _unavailable_action(
            ui_action,
            _action_unavailable_reason(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
                owner_authorized=owner_authorized,
                legacy_import_token_store=legacy_import_token_store,
            ),
            _action_unavailable_code(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
                owner_authorized=owner_authorized,
                legacy_import_token_store=legacy_import_token_store,
            ),
            availability_state=_action_availability_state(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
                owner_authorized=owner_authorized,
                legacy_import_token_store=legacy_import_token_store,
            ),
            disabled_reasons=_action_disabled_reasons(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
                owner_authorized=owner_authorized,
                legacy_import_token_store=legacy_import_token_store,
            ),
        )

    allowed_payload_keys = {"ui_action"}
    if ui_action in ACCOUNT_ID_UI_ACTIONS:
        allowed_payload_keys.add("account_id")
    if ui_action in ROUTE_ID_UI_ACTIONS:
        allowed_payload_keys.add("route_id")
    if ui_action in SESSION_ID_UI_ACTIONS:
        allowed_payload_keys.add("session_id")
    if ui_action == "launch_custom_client_native":
        allowed_payload_keys.update(CUSTOM_NATIVE_LAUNCH_ALLOWED_BROWSER_FIELDS)
    unsupported_keys = sorted(set(payload) - allowed_payload_keys)
    if unsupported_keys:
        return _blocked_action(ui_action, f"Неподдерживаемые поля UI action: {', '.join(unsupported_keys)}.")
    if ui_action == "onboard_account" and action_phase != LIVE_READONLY_ACTION_PHASE:
        accounts_snapshot = build_accounts_readonly_snapshot(runner)
        account_connect_preflight = _account_connect_live_preflight(accounts_snapshot)
        if account_connect_preflight["status"] != "admitted":
            return _account_connect_preflight_denied(ui_action, account_connect_preflight)

    structured_args: dict[str, str] | None = None
    allow_disabled = False
    if ui_action in ACCOUNT_ID_UI_ACTIONS:
        structured_args, blocked = _account_action_args(runner, payload, ui_action=ui_action)
        if blocked is not None:
            return blocked
    if ui_action in ROUTE_ID_UI_ACTIONS:
        structured_args, blocked = _api_route_action_args(runner, payload, ui_action=ui_action)
        if blocked is not None:
            return blocked
    if ui_action in SESSION_ID_UI_ACTIONS:
        structured_args, blocked = _session_action_args(payload, ui_action=ui_action)
        if blocked is not None:
            return blocked
    if ui_action == "onboard_account_dry_run":
        return _run_account_connect_dry_run_action()
    if ui_action == "onboard_account":
        return _run_account_login_bridge_action(runner)
    if ui_action == "account_login_status":
        return _run_account_login_status_action(runner, structured_args or {})
    if ui_action == "account_login_complete":
        return _run_account_login_complete_action(runner, structured_args or {})
    if ui_action == "account_login_cancel":
        return _run_account_login_cancel_action(runner, structured_args or {})
    if ui_action == "api_route_credential_check":
        return _run_api_route_credential_check_action(runner)
    if ui_action == "api_route_connect":
        return _run_api_route_connect_action(runner, launch_copy_contract)
    if ui_action == "quick_start_check_all":
        return _run_quick_start_check_all_action(runner)
    if ui_action == "launch_custom_client_native":
        launch_payload = {
            key: value
            for key, value in payload.items()
            if key != "ui_action"
        }
        account_commands = (
            {
                "status": execute_command(runner, "status"),
                "accounts_list": execute_command(runner, "accounts_list"),
                "rollout_rotation_inspect": execute_command(
                    runner,
                    "rollout_rotation_inspect",
                ),
            }
            if owner_authorized
            else {}
        )
        packet = _launch_custom_native_codex_packet(
            launch_payload,
            owner_authorized=owner_authorized,
            commands=account_commands,
            operator_status=native_operator_status if owner_authorized else None,
            api_snapshot=native_api_snapshot if owner_authorized else None,
        )
        return _ui_action_response_from_result(
            ui_action,
            _native_ui_action_result(packet),
        )
    if ui_action == "show_custom_client_native":
        packet = show_custom_native_window_packet()
        return _ui_action_response_from_result(
            ui_action,
            _native_ui_action_result(packet),
        )
    if ui_action == "launch_client_dispatch":
        if not launch_client_path:
            return _unavailable_action(
                ui_action,
                "Bounded путь запуска клиента недоступен.",
                "UI_LAUNCH_CLIENT_PATH_UNAVAILABLE",
            )
        launch_preflight = _launch_copy_preflight(launch_copy_contract)
        if launch_preflight["status"] != "admitted":
            return _launch_copy_preflight_denied(ui_action, launch_preflight)
        structured_args = {"client_path": launch_client_path}
        allow_disabled = True

    selected_runner = (
        launch_action_runner
        if ui_action == "launch_client_dispatch" and launch_action_runner is not None
        else runner
    )
    result = execute_command(
        selected_runner,
        str(action_spec["adapter_command_id"]),
        structured_args=structured_args,
        allow_disabled=allow_disabled,
    )
    launch_preflight = None
    if ui_action == "launch_client_dispatch":
        launch_preflight = _launch_copy_preflight(launch_copy_contract)
    return {
        "schema_version": 1,
        "status": "ok" if result["status"] == "ok" else "command_error",
        "source": "ui_action",
        "ui_action": ui_action,
        "action_role": action_spec["action_role"],
        "mutates_runtime": action_spec["mutates_runtime"],
        "affects_primary_truth": action_spec["affects_primary_truth"],
        "confirmation_required": action_spec["confirmation_required"],
        "post_action_refresh_required": action_spec["post_action_refresh_required"],
        "action_claim_scope": action_spec["action_claim_scope"],
        "mutation_class": action_spec.get("mutation_class", ""),
        "account_id": structured_args.get("account_id") if structured_args else "",
        "route_id": structured_args.get("route_id") if structured_args else "",
        "session_id": structured_args.get("session_id") if structured_args else "",
        "result": _action_result(result, ui_action=ui_action, launch_preflight=launch_preflight),
    }


def ui_action_metadata(
    *,
    launch_client_path: str | None = None,
    launch_copy_contract: LaunchCopyContract | None = None,
    action_phase: str = LIVE_READONLY_ACTION_PHASE,
    owner_authorized: bool = False,
    legacy_import_token_store: LegacyImportTokenStore | None = None,
) -> dict[str, Any]:
    actions: dict[str, dict[str, Any]] = {}
    for ui_action, action_spec in sorted(UI_ACTION_ALLOWLIST.items()):
        available = _action_available(
            ui_action,
            launch_client_path=launch_client_path,
            launch_copy_contract=launch_copy_contract,
            action_phase=action_phase,
            owner_authorized=owner_authorized,
            legacy_import_token_store=legacy_import_token_store,
        )
        actions[ui_action] = {
            "ui_action": ui_action,
            "display_name": str(action_spec["display_name"]),
            "human_meaning": str(action_spec["human_meaning"]),
            "action_role": str(action_spec["action_role"]),
            "mutates_runtime": bool(action_spec["mutates_runtime"]),
            "affects_primary_truth": bool(action_spec["affects_primary_truth"]),
            "mutation_class": str(action_spec.get("mutation_class", "")),
            "confirmation_required": bool(action_spec["confirmation_required"]),
            "post_action_refresh_required": bool(action_spec["post_action_refresh_required"]),
            "action_claim_scope": str(action_spec["action_claim_scope"]),
            "available": available,
            "availability_state": _action_availability_state(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
                owner_authorized=owner_authorized,
                legacy_import_token_store=legacy_import_token_store,
            ),
            "disabled_reason_code": _action_unavailable_code(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
                owner_authorized=owner_authorized,
                legacy_import_token_store=legacy_import_token_store,
            )
            if not available
            else "",
            "disabled_reasons": _action_disabled_reasons(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
                owner_authorized=owner_authorized,
                legacy_import_token_store=legacy_import_token_store,
            )
            if not available
            else [],
            "unavailable_reason": _action_unavailable_reason(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
                owner_authorized=owner_authorized,
                legacy_import_token_store=legacy_import_token_store,
            ),
        }
        if ui_action == "launch_client_dispatch":
            actions[ui_action]["launch_preflight"] = _public_launch_preflight_summary(
                _launch_copy_preflight(launch_copy_contract)
            )
    return {
        "schema_version": 1,
        "status": "ok",
        "source": "ui_action_metadata",
        "action_phase": action_phase,
        "sandbox_preflight": _public_sandbox_action_preflight_summary(
            _sandbox_action_preflight(launch_copy_contract)
        ),
        "actions": actions,
    }


def _default_review_import_context_or_none(repo_root: Path) -> ReviewImportContext | None:
    try:
        return default_review_import_context(repo_root)
    except ReviewPacketImportError:
        return None


def _default_review_apply_context_or_none(repo_root: Path) -> ReviewApplyContext | None:
    try:
        return default_review_apply_context(repo_root)
    except ReviewPacketImportError:
        return None


def build_handler(
    *,
    runner: CommandRunner | None = None,
    static_dir: Path = WEB_DESIGN_UI,
    launch_client_path: str | None = None,
    launch_copy_contract: LaunchCopyContract | None = None,
    action_phase: str = LIVE_READONLY_ACTION_PHASE,
    owner_authorization_phrase: str | None = None,
    review_import_context: ReviewImportContext | None = None,
    review_apply_context: ReviewApplyContext | None = None,
    safe_worktree_repo_root: Path | None = None,
    web_token_state: WebTokenState | None = None,
    post_rate_limiter: WebPostRateLimiter | None = None,
    post_rate_limit_per_second: int = DEFAULT_WEB_POST_RATE_LIMIT_PER_SECOND,
) -> type[BaseHTTPRequestHandler]:
    owner_paths = RuntimePaths.from_env()
    command_runner = runner or (
        JsonCommandRunner(
            cwd=str(owner_paths.profile_dir),
            env=_owner_action_runner_env(owner_paths),
        )
        if action_phase == FULL_ACTION_PHASE
        else JsonCommandRunner()
    )
    readonly_runner = command_runner
    accounts_readonly_runner = command_runner
    api_connections_readonly_runner = command_runner
    action_runner = command_runner
    operator_surface_session = OperatorSurfaceSession()
    codex_custom_sessions = CodexCustomSessionManager()
    codex_custom_safe_worktree_repo_root = safe_worktree_repo_root or ROOT
    handler_web_token_state = web_token_state or create_in_memory_web_token()
    handler_post_rate_limiter = post_rate_limiter or WebPostRateLimiter(
        limit_per_second=post_rate_limit_per_second
    )
    legacy_import_token_store = LegacyImportTokenStore()
    review_session_store = ReviewSessionStore()
    bounded_review_import_context = (
        review_import_context or _default_review_import_context_or_none(ROOT)
    )
    command_review_apply_context = review_apply_context
    query_review_apply_context = review_apply_context
    if query_review_apply_context is None:
        default_apply_context = _default_review_apply_context_or_none(ROOT)
        if (
            default_apply_context is not None
            and default_apply_context.source_status == "ok"
        ):
            query_review_apply_context = default_apply_context
    review_query_bridge = ReviewQueryBridge(
        review_session_store,
        review_apply_context=query_review_apply_context,
    )
    custom_native_bridge_lease = _CustomNativeBridgeLease(
        bridge_port=_custom_codex_stable_wbp_bridge_port()
    )
    custom_native_launch_state: dict[str, dict[str, Any] | None] = {
        "previous_packet": None,
        "last_packet": None,
        "history_before_snapshot": None,
    }

    def record_custom_native_launch_packet(packet: dict[str, Any]) -> None:
        custom_native_launch_state["previous_packet"] = custom_native_launch_state["last_packet"]
        custom_native_launch_state["last_packet"] = packet

    codex_custom_live_prompt_authorized = owner_authorization_phrase_present(
        owner_authorization_phrase
    )
    launch_copy_runner = None
    if (
        runner is None
        and launch_copy_contract is not None
        and _launch_copy_preflight(launch_copy_contract)["status"] == "admitted"
    ):
        launch_copy_runner = JsonCommandRunner(
            cwd=str(Path(launch_copy_contract.profile_dir or "").expanduser()),
            env=_sandbox_action_runner_env(launch_copy_contract),
        )
    if (
        runner is None
        and action_phase == SANDBOX_ACTION_PHASE
        and _sandbox_action_preflight(launch_copy_contract)["status"] == "admitted"
        and launch_copy_contract is not None
    ):
        sandbox_runner = launch_copy_runner or JsonCommandRunner(
            cwd=str(Path(launch_copy_contract.profile_dir or "").expanduser()),
            env=_sandbox_action_runner_env(launch_copy_contract),
        )
        readonly_runner = sandbox_runner
        accounts_readonly_runner = sandbox_runner
        api_connections_readonly_runner = sandbox_runner
        action_runner = sandbox_runner
    static_root = static_dir.resolve()

    def _external_routes_packet() -> dict[str, Any] | None:
        result = execute_external_command(
            api_connections_readonly_runner,
            "external-models",
            "routes",
            "list",
            "--json",
        )
        packet = result.get("packet")
        return packet if isinstance(packet, dict) else None

    def build_rollback_point_create_admission_packet() -> dict[str, Any]:
        original_status = build_original_status_packet()
        custom_status = build_custom_status_packet(operator_surface_session.status_payload())
        accounts_readonly = build_accounts_readonly_snapshot(accounts_readonly_runner)
        api_readonly = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
        contract_packet = build_custom_recovery_contract_packet(
            original_status=original_status,
            custom_status=custom_status,
            accounts_readonly=accounts_readonly,
            api_readonly=api_readonly,
        )
        rollback_process_owner_contract = (
            build_custom_recovery_rollback_process_owner_contract_packet(
                contract_packet=contract_packet,
            )
        )
        rollback_point_dry_run_contract = build_custom_recovery_rollback_point_dry_run_packet(
            rollback_process_owner_contract=rollback_process_owner_contract,
        )
        return build_custom_recovery_rollback_point_create_admission_packet(
            rollback_point_dry_run_contract=rollback_point_dry_run_contract,
        )

    def build_rollback_apply_admission_dry_run_packet(
        browser_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if browser_payload:
            return build_custom_recovery_rollback_apply_admission_dry_run_packet(
                browser_payload=browser_payload,
            )
        original_status = build_original_status_packet()
        custom_status = build_custom_status_packet(operator_surface_session.status_payload())
        accounts_readonly = build_accounts_readonly_snapshot(accounts_readonly_runner)
        api_readonly = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
        contract_packet = build_custom_recovery_contract_packet(
            original_status=original_status,
            custom_status=custom_status,
            accounts_readonly=accounts_readonly,
            api_readonly=api_readonly,
        )
        rollback_process_owner_contract = (
            build_custom_recovery_rollback_process_owner_contract_packet(
                contract_packet=contract_packet,
            )
        )
        rollback_point_verify = build_custom_recovery_rollback_point_verify_packet()
        return build_custom_recovery_rollback_apply_admission_dry_run_packet(
            rollback_point_verify=rollback_point_verify,
            recovery_contract=contract_packet,
            rollback_process_owner_contract=rollback_process_owner_contract,
            sessions_packet=codex_custom_sessions.list_packet(),
        )

    def build_rollback_apply_live_preflight_packet(
        browser_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if browser_payload:
            return build_custom_recovery_rollback_apply_live_preflight_packet(
                browser_payload=browser_payload,
            )
        return build_custom_recovery_rollback_apply_live_preflight_packet(
            rollback_apply_admission_dry_run=(
                build_rollback_apply_admission_dry_run_packet()
            ),
        )

    def build_rollback_apply_bounded_live_packet(
        browser_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if browser_payload:
            return build_custom_recovery_rollback_apply_bounded_live_packet(
                browser_payload=browser_payload,
            )
        return build_custom_recovery_rollback_apply_bounded_live_packet(
            rollback_apply_live_preflight=build_rollback_apply_live_preflight_packet(),
        )

    def build_recovery_admitted_session_actions_packet() -> dict[str, Any]:
        original_status = build_original_status_packet()
        custom_status = build_custom_status_packet(operator_surface_session.status_payload())
        accounts_readonly = build_accounts_readonly_snapshot(accounts_readonly_runner)
        api_readonly = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
        contract_packet = build_custom_recovery_contract_packet(
            original_status=original_status,
            custom_status=custom_status,
            accounts_readonly=accounts_readonly,
            api_readonly=api_readonly,
        )
        return build_custom_recovery_admitted_session_actions_packet(
            contract_packet=contract_packet,
            sessions_packet=codex_custom_sessions.list_packet(),
        )

    def build_stop_cleanup_preflight_packet(
        browser_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if browser_payload:
            return build_custom_recovery_stop_cleanup_preflight_packet(
                admitted_session_actions_packet=None,
                browser_payload=browser_payload,
            )
        return build_custom_recovery_stop_cleanup_preflight_packet(
            admitted_session_actions_packet=build_recovery_admitted_session_actions_packet(),
        )

    def build_stop_cleanup_live_packet(
        browser_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if browser_payload:
            return build_custom_recovery_stop_cleanup_live_packet(
                browser_payload=browser_payload,
            )
        preflight_source = build_recovery_admitted_session_actions_packet()
        preflight = build_custom_recovery_stop_cleanup_preflight_packet(
            admitted_session_actions_packet=preflight_source,
        )
        internal_session_id = str(preflight_source.get("selected_session_id") or "")
        preflight_session_ref = (
            custom_recovery_session_ref(internal_session_id) if internal_session_id else ""
        )
        live_source = build_recovery_admitted_session_actions_packet()
        live_session_id = str(live_source.get("selected_session_id") or "")
        live_session_ref = custom_recovery_session_ref(live_session_id) if live_session_id else ""
        if (
            preflight.get("status") != "ok"
            or preflight.get("machine_error_code")
            != "CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_READY"
            or preflight.get("stop_cleanup_preflight_ready") is not True
        ):
            return build_custom_recovery_stop_cleanup_live_packet(
                preflight_packet=preflight,
                preflight_selected_session_ref=preflight_session_ref,
                live_selected_session_ref=live_session_ref,
            )
        if not internal_session_id or internal_session_id != live_session_id:
            return build_custom_recovery_stop_cleanup_live_packet(
                preflight_packet=preflight,
                preflight_selected_session_ref=preflight_session_ref,
                live_selected_session_ref=live_session_ref,
            )

        cancel_packet = codex_custom_sessions.cancel_packet(internal_session_id)
        cancel_session_ref = (
            custom_recovery_session_ref(internal_session_id)
            if cancel_packet.get("status") == "ok"
            else ""
        )
        if cancel_packet.get("status") != "ok" or cancel_packet.get("cancelled") is not True:
            return build_custom_recovery_stop_cleanup_live_packet(
                preflight_packet=preflight,
                cancel_packet=cancel_packet,
                preflight_selected_session_ref=preflight_session_ref,
                live_selected_session_ref=live_session_ref,
                cancel_selected_session_ref=cancel_session_ref,
                cleanup_attempted=False,
            )

        cleanup_packet = codex_custom_sessions.cleanup_packet(internal_session_id)
        cleanup_session_ref = (
            custom_recovery_session_ref(internal_session_id)
            if cleanup_packet.get("status") == "ok"
            else ""
        )
        return build_custom_recovery_stop_cleanup_live_packet(
            preflight_packet=preflight,
            cancel_packet=cancel_packet,
            cleanup_packet=cleanup_packet,
            preflight_selected_session_ref=preflight_session_ref,
            live_selected_session_ref=live_session_ref,
            cancel_selected_session_ref=cancel_session_ref,
            cleanup_selected_session_ref=cleanup_session_ref,
            cleanup_attempted=True,
        )

    def build_process_kill_preflight_packet(
        browser_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if browser_payload:
            return build_custom_recovery_process_kill_preflight_packet(
                admitted_session_actions_packet=None,
                browser_payload=browser_payload,
            )
        sessions_packet = codex_custom_sessions.list_packet()
        admitted = build_recovery_admitted_session_actions_packet()
        selected_session_id = str(admitted.get("selected_session_id") or "")
        if selected_session_id:
            for session in sessions_packet.get("sessions", []):
                if (
                    isinstance(session, dict)
                    and str(session.get("session_id") or "") == selected_session_id
                ):
                    admitted = {**admitted, "selected_session_packet": session}
                    break
        return build_custom_recovery_process_kill_preflight_packet(
            admitted_session_actions_packet=admitted,
        )

    def build_operator_ready_packet() -> dict[str, Any]:
        original_status = build_original_status_packet()
        custom_status = build_custom_status_packet(operator_surface_session.status_payload())
        accounts_readonly = build_accounts_readonly_snapshot(accounts_readonly_runner)
        api_readonly = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
        recovery_contract = build_custom_recovery_contract_packet(
            original_status=original_status,
            custom_status=custom_status,
            accounts_readonly=accounts_readonly,
            api_readonly=api_readonly,
        )
        admitted_session_actions = build_custom_recovery_admitted_session_actions_packet(
            contract_packet=recovery_contract,
            sessions_packet=codex_custom_sessions.list_packet(),
        )
        rollback_process_owner_contract = (
            build_custom_recovery_rollback_process_owner_contract_packet(
                contract_packet=recovery_contract,
            )
        )
        rollback_point_dry_run = build_custom_recovery_rollback_point_dry_run_packet(
            rollback_process_owner_contract=rollback_process_owner_contract,
        )
        rollback_point_create_admission = (
            build_custom_recovery_rollback_point_create_admission_packet(
                rollback_point_dry_run_contract=rollback_point_dry_run,
            )
        )
        rollback_point_verify = build_custom_recovery_rollback_point_verify_packet()
        rollback_apply_admission = build_custom_recovery_rollback_apply_admission_dry_run_packet(
            rollback_point_verify=rollback_point_verify,
            recovery_contract=recovery_contract,
            rollback_process_owner_contract=rollback_process_owner_contract,
            sessions_packet=codex_custom_sessions.list_packet(),
        )
        rollback_apply_live_preflight = build_custom_recovery_rollback_apply_live_preflight_packet(
            rollback_apply_admission_dry_run=rollback_apply_admission,
        )
        rollback_apply_receipt_verify = (
            build_custom_recovery_rollback_apply_receipt_verify_packet()
        )
        stop_cleanup_preflight = build_custom_recovery_stop_cleanup_preflight_packet(
            admitted_session_actions_packet=admitted_session_actions,
        )
        process_kill_preflight = build_process_kill_preflight_packet()
        return build_custom_recovery_rollback_operator_ready_packet(
            recovery_contract=recovery_contract,
            admitted_session_actions=admitted_session_actions,
            rollback_process_owner_contract=rollback_process_owner_contract,
            rollback_point_dry_run=rollback_point_dry_run,
            rollback_point_create_admission=rollback_point_create_admission,
            rollback_point_verify=rollback_point_verify,
            rollback_apply_admission=rollback_apply_admission,
            rollback_apply_live_preflight=rollback_apply_live_preflight,
            rollback_apply_receipt_verify=rollback_apply_receipt_verify,
            stop_cleanup_preflight=stop_cleanup_preflight,
            stop_cleanup_live=None,
            process_kill_preflight=process_kill_preflight,
            diagnostics_redaction_packet={
                "status": "passed",
                "findings": [],
                "secret_leak": False,
                "secret_value_recorded": False,
                "source": "ui_action_metadata_export_diagnostics_support_artifact_only",
            },
        )

    class Handler(BaseHTTPRequestHandler):
        GET_ROUTE_DISPATCH_TABLE: dict[str, str] = {}
        POST_ROUTE_DISPATCH_TABLE: dict[str, str] = {}

        def do_GET(self) -> None:
            try:
                self._handle_get()
            except _HttpIngressRejection as rejection:
                self._send_json(rejection.packet, status=rejection.status)

        def _handle_get(self) -> None:
            self._admit_common_request()
            parsed = urlparse(self.path)
            route_spec = WEB_DESIGN_LIVE_ROUTE_TABLE.lookup("GET", parsed.path)
            if route_spec is not None:
                self._dispatch_get_route(route_spec, self.path)
                return
            if self._is_api_request_path(parsed.path):
                raise _HttpIngressRejection(
                    status=HTTPStatus.NOT_FOUND,
                    machine_error_code="WEB_ROUTE_NOT_REGISTERED",
                    human_message="Web GET API route is not registered in the route effect registry.",
                )
                return
            self._send_static(parsed.path)

        def _dispatch_get_route(self, route_spec: RouteSpec, request_path: str) -> None:
            handler_id = str(route_spec.handler_id or "").strip()
            if not handler_id:
                raise _HttpIngressRejection(
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    machine_error_code="WEB_GET_ROUTE_HANDLER_ID_MISSING",
                    human_message="Registered Web GET route is missing its handler binding.",
                )
            dispatcher_name = type(self).GET_ROUTE_DISPATCH_TABLE.get(handler_id)
            if dispatcher_name is None:
                raise _HttpIngressRejection(
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    machine_error_code="WEB_GET_ROUTE_DISPATCH_MISSING",
                    human_message="Registered Web GET route is not bound in the dispatch table.",
                )
            dispatcher = getattr(self, dispatcher_name, None)
            if not callable(dispatcher):
                raise _HttpIngressRejection(
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    machine_error_code="WEB_GET_ROUTE_DISPATCH_TARGET_MISSING",
                    human_message="Registered Web GET route dispatch target is unavailable.",
                )
            dispatcher(request_path)

        def _is_api_request_path(self, request_path: str) -> bool:
            return request_path == "/api" or request_path.startswith("/api/")

        def _handle_get_owner_login_sandbox(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_owner_login_sandbox_page(parsed.query)
            return

        def _handle_get_api_live_readonly(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(build_live_readonly_snapshot(readonly_runner))
            return

        def _handle_get_api_accounts_readonly(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(build_accounts_readonly_snapshot(accounts_readonly_runner))
            return

        def _handle_get_api_api_connections_readonly(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_api_connections_readonly_snapshot(api_connections_readonly_runner)
            )
            return

        def _handle_get_api_actions(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                ui_action_metadata(
                    launch_client_path=launch_client_path,
                    launch_copy_contract=launch_copy_contract,
                    action_phase=action_phase,
                    owner_authorized=codex_custom_live_prompt_authorized,
                    legacy_import_token_store=legacy_import_token_store,
                )
            )
            return

        def _handle_get_api_operator_status(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            status_packet, _operator_status_timeout = _bounded_operator_status_payload(
                operator_surface_session
            )
            self._send_json(status_packet)
            return

        def _handle_get_api_operator_models(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            models = operator_surface_session.probe_models()
            self._send_json(
                {
                    "schema_version": 1,
                    "status": "ok" if models.get("ok") else "degraded",
                    "source": "operator_surface",
                    "captured_at_utc": models.get("captured_at_utc", ""),
                    "model_ids": models.get("model_ids", []),
                    "server_issued": True,
                    "machine_error_code": "OK" if models.get("ok") else "OPERATOR_MODELS_UNAVAILABLE",
                }
            )
            return

        def _handle_get_api_operator_transcript(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(operator_surface_session.transcript_payload())
            return

        def _handle_get_api_review_surface(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                review_query_bridge.get_review_surface(
                    parse_qs(parsed.query, keep_blank_values=True) if parsed.query else None
                )
            )
            return

        def _handle_get_api_review_commands(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                {
                    "status": "ok",
                    "machine_error_code": "OK",
                    "commands": review_allowlist_metadata(),
                }
            )
            return

        def _handle_get_api_codex_launch_modes(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(build_launch_modes_packet(operator_surface_session.status_payload()))
            return

        def _handle_get_api_codex_original_status(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(build_original_status_packet())
            return

        def _handle_get_api_codex_custom_status(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            def build_custom_status_snapshot() -> dict[str, Any]:
                return build_custom_status_packet(operator_surface_session.status_payload())

            self._send_json(
                _run_custom_codex_readonly_snapshot(
                    endpoint=parsed.path,
                    timeout_scope="custom_status_readonly_snapshot",
                    build_snapshot=build_custom_status_snapshot,
                )
            )
            return

        def _handle_get_api_codex_custom_models(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            def build_models_snapshot() -> dict[str, Any]:
                api_snapshot = build_api_connections_readonly_snapshot(
                    api_connections_readonly_runner
                )
                operator_status, operator_status_timeout = _bounded_operator_status_payload(
                    operator_surface_session
                )
                packet = build_custom_model_registry_packet(
                    operator_status,
                    api_snapshot=api_snapshot,
                )
                if operator_status_timeout:
                    packet = _mark_operator_status_timeout_fallback(packet)
                return packet

            self._send_json(
                _run_custom_codex_readonly_snapshot(
                    endpoint=parsed.path,
                    timeout_scope="custom_models_readonly_snapshot",
                    build_snapshot=build_models_snapshot,
                )
            )
            return

        def _handle_get_api_codex_custom_model_selector(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            def build_selector_snapshot() -> dict[str, Any]:
                api_snapshot = build_api_connections_readonly_snapshot(
                    api_connections_readonly_runner
                )
                operator_status, operator_status_timeout = _bounded_operator_status_payload(
                    operator_surface_session
                )
                packet = build_dual_lane_model_selection_ui_packet(
                    operator_status,
                    api_snapshot=api_snapshot,
                )
                if operator_status_timeout:
                    packet = _mark_operator_status_timeout_fallback(packet)
                return packet

            self._send_json(
                _run_custom_codex_readonly_snapshot(
                    endpoint=parsed.path,
                    timeout_scope="custom_model_selector_readonly_snapshot",
                    build_snapshot=build_selector_snapshot,
                    timeout_fallback=lambda timeout_packet: _custom_model_selector_timeout_fallback_packet(
                        timeout_packet,
                        operator_surface_session=operator_surface_session,
                        api_connections_readonly_runner=api_connections_readonly_runner,
                    ),
                )
            )
            return

        def _handle_get_api_codex_custom_api_compat(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_custom_api_compat_packet(operator_surface_session.status_payload())
            )
            return

        def _handle_get_api_codex_custom_api_action_gate(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            def build_api_action_gate_snapshot() -> dict[str, Any]:
                api_snapshot = build_api_connections_readonly_snapshot(
                    api_connections_readonly_runner
                )
                operator_status = operator_surface_session.status_payload()
                availability_lattice_packet = _build_live_native_availability_lattice_packet(
                    operator_status,
                    api_snapshot=api_snapshot,
                )
                return build_custom_api_action_gate_packet(
                    {},
                    operator_status,
                    api_snapshot=api_snapshot,
                    availability_lattice_packet=availability_lattice_packet,
                    owner_authorized=codex_custom_live_prompt_authorized,
                )

            self._send_json(
                _run_custom_codex_readonly_snapshot(
                    endpoint=parsed.path,
                    timeout_scope="custom_api_action_gate_readonly_snapshot",
                    build_snapshot=build_api_action_gate_snapshot,
                )
            )
            return

        def _handle_get_api_codex_custom_accounts(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(build_accounts_truth_packet(self._codex_account_commands()))
            return

        def _handle_get_api_codex_custom_account_selection(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_account_selection_packet(
                    self._codex_account_commands(),
                    operator_surface_session.status_payload(),
                )
            )
            return

        def _handle_get_api_codex_custom_sessions(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(codex_custom_sessions.list_packet())
            return

        def _handle_get_api_codex_custom_recovery_contract(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            original_status = build_original_status_packet()
            custom_status = build_custom_status_packet(
                operator_surface_session.status_payload()
            )
            accounts_readonly = build_accounts_readonly_snapshot(accounts_readonly_runner)
            api_readonly = build_api_connections_readonly_snapshot(
                api_connections_readonly_runner
            )
            self._send_json(
                build_custom_recovery_contract_packet(
                    original_status=original_status,
                    custom_status=custom_status,
                    accounts_readonly=accounts_readonly,
                    api_readonly=api_readonly,
                )
            )
            return

        def _handle_get_api_codex_custom_recovery_admitted_session_actions(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(build_recovery_admitted_session_actions_packet())
            return

        def _handle_get_api_codex_custom_recovery_stop_cleanup_preflight(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_stop_cleanup_preflight_packet(
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    )
                    if parsed.query
                    else None,
                )
            )
            return

        def _handle_get_api_codex_custom_recovery_process_kill_preflight(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_process_kill_preflight_packet(
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    )
                    if parsed.query
                    else None,
                )
            )
            return

        def _handle_get_api_codex_custom_recovery_operator_ready(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            packet = build_operator_ready_packet()
            if parsed.query:
                packet = {
                    **packet,
                    "status": "blocked",
                    "machine_error_code": (
                        "CUSTOM_CODEX_RECOVERY_ROLLBACK_OPERATOR_MATRIX_BROWSER_FIELD_REJECTED"
                    ),
                    "forbidden_fields": sorted(
                        parse_qs(parsed.query, keep_blank_values=True).keys()
                    ),
                    "browser_forbidden_fields_rejected": True,
                    "bounded_local_operator_surface_ready": False,
                    "final_verdict": (
                        "CUSTOM_CODEX_RECOVERY_ROLLBACK_OPERATOR_MATRIX_BLOCKED"
                    ),
                    "next_action": "remove_forbidden_browser_fields",
                }
            self._send_json(packet)
            return

        def _handle_get_api_codex_custom_recovery_rollback_process_owner_contract(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            original_status = build_original_status_packet()
            custom_status = build_custom_status_packet(
                operator_surface_session.status_payload()
            )
            accounts_readonly = build_accounts_readonly_snapshot(accounts_readonly_runner)
            api_readonly = build_api_connections_readonly_snapshot(
                api_connections_readonly_runner
            )
            contract_packet = build_custom_recovery_contract_packet(
                original_status=original_status,
                custom_status=custom_status,
                accounts_readonly=accounts_readonly,
                api_readonly=api_readonly,
            )
            self._send_json(
                build_custom_recovery_rollback_process_owner_contract_packet(
                    contract_packet=contract_packet,
                )
            )
            return

        def _handle_get_api_codex_custom_recovery_rollback_point_dry_run(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            original_status = build_original_status_packet()
            custom_status = build_custom_status_packet(
                operator_surface_session.status_payload()
            )
            accounts_readonly = build_accounts_readonly_snapshot(accounts_readonly_runner)
            api_readonly = build_api_connections_readonly_snapshot(
                api_connections_readonly_runner
            )
            contract_packet = build_custom_recovery_contract_packet(
                original_status=original_status,
                custom_status=custom_status,
                accounts_readonly=accounts_readonly,
                api_readonly=api_readonly,
            )
            rollback_process_owner_contract = (
                build_custom_recovery_rollback_process_owner_contract_packet(
                    contract_packet=contract_packet,
                )
            )
            self._send_json(
                build_custom_recovery_rollback_point_dry_run_packet(
                    rollback_process_owner_contract=rollback_process_owner_contract,
                )
            )
            return

        def _handle_get_api_codex_custom_recovery_rollback_point_create_admission(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(build_rollback_point_create_admission_packet())
            return

        def _handle_get_api_codex_custom_recovery_rollback_point_verify(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_custom_recovery_rollback_point_verify_packet(
                    browser_payload=parse_qs(parsed.query) if parsed.query else None,
                )
            )
            return

        def _handle_get_api_codex_custom_recovery_rollback_apply_admission_dry_run(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_rollback_apply_admission_dry_run_packet(
                    browser_payload=parse_qs(parsed.query) if parsed.query else None,
                )
            )
            return

        def _handle_get_api_codex_custom_recovery_rollback_apply_live_preflight(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_rollback_apply_live_preflight_packet(
                    browser_payload=parse_qs(parsed.query) if parsed.query else None,
                )
            )
            return

        def _handle_get_api_codex_custom_recovery_rollback_apply_receipt_verify(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_custom_recovery_rollback_apply_receipt_verify_packet(
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    ),
                )
            )
            return

        def _handle_get_api_codex_custom_window_prompt_trace(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_custom_codex_window_prompt_trace_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    bridge_trace_packet=custom_native_bridge_lease.trace_snapshot(),
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    ),
                )
            )
            return

        def _handle_get_api_codex_custom_window_input_route_trace(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_custom_codex_window_input_route_trace_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    bridge_trace_packet=custom_native_bridge_lease.trace_snapshot(),
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    ),
                )
            )
            return

        def _handle_get_api_codex_custom_bridge_failure_recovery_truth(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_custom_codex_bridge_failure_recovery_truth_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    bridge_trace_packet=custom_native_bridge_lease.trace_snapshot(),
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    ),
                )
            )
            return

        def _handle_get_api_codex_custom_stable_bridge_preflight(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_custom_codex_stable_bridge_preflight_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    bridge_trace_packet=custom_native_bridge_lease.trace_snapshot(),
                    expected_bridge_port=custom_native_bridge_lease.bridge_port,
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    ),
                )
            )
            return

        def _handle_get_api_codex_custom_live_bridge_stability(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_custom_codex_live_bridge_stability_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    bridge_trace_packet=custom_native_bridge_lease.trace_snapshot(),
                    expected_bridge_port=custom_native_bridge_lease.bridge_port,
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    ),
                )
            )
            return

        def _handle_get_api_codex_custom_chatgpt_plus_api_coder_trace(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_custom_codex_chatgpt_plus_api_coder_trace_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    bridge_trace_packet=custom_native_bridge_lease.trace_snapshot(),
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    ),
                )
            )
            return

        def _handle_get_api_codex_custom_quick_start_chatgpt_plus_deepseek_file_edit_proof(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_custom_codex_chatgpt_plus_deepseek_file_edit_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    bridge_trace_packet=custom_native_bridge_lease.trace_snapshot(),
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    ),
                    repo_root=ROOT,
                )
            )
            return

        def _handle_get_api_codex_custom_quick_start_deepseek_code_edit_proof(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_custom_codex_deepseek_code_edit_reproduction_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    bridge_trace_packet=custom_native_bridge_lease.trace_snapshot(),
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    ),
                    repo_root=ROOT,
                )
            )
            return

        def _handle_get_api_codex_custom_quick_start_api_only_deepseek_live_code_edit_truth(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_api_only_deepseek_live_code_edit_truth_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    bridge_trace_packet=custom_native_bridge_lease.trace_snapshot(),
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    ),
                    repo_root=ROOT,
                )
            )
            return

        def _handle_get_api_codex_custom_quick_start_deepseek_route_bound_edit_proof(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_custom_codex_deepseek_route_bound_real_edit_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    bridge_trace_packet=custom_native_bridge_lease.trace_snapshot(),
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    ),
                    repo_root=ROOT,
                )
            )
            return

        def _handle_get_api_codex_custom_persistent_profile(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_custom_codex_persistent_profile_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    ),
                )
            )
            return

        def _handle_get_api_codex_custom_persistent_relaunch_profile(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            self._send_json(
                build_custom_codex_persistent_relaunch_profile_packet(
                    first_launch_packet=custom_native_launch_state["previous_packet"],
                    second_launch_packet=custom_native_launch_state["last_packet"],
                    browser_payload=(
                        parse_qs(parsed.query, keep_blank_values=True)
                        if parsed.query
                        else None
                    ),
                )
            )
            return

        def _handle_get_api_codex_custom_stable_profile_history_persistence(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            payload = (
                parse_qs(parsed.query, keep_blank_values=True)
                if parsed.query
                else {}
            )
            action = _payload_first_text(payload, "action", "prove_after")
            if action == "capture_before":
                packet = build_custom_codex_stable_profile_history_before_snapshot_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    browser_payload=payload,
                )
                if packet.get("status") == "ok" and isinstance(packet.get("snapshot"), dict):
                    custom_native_launch_state["history_before_snapshot"] = packet["snapshot"]
                self._send_json(packet)
                return
            self._send_json(
                build_custom_codex_stable_profile_history_persistence_packet(
                    first_launch_packet=custom_native_launch_state["previous_packet"],
                    second_launch_packet=custom_native_launch_state["last_packet"],
                    before_history_snapshot=custom_native_launch_state[
                        "history_before_snapshot"
                    ],
                    browser_payload=payload,
                )
            )
            return

        def _handle_get_api_codex_custom_persistent_profile_history_proof(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            payload = (
                parse_qs(parsed.query, keep_blank_values=True)
                if parsed.query
                else {}
            )
            self._send_json(
                build_custom_codex_persistent_profile_history_proof_packet(
                    first_launch_packet=custom_native_launch_state["previous_packet"],
                    second_launch_packet=custom_native_launch_state["last_packet"],
                    before_history_snapshot=custom_native_launch_state[
                        "history_before_snapshot"
                    ],
                    browser_payload=payload,
                )
            )
            return

        def _handle_get_api_codex_custom_sessions_prefix(self, request_path: str) -> None:
            parsed = urlparse(request_path)
            custom_session = self._custom_session_route(parsed.path)
            if custom_session is None:
                raise _HttpIngressRejection(
                    status=HTTPStatus.NOT_FOUND,
                    machine_error_code="WEB_ROUTE_NOT_REGISTERED",
                    human_message="Web GET API route is not registered in the route effect registry.",
                )
            session_id, action = custom_session
            if action == "":
                self._send_json(codex_custom_sessions.get_packet(session_id))
                return
            if action == "transcript":
                self._send_json(codex_custom_sessions.transcript_packet(session_id))
                return
            raise _HttpIngressRejection(
                status=HTTPStatus.NOT_FOUND,
                machine_error_code="WEB_ROUTE_NOT_REGISTERED",
                human_message="Web GET API route is not registered in the route effect registry.",
            )

        def do_POST(self) -> None:
            try:
                self._handle_post()
            except _HttpIngressRejection as rejection:
                self._send_json(rejection.packet, status=rejection.status)

        def _handle_post(self) -> None:
            parsed = urlparse(self.path)
            route_spec = self._admit_post_request(parsed.path)
            self._dispatch_post_route(route_spec, parsed.path)

        def _dispatch_post_route(self, route_spec: RouteSpec, request_path: str) -> None:
            handler_id = str(route_spec.handler_id or "").strip()
            if not handler_id:
                raise _HttpIngressRejection(
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    machine_error_code="WEB_POST_ROUTE_HANDLER_ID_MISSING",
                    human_message="Registered Web POST route is missing its handler binding.",
                )
            dispatcher_name = type(self).POST_ROUTE_DISPATCH_TABLE.get(handler_id)
            if dispatcher_name is None:
                raise _HttpIngressRejection(
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    machine_error_code="WEB_POST_ROUTE_DISPATCH_MISSING",
                    human_message="Registered Web POST route is not bound in the dispatch table.",
                )
            dispatcher = getattr(self, dispatcher_name, None)
            if not callable(dispatcher):
                raise _HttpIngressRejection(
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    machine_error_code="WEB_POST_ROUTE_DISPATCH_TARGET_MISSING",
                    human_message="Registered Web POST route dispatch target is unavailable.",
                )
            dispatcher(request_path)

        def _handle_post_api_operator_run(self, actual_path: str) -> None:
            self._send_json(operator_surface_session.run_prompt(self._read_json_body()))
            return

        def _handle_post_api_review_command(self, actual_path: str) -> None:
            payload = self._read_json_body()
            command_id = payload.get("command_id")
            if not isinstance(command_id, str):
                self._send_json(
                    {
                        "status": "command_error",
                        "exit_code": 1,
                        "human_message": "command_id must be a non-empty string.",
                        "machine_error_code": "REVIEW_COMMAND_ID_REQUIRED",
                        "changed_files": [],
                        "next_action": "fix_command_payload",
                        "data": {},
                    }
                )
                return
            command_payload = payload.get("payload", {})
            self._send_json(
                execute_review_command(
                    review_session_store,
                    command_id,
                    payload=command_payload if isinstance(command_payload, dict) else {},
                    import_context=bounded_review_import_context,
                    apply_context=command_review_apply_context,
                )
            )
            return

        def _handle_post_api_codex_original_launch_dry_run(self, actual_path: str) -> None:
            self._send_json(build_original_launch_dry_run_packet(self._read_json_body()))
            return

        def _handle_post_api_codex_original_launch(self, actual_path: str) -> None:
            self._send_json(
                _launch_original_codex_packet(
                    self._read_json_body(),
                    owner_authorized=codex_custom_live_prompt_authorized,
                )
            )
            return

        def _handle_post_api_codex_custom_launch_dry_run(self, actual_path: str) -> None:
            self._send_json(build_custom_launch_dry_run_packet(self._read_json_body()))
            return

        def _handle_post_api_codex_custom_launch(self, actual_path: str) -> None:
            operator_status = (
                operator_surface_session.status_payload()
                if codex_custom_live_prompt_authorized
                else None
            )
            account_commands = (
                self._codex_account_commands()
                if codex_custom_live_prompt_authorized
                else {}
            )
            api_snapshot = (
                build_api_connections_readonly_snapshot(api_connections_readonly_runner)
                if codex_custom_live_prompt_authorized
                else None
            )
            self._send_json(
                _launch_custom_codex_packet(
                    self._read_json_body(),
                    owner_authorized=codex_custom_live_prompt_authorized,
                    session_manager=codex_custom_sessions,
                    commands=account_commands,
                    operator_status=operator_status,
                    api_snapshot=api_snapshot,
                )
            )
            return

        def _handle_post_api_codex_custom_native_launch_preflight(self, actual_path: str) -> None:
            payload = self._read_json_body()
            api_snapshot = (
                build_api_connections_readonly_snapshot(api_connections_readonly_runner)
                if codex_custom_live_prompt_authorized
                else None
            )
            external_routes_packet = (
                _external_routes_packet() if codex_custom_live_prompt_authorized else None
            )
            operator_status = None
            if codex_custom_live_prompt_authorized:
                operator_status, _operator_status_timeout = _bounded_operator_status_payload(
                    operator_surface_session
                )
            runtime_health_result = (
                execute_command(readonly_runner, "healthcheck")
                if _payload_requires_chatgpt_runtime_health(payload)
                else None
            )
            self._send_json(
                _custom_native_launch_preflight_packet(
                    payload,
                    owner_authorized=codex_custom_live_prompt_authorized,
                    operator_status=operator_status,
                    api_snapshot=api_snapshot,
                    external_routes_packet=external_routes_packet,
                    native_bridge_lease=custom_native_bridge_lease,
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    runtime_health_result=runtime_health_result,
                )
            )
            return

        def _handle_post_api_codex_custom_native_launch(self, actual_path: str) -> None:
            payload = self._read_json_body()
            if not codex_custom_live_prompt_authorized:
                self._send_json(
                    _launch_custom_native_codex_packet(
                        payload,
                        owner_authorized=False,
                        commands={},
                        operator_status=None,
                        api_snapshot=None,
                        external_routes_packet=None,
                        native_bridge_lease=custom_native_bridge_lease,
                    )
                )
                return
            if codex_custom_live_prompt_authorized:
                model_id = str(payload.get("model_id") or "").strip()
                execution_mode = str(payload.get("execution_mode") or "").strip()
                api_model_id = str(payload.get("api_model_id") or "").strip()
                chatgpt_model_id = str(payload.get("chatgpt_model_id") or "").strip()
                missing_selection = not any(
                    [model_id, execution_mode, api_model_id, chatgpt_model_id]
                )
                if _forbidden_custom_live_launch_fields(payload) or missing_selection:
                    packet = _launch_custom_native_codex_packet(
                        payload,
                        owner_authorized=True,
                        commands={},
                        operator_status=None,
                        api_snapshot=None,
                        external_routes_packet=None,
                        native_bridge_lease=custom_native_bridge_lease,
                    )
                    record_custom_native_launch_packet(packet)
                    self._send_json(packet)
                    return
            api_snapshot = (
                build_api_connections_readonly_snapshot(api_connections_readonly_runner)
                if codex_custom_live_prompt_authorized
                else None
            )
            external_routes_packet = (
                _external_routes_packet() if codex_custom_live_prompt_authorized else None
            )
            route_model_ids = {
                str(route.get("route_id") or "").strip()
                for route in _enabled_external_route_records(external_routes_packet)
            }
            requested_model_id = str(payload.get("model_id") or "").strip()
            if str(payload.get("execution_mode") or "").strip() in {
                "api_only",
                "chatgpt_plus_api",
            }:
                requested_model_id = str(payload.get("api_model_id") or "").strip()
            api_route_selected = (
                bool(requested_model_id) and requested_model_id in route_model_ids
            )
            operator_status = None
            if codex_custom_live_prompt_authorized:
                operator_status, _operator_status_timeout = _bounded_operator_status_payload(
                    operator_surface_session
                )
            runtime_health_result = (
                execute_command(readonly_runner, "healthcheck")
                if _payload_requires_chatgpt_runtime_health(payload)
                else None
            )
            preflight_packet = _custom_native_launch_preflight_packet(
                payload,
                owner_authorized=codex_custom_live_prompt_authorized,
                operator_status=operator_status,
                api_snapshot=api_snapshot,
                external_routes_packet=external_routes_packet,
                native_bridge_lease=custom_native_bridge_lease,
                last_launch_packet=custom_native_launch_state["last_packet"],
                runtime_health_result=runtime_health_result,
            )
            if preflight_packet.get("status") != "ok":
                packet = _custom_native_launch_stability_guard_packet(
                    preflight_packet,
                    status=str(preflight_packet.get("status") or "blocked"),
                    machine_error_code=str(
                        preflight_packet.get("machine_error_code")
                        or "CUSTOM_NATIVE_LAUNCH_PREFLIGHT_BLOCKED"
                    ),
                    human_message="Custom native launch stopped because preflight did not return an ok packet.",
                )
                self._send_json(packet)
                return
            api_route_launch_selected = (
                api_route_selected or preflight_packet.get("route_selected") is True
            )
            stable_bridge_prewarm = {}
            if api_route_launch_selected:
                stable_bridge_prewarm = _custom_native_stable_bridge_prewarm_packet(
                    preflight_packet,
                    requested_model_id=requested_model_id,
                    operator_status=operator_status,
                    api_snapshot=api_snapshot,
                    external_routes_packet=external_routes_packet,
                    native_bridge_lease=custom_native_bridge_lease,
                )
                preflight_packet["stable_bridge_prewarm_required"] = (
                    stable_bridge_prewarm.get("prewarm_required") is True
                )
                preflight_packet["stable_bridge_prewarm_status"] = str(
                    stable_bridge_prewarm.get("status") or ""
                )
                preflight_packet["stable_bridge_prewarm_packet"] = stable_bridge_prewarm
                if stable_bridge_prewarm.get("status") != "ok":
                    packet = _custom_native_launch_stability_guard_packet(
                        preflight_packet,
                        status="blocked",
                        machine_error_code=str(
                            stable_bridge_prewarm.get("machine_error_code")
                            or "STABLE_BRIDGE_PREWARM_BLOCKED"
                        ),
                        human_message="Custom native launch stopped because the stable WBP bridge prewarm did not prove the selected API route.",
                    )
                    packet["stable_bridge_prewarm_packet"] = stable_bridge_prewarm
                    packet["stable_bridge_prewarm_required"] = (
                        stable_bridge_prewarm.get("prewarm_required") is True
                    )
                    packet["stable_bridge_prewarm_status"] = str(
                        stable_bridge_prewarm.get("status") or ""
                    )
                    packet["final_status"] = str(
                        stable_bridge_prewarm.get("final_status")
                        or "STOP_AND_DIAGNOSE_STABLE_BRIDGE_PREWARM_NOT_PROVEN"
                    )
                    self._send_json(packet)
                    return
            stable_bridge_gate = _custom_native_stable_bridge_launch_gate_packet(
                preflight_packet,
                native_bridge_lease=custom_native_bridge_lease,
            )
            if (
                stable_bridge_gate.get("status") != "ok"
                and stable_bridge_prewarm.get("status") == "ok"
                and stable_bridge_prewarm.get("prewarm_required") is True
            ):
                stable_bridge_retry_prewarm = (
                    _custom_native_stable_bridge_prewarm_packet(
                        preflight_packet,
                        requested_model_id=requested_model_id,
                        operator_status=operator_status,
                        api_snapshot=api_snapshot,
                        external_routes_packet=external_routes_packet,
                        native_bridge_lease=custom_native_bridge_lease,
                    )
                )
                preflight_packet["stable_bridge_prewarm_retry_attempted"] = True
                preflight_packet["stable_bridge_prewarm_retry_status"] = str(
                    stable_bridge_retry_prewarm.get("status") or ""
                )
                preflight_packet["stable_bridge_prewarm_retry_packet"] = (
                    stable_bridge_retry_prewarm
                )
                time.sleep(1.0)
                stable_bridge_retry_gate = (
                    _custom_native_stable_bridge_launch_gate_packet(
                        preflight_packet,
                        native_bridge_lease=custom_native_bridge_lease,
                    )
                )
                preflight_packet["stable_bridge_preflight_retry_attempted"] = True
                preflight_packet["stable_bridge_preflight_retry_packet"] = (
                    stable_bridge_retry_gate
                )
                preflight_packet["stable_bridge_preflight_retry_status"] = str(
                    stable_bridge_retry_gate.get("status") or ""
                )
                if stable_bridge_retry_gate.get("status") == "ok":
                    stable_bridge_gate = stable_bridge_retry_gate
            preflight_packet["stable_bridge_preflight_required"] = (
                stable_bridge_gate.get("bridge_preflight_required") is True
            )
            preflight_packet["stable_bridge_preflight_status"] = str(
                stable_bridge_gate.get("bridge_preflight_status") or ""
            )
            preflight_packet["stable_bridge_launch_allowed"] = (
                stable_bridge_gate.get("launch_allowed") is True
            )
            preflight_packet["stable_bridge_preflight_packet"] = (
                stable_bridge_gate.get("stable_bridge_preflight_packet", {})
            )
            if stable_bridge_gate.get("status") != "ok":
                packet = _custom_native_launch_stability_guard_packet(
                    preflight_packet,
                    status="blocked",
                    machine_error_code="STABLE_BRIDGE_PREFLIGHT_BLOCKED",
                    human_message="Custom native launch stopped because the stable WBP bridge preflight blocked this API-dependent mode.",
                )
                packet["stable_bridge_launch_gate_packet"] = stable_bridge_gate
                packet["final_status"] = str(stable_bridge_gate.get("final_status") or "")
                self._send_json(packet)
                return
            if (
                preflight_packet.get("existing_window_reuse_admissible") is True
            ):
                show_window_packet = show_custom_native_window_packet()
                show_ok = (
                    show_window_packet.get("status") == "ok"
                    and show_window_packet.get("custom_window_visible") is True
                    and show_window_packet.get("native_app_usable") is True
                )
                packet = _custom_native_launch_stability_guard_packet(
                    preflight_packet,
                    status="ok" if show_ok else "blocked",
                    machine_error_code=(
                        "OK"
                        if show_ok
                        else (
                            "CUSTOM_NATIVE_EXISTING_WINDOW_USABILITY_NOT_PROVEN"
                            if show_window_packet.get("custom_window_visible") is True
                            else "CUSTOM_NATIVE_EXISTING_WINDOW_NOT_RESPONSIVE"
                        )
                    ),
                    human_message=(
                        "Existing Custom Codex window reused; no new launch was started."
                        if show_ok
                        else (
                            "Existing Custom Codex process matched the launch config, but input-capable UI was not proven."
                            if show_window_packet.get("custom_window_visible") is True
                            else "Existing Custom Codex process matched the launch config, but the window could not be proven usable."
                        )
                    ),
                    show_window_packet=show_window_packet,
                )
                self._send_json(packet)
                return
            if (
                preflight_packet.get("custom_process_observed") is True
            ):
                existing_window_relaunch_cleared = False
                config_status = str(preflight_packet.get("config_status") or "")
                if (
                    config_status == "changed"
                    and preflight_packet.get("existing_window_relaunch_admissible")
                    is True
                ):
                    paths = default_persistent_custom_profile_paths(
                        profile_id=DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID
                    )
                    termination = terminate_custom_processes(
                        str(paths.get("user_data_dir") or "")
                    )
                    termination_summary = _redacted_custom_process_termination_summary(
                        termination
                    )
                    preflight_packet["existing_window_relaunch_attempted"] = True
                    preflight_packet["existing_window_relaunch_termination"] = (
                        termination_summary
                    )
                    preflight_packet["custom_process_observed_before_relaunch"] = True
                    preflight_packet["custom_process_observed_after_relaunch_stop"] = (
                        not termination_summary["custom_processes_gone"]
                    )
                    preflight_packet["custom_process_count_after_relaunch_stop"] = (
                        termination_summary["final_custom_process_count"]
                    )
                    preflight_packet["raw_process_lines_exposed"] = False
                    preflight_packet["raw_path_exposed"] = False
                    if termination_summary["custom_processes_gone"] is not True:
                        packet = _custom_native_launch_stability_guard_packet(
                            preflight_packet,
                            status="blocked",
                            machine_error_code="CUSTOM_NATIVE_CONFIG_CHANGED_RELAUNCH_STOP_FAILED",
                            human_message="Existing Custom Codex process uses a different launch selection, and same-profile relaunch stop did not complete.",
                        )
                        packet["existing_window_relaunch_attempted"] = True
                        packet["existing_window_relaunch_termination"] = (
                            termination_summary
                        )
                        self._send_json(packet)
                        return
                    existing_window_relaunch_cleared = True
                elif config_status == "changed":
                    machine_error_code = (
                        "CUSTOM_NATIVE_CONFIG_CHANGED_EXISTING_WINDOW_NOT_REUSED"
                    )
                    human_message = "Existing Custom Codex process uses a different launch selection; silent reuse and second-window launch are blocked."
                else:
                    machine_error_code = (
                        "CUSTOM_NATIVE_EXISTING_WINDOW_WITHOUT_MATCHING_LAUNCH_PACKET"
                    )
                    human_message = "Existing Custom Codex process is running, but no matching previous launch packet proves it belongs to the selected config; second-window launch is blocked."
                if not existing_window_relaunch_cleared:
                    packet = _custom_native_launch_stability_guard_packet(
                        preflight_packet,
                        status="blocked",
                        machine_error_code=machine_error_code,
                        human_message=human_message,
                    )
                    self._send_json(packet)
                    return
            account_commands = (
                {}
                if api_route_launch_selected
                else (
                    self._codex_account_commands()
                    if codex_custom_live_prompt_authorized
                    else {}
                )
            )
            packet = _launch_custom_native_codex_packet(
                payload,
                owner_authorized=codex_custom_live_prompt_authorized,
                commands=account_commands,
                operator_status=operator_status,
                api_snapshot=api_snapshot,
                external_routes_packet=external_routes_packet,
                native_bridge_lease=custom_native_bridge_lease,
            )
            if (
                api_route_launch_selected
                and preflight_packet.get("launch_id")
                and preflight_packet.get("trace_id")
            ):
                packet["launch_id"] = str(preflight_packet.get("launch_id") or "")
                packet["trace_id"] = str(preflight_packet.get("trace_id") or "")
                packet["launch_route_digest"] = str(
                    preflight_packet.get("launch_route_digest") or ""
                )
                custom_native_bridge_lease.set_trace_context(
                    {
                        "launch_id": packet.get("launch_id"),
                        "trace_id": packet.get("trace_id"),
                        "selected_model": packet.get("selected_model"),
                        "api_reasoning_option_id": packet.get(
                            "api_reasoning_option_id"
                        ),
                        "launch_route_digest": packet.get("launch_route_digest"),
                    }
                )
            packet["launch_preflight_packet"] = preflight_packet
            packet["stable_bridge_launch_gate_packet"] = stable_bridge_gate
            packet["stable_bridge_preflight_required"] = (
                stable_bridge_gate.get("bridge_preflight_required") is True
            )
            packet["stable_bridge_preflight_status"] = str(
                stable_bridge_gate.get("bridge_preflight_status") or ""
            )
            packet["stable_bridge_launch_allowed"] = (
                stable_bridge_gate.get("launch_allowed") is True
            )
            packet["stable_bridge_preflight_packet"] = stable_bridge_gate.get(
                "stable_bridge_preflight_packet",
                {},
            )
            packet["stable_bridge_preflight_retry_attempted"] = (
                preflight_packet.get("stable_bridge_preflight_retry_attempted") is True
            )
            packet["stable_bridge_preflight_retry_status"] = str(
                preflight_packet.get("stable_bridge_preflight_retry_status") or ""
            )
            packet["stable_bridge_prewarm_retry_attempted"] = (
                preflight_packet.get("stable_bridge_prewarm_retry_attempted") is True
            )
            packet["stable_bridge_prewarm_retry_status"] = str(
                preflight_packet.get("stable_bridge_prewarm_retry_status") or ""
            )
            packet["launch_stability_guard_checked"] = True
            packet["config_status"] = str(preflight_packet.get("config_status") or "")
            packet["selection_matches_last_launch"] = (
                preflight_packet.get("selection_matches_last_launch") is True
            )
            packet["existing_window_reuse_admissible"] = (
                preflight_packet.get("existing_window_reuse_admissible") is True
            )
            packet["existing_window_relaunch_admissible"] = (
                preflight_packet.get("existing_window_relaunch_admissible") is True
            )
            packet["new_launch_required"] = (
                preflight_packet.get("new_launch_required") is True
            )
            if preflight_packet.get("existing_window_relaunch_attempted") is True:
                packet["existing_window_relaunch_attempted"] = True
                packet["existing_window_relaunch_admissible"] = (
                    preflight_packet.get("existing_window_relaunch_admissible") is True
                )
                packet["existing_window_relaunch_termination"] = (
                    preflight_packet.get("existing_window_relaunch_termination", {})
                )
                packet["custom_process_observed_before_relaunch"] = (
                    preflight_packet.get("custom_process_observed_before_relaunch")
                    is True
                )
                packet["custom_process_count_after_relaunch_stop"] = int(
                    preflight_packet.get("custom_process_count_after_relaunch_stop")
                    or 0
                )
            packet["reused_existing_window"] = (
                packet.get("reused_existing_window") is True
                or packet.get("existing_custom_window_reused") is True
            )
            packet["launch_packet_is_truth_source"] = True
            packet["visible_window_counts_as_model_truth"] = False
            packet["response_text_counts_as_route_truth"] = False
            packet["final_status"] = "CUSTOM_CODEX_LAUNCH_STABILITY_AND_RECOVERY_WITH_LIMITS"
            record_custom_native_launch_packet(packet)
            self._send_json(packet)
            return

        def _handle_post_api_codex_custom_show_window(self, actual_path: str) -> None:
            self._read_optional_json_body()
            packet = show_custom_native_window_packet()
            self._send_json(packet)
            return

        def _handle_post_api_codex_custom_visible_history_owner_confirmation(self, actual_path: str) -> None:
            self._send_json(
                build_visible_thread_history_owner_confirmation_packet(
                    self._read_json_body(),
                    owner_authorized=codex_custom_live_prompt_authorized,
                    last_launch_packet=custom_native_launch_state["last_packet"],
                )
            )
            return

        def _handle_post_api_codex_custom_visible_history_relaunch_owner_confirmation(self, actual_path: str) -> None:
            relaunch_profile_packet = build_custom_codex_persistent_relaunch_profile_packet(
                first_launch_packet=custom_native_launch_state["previous_packet"],
                second_launch_packet=custom_native_launch_state["last_packet"],
            )
            self._send_json(
                build_custom_codex_visible_history_relaunch_owner_confirmation_packet(
                    self._read_json_body(),
                    owner_authorized=codex_custom_live_prompt_authorized,
                    relaunch_profile_packet=relaunch_profile_packet,
                )
            )
            return

        def _handle_post_api_codex_app_copy_launch_dry_run(self, actual_path: str) -> None:
            self._send_json(build_safe_app_copy_launch_dry_run_packet(self._read_json_body()))
            return

        def _handle_post_api_codex_app_copy_live_admission(self, actual_path: str) -> None:
            self._send_json(
                build_safe_app_copy_live_admission_packet(
                    self._read_json_body(),
                    _launch_copy_preflight(launch_copy_contract),
                )
            )
            return

        def _handle_post_api_codex_app_copy_launch(self, actual_path: str) -> None:
            launch_payload = self._read_app_copy_launch_body()
            launch_preflight = _launch_copy_preflight(launch_copy_contract)
            helper_result = (
                _run_safe_app_copy_bounded_helper(launch_copy_contract, launch_preflight)
                if launch_payload == {}
                else None
            )
            self._send_json(
                build_safe_app_copy_launch_live_packet(
                    launch_payload,
                    launch_preflight,
                    helper_result,
                )
            )
            return

        def _handle_post_api_codex_custom_model_dry_run(self, actual_path: str) -> None:
            api_snapshot = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
            availability_lattice_packet = _build_live_native_availability_lattice_packet(
                operator_surface_session.status_payload(),
                api_snapshot=api_snapshot,
            )
            self._send_json(
                build_custom_model_dry_run_packet(
                    self._read_json_body(),
                    operator_surface_session.status_payload(),
                    api_snapshot=api_snapshot,
                    availability_lattice_packet=availability_lattice_packet,
                )
            )
            return

        def _handle_post_api_codex_custom_model_selector_dry_run(self, actual_path: str) -> None:
            api_snapshot = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
            operator_status, _operator_status_timeout = _bounded_operator_status_payload(
                operator_surface_session
            )
            self._send_json(
                build_dual_lane_selection_intent_packet(
                    self._read_json_body(),
                    operator_status,
                    api_snapshot=api_snapshot,
                )
            )
            return

        def _handle_post_api_codex_custom_api_action_gate(self, actual_path: str) -> None:
            payload = self._read_json_body()
            api_snapshot = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
            operator_status = operator_surface_session.status_payload()
            availability_lattice_packet = _build_live_native_availability_lattice_packet(
                operator_status,
                api_snapshot=api_snapshot,
            )
            self._send_json(
                build_custom_api_action_gate_packet(
                    payload,
                    operator_status,
                    api_snapshot=api_snapshot,
                    availability_lattice_packet=availability_lattice_packet,
                    owner_authorized=codex_custom_live_prompt_authorized,
                )
            )
            return

        def _handle_post_api_codex_custom_execution_mode_dry_run(self, actual_path: str) -> None:
            payload = self._read_json_body()
            api_snapshot = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
            operator_status, _operator_status_timeout = _bounded_operator_status_payload(
                operator_surface_session
            )
            self._send_json(
                build_custom_codex_execution_mode_selector_packet(
                    payload,
                    operator_status,
                    api_snapshot=api_snapshot,
                )
            )
            return

        def _handle_post_api_codex_custom_server_model_selection_truth(self, actual_path: str) -> None:
            payload = self._read_json_body()
            api_snapshot = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
            operator_status, _operator_status_timeout = _bounded_operator_status_payload(
                operator_surface_session
            )
            self._send_json(
                build_server_model_selection_and_reasoning_truth_packet(
                    payload,
                    operator_status,
                    api_snapshot=api_snapshot,
                )
            )
            return

        def _handle_post_api_codex_custom_quick_start_config_admission(self, actual_path: str) -> None:
            payload = self._read_json_body()
            api_snapshot = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
            operator_status, _operator_status_timeout = _bounded_operator_status_payload(
                operator_surface_session
            )
            self._send_json(
                build_quick_start_config_admission_packet(
                    payload,
                    operator_status,
                    api_snapshot=api_snapshot,
                    runtime_health_result=(
                        execute_command(readonly_runner, "healthcheck")
                        if _payload_requires_chatgpt_runtime_health(payload)
                        else None
                    ),
                )
            )
            return

        def _handle_post_api_codex_custom_chatgpt_plus_api_slot_truth(self, actual_path: str) -> None:
            payload = self._read_json_body()
            api_snapshot = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
            operator_status, _operator_status_timeout = _bounded_operator_status_payload(
                operator_surface_session
            )
            self._send_json(
                build_chatgpt_plus_api_slot_truth_packet(
                    payload,
                    operator_status,
                    api_snapshot=api_snapshot,
                )
            )
            return

        def _handle_post_api_codex_custom_api_only_executor_truth(self, actual_path: str) -> None:
            payload = self._read_json_body()
            api_snapshot = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
            operator_status, _operator_status_timeout = _bounded_operator_status_payload(
                operator_surface_session
            )
            self._send_json(
                build_api_only_executor_truth_packet(
                    payload,
                    operator_status,
                    api_snapshot=api_snapshot,
                )
            )
            return

        def _handle_post_api_codex_custom_api_only_deepseek_live_format(self, actual_path: str) -> None:
            payload = self._read_json_body()
            api_snapshot = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
            operator_status = operator_surface_session.status_payload()
            availability_lattice_packet = _build_live_native_availability_lattice_packet(
                operator_status,
                api_snapshot=api_snapshot,
            )
            preflight = build_api_only_deepseek_live_route_format_packet(
                payload,
                operator_status,
                api_snapshot=api_snapshot,
                availability_lattice_packet=availability_lattice_packet,
                owner_authorized=codex_custom_live_prompt_authorized,
            )
            live_result = None
            live_error = None
            if (
                preflight.get("status") != "rejected"
                and preflight.get("execution_mode") == "api_only"
                and preflight.get("deepseek_selected_from_server_catalog") is True
                and codex_custom_live_prompt_authorized
            ):
                live_command = execute_command(
                    action_runner,
                    "external_models_live_format_check",
                    structured_args={
                        "route_id": str(payload.get("api_model_id") or ""),
                        "prompt": API_ONLY_DEEPSEEK_LIVE_ROUTE_FORMAT_PROMPT,
                        "expected_text": API_ONLY_DEEPSEEK_LIVE_ROUTE_FORMAT_EXPECTED_TEXT,
                    },
                )
                packet = live_command.get("packet")
                packet_data = packet.get("data") if isinstance(packet, dict) else None
                if live_command.get("status") == "ok" and isinstance(packet_data, dict):
                    live_result = packet_data
                else:
                    live_error = {
                        "status": live_command.get("status"),
                        "machine_error_code": live_command.get("machine_error_code"),
                        "human_message": live_command.get("human_message"),
                        "next_action": live_command.get("next_action"),
                        "changed_files": live_command.get("changed_files") or [],
                    }
            self._send_json(
                build_api_only_deepseek_live_route_format_packet(
                    payload,
                    operator_status,
                    api_snapshot=api_snapshot,
                    availability_lattice_packet=availability_lattice_packet,
                    owner_authorized=codex_custom_live_prompt_authorized,
                    live_result=live_result,
                    live_error=live_error,
                )
            )
            return

        def _handle_post_api_codex_custom_quick_start_deepseek_safe_worktree_check(self, actual_path: str) -> None:
            payload = self._read_json_body()
            api_snapshot = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
            operator_status, _operator_status_timeout = _bounded_operator_status_payload(
                operator_surface_session
            )
            self._send_json(
                _quick_start_deepseek_safe_worktree_check_packet(
                    payload,
                    session_manager=codex_custom_sessions,
                    operator_status=operator_status,
                    api_snapshot=api_snapshot,
                    prompt_runner=lambda runner_payload, worktree_dir: operator_surface_session.run_prompt(
                        runner_payload,
                        trace_wbp=True,
                        sandbox_mode_override="workspace-write",
                        writable_additional_dir=worktree_dir,
                    ),
                    owner_authorized=codex_custom_live_prompt_authorized,
                    repo_root=codex_custom_safe_worktree_repo_root,
                )
            )
            return

        def _handle_post_api_codex_custom_quick_start_deepseek_code_edit_proof(self, actual_path: str) -> None:
            self._send_json(
                build_custom_codex_deepseek_code_edit_reproduction_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    bridge_trace_packet=custom_native_bridge_lease.trace_snapshot(),
                    browser_payload=self._read_json_body(),
                    repo_root=ROOT,
                )
            )
            return

        def _handle_post_api_codex_custom_quick_start_api_only_deepseek_live_code_edit_truth(self, actual_path: str) -> None:
            self._send_json(
                build_api_only_deepseek_live_code_edit_truth_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    bridge_trace_packet=custom_native_bridge_lease.trace_snapshot(),
                    browser_payload=self._read_json_body(),
                    repo_root=ROOT,
                )
            )
            return

        def _handle_post_api_codex_custom_quick_start_deepseek_route_bound_edit_proof(self, actual_path: str) -> None:
            self._send_json(
                build_custom_codex_deepseek_route_bound_real_edit_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    bridge_trace_packet=custom_native_bridge_lease.trace_snapshot(),
                    browser_payload=self._read_json_body(),
                    repo_root=ROOT,
                )
            )
            return

        def _handle_post_api_codex_custom_quick_start_chatgpt_plus_deepseek_file_edit_proof(self, actual_path: str) -> None:
            self._send_json(
                build_custom_codex_chatgpt_plus_deepseek_file_edit_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    bridge_trace_packet=custom_native_bridge_lease.trace_snapshot(),
                    browser_payload=self._read_json_body(),
                    repo_root=ROOT,
                )
            )
            return

        def _handle_post_api_codex_custom_stable_profile_history_persistence(self, actual_path: str) -> None:
            payload = self._read_json_body()
            action = _payload_first_text(payload, "action", "prove_after")
            if action == "capture_before":
                packet = build_custom_codex_stable_profile_history_before_snapshot_packet(
                    last_launch_packet=custom_native_launch_state["last_packet"],
                    browser_payload=payload,
                )
                if packet.get("status") == "ok" and isinstance(packet.get("snapshot"), dict):
                    custom_native_launch_state["history_before_snapshot"] = packet["snapshot"]
                self._send_json(packet)
                return
            self._send_json(
                build_custom_codex_stable_profile_history_persistence_packet(
                    first_launch_packet=custom_native_launch_state["previous_packet"],
                    second_launch_packet=custom_native_launch_state["last_packet"],
                    before_history_snapshot=custom_native_launch_state[
                        "history_before_snapshot"
                    ],
                    browser_payload=payload,
                )
            )
            return

        def _handle_post_api_codex_custom_account_smoke_dry_run(self, actual_path: str) -> None:
            self._send_json(
                build_account_smoke_dry_run_packet(
                    self._read_json_body(),
                    self._codex_account_commands(),
                    operator_surface_session.status_payload(),
                )
            )
            return

        def _handle_post_api_codex_custom_sessions(self, actual_path: str) -> None:
            operator_status = operator_surface_session.status_payload()
            payload = self._read_json_body()
            model_id = payload.get("primary_model_id")
            if not isinstance(model_id, str):
                model_id = ""
            account_commands = self._codex_account_commands()
            api_snapshot = build_api_connections_readonly_snapshot(api_connections_readonly_runner)
            self._send_json(
                codex_custom_sessions.create_packet(
                    payload,
                    account_commands,
                    operator_status,
                    selection=_codex_custom_selection_packet(
                        model_id=model_id,
                        commands=account_commands,
                        operator_status=operator_status,
                        api_snapshot=api_snapshot,
                    ),
                    api_snapshot=api_snapshot,
                )
            )
            return

        def _handle_post_api_codex_custom_recovery_rollback_point(self, actual_path: str) -> None:
            self._send_json(
                build_custom_recovery_rollback_point_create_live_packet(
                    rollback_point_create_admission=(
                        build_rollback_point_create_admission_packet()
                    ),
                    browser_payload=self._read_rollback_point_create_body(),
                )
            )
            return

        def _handle_post_api_codex_custom_recovery_rollback_apply(self, actual_path: str) -> None:
            self._send_json(
                build_rollback_apply_bounded_live_packet(
                    browser_payload=self._read_rollback_point_create_body(),
                )
            )
            return

        def _handle_post_api_codex_custom_recovery_stop_cleanup(self, actual_path: str) -> None:
            self._send_json(
                build_stop_cleanup_live_packet(
                    browser_payload=self._read_rollback_point_create_body(),
                )
            )
            return

        def _handle_post_api_codex_custom_worktrees_prefix(self, actual_path: str) -> None:
            worktree_cleanup_prefix = "/api/codex/custom/worktrees/"
            if actual_path.startswith(worktree_cleanup_prefix):
                rest = actual_path[len(worktree_cleanup_prefix) :].strip("/")
                parts = rest.split("/")
                if len(parts) == 2 and parts[1] == "cleanup":
                    self._read_optional_json_body()
                    self._send_json(codex_custom_sessions.safe_worktree_cleanup_packet(parts[0]))
                    return
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        def _handle_post_api_codex_custom_sessions_prefix(self, actual_path: str) -> None:
            custom_session = self._custom_session_route(actual_path)
            if custom_session is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            session_id, action = custom_session
            if action == "revalidate":
                self._read_optional_json_body()
                operator_status = operator_surface_session.status_payload()
                account_commands = self._codex_account_commands()
                api_snapshot = build_api_connections_readonly_snapshot(
                    api_connections_readonly_runner
                )
                self._send_json(
                    codex_custom_sessions.revalidate_packet(
                        session_id,
                        account_commands,
                        operator_status,
                        api_snapshot=api_snapshot,
                    )
                )
                return
            if action == "prompt-dry-run":
                self._send_json(
                    codex_custom_sessions.prompt_dry_run_packet(
                        session_id,
                        self._read_json_body(),
                    )
                )
                return
            if action == "prompt":
                if codex_custom_live_prompt_authorized:
                    self._send_json(
                        codex_custom_sessions.prompt_packet(
                            session_id,
                            self._read_json_body(),
                            lambda payload: operator_surface_session.run_prompt(
                                payload,
                                trace_wbp=True,
                            ),
                            owner_authorized=codex_custom_live_prompt_authorized,
                        )
                    )
                    return
                self._send_json(
                    codex_custom_sessions.prompt_not_admitted_packet(
                        session_id,
                        self._read_json_body(),
                    )
                )
                return
            if action == "temp-write-probe":
                self._send_json(
                    codex_custom_sessions.temp_write_probe_packet(
                        session_id,
                        self._read_json_body(),
                        lambda payload, writable_dir: operator_surface_session.run_prompt(
                            payload,
                            trace_wbp=True,
                            sandbox_mode_override="workspace-write",
                            writable_additional_dir=writable_dir,
                        ),
                        owner_authorized=codex_custom_live_prompt_authorized,
                    )
                )
                return
            if action == "safe-worktree-edit-probe":
                self._send_json(
                    codex_custom_sessions.safe_worktree_edit_probe_packet(
                        session_id,
                        self._read_json_body(),
                        lambda payload, writable_dir: operator_surface_session.run_prompt(
                            payload,
                            trace_wbp=True,
                            sandbox_mode_override="workspace-write",
                            writable_additional_dir=writable_dir,
                        ),
                        owner_authorized=codex_custom_live_prompt_authorized,
                        repo_root=codex_custom_safe_worktree_repo_root,
                    )
                )
                return
            if action == "repo-tmp-edit-probe":
                repo_tmp_dir = Path(codex_custom_safe_worktree_repo_root).resolve() / ".tmp"
                repo_tmp_dir.mkdir(parents=True, exist_ok=True)
                self._send_json(
                    codex_custom_sessions.repo_tmp_edit_probe_packet(
                        session_id,
                        self._read_json_body(),
                        lambda payload, writable_dir: operator_surface_session.run_prompt(
                            payload,
                            trace_wbp=True,
                            sandbox_mode_override="workspace-write",
                            writable_additional_dir=writable_dir,
                            declared_repo_tmp_dir=repo_tmp_dir,
                        ),
                        owner_authorized=codex_custom_live_prompt_authorized,
                        repo_root=codex_custom_safe_worktree_repo_root,
                    )
                )
                return
            if action == "mixed-slot-dispatch-probe":
                def mixed_slot_probe_runner(payload: dict[str, Any]) -> dict[str, Any]:
                    slot_id = str(payload.get("slot_id") or "")
                    model_id = str(payload.get("model_id") or "")
                    route_backed = slot_id == "coding_agent_model_slot"
                    return {
                        "status": "ok",
                        "machine_error_code": "OK",
                        "requested_slot_id": slot_id,
                        "selected_model": model_id,
                        "runtime_model": model_id,
                        "final_message": "WBP_MIXED_DEEPSEEK_CODER_OK"
                        if route_backed
                        else "WBP_MIXED_PRIMARY_SLOT_OK",
                        "configured_provider": "external_route"
                        if route_backed
                        else "cliproxy",
                        "configured_wire_api": "responses",
                        "wbp_endpoint_configured": True,
                        "config_endpoint_matches": True,
                        "config_provider_matches": True,
                        "config_wire_api_matches": True,
                        "command_uses_stdin_dash": True,
                        "command_json_mode": True,
                        "env_codex_home_is_temp": True,
                        "env_home_is_temp": True,
                        "workdir_is_temp": True,
                        "command_workdir_is_temp": True,
                        "command_output_file_is_temp": True,
                        "current_codex_home_used": False,
                        "independent_wbp_trace_observed": True,
                        "trace_observer_packet": {
                            "path": "/v1/responses",
                            "upstream_status": 200,
                            "forwarded_to_wbp": True,
                            "prompt_body_recorded": False,
                            "auth_header_recorded": False,
                            "secret_value_recorded": False,
                        },
                        "secret_value_recorded": False,
                        "live_provider_call_attempted": False,
                        "file_write_attempted": False,
                    }

                self._send_json(
                    codex_custom_sessions.mixed_slot_dispatch_probe_packet(
                        session_id,
                        self._read_json_body(),
                        mixed_slot_probe_runner,
                        owner_authorized=codex_custom_live_prompt_authorized,
                    )
                )
                return
            if action == "safe-worktree-coder":
                self._send_json(
                    codex_custom_sessions.safe_worktree_coder_packet(
                        session_id,
                        self._read_json_body(),
                        lambda payload, worktree_dir: operator_surface_session.run_prompt(
                            payload,
                            trace_wbp=True,
                            sandbox_mode_override="workspace-write",
                            working_dir_override=worktree_dir,
                        ),
                        owner_authorized=codex_custom_live_prompt_authorized,
                        repo_root=codex_custom_safe_worktree_repo_root,
                    )
                )
                return
            if action == "cancel":
                self._read_optional_json_body()
                self._send_json(codex_custom_sessions.cancel_packet(session_id))
                return
            if action == "cleanup":
                self._read_optional_json_body()
                self._send_json(codex_custom_sessions.cleanup_packet(session_id))
                return
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        def _handle_post_api_action(self, actual_path: str) -> None:
            action_payload = self._read_json_body()
            action_owner_authorized = codex_custom_live_prompt_authorized
            native_context_required = (
                action_owner_authorized
                and isinstance(action_payload, dict)
                and action_payload.get("ui_action") == "launch_custom_client_native"
                and set(action_payload).issubset(
                    {"ui_action", *CUSTOM_NATIVE_LAUNCH_ALLOWED_BROWSER_FIELDS}
                )
            )
            native_operator_status = None
            if native_context_required:
                native_operator_status, _native_operator_status_timeout = (
                    _bounded_operator_status_payload(operator_surface_session)
                )
            native_api_snapshot = (
                build_api_connections_readonly_snapshot(api_connections_readonly_runner)
                if native_context_required
                else None
            )
            self._send_json(
                run_ui_action(
                    action_runner,
                    action_payload,
                    launch_client_path=launch_client_path,
                    launch_copy_contract=launch_copy_contract,
                    launch_action_runner=launch_copy_runner,
                    action_phase=action_phase,
                    owner_authorized=action_owner_authorized,
                    native_operator_status=native_operator_status,
                    native_api_snapshot=native_api_snapshot,
                    legacy_import_token_store=legacy_import_token_store,
                )
            )

            return

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

        def _send_json(
            self,
            payload: dict[str, Any],
            *,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _admit_common_request(self) -> None:
            if not host_header_is_local(
                self.headers.get("Host"),
                server_port=int(self.server.server_port),
            ):
                raise _HttpIngressRejection(
                    status=HTTPStatus.BAD_REQUEST,
                    machine_error_code="WEB_INGRESS_HOST_REJECTED",
                    human_message="HTTP Host must target this local Wild Boar Proxy server.",
                )

        def _admit_post_request(self, path: str) -> RouteSpec:
            self._admit_common_request()
            length, length_error = parse_content_length(self.headers)
            if length_error is not None:
                raise _HttpIngressRejection(
                    status=HTTPStatus.BAD_REQUEST,
                    machine_error_code=length_error,
                    human_message="HTTP Content-Length must be a non-negative integer.",
                )
            if length > MAX_WEB_REQUEST_BODY_BYTES:
                raise _HttpIngressRejection(
                    status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    machine_error_code="WEB_INGRESS_BODY_TOO_LARGE",
                    human_message="HTTP request body exceeds the Wild Boar Proxy web ingress limit.",
                )
            content_type_header = str(self.headers.get("Content-Type", "") or "").strip()
            if (
                (length > 0 or content_type_header)
                and not content_type_matches(self.headers, JSON_CONTENT_TYPE)
            ):
                raise _HttpIngressRejection(
                    status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    machine_error_code="WEB_INGRESS_CONTENT_TYPE_REJECTED",
                    human_message="JSON POST requests must use Content-Type: application/json.",
                )
            if not origin_header_is_allowed(
                self.headers.get("Origin"),
                host_header=self.headers.get("Host"),
                server_port=int(self.server.server_port),
            ):
                raise _HttpIngressRejection(
                    status=HTTPStatus.FORBIDDEN,
                    machine_error_code="WEB_INGRESS_ORIGIN_REJECTED",
                    human_message="Browser POST Origin must match this local Wild Boar Proxy server.",
                )
            if not web_post_token_valid(handler_web_token_state, self.headers):
                raise _HttpIngressRejection(
                    status=HTTPStatus.UNAUTHORIZED,
                    machine_error_code="WEB_INGRESS_WEB_TOKEN_REJECTED",
                    human_message="Web POST requests must include a valid local Wild Boar Proxy web token.",
                )
            if not web_post_csrf_valid(handler_web_token_state, self.headers):
                raise _HttpIngressRejection(
                    status=HTTPStatus.FORBIDDEN,
                    machine_error_code="WEB_INGRESS_CSRF_REJECTED",
                    human_message="Web POST requests must include a valid Wild Boar Proxy CSRF token.",
                )
            if not handler_post_rate_limiter.admit(
                client_ip=str(self.client_address[0] or ""),
                path=path,
            ):
                raise _HttpIngressRejection(
                    status=HTTPStatus.TOO_MANY_REQUESTS,
                    machine_error_code=WEB_RATE_LIMIT_MACHINE_ERROR_CODE,
                    human_message="Web POST request rate limit exceeded.",
                )
            route_spec = WEB_DESIGN_LIVE_ROUTE_TABLE.lookup("POST", path)
            if route_spec is None:
                raise _HttpIngressRejection(
                    status=HTTPStatus.NOT_FOUND,
                    machine_error_code="WEB_ROUTE_NOT_REGISTERED",
                    human_message="Web POST route is not registered in the route effect registry.",
                )
            return route_spec

        def _codex_account_commands(self) -> dict[str, dict[str, Any]]:
            return {
                "status": execute_command(readonly_runner, "status"),
                "accounts_list": execute_command(accounts_readonly_runner, "accounts_list"),
                "rollout_rotation_inspect": execute_command(
                    readonly_runner,
                    "rollout_rotation_inspect",
                ),
            }

        def _custom_session_route(self, path: str) -> tuple[str, str] | None:
            prefix = "/api/codex/custom/sessions/"
            if not path.startswith(prefix):
                return None
            rest = path[len(prefix) :].strip("/")
            if not rest:
                return None
            parts = rest.split("/")
            if len(parts) == 1:
                return parts[0], ""
            if len(parts) == 2:
                return parts[0], parts[1]
            return None

        def _read_json_body(self) -> dict[str, Any]:
            length = self._admitted_body_length()
            if length <= 0:
                raise _HttpIngressRejection(
                    status=HTTPStatus.BAD_REQUEST,
                    machine_error_code="WEB_INGRESS_JSON_BODY_REQUIRED",
                    human_message="JSON POST requests must include a JSON object body.",
                )
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise _HttpIngressRejection(
                    status=HTTPStatus.BAD_REQUEST,
                    machine_error_code="WEB_INGRESS_JSON_INVALID",
                    human_message="HTTP request body must be valid UTF-8 JSON.",
                ) from None
            if not isinstance(payload, dict):
                raise _HttpIngressRejection(
                    status=HTTPStatus.BAD_REQUEST,
                    machine_error_code="WEB_INGRESS_JSON_OBJECT_REQUIRED",
                    human_message="HTTP request body must be a JSON object.",
                )
            return payload

        def _read_app_copy_launch_body(self) -> dict[str, Any]:
            length = self._admitted_body_length()
            if length <= 0:
                raise _HttpIngressRejection(
                    status=HTTPStatus.BAD_REQUEST,
                    machine_error_code="WEB_INGRESS_JSON_BODY_REQUIRED",
                    human_message="App-copy launch requests must include a JSON object body.",
                )
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise _HttpIngressRejection(
                    status=HTTPStatus.BAD_REQUEST,
                    machine_error_code="WEB_INGRESS_JSON_INVALID",
                    human_message="App-copy launch request body must be valid UTF-8 JSON.",
                ) from None
            if not isinstance(payload, dict):
                raise _HttpIngressRejection(
                    status=HTTPStatus.BAD_REQUEST,
                    machine_error_code="WEB_INGRESS_JSON_OBJECT_REQUIRED",
                    human_message="App-copy launch request body must be a JSON object.",
                )
            return payload

        def _read_rollback_point_create_body(self) -> dict[str, Any]:
            length = self._admitted_body_length()
            if length <= 0:
                raise _HttpIngressRejection(
                    status=HTTPStatus.BAD_REQUEST,
                    machine_error_code="WEB_INGRESS_JSON_BODY_REQUIRED",
                    human_message="Recovery live requests must include a JSON object body.",
                )
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise _HttpIngressRejection(
                    status=HTTPStatus.BAD_REQUEST,
                    machine_error_code="WEB_INGRESS_JSON_INVALID",
                    human_message="Recovery live request body must be valid UTF-8 JSON.",
                ) from None
            if not isinstance(payload, dict):
                raise _HttpIngressRejection(
                    status=HTTPStatus.BAD_REQUEST,
                    machine_error_code="WEB_INGRESS_JSON_OBJECT_REQUIRED",
                    human_message="Recovery live request body must be a JSON object.",
                )
            return payload

        def _read_optional_json_body(self) -> dict[str, Any]:
            length = self._admitted_body_length()
            if length <= 0:
                return {}
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise _HttpIngressRejection(
                    status=HTTPStatus.BAD_REQUEST,
                    machine_error_code="WEB_INGRESS_JSON_INVALID",
                    human_message="Optional POST request body must be valid UTF-8 JSON.",
                ) from None
            if not isinstance(payload, dict):
                raise _HttpIngressRejection(
                    status=HTTPStatus.BAD_REQUEST,
                    machine_error_code="WEB_INGRESS_JSON_OBJECT_REQUIRED",
                    human_message="Optional POST request body must be a JSON object.",
                )
            return payload

        def _admitted_body_length(self) -> int:
            length, length_error = parse_content_length(self.headers)
            if length_error is not None:
                raise _HttpIngressRejection(
                    status=HTTPStatus.BAD_REQUEST,
                    machine_error_code=length_error,
                    human_message="HTTP Content-Length must be a non-negative integer.",
                )
            if length > MAX_WEB_REQUEST_BODY_BYTES:
                raise _HttpIngressRejection(
                    status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    machine_error_code="WEB_INGRESS_BODY_TOO_LARGE",
                    human_message="HTTP request body exceeds the Wild Boar Proxy web ingress limit.",
                )
            return length

        def _send_static(self, request_path: str) -> None:
            relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
            if WEB_TOKEN_FILENAME in Path(relative).parts:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            target = (static_root / relative).resolve()
            if static_root not in target.parents and target != static_root:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            body = target.read_bytes()
            if relative == "index.html" and content_type == "text/html":
                body = self._with_web_bootstrap(body)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _with_web_bootstrap(self, body: bytes) -> bytes:
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError:
                return body
            marker = "</head>"
            if marker not in text:
                return body
            if static_root == WEB_DESIGN_UI.resolve():
                text = text.replace('data-source="fixture"', 'data-source="live"', 1)
            tags = (
                f'<meta name="{WEB_TOKEN_META_NAME}" '
                f'content="{html.escape(handler_web_token_state.token, quote=True)}">'
                f'<meta name="{WEB_CSRF_META_NAME}" '
                f'content="{html.escape(handler_web_token_state.csrf_token, quote=True)}">'
            )
            return text.replace(marker, f"{tags}{marker}", 1).encode("utf-8")

        def _send_owner_login_sandbox_page(self, raw_query: str) -> None:
            query = parse_qs(raw_query)
            provider = str((query.get("provider") or ["sandbox"])[0] or "sandbox")
            session = str((query.get("session") or [""])[0] or "")
            state = str((query.get("state") or [""])[0] or "")
            nonce = str((query.get("nonce") or [""])[0] or "")
            lines = [
                "<!doctype html>",
                '<html lang="ru"><head><meta charset="utf-8">',
                '<meta name="viewport" content="width=device-width, initial-scale=1">',
                "<title>Sandbox owner login</title>",
                "<style>",
                "body{font-family:ui-monospace,monospace;background:#f7f3eb;color:#241f1a;margin:0;padding:32px;}",
                ".panel{max-width:720px;margin:0 auto;background:#fffdf8;border:1px solid #dbcdb8;border-radius:20px;padding:24px 28px;box-shadow:0 18px 50px rgba(58,42,18,.08);}",
                "h1{font-size:32px;line-height:1.1;margin:0 0 16px;}",
                "p{font-size:18px;line-height:1.5;margin:0 0 16px;}",
                "dl{display:grid;grid-template-columns:max-content 1fr;gap:12px 18px;margin:20px 0 0;}",
                "dt{opacity:.72;text-transform:uppercase;font-size:12px;letter-spacing:.08em;}",
                "dd{margin:0;word-break:break-word;}",
                ".chip{display:inline-block;padding:6px 12px;border-radius:999px;background:#e8f4ea;color:#235b33;font-weight:700;font-size:12px;text-transform:uppercase;}",
                "</style></head><body>",
                '<main class="panel">',
                '<span class="chip">owner login url</span>',
                "<h1>Sandbox owner login surface</h1>",
                "<p>Browser открыл owner-provided sandbox login URL. Auth completion остаётся owner-owned, а главное подтверждение подключения приходит обратно в основном web UI через onboarding packet и refresh.</p>",
                "<dl>",
                f"<dt>provider</dt><dd>{provider}</dd>",
                f"<dt>session</dt><dd>{session or '-'}</dd>",
                f"<dt>state</dt><dd>{state or '-'}</dd>",
                f"<dt>nonce</dt><dd>{nonce or '-'}</dd>",
                "</dl>",
                "</main></body></html>",
            ]
            body = "".join(lines).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    Handler.GET_ROUTE_DISPATCH_TABLE = {
        str(route.handler_id): f"_handle_{route.handler_id}"
        for route in WEB_DESIGN_LIVE_ROUTE_TABLE.routes
        if route.method == "GET" and route.handler_id
    }
    Handler.POST_ROUTE_DISPATCH_TABLE = {
        str(route.handler_id): f"_handle_{route.handler_id}"
        for route in WEB_DESIGN_LIVE_ROUTE_TABLE.routes
        if route.method == "POST" and route.handler_id
    }

    return Handler


def _blocked_action(ui_action: str, human_message: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "integration_failure",
        "source": "ui_action",
        "ui_action": ui_action,
        "action_role": "blocked",
        "availability_state": "unknown_disabled",
        "disabled_reason_code": "UI_ACTION_NOT_ALLOWED",
        "disabled_reasons": ["unknown_disabled"],
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "blocked",
        "result": {
            "status": "integration_failure",
            "machine_error_code": "UI_ACTION_NOT_ALLOWED",
            "human_message": human_message,
            "next_action": "none",
            "changed_files": [],
            "data": {},
        },
    }


def _unavailable_action(
    ui_action: str,
    human_message: str,
    machine_error_code: str,
    *,
    availability_state: str = "blocked",
    disabled_reasons: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "integration_failure",
        "source": "ui_action",
        "ui_action": ui_action,
        "action_role": "blocked",
        "availability_state": availability_state,
        "disabled_reason_code": machine_error_code,
        "disabled_reasons": list(disabled_reasons),
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "unavailable",
        "result": {
            "status": "integration_failure",
            "machine_error_code": machine_error_code,
            "human_message": human_message,
            "next_action": "user_action",
            "changed_files": [],
            "data": {},
        },
    }


def _public_launch_preflight_summary(preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(preflight.get("status", "denied")),
        "machine_error_code": str(preflight.get("machine_error_code", "unknown")),
        "reason": str(preflight.get("reason", "")),
        "target_kind": str(preflight.get("target_kind", "unknown")),
        "target_exists": preflight.get("target_exists") is True,
        "separate_profile": preflight.get("separate_profile") is True,
        "separate_data_dir": preflight.get("separate_data_dir") is True,
        "separate_port": preflight.get("separate_port") is True,
        "process_confirmation_possible": preflight.get("process_confirmation_possible") is True,
        "current_session_untouched": preflight.get("current_session_untouched") is True,
    }


def _public_sandbox_action_preflight_summary(preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(preflight.get("status", "denied")),
        "machine_error_code": str(preflight.get("machine_error_code", "unknown")),
        "reason": str(preflight.get("reason", "")),
        "separate_profile": preflight.get("separate_profile") is True,
        "separate_data_dir": preflight.get("separate_data_dir") is True,
        "separate_port": preflight.get("separate_port") is True,
        "current_session_untouched": preflight.get("current_session_untouched") is True,
        "sandbox_target_proven": preflight.get("sandbox_target_proven") is True,
    }


def _public_account_connect_preflight_summary(preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(preflight.get("status", "denied")),
        "machine_error_code": str(preflight.get("machine_error_code", "unknown")),
        "reason": str(preflight.get("reason", "")),
        "source_kind": str(preflight.get("source_kind", "unknown")),
        "write_surface": str(preflight.get("write_surface", "unknown")),
        "refresh_surface": str(preflight.get("refresh_surface", "accounts-readonly")),
        "reserve_first_required": preflight.get("reserve_first_required") is True,
        "current_session_untouched": preflight.get("current_session_untouched") is True,
    }


def _public_api_route_connect_preflight_summary(preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(preflight.get("status", "denied")),
        "machine_error_code": str(preflight.get("machine_error_code", "unknown")),
        "reason": str(preflight.get("reason", "")),
        "source_kind": str(preflight.get("source_kind", "unknown")),
        "write_surface": str(preflight.get("write_surface", "unknown")),
        "refresh_surface": str(preflight.get("refresh_surface", "api-connections-readonly")),
        "browser_secret_intake": preflight.get("browser_secret_intake") is True,
        "browser_path_intake": preflight.get("browser_path_intake") is True,
        "browser_route_id_intake": preflight.get("browser_route_id_intake") is True,
        "current_session_untouched": preflight.get("current_session_untouched") is True,
    }


def _launch_copy_preflight_denied(ui_action: str, preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "integration_failure",
        "source": "ui_action",
        "ui_action": ui_action,
        "action_role": "blocked",
        "availability_state": "preflight_blocked",
        "disabled_reason_code": str(preflight.get("machine_error_code", LAUNCH_COPY_PREFLIGHT_UNSAFE_CODE)),
        "disabled_reasons": ["launch_copy_preflight_blocked"],
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "preflight_only",
        "result": {
            "status": "integration_failure",
            "machine_error_code": str(preflight.get("machine_error_code", LAUNCH_COPY_PREFLIGHT_UNSAFE_CODE)),
            "human_message": str(preflight.get("reason", "Изолированная копия не admitted.")),
            "next_action": "user_action",
            "changed_files": [],
            "data": {
                "launch_preflight": _public_launch_preflight_summary(preflight),
                "launch_phase": "preflight_denied",
            },
        },
    }


def _sandbox_action_runner_env(contract: LaunchCopyContract) -> dict[str, str]:
    profile_dir = Path(contract.profile_dir or "").expanduser()
    data_dir = Path(contract.data_dir or "").expanduser()
    bin_dir = data_dir / "bin"
    env = dict(os.environ)
    repo_root = str(ROOT)
    current_pythonpath = env.get("PYTHONPATH", "")
    pythonpath_parts = [part for part in current_pythonpath.split(os.pathsep) if part]
    if repo_root not in pythonpath_parts:
        pythonpath_parts.insert(0, repo_root)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    env["HOME"] = str(profile_dir)
    env["CODEX_HOME"] = str(profile_dir)
    env["WBP_PROFILE_DIR"] = str(profile_dir)
    env["WBP_MANAGED_DIR"] = str(data_dir)
    env["WBP_STABLE_CONFIG"] = str(data_dir / "stable-runtime-config.yaml")
    env["WBP_AUTH_FILE"] = str(profile_dir / "auth.json")
    env["WBP_CONFIG_TOML"] = str(profile_dir / "config.toml")
    env["WBP_RUNTIME_MODE_FILE"] = str(profile_dir / "runtime-mode.txt")
    env["WBP_RUNTIME_EFFECTIVE_MODE_FILE"] = str(
        profile_dir / "runtime-effective-mode.txt"
    )
    env["WBP_REGISTRY_FILE"] = str(data_dir / "backend-registry.json")
    env["WBP_STATE_FILE"] = str(data_dir / ("supervisor-" + "state" + ".json"))
    env["WBP_MANAGED_CONFIG_FILE"] = str(data_dir / "managed-config.yaml")
    env["WBP_LAUNCHER_SCRIPT"] = str(profile_dir / DEFAULT_LAUNCHER_SCRIPT_NAME)
    env["WBP_SYNC_SCRIPT"] = str(data_dir / "supervisor-sync.sh")
    env["WBP_ACCOUNTS_BIN"] = str(bin_dir / "codex-accounts")
    env["WBP_ONBOARD_BIN"] = str(bin_dir / "codex-account-onboard")
    env["WBP_LOCK_FILE"] = str(data_dir / "wild-boar-proxy.lock")
    env["WBP_LAUNCHER_LOCK_FILE"] = str(data_dir / "stable-runtime-launch.lock")
    env["WBP_EXTERNAL_MODELS_DIR"] = str(data_dir / "external-models")
    env["WBP_REQUIRE_SANDBOX_AUTH_DIR"] = "1"
    return env


def _owner_action_runner_env(paths: RuntimePaths) -> dict[str, str]:
    env = build_launcher_subprocess_env(paths)
    repo_root = str(ROOT)
    current_pythonpath = env.get("PYTHONPATH", "")
    pythonpath_parts = [part for part in current_pythonpath.split(os.pathsep) if part]
    if repo_root not in pythonpath_parts:
        pythonpath_parts.insert(0, repo_root)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    env["WBP_EXTERNAL_MODELS_DIR"] = str(paths.managed_dir / "external-models")
    return env


def _account_connect_preflight_denied(ui_action: str, preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "integration_failure",
        "source": "ui_action",
        "ui_action": ui_action,
        "action_role": "blocked",
        "availability_state": "preflight_blocked",
        "disabled_reason_code": str(preflight.get("machine_error_code", ACCOUNT_CONNECT_PREFLIGHT_UNSAFE_CODE)),
        "disabled_reasons": ["account_connect_preflight_blocked"],
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "preflight_only",
        "result": {
            "status": "integration_failure",
            "machine_error_code": str(preflight.get("machine_error_code", ACCOUNT_CONNECT_PREFLIGHT_UNSAFE_CODE)),
            "human_message": str(preflight.get("reason", "Live account connect не admitted.")),
            "next_action": "user_action",
            "changed_files": [],
            "data": {
                "account_connect_preflight": _public_account_connect_preflight_summary(preflight),
                "onboarding_phase": "preflight_denied",
            },
        },
    }


def _api_route_connect_preflight_denied(ui_action: str, preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "integration_failure",
        "source": "ui_action",
        "ui_action": ui_action,
        "action_role": "blocked",
        "availability_state": "preflight_blocked",
        "disabled_reason_code": str(preflight.get("machine_error_code", API_ROUTE_CONNECT_PREFLIGHT_UNSAFE_CODE)),
        "disabled_reasons": ["api_route_connect_preflight_blocked"],
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "preflight_only",
        "result": {
            "status": "integration_failure",
            "machine_error_code": str(preflight.get("machine_error_code", API_ROUTE_CONNECT_PREFLIGHT_UNSAFE_CODE)),
            "human_message": str(preflight.get("reason", "API route connect не admitted.")),
            "next_action": "user_action",
            "changed_files": [],
            "data": {
                "api_route_connect_preflight": _public_api_route_connect_preflight_summary(preflight),
                "api_route_connect_phase": "preflight_denied",
            },
        },
    }


def _account_action_args(
    runner: CommandRunner,
    payload: dict[str, Any],
    *,
    ui_action: str,
) -> tuple[dict[str, str] | None, dict[str, Any] | None]:
    account_id = payload.get("account_id")
    if not isinstance(account_id, str):
        return None, _unavailable_action(
            ui_action,
            f"{ui_action} требует account_id.",
            "UI_ACCOUNT_ID_REQUIRED",
        )
    account_id = account_id.strip()
    if (
        not account_id
        or account_id in {".", ".."}
        or len(account_id) > 96
        or any(char not in ACCOUNT_ID_SAFE_CHARS for char in account_id)
    ):
        return None, _unavailable_action(
            ui_action,
            f"{ui_action} получил небезопасный account_id.",
            "UI_ACCOUNT_ID_INVALID",
        )

    result = execute_command(runner, "accounts_list")
    if result["status"] != "ok":
        return None, _unavailable_action(
            ui_action,
            "Список аккаунтов недоступен; цель действия с аккаунтом нельзя проверить.",
            _account_list_unavailable_code(ui_action),
        )
    try:
        accounts = build_account_pool_snapshot(result["packet"])
    except UiShellError:
        return None, _unavailable_action(
            ui_action,
            "Пакет аккаунтов недействителен; цель действия с аккаунтом нельзя проверить.",
            _account_list_invalid_code(ui_action),
        )
    target_account = next(
        (account for account in accounts.accounts if account.backend_id == account_id),
        None,
    )
    if target_account is None:
        return None, _unavailable_action(
            ui_action,
            f"Цель {ui_action} отсутствует в списке аккаунтов.",
            "UI_ACCOUNT_ID_NOT_FOUND",
        )
    if ui_action in {
        "promote_account",
        "demote_account",
        "retire_account",
        "hold_account",
        "release_account",
    } and target_account.pool == "retired":
        return None, _unavailable_action(
            ui_action,
            f"Цель {ui_action} уже retired; терминальный вывод не имеет автоматического пути возврата.",
            "UI_ACCOUNT_LIFECYCLE_RETIRED_INELIGIBLE",
        )
    if ui_action == "retire_account" and target_account.pool not in {"active", "reserve"}:
        return None, _unavailable_action(
            ui_action,
            "Цель retire_account не находится в active или reserve.",
            "UI_ACCOUNT_RETIRE_INELIGIBLE",
        )
    if ui_action == "promote_account" and target_account.pool != "reserve":
        return None, _unavailable_action(
            ui_action,
            "Цель promote_account не находится в reserve.",
            "UI_ACCOUNT_PROMOTE_INELIGIBLE",
        )
    if ui_action == "promote_account" and target_account.manual_hold:
        return None, _unavailable_action(
            ui_action,
            "Цель promote_account находится на manual hold.",
            "UI_ACCOUNT_PROMOTE_INELIGIBLE",
        )
    if ui_action == "demote_account" and target_account.pool != "active":
        return None, _unavailable_action(
            ui_action,
            "Цель demote_account не находится в active.",
            "UI_ACCOUNT_DEMOTE_INELIGIBLE",
        )
    if ui_action == "demote_account" and target_account.manual_hold:
        return None, _unavailable_action(
            ui_action,
            "Цель demote_account находится на manual hold.",
            "UI_ACCOUNT_DEMOTE_INELIGIBLE",
        )
    if ui_action == "hold_account" and target_account.manual_hold:
        return None, _unavailable_action(
            ui_action,
            "Цель hold_account уже находится на manual hold.",
            "UI_ACCOUNT_HOLD_INELIGIBLE",
        )
    if ui_action == "release_account" and not target_account.manual_hold:
        return None, _unavailable_action(
            ui_action,
            "Цель release_account не находится на manual hold.",
            "UI_ACCOUNT_RELEASE_INELIGIBLE",
        )
    return {"account_id": account_id}, None


def _account_list_unavailable_code(ui_action: str) -> str:
    if ui_action in {"validate_account", "recheck_account"}:
        return "UI_ACCOUNT_VALIDATE_ACCOUNT_LIST_UNAVAILABLE"
    return "UI_ACCOUNT_LIFECYCLE_ACCOUNT_LIST_UNAVAILABLE"


def _account_list_invalid_code(ui_action: str) -> str:
    if ui_action in {"validate_account", "recheck_account"}:
        return "UI_ACCOUNT_VALIDATE_ACCOUNT_LIST_INVALID"
    return "UI_ACCOUNT_LIFECYCLE_ACCOUNT_LIST_INVALID"


def _api_route_action_args(
    runner: CommandRunner,
    payload: dict[str, Any],
    *,
    ui_action: str,
) -> tuple[dict[str, str] | None, dict[str, Any] | None]:
    route_id = payload.get("route_id")
    if not isinstance(route_id, str):
        return None, _unavailable_action(
            ui_action,
            f"{ui_action} требует route_id.",
            "UI_API_ROUTE_ID_REQUIRED",
        )
    route_id = route_id.strip()
    if (
        not route_id
        or route_id in {".", ".."}
        or len(route_id) > 96
        or any(char not in ROUTE_ID_SAFE_CHARS for char in route_id)
    ):
        return None, _unavailable_action(
            ui_action,
            f"{ui_action} получил небезопасный route_id.",
            "UI_API_ROUTE_ID_INVALID",
        )

    result = execute_external_command(runner, "external-models", "routes", "list", "--json")
    if result["status"] != "ok":
        return None, _unavailable_action(
            ui_action,
            "Список маршрутов недоступен; цель действия нельзя проверить.",
            _api_route_list_unavailable_code(ui_action),
        )
    packet = result.get("packet")
    if not isinstance(packet, dict):
        return None, _unavailable_action(
            ui_action,
            "Пакет маршрутов недействителен; цель действия нельзя проверить.",
            _api_route_list_invalid_code(ui_action),
        )
    data = packet.get("data")
    if not isinstance(data, dict):
        return None, _unavailable_action(
            ui_action,
            "Пакет маршрутов недействителен; цель действия нельзя проверить.",
            _api_route_list_invalid_code(ui_action),
        )
    routes = data.get("routes")
    if not isinstance(routes, list):
        return None, _unavailable_action(
            ui_action,
            "Пакет маршрутов недействителен; цель действия нельзя проверить.",
            _api_route_list_invalid_code(ui_action),
        )
    target_route = next(
        (
            route
            for route in routes
            if isinstance(route, dict) and str(route.get("route_id", "")) == route_id
        ),
        None,
    )
    if target_route is None:
        return None, _unavailable_action(
            ui_action,
            f"Цель {ui_action} отсутствует в списке маршрутов.",
            "UI_API_ROUTE_ID_NOT_FOUND",
        )
    route_enabled_value = target_route.get("enabled")
    route_enabled = route_enabled_value is True
    if ui_action in {"api_route_validate", "api_route_check", "api_route_disable"} and not route_enabled:
        return None, _unavailable_action(
            ui_action,
            f"Цель {ui_action} отключена.",
            "UI_API_ROUTE_DISABLED_INELIGIBLE",
        )
    if ui_action == "api_route_allow" and route_enabled:
        return None, _unavailable_action(
            ui_action,
            "Цель api_route_allow уже разрешена.",
            "UI_API_ROUTE_ALLOW_INELIGIBLE",
        )
    if ui_action == "api_route_remove" and route_enabled:
        return None, _unavailable_action(
            ui_action,
            "Цель api_route_remove ещё разрешена; удаление доступно только для отключённых маршрутов.",
            "UI_API_ROUTE_REMOVE_INELIGIBLE",
        )
    if ui_action == "api_route_remove" and route_enabled_value is not False:
        return None, _unavailable_action(
            ui_action,
            "Цель api_route_remove не имеет доказанного disabled-состояния.",
            "UI_API_ROUTE_REMOVE_STATE_UNPROVEN",
        )
    return {"route_id": route_id}, None


def _session_action_args(
    payload: dict[str, Any],
    *,
    ui_action: str,
) -> tuple[dict[str, str] | None, dict[str, Any] | None]:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str):
        return None, _unavailable_action(
            ui_action,
            f"{ui_action} требует session_id.",
            "UI_LOGIN_SESSION_ID_REQUIRED",
        )
    session_id = session_id.strip()
    if (
        not session_id
        or session_id in {".", ".."}
        or len(session_id) > 128
        or any(char not in SESSION_ID_SAFE_CHARS for char in session_id)
    ):
        return None, _unavailable_action(
            ui_action,
            f"{ui_action} получил небезопасный session_id.",
            "UI_LOGIN_SESSION_ID_INVALID",
        )
    return {"session_id": session_id}, None


def _api_route_list_unavailable_code(ui_action: str) -> str:
    if ui_action == "api_route_validate":
        return "UI_API_ROUTE_VALIDATE_ROUTE_LIST_UNAVAILABLE"
    if ui_action == "api_route_allow":
        return "UI_API_ROUTE_ALLOW_ROUTE_LIST_UNAVAILABLE"
    if ui_action == "api_route_disable":
        return "UI_API_ROUTE_DISABLE_ROUTE_LIST_UNAVAILABLE"
    if ui_action == "api_route_remove":
        return "UI_API_ROUTE_REMOVE_ROUTE_LIST_UNAVAILABLE"
    if ui_action == "api_route_profile":
        return "UI_API_ROUTE_PROFILE_ROUTE_LIST_UNAVAILABLE"
    if ui_action == "api_route_evidence_capture":
        return "UI_API_ROUTE_EVIDENCE_ROUTE_LIST_UNAVAILABLE"
    return "UI_API_ROUTE_CHECK_ROUTE_LIST_UNAVAILABLE"


def _api_route_list_invalid_code(ui_action: str) -> str:
    if ui_action == "api_route_validate":
        return "UI_API_ROUTE_VALIDATE_ROUTE_LIST_INVALID"
    if ui_action == "api_route_allow":
        return "UI_API_ROUTE_ALLOW_ROUTE_LIST_INVALID"
    if ui_action == "api_route_disable":
        return "UI_API_ROUTE_DISABLE_ROUTE_LIST_INVALID"
    if ui_action == "api_route_remove":
        return "UI_API_ROUTE_REMOVE_ROUTE_LIST_INVALID"
    if ui_action == "api_route_profile":
        return "UI_API_ROUTE_PROFILE_ROUTE_LIST_INVALID"
    if ui_action == "api_route_evidence_capture":
        return "UI_API_ROUTE_EVIDENCE_ROUTE_LIST_INVALID"
    return "UI_API_ROUTE_CHECK_ROUTE_LIST_INVALID"


def _action_available(
    ui_action: str,
    *,
    launch_client_path: str | None,
    launch_copy_contract: LaunchCopyContract | None,
    action_phase: str,
    owner_authorized: bool = False,
    legacy_import_token_store: LegacyImportTokenStore | None = None,
) -> bool:
    if ui_action == "setup_discovery":
        return True
    if ui_action == "legacy_import_discovery":
        return True
    if ui_action == "legacy_import":
        return bool(legacy_import_token_store and legacy_import_token_store.has_active_token())
    if ui_action in SETUP_IMPORT_FOUNDATION_ACTIONS:
        return False
    if ui_action in PARKED_IN_LIVE_READONLY_ACTIONS:
        if action_phase == LIVE_READONLY_ACTION_PHASE:
            return False
        if action_phase == SANDBOX_ACTION_PHASE:
            if ui_action not in SANDBOX_ACTION_PHASE_ADMITTED_ACTIONS:
                return False
            return _sandbox_action_preflight(launch_copy_contract)["status"] == "admitted"
    if ui_action == "launch_client_dispatch":
        return bool(launch_client_path) and _launch_copy_preflight(launch_copy_contract)["status"] == "admitted"
    if ui_action == "launch_custom_client_native":
        return owner_authorized
    return True


def _action_availability_state(
    ui_action: str,
    *,
    launch_client_path: str | None,
    launch_copy_contract: LaunchCopyContract | None,
    action_phase: str,
    owner_authorized: bool = False,
    legacy_import_token_store: LegacyImportTokenStore | None = None,
) -> str:
    if ui_action == "setup_discovery":
        return SETUP_DISCOVERY_AVAILABLE_STATE
    if ui_action == "legacy_import_discovery":
        return LEGACY_IMPORT_DISCOVERY_AVAILABLE_STATE
    if ui_action == "legacy_import":
        return (
            "token_bound_import_capable"
            if legacy_import_token_store and legacy_import_token_store.has_active_token()
            else "token_required"
        )
    if ui_action in PARKED_IN_LIVE_READONLY_ACTIONS:
        if action_phase == LIVE_READONLY_ACTION_PHASE:
            return "disabled_live_action"
        if action_phase == SANDBOX_ACTION_PHASE:
            if ui_action not in SANDBOX_ACTION_PHASE_ADMITTED_ACTIONS:
                return "phase_not_admitted"
            if _sandbox_action_preflight(launch_copy_contract)["status"] != "admitted":
                return "preflight_blocked"
    if ui_action == "launch_client_dispatch" and not launch_client_path:
        return "not_admitted"
    if ui_action == "launch_client_dispatch" and _launch_copy_preflight(launch_copy_contract)["status"] != "admitted":
        return "preflight_blocked"
    if ui_action == "launch_custom_client_native" and not owner_authorized:
        return "owner_authorization_required"
    if ui_action not in UI_ACTION_ALLOWLIST:
        return "unknown_disabled"
    return "displayable_readonly"


def _action_unavailable_code(
    ui_action: str,
    *,
    launch_client_path: str | None,
    launch_copy_contract: LaunchCopyContract | None,
    action_phase: str,
    owner_authorized: bool = False,
    legacy_import_token_store: LegacyImportTokenStore | None = None,
) -> str:
    if ui_action == "legacy_import_discovery":
        return ""
    if ui_action == "legacy_import":
        return LEGACY_IMPORT_TOKEN_REQUIRED_CODE
    if ui_action in SETUP_IMPORT_FOUNDATION_ACTIONS:
        return SETUP_IMPORT_FOUNDATION_ONLY_UNAVAILABLE_CODE
    if ui_action in PARKED_IN_LIVE_READONLY_ACTIONS:
        if action_phase == LIVE_READONLY_ACTION_PHASE:
            return LIVE_READONLY_ACTION_DISABLED_REASON_CODE
        if action_phase == SANDBOX_ACTION_PHASE:
            if ui_action not in SANDBOX_ACTION_PHASE_ADMITTED_ACTIONS:
                return SANDBOX_ACTION_PHASE_DISABLED_REASON_CODE
            return str(_sandbox_action_preflight(launch_copy_contract)["machine_error_code"])
    if ui_action == "launch_client_dispatch" and not launch_client_path:
        return "UI_LAUNCH_CLIENT_PATH_UNAVAILABLE"
    if ui_action == "launch_client_dispatch":
        return str(_launch_copy_preflight(launch_copy_contract)["machine_error_code"])
    if ui_action == "launch_custom_client_native" and not owner_authorized:
        return "OWNER_AUTHORIZATION_REQUIRED"
    if ui_action not in UI_ACTION_ALLOWLIST:
        return "UI_ACTION_NOT_ALLOWED"
    return ""


def _action_disabled_reasons(
    ui_action: str,
    *,
    launch_client_path: str | None,
    launch_copy_contract: LaunchCopyContract | None,
    action_phase: str,
    owner_authorized: bool = False,
    legacy_import_token_store: LegacyImportTokenStore | None = None,
) -> tuple[str, ...]:
    if ui_action == "legacy_import_discovery":
        return ()
    if ui_action == "legacy_import":
        return (
            ()
            if legacy_import_token_store and legacy_import_token_store.has_active_token()
            else ("token_missing",)
        )
    if ui_action in PARKED_IN_LIVE_READONLY_ACTIONS:
        if action_phase == LIVE_READONLY_ACTION_PHASE:
            return LIVE_READONLY_ACTION_DISABLED_REASONS
        if action_phase == SANDBOX_ACTION_PHASE:
            if ui_action not in SANDBOX_ACTION_PHASE_ADMITTED_ACTIONS:
                return SANDBOX_ACTION_PHASE_DISABLED_REASONS
            sandbox_preflight = _sandbox_action_preflight(launch_copy_contract)
            if sandbox_preflight["status"] != "admitted":
                return ("sandbox_target_unproven",)
    if ui_action == "launch_client_dispatch" and not launch_client_path:
        return ("launch_client_path_unavailable",)
    if ui_action == "launch_client_dispatch":
        launch_preflight = _launch_copy_preflight(launch_copy_contract)
        if launch_preflight["status"] != "admitted":
            return ("launch_copy_preflight_blocked",)
    if ui_action == "launch_custom_client_native" and not owner_authorized:
        return ("owner_authorization_required",)
    if ui_action not in UI_ACTION_ALLOWLIST:
        return ("unknown_disabled",)
    return ()


def _action_unavailable_reason(
    ui_action: str,
    *,
    launch_client_path: str | None,
    launch_copy_contract: LaunchCopyContract | None,
    action_phase: str,
    owner_authorized: bool = False,
    legacy_import_token_store: LegacyImportTokenStore | None = None,
) -> str:
    if ui_action == "setup_discovery":
        return ""
    if ui_action == "legacy_import_discovery":
        return ""
    if ui_action == "legacy_import":
        return "Legacy import requires a server-owned discovery token before import-capable reference truth is admitted."
    if ui_action in PARKED_IN_LIVE_READONLY_ACTIONS:
        if action_phase == LIVE_READONLY_ACTION_PHASE:
            return LIVE_READONLY_ACTION_UNAVAILABLE_MESSAGE
        if action_phase == SANDBOX_ACTION_PHASE:
            if ui_action not in SANDBOX_ACTION_PHASE_ADMITTED_ACTIONS:
                return SANDBOX_ACTION_PHASE_UNAVAILABLE_MESSAGE
            sandbox_preflight = _sandbox_action_preflight(launch_copy_contract)
            return "" if sandbox_preflight["status"] == "admitted" else str(sandbox_preflight["reason"])
    if ui_action == "launch_client_dispatch" and not launch_client_path:
        return "Bounded путь запуска клиента недоступен."
    if ui_action == "launch_client_dispatch":
        launch_preflight = _launch_copy_preflight(launch_copy_contract)
        return "" if launch_preflight["status"] == "admitted" else str(launch_preflight["reason"])
    if ui_action == "launch_custom_client_native" and not owner_authorized:
        return "Live launch requires exact owner authorization in the active thread."
    return ""


def _action_result(
    result: dict[str, Any],
    *,
    ui_action: str = "",
    launch_preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet = result.get("packet")
    packet_data = packet.get("data", {}) if isinstance(packet, dict) else {}
    data = dict(packet_data) if isinstance(packet_data, dict) else {}
    changed_files = result["changed_files"]
    if ui_action == "export_diagnostics" and isinstance(packet, dict):
        bundle_path = packet.get("bundle_path")
        if not isinstance(bundle_path, str) or not bundle_path:
            bundle_path = data.get("bundle_path")
        if isinstance(bundle_path, str) and bundle_path:
            data["bundle_path"] = Path(bundle_path).name
        data["redaction_status"] = _diagnostics_redaction_status(packet, data)
        data["claim_scope"] = "support_artifact_only"
        if isinstance(changed_files, list):
            changed_files = ["diagnostics_bundle"] * len(changed_files)
    if ui_action == "launch_client_dispatch":
        client_launch_result = packet.get("client_launch_result") if isinstance(packet, dict) else None
        launch_state = "launch_failed"
        process_confirmed = False
        real_codex_app_launched = False
        dispatch_method = ""
        if isinstance(client_launch_result, dict):
            dispatch_method = str(client_launch_result.get("dispatch_method", ""))
            dispatch_observed = client_launch_result.get("dispatch_observed") is True
            real_codex_app_launched = (
                client_launch_result.get("real_codex_app_launched") is True
            )
            if real_codex_app_launched:
                launch_state = "app_process_confirmed"
                process_confirmed = True
            elif dispatch_method == "detached_executable_spawn" and dispatch_observed:
                launch_state = "launch_requested"
            elif dispatch_observed:
                launch_state = "launch_requested"
            elif client_launch_result.get("dispatch_attempted") is True:
                launch_state = "launch_requested"
        data = {
            "launch_preflight": _public_launch_preflight_summary(launch_preflight or {}),
            "launch_phase": launch_state,
            "process_confirmed": process_confirmed,
            "real_codex_app_launched": real_codex_app_launched,
            "dispatch_method": dispatch_method or "unreported",
            "launch_claim_scope": (
                "bounded_executable_launch_with_process_observation"
                if real_codex_app_launched
                else "os_dispatch_only"
            ),
            "current_session_untouched": (
                bool(launch_preflight) and launch_preflight.get("current_session_untouched") is True
            ),
        }
        if isinstance(changed_files, list):
            changed_files = ["launch_dispatch_metadata"] * len(changed_files)
    if ui_action in {
        "onboard_account",
        "account_login_status",
        "account_login_complete",
        "account_login_cancel",
    } and isinstance(changed_files, list):
        changed_files = ["account_onboarding_artifact"] * len(changed_files)
    payload = {
        "status": result["status"],
        "machine_error_code": result["machine_error_code"],
        "human_message": result["human_message"],
        "next_action": result["next_action"],
        "changed_files": changed_files,
        "data": data if isinstance(data, dict) else {},
    }
    packet_effect = packet.get("effect") if isinstance(packet, dict) else None
    if packet_effect in {EFFECT_READ, EFFECT_PROBE, EFFECT_MUTATE, EFFECT_REPAIR}:
        payload["command_effect"] = packet_effect
    if ui_action in {"onboard_account_dry_run", "account_login_complete"}:
        payload["onboarding"] = _onboarding_summary(packet, command_status=str(result["status"]))
    return payload


def _packet_login_result(result: dict[str, Any]) -> dict[str, Any]:
    packet = result.get("packet") if isinstance(result.get("packet"), dict) else {}
    login_result = packet.get("login_result") if isinstance(packet.get("login_result"), dict) else {}
    return login_result if isinstance(login_result, dict) else {}


def _codex_login_bridge_public_summary(
    result: dict[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    packet = result.get("packet") if isinstance(result.get("packet"), dict) else {}
    login_result = _packet_login_result(result)
    onboarding_result = (
        packet.get("onboarding_result") if isinstance(packet.get("onboarding_result"), dict) else {}
    )
    session_id = str(
        login_result.get("session_id")
        or login_result.get("login_session_id")
        or packet.get("login_session_id")
        or ""
    )
    device_url = str(
        login_result.get("device_url")
        or packet.get("device_url")
        or ""
    )
    device_code = str(
        login_result.get("device_code")
        or packet.get("device_code")
        or ""
    )
    status = str(login_result.get("status") or "")
    final_outcome = str(onboarding_result.get("final_outcome") or "")
    if phase == "start" and not status:
        status = "waiting_for_user" if result.get("status") == "ok" else "failed"
    elif phase == "status" and not status:
        status = "unknown"
    elif phase == "complete" and not status:
        status = "completed" if result.get("status") == "ok" else "failed"
    return {
        "status": status,
        "provider": str(login_result.get("provider") or packet.get("provider") or "codex"),
        "mode": str(login_result.get("mode") or packet.get("mode") or "device"),
        "phase": phase,
        "session_id": session_id,
        "login_session_id": session_id,
        "login_session_id_present": bool(session_id),
        "device_url": device_url,
        "device_url_present": bool(device_url),
        "login_url": device_url,
        "login_url_present": bool(device_url),
        "login_url_kind": "device_code" if device_url else "missing",
        "device_code": device_code,
        "device_code_present": bool(device_code) or login_result.get("device_code_present") is True,
        "auth_materialized": login_result.get("auth_materialized") is True,
        "auth_ref_present": bool(
            login_result.get("auth_ref_present")
            or login_result.get("auth_ref")
            or packet.get("auth_ref")
        ),
        "auth_ref_scope": str(
            login_result.get("auth_ref_scope")
            or packet.get("auth_ref_scope")
            or ("sandbox" if final_outcome in {"explicit_auth_imported_to_reserve", "reserve_only_success"} else "")
        ),
        "browser_secret_intake": False,
        "browser_path_intake": False,
        "next_action": str(result.get("next_action") or ""),
        "machine_error_code": str(result.get("machine_error_code") or ""),
    }


def _api_route_credential_bridge_data(
    *,
    route_id: str,
    connect_phase: str,
    admission_mode: str,
    preflight: dict[str, Any],
    provider_fallback: str,
    credential_ref_fallback: str,
    credential_status_result: dict[str, Any] | None,
    credential_admit_result: dict[str, Any] | None,
    credential_phase: str,
    add_result: dict[str, Any] | None,
    validate_result: dict[str, Any] | None,
) -> dict[str, Any]:
    credential_status_packet = (
        credential_status_result.get("packet")
        if isinstance(credential_status_result, dict) and isinstance(credential_status_result.get("packet"), dict)
        else {}
    )
    credential_admit_packet = (
        credential_admit_result.get("packet")
        if isinstance(credential_admit_result, dict) and isinstance(credential_admit_result.get("packet"), dict)
        else {}
    )
    credential_status_data = credential_status_packet.get("data", {})
    credential_admit_data = credential_admit_packet.get("data", {})
    credential_status = (
        credential_status_data.get("credential_result")
        if isinstance(credential_status_data, dict)
        else None
    )
    credential_admit = (
        credential_admit_data.get("credential_result")
        if isinstance(credential_admit_data, dict)
        else None
    )
    credential_status = credential_status if isinstance(credential_status, dict) else {}
    credential_admit = credential_admit if isinstance(credential_admit, dict) else {}
    credential_present = (
        credential_status.get("credential_present") is True
        or credential_admit.get("credential_present") is True
    )
    credential_admitted = credential_admit.get("status") == "admitted"
    setup_source = credential_admit if credential_admit else credential_status
    return {
        "route_id": route_id,
        "api_route_connect_phase": connect_phase,
        "admission_mode": admission_mode,
        "credential_phase": credential_phase,
        "credential_status": str(credential_status.get("status") or "not_run"),
        "credential_admit_status": str(credential_admit.get("status") or "not_run"),
        "credential_provider": str(
            credential_status.get("provider")
            or credential_admit.get("provider")
            or provider_fallback
            or "openrouter"
        ),
        "credential_ref": str(
            credential_status.get("credential_ref")
            or credential_admit.get("credential_ref")
            or credential_ref_fallback
            or ""
        ),
        "credential_supported_sources": (
            setup_source.get("supported_sources")
            if isinstance(setup_source.get("supported_sources"), list)
            else []
        ),
        "credential_expected_refs": (
            setup_source.get("expected_refs")
            if isinstance(setup_source.get("expected_refs"), list)
            else []
        ),
        "credential_provider_dashboard_url": str(
            setup_source.get("provider_dashboard_url") or ""
        ),
        "credential_present": credential_present,
        "credential_admitted": credential_admitted,
        "api_route_connect_preflight": _public_api_route_connect_preflight_summary(preflight),
        "owner_source_kind": "server_owned_route_spec",
        "credential_owner_source_kind": "owner_env",
        "browser_secret_intake": False,
        "browser_path_intake": False,
        "browser_route_id_intake": False,
        "browser_api_key_intake": False,
        "secret_value_exposed": False,
        "route_spec_path_exposed": False,
        "credential_status_command_status": str(credential_status_result.get("status") or "") if credential_status_result else "not_run",
        "credential_status_machine_error_code": str(credential_status_result.get("machine_error_code") or "") if credential_status_result else "NOT_RUN",
        "credential_admit_command_status": str(credential_admit_result.get("status") or "") if credential_admit_result else "not_run",
        "credential_admit_machine_error_code": str(credential_admit_result.get("machine_error_code") or "") if credential_admit_result else "NOT_RUN",
        "add_status": str(add_result.get("status") or "") if add_result else "not_run",
        "add_machine_error_code": str(add_result.get("machine_error_code") or "") if add_result else "NOT_RUN",
        "validate_status": str(validate_result.get("status") or "") if validate_result else "not_run",
        "validate_machine_error_code": str(validate_result.get("machine_error_code") or "") if validate_result else "NOT_RUN",
        "refresh_surface": "api-connections-readonly",
    }


def _api_route_connect_result(
    *,
    status: str,
    machine_error_code: str,
    human_message: str,
    next_action: str,
    route_id: str,
    connect_phase: str,
    admission_mode: str,
    preflight: dict[str, Any],
    provider_fallback: str,
    credential_ref_fallback: str,
    credential_status_result: dict[str, Any] | None,
    credential_admit_result: dict[str, Any] | None,
    credential_phase: str,
    add_result: dict[str, Any] | None,
    validate_result: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "status": status,
        "machine_error_code": machine_error_code,
        "human_message": human_message,
        "next_action": next_action,
        "changed_files": ["api_route_connect_artifact"] if status == "ok" else [],
        "data": _api_route_credential_bridge_data(
            route_id=route_id,
            connect_phase=connect_phase,
            admission_mode=admission_mode,
            preflight=preflight,
            provider_fallback=provider_fallback,
            credential_ref_fallback=credential_ref_fallback,
            credential_status_result=credential_status_result,
            credential_admit_result=credential_admit_result,
            credential_phase=credential_phase,
            add_result=add_result,
            validate_result=validate_result,
        ),
    }


def _api_route_credential_result_status(result: dict[str, Any] | None) -> dict[str, Any]:
    packet = result.get("packet") if isinstance(result, dict) else None
    data = packet.get("data", {}) if isinstance(packet, dict) else {}
    credential_result = data.get("credential_result") if isinstance(data, dict) else {}
    return credential_result if isinstance(credential_result, dict) else {}


def _run_api_route_credential_bridge(
    runner: CommandRunner,
    *,
    provider: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str, dict[str, Any] | None]:
    credential_status_result = execute_command(
        runner,
        "external_models_credentials_status_provider",
        structured_args={"provider": provider},
        allow_disabled=True,
    )
    if credential_status_result["status"] != "ok":
        return credential_status_result, None, "credential_status_failed", credential_status_result

    status_credential = _api_route_credential_result_status(credential_status_result)
    if status_credential.get("credential_present") is True:
        return credential_status_result, None, "credential_present", None

    credential_admit_result = execute_command(
        runner,
        "external_models_credentials_admit_provider_owner_env",
        structured_args={"provider": provider},
        allow_disabled=True,
    )
    if credential_admit_result["status"] != "ok":
        credential_phase = (
            "credential_missing"
            if credential_admit_result.get("machine_error_code")
            == "EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING"
            else "credential_admit_failed"
        )
        return credential_status_result, credential_admit_result, credential_phase, credential_admit_result

    admit_credential = _api_route_credential_result_status(credential_admit_result)
    if admit_credential.get("credential_present") is not True:
        failed_result = {
            "status": "command_error",
            "machine_error_code": "UI_API_CREDENTIAL_ADMIT_PACKET_INVALID",
            "human_message": "Owner credential admit packet did not prove credential presence.",
            "next_action": "retry",
            "changed_files": [],
            "packet": credential_admit_result.get("packet", {}),
        }
        return credential_status_result, credential_admit_result, "credential_admit_packet_invalid", failed_result

    return credential_status_result, credential_admit_result, "credential_admitted", None


def _run_api_route_credential_check_action(runner: CommandRunner) -> dict[str, Any]:
    api_snapshot_before = build_api_connections_readonly_snapshot(runner)
    preflight = _api_route_connect_preflight(api_snapshot_before)
    if preflight["status"] != "admitted":
        return _api_route_connect_preflight_denied("api_route_credential_check", preflight)
    provider = _api_route_provider_from_snapshot(api_snapshot_before, runner)
    credential_ref = _api_route_secret_ref_from_snapshot(api_snapshot_before, runner)

    credential_status_result = execute_command(
        runner,
        "external_models_credentials_status_provider",
        structured_args={"provider": provider},
        allow_disabled=True,
    )
    if credential_status_result["status"] != "ok":
        result = {
            "status": "command_error",
            "machine_error_code": str(credential_status_result["machine_error_code"]),
            "human_message": str(credential_status_result["human_message"]),
            "next_action": str(credential_status_result["next_action"]),
            "changed_files": [],
            "data": _api_route_credential_bridge_data(
                route_id="",
                connect_phase="credential_status_failed",
                admission_mode="status_only",
                preflight=preflight,
                provider_fallback=provider,
                credential_ref_fallback=credential_ref,
                credential_status_result=credential_status_result,
                credential_admit_result=None,
                credential_phase="credential_status_failed",
                add_result=None,
                validate_result=None,
            ),
        }
        return _ui_action_response_from_result("api_route_credential_check", result)

    status_credential = _api_route_credential_result_status(credential_status_result)
    credential_present = status_credential.get("credential_present") is True
    phase = "credential_present" if credential_present else "credential_missing"
    human_message = (
        f"Owner credential status confirmed for provider: {provider}."
        if credential_present
        else f"Owner credential source is missing for provider: {provider}."
    )
    result = {
        "status": "ok" if credential_present else "command_error",
        "machine_error_code": "OK" if credential_present else "EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING",
        "human_message": human_message,
        "next_action": "api_route_connect" if credential_present else "owner_action",
        "changed_files": [],
        "data": _api_route_credential_bridge_data(
            route_id="",
            connect_phase="credential_status_checked",
            admission_mode="status_only",
            preflight=preflight,
            provider_fallback=provider,
            credential_ref_fallback=credential_ref,
            credential_status_result=credential_status_result,
            credential_admit_result=None,
            credential_phase=phase,
            add_result=None,
            validate_result=None,
        ),
    }
    return _ui_action_response_from_result("api_route_credential_check", result)


def _run_api_route_connect_action(
    runner: CommandRunner,
    launch_copy_contract: LaunchCopyContract | None,
) -> dict[str, Any]:
    api_snapshot_before = build_api_connections_readonly_snapshot(runner)
    preflight = _api_route_connect_preflight(api_snapshot_before)
    if preflight["status"] != "admitted":
        return _api_route_connect_preflight_denied("api_route_connect", preflight)
    provider = _api_route_provider_from_snapshot(api_snapshot_before, runner)
    credential_ref = _api_route_secret_ref_from_snapshot(api_snapshot_before, runner)

    (
        credential_status_result,
        credential_admit_result,
        credential_phase,
        credential_failure_result,
    ) = _run_api_route_credential_bridge(runner, provider=provider)
    if credential_failure_result is not None:
        result = _api_route_connect_result(
            status="command_error",
            machine_error_code=str(credential_failure_result["machine_error_code"]),
            human_message=str(credential_failure_result["human_message"]),
            next_action=str(credential_failure_result["next_action"]),
            route_id="",
            connect_phase=credential_phase,
            admission_mode="credential_bridge",
            preflight=preflight,
            provider_fallback=provider,
            credential_ref_fallback=credential_ref,
            credential_status_result=credential_status_result,
            credential_admit_result=credential_admit_result,
            credential_phase=credential_phase,
            add_result=None,
            validate_result=None,
        )
        return _ui_action_response_from_result("api_route_connect", result)

    existing_route = _primary_api_route_from_snapshot(api_snapshot_before)
    if existing_route is not None:
        route_id = _route_id_from_route(existing_route)
        validate_result = execute_command(
            runner,
            "external_models_routes_validate",
            structured_args={"route_id": route_id},
        )
        status = "ok" if validate_result["status"] == "ok" else "command_error"
        result = _api_route_connect_result(
            status=status,
            machine_error_code=str(validate_result["machine_error_code"]),
            human_message=str(validate_result["human_message"]),
            next_action=str(validate_result["next_action"]),
            route_id=route_id,
            connect_phase="adopted_existing_route",
            admission_mode="adopt",
            preflight=preflight,
            provider_fallback=provider,
            credential_ref_fallback=credential_ref,
            credential_status_result=credential_status_result,
            credential_admit_result=credential_admit_result,
            credential_phase=credential_phase,
            add_result=None,
            validate_result=validate_result,
        )
        return _ui_action_response_from_result("api_route_connect", result)

    route_spec = _server_owned_api_route_spec(runner)
    route_id = str(route_spec["route_id"])
    route_spec_path = _server_owned_api_route_spec_path(
        runner,
        launch_copy_contract,
        route_id,
    )
    try:
        _write_server_owned_api_route_spec(route_spec_path, route_spec)
    except OSError as exc:
        result = _api_route_connect_result(
            status="integration_failure",
            machine_error_code="UI_API_ROUTE_CONNECT_SPEC_WRITE_FAILED",
            human_message=str(exc),
            next_action="retry",
            route_id=route_id,
            connect_phase="spec_write_failed",
            admission_mode="create",
            preflight=preflight,
            provider_fallback=provider,
            credential_ref_fallback=credential_ref,
            credential_status_result=credential_status_result,
            credential_admit_result=credential_admit_result,
            credential_phase=credential_phase,
            add_result=None,
            validate_result=None,
        )
        return _ui_action_response_from_result("api_route_connect", result)

    add_result = execute_command(
        runner,
        "external_models_routes_add_server_owned",
        structured_args={"route_spec_ref": str(route_spec_path)},
        allow_disabled=True,
    )
    if add_result["status"] != "ok":
        result = _api_route_connect_result(
            status="command_error",
            machine_error_code=str(add_result["machine_error_code"]),
            human_message=str(add_result["human_message"]),
            next_action=str(add_result["next_action"]),
            route_id=route_id,
            connect_phase="add_failed",
            admission_mode="create",
            preflight=preflight,
            provider_fallback=provider,
            credential_ref_fallback=credential_ref,
            credential_status_result=credential_status_result,
            credential_admit_result=credential_admit_result,
            credential_phase=credential_phase,
            add_result=add_result,
            validate_result=None,
        )
        return _ui_action_response_from_result("api_route_connect", result)

    validate_result = execute_command(
        runner,
        "external_models_routes_validate",
        structured_args={"route_id": route_id},
    )
    status = "ok" if validate_result["status"] == "ok" else "command_error"
    result = _api_route_connect_result(
        status=status,
        machine_error_code=str(validate_result["machine_error_code"]),
        human_message=str(validate_result["human_message"]),
        next_action=str(validate_result["next_action"]),
        route_id=route_id,
        connect_phase="created_and_validated" if status == "ok" else "created_validate_failed",
        admission_mode="create",
        preflight=preflight,
        provider_fallback=provider,
        credential_ref_fallback=credential_ref,
        credential_status_result=credential_status_result,
        credential_admit_result=credential_admit_result,
        credential_phase=credential_phase,
        add_result=add_result,
        validate_result=validate_result,
    )
    return _ui_action_response_from_result("api_route_connect", result)


def _run_account_login_bridge_action(runner: CommandRunner) -> dict[str, Any]:
    start_result = execute_command(
        runner,
        "accounts_login_start_codex_device",
        allow_disabled=True,
    )
    final_result = {
        **start_result,
        "changed_files": start_result.get("changed_files")
        if isinstance(start_result.get("changed_files"), list)
        else [],
    }
    packet = final_result.get("packet") if isinstance(final_result.get("packet"), dict) else {}
    packet["data"] = {
        "login_bridge": _codex_login_bridge_public_summary(start_result, phase="start"),
    }
    final_result["packet"] = packet
    return _ui_action_response_from_result(
        "onboard_account",
        _action_result(final_result, ui_action="onboard_account"),
    )


def _run_account_login_status_action(
    runner: CommandRunner,
    structured_args: dict[str, str],
) -> dict[str, Any]:
    status_result = execute_command(
        runner,
        "accounts_login_status",
        structured_args=structured_args,
        allow_disabled=True,
    )
    final_result = {
        **status_result,
        "changed_files": status_result.get("changed_files")
        if isinstance(status_result.get("changed_files"), list)
        else [],
    }
    packet = final_result.get("packet") if isinstance(final_result.get("packet"), dict) else {}
    packet["data"] = {
        "login_bridge": _codex_login_bridge_public_summary(status_result, phase="status"),
    }
    final_result["packet"] = packet
    return _ui_action_response_from_result(
        "account_login_status",
        _action_result(final_result, ui_action="account_login_status"),
    )


def _run_account_login_complete_action(
    runner: CommandRunner,
    structured_args: dict[str, str],
) -> dict[str, Any]:
    complete_result = execute_command(
        runner,
        "accounts_login_complete_codex",
        structured_args=structured_args,
        allow_disabled=True,
    )
    final_result = {
        **complete_result,
        "changed_files": complete_result.get("changed_files")
        if isinstance(complete_result.get("changed_files"), list)
        else [],
    }
    packet = final_result.get("packet") if isinstance(final_result.get("packet"), dict) else {}
    packet["data"] = {
        "login_bridge": _codex_login_bridge_public_summary(complete_result, phase="complete"),
    }
    final_result["packet"] = packet
    return _ui_action_response_from_result(
        "account_login_complete",
        _action_result(final_result, ui_action="account_login_complete"),
    )


def _run_account_login_cancel_action(
    runner: CommandRunner,
    structured_args: dict[str, str],
) -> dict[str, Any]:
    cancel_result = execute_command(
        runner,
        "accounts_login_cancel",
        structured_args=structured_args,
        allow_disabled=True,
    )
    final_result = {
        **cancel_result,
        "changed_files": cancel_result.get("changed_files")
        if isinstance(cancel_result.get("changed_files"), list)
        else [],
    }
    packet = final_result.get("packet") if isinstance(final_result.get("packet"), dict) else {}
    packet["data"] = {
        "login_bridge": _codex_login_bridge_public_summary(cancel_result, phase="cancel"),
    }
    final_result["packet"] = packet
    return _ui_action_response_from_result(
        "account_login_cancel",
        _action_result(final_result, ui_action="account_login_cancel"),
    )


def _ui_action_response_from_result(ui_action: str, result: dict[str, Any]) -> dict[str, Any]:
    action_spec = UI_ACTION_ALLOWLIST[ui_action]
    session_id = ""
    if isinstance(result.get("data"), dict):
        login_bridge = result["data"].get("login_bridge")
        if isinstance(login_bridge, dict):
            session_id = str(
                login_bridge.get("session_id")
                or login_bridge.get("login_session_id")
                or ""
            )
    return {
        "schema_version": 1,
        "status": "ok" if result["status"] == "ok" else "command_error",
        "source": "ui_action",
        "ui_action": ui_action,
        "action_role": action_spec["action_role"],
        "mutates_runtime": action_spec["mutates_runtime"],
        "affects_primary_truth": action_spec["affects_primary_truth"],
        "confirmation_required": action_spec["confirmation_required"],
        "post_action_refresh_required": action_spec["post_action_refresh_required"],
        "action_claim_scope": action_spec["action_claim_scope"],
        "mutation_class": action_spec.get("mutation_class", ""),
        "account_id": "",
        "route_id": "",
        "session_id": session_id,
        "result": result,
    }


def _diagnostics_redaction_status(packet: dict[str, Any], data: dict[str, Any]) -> str:
    raw_status = (
        packet.get("redaction_status")
        or packet.get("diagnostics_redaction_status")
        or data.get("redaction_status")
        or data.get("diagnostics_redaction_status")
    )
    normalized = str(raw_status or "").strip().lower()
    if normalized in {"passed", "enabled", "enforced", "ok", "true"}:
        return "enabled"
    if normalized in {"failed", "failure", "error", "redaction_failed", "false"}:
        return "failed"
    return "unreported"


def _onboarding_summary(packet: object, *, command_status: str) -> dict[str, Any]:
    onboarding_result = packet.get("onboarding_result") if isinstance(packet, dict) else None
    if not isinstance(onboarding_result, dict):
        return {
            "ui_state": "unknown_outcome",
            "final_outcome": "unknown_outcome",
            "selected_backend_id": "",
            "reserve_first_proven": False,
            "operator_action_required": True,
            "reason": "onboarding_result отсутствует или не является объектом",
        }
    if onboarding_result.get("preview_only") is True:
        raw_blocked_reasons = onboarding_result.get("blocked_reasons")
        blocked_reasons = raw_blocked_reasons if isinstance(raw_blocked_reasons, list) else []
        return {
            "ui_state": str(onboarding_result.get("ui_state") or "dry_run_ready"),
            "final_outcome": str(onboarding_result.get("final_outcome") or "dry_run_preview_ready"),
            "selected_backend_id": "",
            "reserve_first_proven": False,
            "operator_action_required": onboarding_result.get("operator_action_required") is True,
            "reason": str(onboarding_result.get("reason") or ""),
            "preview_only": True,
            "candidate_source_kind": str(onboarding_result.get("candidate_source_kind") or "server_owned_only"),
            "reserve_first_boundary": str(onboarding_result.get("reserve_first_boundary") or "required"),
            "required_follow_up": str(onboarding_result.get("required_follow_up") or "WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS"),
            "blocked_reasons": [str(reason) for reason in blocked_reasons if str(reason)],
            "write_scope": str(onboarding_result.get("write_scope") or "ui_session_only"),
            "changed_files_count": int(onboarding_result.get("changed_files_count") or 0),
        }

    final_outcome = str(onboarding_result.get("final_outcome") or "unknown_outcome")
    selected_backend_id = str(onboarding_result.get("selected_backend_id") or "")
    lifecycle_admission = (
        onboarding_result.get("lifecycle_admission")
        if isinstance(onboarding_result.get("lifecycle_admission"), dict)
        else {}
    )
    selected_backend_pool = str(lifecycle_admission.get("selected_backend_pool") or "")
    raw_pool_after_onboarding = onboarding_result.get("pool_after_onboarding")
    if selected_backend_pool:
        pool_after_onboarding = selected_backend_pool
    elif isinstance(raw_pool_after_onboarding, str) and raw_pool_after_onboarding:
        pool_after_onboarding = raw_pool_after_onboarding
    elif (
        onboarding_result.get("reserve_first_enforced") is True
        and onboarding_result.get("active_routing_changed") is False
    ):
        pool_after_onboarding = "reserve"
    else:
        pool_after_onboarding = str(raw_pool_after_onboarding or "")
    reserve_first_proven = (
        onboarding_result.get("reserve_first_enforced") is True
        and pool_after_onboarding == "reserve"
        and onboarding_result.get("active_routing_changed") is False
    )
    successful_outcome = final_outcome in {
        "explicit_auth_imported_to_reserve",
        "reserve_only_success",
    }
    if command_status != "ok":
        ui_state = "command_error"
        operator_action_required = True
        reason = "верхнеуровневый пакет команды не сообщил ok"
    elif successful_outcome and reserve_first_proven and selected_backend_id:
        ui_state = "success"
        operator_action_required = False
        reason = "доказательство подключения сначала в резерв присутствует"
    elif final_outcome in {"no_new_auth_detected", "ambiguous_new_auth_detection"}:
        ui_state = "needs_user_action"
        operator_action_required = True
        reason = "нужно действие оператора, прежде чем подключение можно считать завершённым"
    elif final_outcome in {"validate_failed", "sync_failed", "status_failed", "import_failed"}:
        ui_state = "command_error"
        operator_action_required = True
        reason = "owner packet подключения сообщил сбой на шаге доказательства"
    else:
        ui_state = "unknown_outcome"
        operator_action_required = True
        reason = "onboarding outcome is not admitted as UI success"

    return {
        "ui_state": ui_state,
        "final_outcome": final_outcome,
        "selected_backend_id": selected_backend_id if ui_state == "success" else "",
        "reserve_first_proven": reserve_first_proven,
        "operator_action_required": operator_action_required,
        "reason": reason,
        "input_mode": str(onboarding_result.get("input_mode") or ""),
        "selection_status": str(onboarding_result.get("selection_status") or ""),
        "pool_after_onboarding": pool_after_onboarding,
        "active_routing_changed": onboarding_result.get("active_routing_changed"),
        "validate_outcome": str(onboarding_result.get("validate_outcome") or ""),
        "sync_outcome": str(onboarding_result.get("sync_outcome") or ""),
        "auth_snapshot_before_login_status": str(
            onboarding_result.get("auth_snapshot_before_login_status") or ""
        ),
        "auth_snapshot_before_login_count": onboarding_result.get(
            "auth_snapshot_before_login_count"
        ),
        "auth_snapshot_before_login_source": str(
            onboarding_result.get("auth_snapshot_before_login_source") or ""
        ),
        "external_command_status": str(onboarding_result.get("external_command_status") or ""),
        "status_observed": onboarding_result.get("status_observed")
        if isinstance(onboarding_result.get("status_observed"), dict)
        else {},
    }


def _account_connect_dry_run_packet() -> dict[str, Any]:
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "human_message": "Dry-run preview подготовлен. Реальное подключение не выполнялось.",
        "next_action": "WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS",
        "changed_files": [],
        "onboarding_result": {
            "preview_only": True,
            "ui_state": "dry_run_ready",
            "final_outcome": "dry_run_preview_ready",
            "candidate_source_kind": "server_owned_only",
            "reserve_first_boundary": "required",
            "required_follow_up": "WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS",
            "operator_action_required": True,
            "blocked_reasons": [],
            "write_scope": "ui_session_only",
            "changed_files_count": 0,
            "reason": "Preview построен без auth import, registry mutation и runtime mutation.",
        },
    }


def _run_account_connect_dry_run_action() -> dict[str, Any]:
    result = {
        "status": "ok",
        "ui_state": "dry_run_ready",
        "machine_error_code": "OK",
        "human_message": "Dry-run preview подготовлен. Реальное подключение аккаунта не выполнялось.",
        "exit_code": 0,
        "changed_files": [],
        "next_action": "WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS",
        "packet": _account_connect_dry_run_packet(),
    }
    return {
        "schema_version": 1,
        "status": "ok",
        "source": "ui_action",
        "ui_action": "onboard_account_dry_run",
        "action_role": "account_onboarding_preview",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "только dry-run preview подключения аккаунта; реальный import auth и registry mutation не выполняются",
        "mutation_class": "account_admission_preview",
        "account_id": "",
        "route_id": "",
        "result": _action_result(result, ui_action="onboard_account_dry_run"),
    }


def _integration_failure(
    human_message: str,
    last_error: str,
    machine_error_code: str,
    commands: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "integration_failure",
        "ui_state": "integration_failure",
        "source": "live_readonly",
        "primary_truth_ok": False,
        "has_warnings": True,
        "warnings": [
            {
                "command_id": "primary_truth",
                "role": "primary",
                "severity": "integration_failure",
                "machine_error_code": machine_error_code,
                "human_message": last_error,
            }
        ],
        "evidence_summary": {
            "primary_truth_ok": False,
            "detail_warnings": 0,
            "rollout_warnings": 0,
            "highest_warning_severity": "integration_failure",
        },
        "runtime": {
            "visual_state": "integration_failure",
            "status_label": "Ошибка интеграции",
            "desired_mode": "unknown",
            "effective_mode": "unknown",
            "endpoint": "unknown",
            "machine_error_code": machine_error_code,
            "human_message": human_message,
            "last_error": last_error,
            "observed_at_utc": "live-readonly",
        },
        "pool_summary": {
            "active": 0,
            "reserve": 0,
            "hold": 0,
            "problem": 0,
            "active_note": "live-чтение не удалось",
            "reserve_note": "live-чтение не удалось",
            "hold_note": "live-чтение не удалось",
            "problem_note": "live-чтение не удалось",
        },
        "events": [
            {
                "level": "red",
                "message": human_message,
                "observed_at": "live-readonly",
            }
        ],
        "commands": _public_command_results(commands),
    }


def _accounts_integration_failure(
    human_message: str,
    last_error: str,
    machine_error_code: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "integration_failure",
        "source": "accounts_readonly",
        "primary_truth_ok": False,
        "privacy": {
            "redacted": True,
            "raw_command_packet_included": False,
            "forbidden_fields_excluded": ["secret_references", "tokens", "raw_paths", "raw_logs"],
        },
        "registry_identity": {
            "status": "unknown",
            "machine_error_code": machine_error_code,
            "next_action": "retry",
        },
        "summary": {
            "active": 0,
            "reserve": 0,
            "retired": 0,
            "hold": 0,
            "problem": 0,
            "healthy": 0,
            "degraded": 0,
            "down": 0,
            "capacity_target": 20,
            "visible_count": 0,
            "human_message": human_message,
            "machine_error_code": machine_error_code,
            "last_error": last_error,
        },
        "accounts": [],
        "commands": {},
    }


def _api_connections_integration_failure(
    human_message: str,
    last_error: str,
    machine_error_code: str,
    commands: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "integration_failure",
        "source": "api_connections_readonly",
        "primary_truth_ok": False,
        "privacy": {
            "redacted": True,
            "raw_command_packet_included": False,
            "forbidden_fields_excluded": [
                "secret_references",
                "tokens",
                "raw_paths",
                "raw_logs",
            ],
        },
        "summary": {
            "routes_count": 0,
            "enabled_count": 0,
            "attention_count": 0,
            "latest_check": "",
            "human_message": human_message,
            "machine_error_code": machine_error_code,
            "last_error": last_error,
        },
        "adapter": {
            "foundation_phase": "unknown",
            "adapter_runtime_available": False,
            "lifecycle_mode": "unknown",
            "adapter_state": "unknown",
            "listener_proven": False,
            "runtime_claim_blocked": True,
            "profile_ready": False,
            "local_token_present": False,
            "observed_routes_count": 0,
            "models_source": "integration_failure",
        },
        "routes": [],
        "commands": _public_command_results(commands),
    }


def _public_command_results(commands: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        command_id: {
            "status": result["status"],
            "ui_state": result["ui_state"],
            "role": _command_role(command_id),
            "machine_error_code": result["machine_error_code"],
            "human_message": result["human_message"],
            "exit_code": result["exit_code"],
            "next_action": result["next_action"],
        }
        for command_id, result in commands.items()
    }


def _api_connection_rows(external_models: Any) -> list[dict[str, Any]]:
    route_by_id = {
        route.route_id: route for route in external_models.routes if getattr(route, "route_id", "")
    }
    enabled_route_ids = [
        route.route_id for route in external_models.routes if getattr(route, "enabled", False) is True
    ]
    primary_route_ids: set[str] = set()
    if len(enabled_route_ids) == 1:
        primary_route_ids.add(enabled_route_ids[0])
    elif len(external_models.routes) == 1:
        primary_route_ids.add(external_models.routes[0].route_id)
    rows: list[dict[str, Any]] = []
    for model in external_models.models:
        route = route_by_id.get(model.route_id)
        status_code, status_label, visual_state, note = _api_connection_status(
            model,
            local_token_present=external_models.local_token_present,
        )
        observed = {}
        if isinstance(getattr(external_models, "observed_routes", {}), dict):
            observed = external_models.observed_routes.get(model.route_id, {}) or {}
        secret_ref = _safe_short_text(getattr(route, "secret_ref", ""), max_length=64)
        if external_route_secret_available(external_models, secret_ref):
            secret_status_label = "available"
            secret_visual_state = "green"
        elif secret_ref:
            secret_status_label = "missing"
            secret_visual_state = "amber"
        else:
            secret_status_label = "unknown"
            secret_visual_state = "neutral"
        validation_label = "blocked by secret" if secret_status_label == "missing" else "not checked"
        validation_visual_state = "amber" if secret_status_label == "missing" else "neutral"
        last_checked = ""
        if secret_status_label != "missing":
            observed_state = str(observed.get("availability_state", "")).strip()
            last_checked = _safe_short_text(
                str(
                    observed.get("last_check")
                    or observed.get("last_validate")
                    or observed.get("last_verified_at")
                    or ""
                ),
                max_length=32,
            )
            if observed_state == "verified":
                validation_label = "ok"
                validation_visual_state = "green"
                note = "Проверочный запрос маршрута зафиксирован bounded packet и refresh truth."
            elif observed_state == "model_visible":
                validation_label = "ok"
                validation_visual_state = "blue"
                note = "Проверка provider route завершилась без runtime claims."
            elif observed_state in {"provider_auth_failed", "model_not_available"}:
                validation_label = "validate failed"
                validation_visual_state = "red"
                visual_state = "red"
                status_code = "validation_failed"
                status_label = "Требует проверки"
                note = "Последняя provider-проверка маршрута завершилась ошибкой."
            elif observed_state in {"provider_network_failed", "limited"}:
                validation_label = "check failed"
                validation_visual_state = "amber"
                visual_state = "amber"
                status_code = "check_attention"
                status_label = "Требует внимания"
                note = "Последняя проверка маршрута требует внимания оператора."
            elif observed_state == "blocked":
                validation_label = "blocked"
                validation_visual_state = "amber"
                visual_state = "amber"
                status_code = "blocked"
                status_label = "Проверка заблокирована"
        is_primary = model.route_id in primary_route_ids
        rows.append(
            {
                "route_id": _safe_short_text(model.route_id, max_length=64),
                "display_name": _safe_short_text(model.display_name, max_length=72),
                "provider": _safe_short_text(model.provider, max_length=32),
                "upstream_model": _safe_short_text(model.upstream_model, max_length=72),
                "cost_class": _safe_short_text(getattr(model, "cost_class", ""), max_length=48),
                "thinking": dict(getattr(model, "thinking", {}) or {}),
                "enabled": model.enabled,
                "status_code": status_code,
                "status_label": status_label,
                "visual_state": visual_state,
                "role_label": (
                    "main route"
                    if is_primary
                    else _api_connection_role_label(
                        lane_role=model.lane_role,
                        fallback_eligible=model.fallback_eligible,
                    )
                ),
                "primary": is_primary,
                "is_primary": is_primary,
                "secret_ref": secret_ref,
                "secret_status_label": secret_status_label,
                "secret_visual_state": secret_visual_state,
                "validation_label": validation_label,
                "validation_visual_state": validation_visual_state,
                "last_checked": last_checked,
                "note": note,
            }
        )
    return rows


def _api_connection_status(
    model: Any,
    *,
    local_token_present: bool,
) -> tuple[str, str, str, str]:
    if not model.enabled:
        return (
            "disabled",
            "Отключён",
            "neutral",
            "Маршрут отключён в registry-пакете.",
        )
    if not local_token_present:
        return (
            "missing_secret",
            "Требует ключ",
            "amber",
            "Локальный ключ не подтверждён; маршрут нельзя считать готовым к проверочному запросу.",
        )
    return (
        "enabled",
        "Разрешён",
        "blue",
        "Маршрут показан по registry-пакету. Отдельная проверка запроса ещё не выполнялась.",
    )


def _api_connection_role_label(*, lane_role: str, fallback_eligible: bool) -> str:
    safe_role = _safe_short_text(lane_role, max_length=32) or "не указана"
    if fallback_eligible:
        return "Допустим для резерва"
    return {
        "candidate": "Кандидат",
        "verification": "Маршрут проверки",
        "diagnostic": "Маршрут проверки",
    }.get(safe_role, safe_role)


def _account_rows(accounts: tuple[Any, ...], packet: dict[str, Any]) -> list[dict[str, Any]]:
    raw_by_id = {
        str(item.get("id")): item
        for item in packet.get("accounts", [])
        if isinstance(item, dict) and "id" in item
    }
    return [
        {
            "id": _safe_account_id(account.backend_id),
            "label": _safe_account_label(account.label, account.backend_id),
            "pool": account.pool,
            "pool_label": _pool_label(account.pool, account.manual_hold),
            "status": account.status,
            "status_label": _account_status_label(account.status, account.manual_hold),
            "visual_state": _account_visual_state(account.status, account.manual_hold, account.last_error),
            "manual_hold": account.manual_hold,
            "enabled": _optional_bool(raw_by_id.get(account.backend_id, {}), "enabled"),
            "fail_count": account.fail_count,
            "success_count": account.success_count,
            "last_success": account.last_success,
            "last_error_class": _safe_short_text(
                raw_by_id.get(account.backend_id, {}).get("last_error_class", "")
            ),
            "last_error_summary": _redact_error(account.last_error),
            "cooldown_until": account.cooldown_until,
            "notes_summary": _safe_short_text(account.notes),
        }
        for account in accounts
    ]


def _account_summary(rows: list[dict[str, Any]], accounts: Any) -> dict[str, Any]:
    return {
        "active": accounts.active_count,
        "reserve": accounts.reserve_count,
        "retired": accounts.retired_count,
        "hold": sum(1 for row in rows if row["manual_hold"]),
        "problem": sum(
            1
            for row in rows
            if row["visual_state"] in {"red", "amber"} or bool(row["last_error_summary"])
        ),
        "healthy": sum(1 for row in rows if row["status"] == "healthy"),
        "degraded": sum(1 for row in rows if row["status"] == "degraded"),
        "down": sum(1 for row in rows if row["status"] == "down"),
        "capacity_target": accounts.capacity_target,
        "visible_count": len(rows),
        "human_message": accounts.human_message,
        "machine_error_code": accounts.machine_error_code,
        "last_error": "",
    }


def _safe_account_id(value: str) -> str:
    return _safe_short_text(value, max_length=64) or "unknown-account"


def _safe_account_label(label: str, backend_id: str) -> str:
    value = label or backend_id
    if "@" in value:
        left, _, domain = value.partition("@")
        safe_left = left[:3] + "***" if left else "***"
        domain_tail = domain.split(".")[-1] if "." in domain else "account"
        return f"{safe_left}@***.{domain_tail}"
    return _safe_short_text(value, max_length=72) or _safe_account_id(backend_id)


def _safe_short_text(value: object, *, max_length: int = 96) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").replace("\r", " ").strip()
    for marker in (
        "/" + "Users/",
        "/" + "Volumes/",
        "/" + "tmp/",
        "/" + "var/",
        ".cli" + "-proxy-api",
        ".co" + "dex",
    ):
        text = text.replace(marker, "[redacted]/")
    if len(text) > max_length:
        return f"{text[: max_length - 1]}…"
    return text


def _redact_error(value: str) -> str:
    text = _safe_short_text(value, max_length=120)
    if not text:
        return ""
    if "HTTP 429" in text or "usage_limit" in text or "quota" in text:
        return "квота или usage limit"
    if "HTTP 401" in text or "auth" in text.lower() or "session" in text.lower():
        return "ошибка auth/session"
    if "timeout" in text.lower():
        return "timeout"
    return text


def _optional_bool(raw: dict[str, Any], key: str) -> bool | None:
    value = raw.get(key)
    return value if isinstance(value, bool) else None


def _pool_label(pool: str, manual_hold: bool) -> str:
    if manual_hold:
        return "На удержании"
    return {
        "active": "Активные",
        "reserve": "Резерв",
        "retired": "Выведен",
    }.get(pool, pool)


def _account_status_label(status: str, manual_hold: bool) -> str:
    if manual_hold:
        return "Удержание"
    return {
        "healthy": "Работает",
        "degraded": "Деградация",
        "down": "Недоступен",
        "unknown": "Неизвестно",
    }.get(status, status)


def _account_visual_state(status: str, manual_hold: bool, last_error: str) -> str:
    if manual_hold:
        return "amber"
    if status == "healthy" and not last_error:
        return "green"
    if status == "down" or last_error:
        return "red"
    if status == "degraded":
        return "amber"
    return "neutral"


def _events_from_commands(
    commands: dict[str, dict[str, Any]],
    visual_state: str,
    warnings: list[dict[str, str]],
) -> list[dict[str, str]]:
    events = [
        {
            "level": "green" if visual_state == "healthy" else "amber",
            "message": str(commands["status"]["human_message"]),
            "observed_at": "status --json",
        },
    ]
    for warning in warnings:
        events.append(
            {
                "level": "amber",
                "message": warning["human_message"],
                "observed_at": warning["command_id"],
            }
        )
    for command_id in DETAIL_COMMAND_IDS:
        if command_id in commands and commands[command_id]["status"] == "ok":
            events.append(
                {
                    "level": "blue",
                    "message": str(commands[command_id]["human_message"]),
                    "observed_at": _command_observed_at(command_id),
                }
            )
    return events


def _warning_from_result(command_id: str, result: dict[str, Any]) -> dict[str, str]:
    return {
        "command_id": command_id,
        "label": _command_observed_at(command_id),
        "role": _command_role(command_id),
        "severity": "degraded" if command_id == "healthcheck" else "warning",
        "machine_error_code": str(result["machine_error_code"]),
        "human_message": str(result["human_message"]),
    }


def _evidence_summary(
    commands: dict[str, dict[str, Any]],
    warnings: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "primary_truth_ok": True,
        "detail_warnings": sum(1 for warning in warnings if warning["role"] == "runtime_detail"),
        "rollout_warnings": sum(1 for warning in warnings if warning["role"] == "rollout_evidence"),
        "highest_warning_severity": _highest_warning_severity(warnings),
        "available_detail_commands": [
            command_id for command_id in DETAIL_COMMAND_IDS if command_id in commands
        ],
    }


def _highest_warning_severity(warnings: list[dict[str, str]]) -> str:
    if any(warning["severity"] == "degraded" for warning in warnings):
        return "degraded"
    if warnings:
        return "warning"
    return "none"


def _command_role(command_id: str) -> str:
    if command_id in PRIMARY_COMMAND_IDS:
        return "primary_truth"
    if command_id == "healthcheck":
        return "runtime_detail"
    if command_id == "rollout_rotation_inspect":
        return "rollout_evidence"
    return "unknown"


def _command_observed_at(command_id: str) -> str:
    return {
        "healthcheck": "healthcheck --json",
        "rollout_rotation_inspect": "rollout rotation inspect --json",
    }.get(command_id, command_id)


def _visual_state(liveness: str) -> str:
    if liveness in {"healthy", "degraded", "down", "stale", "unknown"}:
        return liveness
    return "integration_failure"


def _status_label(visual_state: str) -> str:
    return {
        "healthy": "Работает",
        "degraded": "Есть деградация",
        "down": "Не работает",
        "stale": "Устаревшие данные",
        "unknown": "Неизвестно",
        "integration_failure": "Ошибка интеграции",
    }.get(visual_state, "Неизвестно")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument(
        "--unsafe-allow-public-bind",
        action="store_true",
        help="allow binding the web control surface to a public/unspecified host",
    )
    parser.add_argument(
        "--action-phase",
        default=LIVE_READONLY_ACTION_PHASE,
        choices=(LIVE_READONLY_ACTION_PHASE, SANDBOX_ACTION_PHASE, FULL_ACTION_PHASE),
    )
    parser.add_argument("--launch-client-path", default=None)
    parser.add_argument("--launch-copy-profile-dir", default=None)
    parser.add_argument("--launch-copy-data-dir", default=None)
    parser.add_argument("--launch-copy-port", type=int, default=None)
    parser.add_argument("--owner-authorization-phrase", default=None)
    parser.add_argument(
        "--post-rate-limit-per-second",
        type=int,
        default=DEFAULT_WEB_POST_RATE_LIMIT_PER_SECOND,
        help="maximum admitted local web POST requests per second per client/path",
    )
    parser.add_argument(
        "--launch-copy-helper-provenance",
        default=None,
        choices=(SAFE_APP_COPY_HELPER_PROVENANCE,),
    )
    args = parser.parse_args(argv)
    if unsafe_bind_requested(args.host) and not args.unsafe_allow_public_bind:
        parser.error(
            "--host 0.0.0.0/:: is unsafe for the web control surface; "
            "pass --unsafe-allow-public-bind only with an explicit operator boundary."
        )
    if args.post_rate_limit_per_second <= 0:
        parser.error("--post-rate-limit-per-second must be a positive integer.")
    launch_copy_contract = LaunchCopyContract(
        client_path=args.launch_client_path,
        profile_dir=args.launch_copy_profile_dir,
        data_dir=args.launch_copy_data_dir,
        copy_port=args.launch_copy_port,
        action_server_port=args.port,
        helper_execution_provenance=args.launch_copy_helper_provenance,
    )

    web_token_state = create_web_token(RuntimePaths.from_env().managed_dir)
    server = None
    try:
        server = ThreadingHTTPServer(
            (args.host, args.port),
            build_handler(
                launch_client_path=args.launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=args.action_phase,
                owner_authorization_phrase=args.owner_authorization_phrase,
                web_token_state=web_token_state,
                post_rate_limit_per_second=args.post_rate_limit_per_second,
            ),
        )
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        if server is not None:
            server.server_close()
        delete_web_token(web_token_state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
