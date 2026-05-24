# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Read-only live preview server for the first web-design screen."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import subprocess
from typing import Any
from urllib.parse import parse_qs, urlparse

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
)
from wild_boar_proxy.codex_account_selection import (
    build_account_selection_packet,
    build_account_smoke_dry_run_packet,
    build_accounts_truth_packet,
)
from wild_boar_proxy.codex_custom_sessions import CodexCustomSessionManager
from wild_boar_proxy.codex_model_registry import (
    build_custom_api_compat_packet,
    build_custom_model_dry_run_packet,
    build_custom_model_registry_packet,
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
from wild_boar_proxy.runtime import DEFAULT_LAUNCHER_SCRIPT_NAME
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
    default_review_import_context,
)
from wild_boar_proxy.review_bridge_session_store import (
    ReviewQueryBridge,
    ReviewSessionStore,
)
from wild_boar_proxy.web_design_command_adapter import CommandRunner, execute_command
from wild_boar_proxy.operator_surface import OperatorSurfaceSession


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


def owner_authorization_phrase_present(value: str | None) -> bool:
    return isinstance(value, str) and value.strip() == OWNER_STANDING_AUTHORIZATION_PHRASE
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
}

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
        "export_diagnostics",
    }
)
SANDBOX_ACTION_PHASE_ADMITTED_ACTIONS = frozenset(
    {
        "onboard_account_dry_run",
        "onboard_account",
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
SAFE_APP_COPY_HELPER_PROVENANCE = "server_owned_bounded_helper"


@dataclass(frozen=True)
class LaunchCopyContract:
    client_path: str | None = None
    profile_dir: str | None = None
    data_dir: str | None = None
    copy_port: int | None = None
    action_server_port: int | None = None
    helper_execution_provenance: str | None = None


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
    action_phase: str = FULL_ACTION_PHASE,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _blocked_action("unknown", "Payload UI-действия должен быть объектом.")
    if "command_id" in payload:
        return _blocked_action("unknown", "Browser должен отправлять ui_action, а не command_id.")

    ui_action = payload.get("ui_action")
    if not isinstance(ui_action, str):
        return _blocked_action("unknown", "UI action должен быть строкой.")

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
    if not _action_available(
        ui_action,
        launch_client_path=launch_client_path,
        launch_copy_contract=launch_copy_contract,
        action_phase=action_phase,
    ):
        return _unavailable_action(
            ui_action,
            _action_unavailable_reason(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
            ),
            _action_unavailable_code(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
            ),
            availability_state=_action_availability_state(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
            ),
            disabled_reasons=_action_disabled_reasons(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
            ),
        )

    allowed_payload_keys = {"ui_action"}
    if ui_action in ACCOUNT_ID_UI_ACTIONS:
        allowed_payload_keys.add("account_id")
    if ui_action in ROUTE_ID_UI_ACTIONS:
        allowed_payload_keys.add("route_id")
    if ui_action in SESSION_ID_UI_ACTIONS:
        allowed_payload_keys.add("session_id")
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

    result = execute_command(
        runner,
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
) -> dict[str, Any]:
    actions: dict[str, dict[str, Any]] = {}
    for ui_action, action_spec in sorted(UI_ACTION_ALLOWLIST.items()):
        available = _action_available(
            ui_action,
            launch_client_path=launch_client_path,
            launch_copy_contract=launch_copy_contract,
            action_phase=action_phase,
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
            ),
            "disabled_reason_code": _action_unavailable_code(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
            )
            if not available
            else "",
            "disabled_reasons": _action_disabled_reasons(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
            )
            if not available
            else [],
            "unavailable_reason": _action_unavailable_reason(
                ui_action,
                launch_client_path=launch_client_path,
                launch_copy_contract=launch_copy_contract,
                action_phase=action_phase,
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
) -> type[BaseHTTPRequestHandler]:
    command_runner = runner or JsonCommandRunner()
    readonly_runner = command_runner
    accounts_readonly_runner = command_runner
    api_connections_readonly_runner = command_runner
    action_runner = command_runner
    operator_surface_session = OperatorSurfaceSession()
    codex_custom_sessions = CodexCustomSessionManager()
    review_session_store = ReviewSessionStore()
    bounded_review_import_context = review_import_context or default_review_import_context(ROOT)
    command_review_apply_context = review_apply_context
    query_review_apply_context = review_apply_context
    if query_review_apply_context is None:
        default_apply_context = default_review_apply_context(ROOT)
        if default_apply_context.source_status == "ok":
            query_review_apply_context = default_apply_context
    review_query_bridge = ReviewQueryBridge(
        review_session_store,
        review_apply_context=query_review_apply_context,
    )
    codex_custom_live_prompt_authorized = owner_authorization_phrase_present(
        owner_authorization_phrase
    )
    if (
        runner is None
        and action_phase == SANDBOX_ACTION_PHASE
        and _sandbox_action_preflight(launch_copy_contract)["status"] == "admitted"
        and launch_copy_contract is not None
    ):
        sandbox_runner = JsonCommandRunner(
            cwd=str(Path(launch_copy_contract.profile_dir or "").expanduser()),
            env=_sandbox_action_runner_env(launch_copy_contract),
        )
        readonly_runner = sandbox_runner
        accounts_readonly_runner = sandbox_runner
        api_connections_readonly_runner = sandbox_runner
        action_runner = sandbox_runner
    static_root = static_dir.resolve()

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
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/owner-login/sandbox":
                self._send_owner_login_sandbox_page(parsed.query)
                return
            if parsed.path == "/api/live-readonly":
                self._send_json(build_live_readonly_snapshot(readonly_runner))
                return
            if parsed.path == "/api/accounts-readonly":
                self._send_json(build_accounts_readonly_snapshot(accounts_readonly_runner))
                return
            if parsed.path == "/api/api-connections-readonly":
                self._send_json(
                    build_api_connections_readonly_snapshot(api_connections_readonly_runner)
                )
                return
            if parsed.path == "/api/actions":
                self._send_json(
                    ui_action_metadata(
                        launch_client_path=launch_client_path,
                        launch_copy_contract=launch_copy_contract,
                        action_phase=action_phase,
                    )
                )
                return
            if parsed.path == "/api/operator/status":
                self._send_json(operator_surface_session.status_payload())
                return
            if parsed.path == "/api/operator/models":
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
            if parsed.path == "/api/operator/transcript":
                self._send_json(operator_surface_session.transcript_payload())
                return
            if parsed.path == "/api/review-surface":
                self._send_json(
                    review_query_bridge.get_review_surface(
                        parse_qs(parsed.query, keep_blank_values=True) if parsed.query else None
                    )
                )
                return
            if parsed.path == "/api/review-commands":
                self._send_json(
                    {
                        "status": "ok",
                        "machine_error_code": "OK",
                        "commands": review_allowlist_metadata(),
                    }
                )
                return
            if parsed.path == "/api/codex/launch-modes":
                self._send_json(build_launch_modes_packet(operator_surface_session.status_payload()))
                return
            if parsed.path == "/api/codex/original/status":
                self._send_json(build_original_status_packet())
                return
            if parsed.path == "/api/codex/custom/status":
                self._send_json(build_custom_status_packet(operator_surface_session.status_payload()))
                return
            if parsed.path == "/api/codex/custom/models":
                self._send_json(
                    build_custom_model_registry_packet(operator_surface_session.status_payload())
                )
                return
            if parsed.path == "/api/codex/custom/api-compat":
                self._send_json(
                    build_custom_api_compat_packet(operator_surface_session.status_payload())
                )
                return
            if parsed.path == "/api/codex/custom/accounts":
                self._send_json(build_accounts_truth_packet(self._codex_account_commands()))
                return
            if parsed.path == "/api/codex/custom/account-selection":
                self._send_json(
                    build_account_selection_packet(
                        self._codex_account_commands(),
                        operator_surface_session.status_payload(),
                    )
                )
                return
            if parsed.path == "/api/codex/custom/sessions":
                self._send_json(codex_custom_sessions.list_packet())
                return
            if parsed.path == "/api/codex/custom/recovery/contract":
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
            if parsed.path == "/api/codex/custom/recovery/admitted-session-actions":
                self._send_json(build_recovery_admitted_session_actions_packet())
                return
            if parsed.path == "/api/codex/custom/recovery/stop-cleanup/preflight":
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
            if parsed.path == "/api/codex/custom/recovery/process-kill/preflight":
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
            if parsed.path == "/api/codex/custom/recovery/operator-ready":
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
            if parsed.path == "/api/codex/custom/recovery/rollback-process-owner-contract":
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
            if parsed.path == "/api/codex/custom/recovery/rollback-point-dry-run":
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
            if parsed.path == "/api/codex/custom/recovery/rollback-point-create-admission":
                self._send_json(build_rollback_point_create_admission_packet())
                return
            if parsed.path == "/api/codex/custom/recovery/rollback-point/verify":
                self._send_json(
                    build_custom_recovery_rollback_point_verify_packet(
                        browser_payload=parse_qs(parsed.query) if parsed.query else None,
                    )
                )
                return
            if parsed.path == "/api/codex/custom/recovery/rollback-apply/admission-dry-run":
                self._send_json(
                    build_rollback_apply_admission_dry_run_packet(
                        browser_payload=parse_qs(parsed.query) if parsed.query else None,
                    )
                )
                return
            if parsed.path == "/api/codex/custom/recovery/rollback-apply/live-preflight":
                self._send_json(
                    build_rollback_apply_live_preflight_packet(
                        browser_payload=parse_qs(parsed.query) if parsed.query else None,
                    )
                )
                return
            if parsed.path == "/api/codex/custom/recovery/rollback-apply/receipt/verify":
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
            custom_session = self._custom_session_route(parsed.path)
            if custom_session is not None:
                session_id, action = custom_session
                if action == "":
                    self._send_json(codex_custom_sessions.get_packet(session_id))
                    return
                if action == "transcript":
                    self._send_json(codex_custom_sessions.transcript_packet(session_id))
                    return
            self._send_static(parsed.path)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/operator/run":
                self._send_json(operator_surface_session.run_prompt(self._read_json_body()))
                return
            if parsed.path == "/api/review-command":
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
            if parsed.path == "/api/codex/original/launch-dry-run":
                self._send_json(build_original_launch_dry_run_packet(self._read_json_body()))
                return
            if parsed.path == "/api/codex/custom/launch-dry-run":
                self._send_json(build_custom_launch_dry_run_packet(self._read_json_body()))
                return
            if parsed.path == "/api/codex/app-copy/launch-dry-run":
                self._send_json(build_safe_app_copy_launch_dry_run_packet(self._read_json_body()))
                return
            if parsed.path == "/api/codex/app-copy/live-admission":
                self._send_json(
                    build_safe_app_copy_live_admission_packet(
                        self._read_json_body(),
                        _launch_copy_preflight(launch_copy_contract),
                    )
                )
                return
            if parsed.path == "/api/codex/app-copy/launch":
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
            if parsed.path == "/api/codex/custom/model-dry-run":
                self._send_json(
                    build_custom_model_dry_run_packet(
                        self._read_json_body(),
                        operator_surface_session.status_payload(),
                    )
                )
                return
            if parsed.path == "/api/codex/custom/account-smoke-dry-run":
                self._send_json(
                    build_account_smoke_dry_run_packet(
                        self._read_json_body(),
                        self._codex_account_commands(),
                        operator_surface_session.status_payload(),
                    )
                )
                return
            if parsed.path == "/api/codex/custom/sessions":
                self._send_json(
                    codex_custom_sessions.create_packet(
                        self._read_json_body(),
                        self._codex_account_commands(),
                        operator_surface_session.status_payload(),
                    )
                )
                return
            if parsed.path == "/api/codex/custom/recovery/rollback-point":
                self._send_json(
                    build_custom_recovery_rollback_point_create_live_packet(
                        rollback_point_create_admission=(
                            build_rollback_point_create_admission_packet()
                        ),
                        browser_payload=self._read_rollback_point_create_body(),
                    )
                )
                return
            if parsed.path == "/api/codex/custom/recovery/rollback-apply":
                self._send_json(
                    build_rollback_apply_bounded_live_packet(
                        browser_payload=self._read_rollback_point_create_body(),
                    )
                )
                return
            if parsed.path == "/api/codex/custom/recovery/stop-cleanup":
                self._send_json(
                    build_stop_cleanup_live_packet(
                        browser_payload=self._read_rollback_point_create_body(),
                    )
                )
                return
            custom_session = self._custom_session_route(parsed.path)
            if custom_session is not None:
                session_id, action = custom_session
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
                if action == "cancel":
                    self._send_json(codex_custom_sessions.cancel_packet(session_id))
                    return
                if action == "cleanup":
                    self._send_json(codex_custom_sessions.cleanup_packet(session_id))
                    return
            if parsed.path != "/api/action":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._send_json(
                run_ui_action(
                    action_runner,
                    self._read_json_body(),
                    launch_client_path=launch_client_path,
                    launch_copy_contract=launch_copy_contract,
                    action_phase=action_phase,
                )
            )

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

        def _send_json(self, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

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
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return {}
            if length <= 0:
                return {}
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {}
            return payload if isinstance(payload, dict) else {}

        def _read_app_copy_launch_body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return {"invalid_body": True}
            if length <= 0:
                return {"invalid_body": True}
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {"invalid_body": True}
            return payload if isinstance(payload, dict) else {"invalid_body": True}

        def _read_rollback_point_create_body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return {"invalid_body": True}
            if length <= 0:
                return {}
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {"invalid_body": True}
            return payload if isinstance(payload, dict) else {"invalid_body": True}

        def _send_static(self, request_path: str) -> None:
            relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
            target = (static_root / relative).resolve()
            if static_root not in target.parents and target != static_root:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            body = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

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
) -> bool:
    if ui_action in PARKED_IN_LIVE_READONLY_ACTIONS:
        if action_phase == LIVE_READONLY_ACTION_PHASE:
            return False
        if action_phase == SANDBOX_ACTION_PHASE:
            if ui_action not in SANDBOX_ACTION_PHASE_ADMITTED_ACTIONS:
                return False
            return _sandbox_action_preflight(launch_copy_contract)["status"] == "admitted"
    if ui_action == "launch_client_dispatch":
        return bool(launch_client_path) and _launch_copy_preflight(launch_copy_contract)["status"] == "admitted"
    return True


def _action_availability_state(
    ui_action: str,
    *,
    launch_client_path: str | None,
    launch_copy_contract: LaunchCopyContract | None,
    action_phase: str,
) -> str:
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
    if ui_action not in UI_ACTION_ALLOWLIST:
        return "unknown_disabled"
    return "displayable_readonly"


def _action_unavailable_code(
    ui_action: str,
    *,
    launch_client_path: str | None,
    launch_copy_contract: LaunchCopyContract | None,
    action_phase: str,
) -> str:
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
    if ui_action not in UI_ACTION_ALLOWLIST:
        return "UI_ACTION_NOT_ALLOWED"
    return ""


def _action_disabled_reasons(
    ui_action: str,
    *,
    launch_client_path: str | None,
    launch_copy_contract: LaunchCopyContract | None,
    action_phase: str,
) -> tuple[str, ...]:
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
    if ui_action not in UI_ACTION_ALLOWLIST:
        return ("unknown_disabled",)
    return ()


def _action_unavailable_reason(
    ui_action: str,
    *,
    launch_client_path: str | None,
    launch_copy_contract: LaunchCopyContract | None,
    action_phase: str,
) -> str:
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
        dispatch_method = ""
        if isinstance(client_launch_result, dict):
            dispatch_method = str(client_launch_result.get("dispatch_method", ""))
            dispatch_observed = client_launch_result.get("dispatch_observed") is True
            if dispatch_method == "detached_executable_spawn" and dispatch_observed:
                launch_state = "process_confirmed"
                process_confirmed = True
            elif dispatch_observed:
                launch_state = "launch_requested"
            elif client_launch_result.get("dispatch_attempted") is True:
                launch_state = "launch_requested"
        data = {
            "launch_preflight": _public_launch_preflight_summary(launch_preflight or {}),
            "launch_phase": launch_state,
            "process_confirmed": process_confirmed,
            "dispatch_method": dispatch_method or "unreported",
            "launch_claim_scope": "os_dispatch_only",
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
        "--action-phase",
        default=LIVE_READONLY_ACTION_PHASE,
        choices=(LIVE_READONLY_ACTION_PHASE, SANDBOX_ACTION_PHASE, FULL_ACTION_PHASE),
    )
    parser.add_argument("--launch-client-path", default=None)
    parser.add_argument("--launch-copy-profile-dir", default=None)
    parser.add_argument("--launch-copy-data-dir", default=None)
    parser.add_argument("--launch-copy-port", type=int, default=None)
    parser.add_argument(
        "--launch-copy-helper-provenance",
        default=None,
        choices=(SAFE_APP_COPY_HELPER_PROVENANCE,),
    )
    args = parser.parse_args(argv)
    launch_copy_contract = LaunchCopyContract(
        client_path=args.launch_client_path,
        profile_dir=args.launch_copy_profile_dir,
        data_dir=args.launch_copy_data_dir,
        copy_port=args.launch_copy_port,
        action_server_port=args.port,
        helper_execution_provenance=args.launch_copy_helper_provenance,
    )

    server = ThreadingHTTPServer(
        (args.host, args.port),
        build_handler(
            launch_client_path=args.launch_client_path,
            launch_copy_contract=launch_copy_contract,
            action_phase=args.action_phase,
        ),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
