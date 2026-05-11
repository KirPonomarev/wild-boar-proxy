# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import html
import json
import subprocess
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs

from .ui_shell import (
    AccountPoolSnapshot,
    ExternalActionResult,
    ExternalModelsSnapshot,
    JsonCommandRunner,
    RuntimeSnapshot,
    UiShellError,
    build_external_action_result,
    load_account_pool_snapshot,
    load_external_models_snapshot,
    load_runtime_snapshot,
    run_account_mutation_and_refresh,
    run_account_onboard_and_refresh,
    run_account_validate_and_refresh,
    run_diagnostics_export_and_refresh,
    run_launch_client_and_refresh,
    run_mode_control_and_refresh,
    run_smoke_and_refresh,
    run_stable_repair_and_refresh,
    run_sync_and_refresh,
)


@dataclass(frozen=True)
class DashboardState:
    runtime: RuntimeSnapshot
    accounts: AccountPoolSnapshot
    external_models: ExternalModelsSnapshot
    flash: str = ""
    external_action: ExternalActionResult | None = None
    events: tuple["UiEvent", ...] = ()


@dataclass(frozen=True)
class UiEvent:
    observed_at: str
    request: str
    outcome: str


def _integration_state(message: str, *, flash: str) -> DashboardState:
    return DashboardState(
        runtime=RuntimeSnapshot.integration_failure(message),
        accounts=AccountPoolSnapshot.integration_failure(message),
        external_models=ExternalModelsSnapshot.integration_failure(message),
        flash=flash,
    )


def _with_events(state: DashboardState, events: tuple[UiEvent, ...]) -> DashboardState:
    return DashboardState(
        runtime=state.runtime,
        accounts=state.accounts,
        external_models=state.external_models,
        flash=state.flash,
        external_action=state.external_action,
        events=events,
    )


def load_dashboard_state(
    runner: JsonCommandRunner,
    *,
    flash: str = "",
    external_action: ExternalActionResult | None = None,
) -> DashboardState:
    try:
        runtime = load_runtime_snapshot(runner)
        accounts = load_account_pool_snapshot(runner)
        external_models = load_external_models_snapshot(runner)
    except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
        return _integration_state(str(exc), flash=flash or "Не удалось обновить панель управления.")
    return DashboardState(
        runtime=runtime,
        accounts=accounts,
        external_models=external_models,
        flash=flash or runtime.human_message,
        external_action=external_action,
    )


def _action_flash(payload: dict[str, Any]) -> str:
    message = str(payload.get("human_message", "Action completed."))
    machine_error = str(payload.get("machine_error_code", ""))
    if machine_error and machine_error != "OK":
        return f"{message} [{machine_error}]"
    return message


def apply_action(
    runner: JsonCommandRunner,
    fields: dict[str, str],
    *,
    current_external_action: ExternalActionResult | None = None,
) -> DashboardState:
    action = fields.get("action", "").strip()
    if not action:
        return load_dashboard_state(runner, flash="Действие не указано.")
    try:
        if action == "mode_stable":
            payload, runtime = run_mode_control_and_refresh(
                runner, ("mode", "set", "stable", "--json")
            )
            accounts = load_account_pool_snapshot(runner)
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=runtime,
                accounts=accounts,
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=current_external_action,
            )
        if action == "mode_managed":
            payload, runtime = run_mode_control_and_refresh(
                runner, ("mode", "set", "managed", "--json")
            )
            accounts = load_account_pool_snapshot(runner)
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=runtime,
                accounts=accounts,
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=current_external_action,
            )
        if action == "sync":
            payload, runtime, accounts = run_sync_and_refresh(runner)
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=runtime,
                accounts=accounts,
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=current_external_action,
            )
        if action == "smoke":
            payload, runtime = run_smoke_and_refresh(runner)
            accounts = load_account_pool_snapshot(runner)
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=runtime,
                accounts=accounts,
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=current_external_action,
            )
        if action == "stable_repair":
            payload, runtime, accounts = run_stable_repair_and_refresh(runner)
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=runtime,
                accounts=accounts,
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=current_external_action,
            )
        if action == "diagnostics":
            payload, runtime, accounts = run_diagnostics_export_and_refresh(runner)
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=runtime,
                accounts=accounts,
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=current_external_action,
            )
        if action == "launch_client":
            client_path = fields.get("client_path", "").strip()
            if not client_path:
                return load_dashboard_state(
                    runner,
                    flash="Нужен абсолютный путь к клиенту.",
                    external_action=current_external_action,
                )
            payload, runtime = run_launch_client_and_refresh(
                runner,
                ("launch", "client", "--client-path", client_path, "--json"),
            )
            accounts = load_account_pool_snapshot(runner)
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=runtime,
                accounts=accounts,
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=current_external_action,
            )
        if action == "onboard":
            auth_ref = fields.get("auth_ref", "").strip()
            if not auth_ref:
                return load_dashboard_state(
                    runner,
                    flash="Нужен явный путь к auth-файлу.",
                    external_action=current_external_action,
                )
            payload, runtime, accounts = run_account_onboard_and_refresh(
                runner,
                ("accounts", "onboard", "--json", "--auth-ref", auth_ref, "--non-interactive"),
            )
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=runtime,
                accounts=accounts,
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=current_external_action,
            )
        route_id = fields.get("route_id", "").strip()
        if action == "external_route_enable":
            if not route_id:
                return load_dashboard_state(
                    runner,
                    flash="Нужен route_id для external-models.",
                    external_action=current_external_action,
                )
            payload = runner.run(
                "external-models", "routes", "enable", "--json", "--route", route_id
            ).payload
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=load_runtime_snapshot(runner),
                accounts=load_account_pool_snapshot(runner),
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=build_external_action_result(
                    action="external_route_enable",
                    action_payload=payload,
                ),
            )
        if action == "external_route_disable":
            if not route_id:
                return load_dashboard_state(
                    runner,
                    flash="Нужен route_id для external-models.",
                    external_action=current_external_action,
                )
            payload = runner.run(
                "external-models", "routes", "disable", "--json", "--route", route_id
            ).payload
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=load_runtime_snapshot(runner),
                accounts=load_account_pool_snapshot(runner),
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=build_external_action_result(
                    action="external_route_disable",
                    action_payload=payload,
                ),
            )
        if action == "external_validate":
            if not route_id:
                return load_dashboard_state(
                    runner,
                    flash="Нужен route_id для external-models.",
                    external_action=current_external_action,
                )
            payload = runner.run(
                "external-models", "routes", "validate", "--json", "--route", route_id
            ).payload
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=load_runtime_snapshot(runner),
                accounts=load_account_pool_snapshot(runner),
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=build_external_action_result(
                    action="external_validate",
                    action_payload=payload,
                ),
            )
        if action == "external_check":
            if not route_id:
                return load_dashboard_state(
                    runner,
                    flash="Нужен route_id для external-models.",
                    external_action=current_external_action,
                )
            payload = runner.run(
                "external-models", "check", "--json", "--route", route_id
            ).payload
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=load_runtime_snapshot(runner),
                accounts=load_account_pool_snapshot(runner),
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=build_external_action_result(
                    action="external_check",
                    action_payload=payload,
                ),
            )
        if action == "external_profile":
            if not route_id:
                return load_dashboard_state(
                    runner,
                    flash="Нужен route_id для external-models.",
                    external_action=current_external_action,
                )
            payload = runner.run(
                "external-models",
                "profile",
                "codex-desktop",
                "--json",
                "--route",
                route_id,
            ).payload
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=load_runtime_snapshot(runner),
                accounts=load_account_pool_snapshot(runner),
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=build_external_action_result(
                    action="external_profile",
                    action_payload=payload,
                ),
            )
        if action == "external_evidence":
            if not route_id:
                return load_dashboard_state(
                    runner,
                    flash="Нужен route_id для external-models.",
                    external_action=current_external_action,
                )
            payload = runner.run(
                "external-models", "evidence", "capture", "--json", "--route", route_id
            ).payload
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=load_runtime_snapshot(runner),
                accounts=load_account_pool_snapshot(runner),
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=build_external_action_result(
                    action="external_evidence",
                    action_payload=payload,
                ),
            )

        backend_id = fields.get("backend_id", "").strip()
        if not backend_id:
            return load_dashboard_state(
                runner,
                flash="Нужен идентификатор backend-а.",
                external_action=current_external_action,
            )
        if action in {"validate", "recheck"}:
            payload, accounts = run_account_validate_and_refresh(runner, backend_id)
            runtime = load_runtime_snapshot(runner)
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=runtime,
                accounts=accounts,
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=current_external_action,
            )
        if action == "promote":
            payload, runtime, accounts = run_account_mutation_and_refresh(
                runner, ("accounts", "promote", backend_id, "--json")
            )
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=runtime,
                accounts=accounts,
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=current_external_action,
            )
        if action == "demote":
            payload, runtime, accounts = run_account_mutation_and_refresh(
                runner, ("accounts", "demote", backend_id, "--json")
            )
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=runtime,
                accounts=accounts,
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=current_external_action,
            )
        if action == "hold":
            payload, runtime, accounts = run_account_mutation_and_refresh(
                runner, ("accounts", "hold", backend_id, "--json")
            )
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=runtime,
                accounts=accounts,
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=current_external_action,
            )
        if action == "release":
            payload, runtime, accounts = run_account_mutation_and_refresh(
                runner, ("accounts", "release", backend_id, "--json")
            )
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=runtime,
                accounts=accounts,
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=current_external_action,
            )
        if action == "retire":
            payload, runtime, accounts = run_account_mutation_and_refresh(
                runner, ("accounts", "retire", backend_id, "--json")
            )
            external_models = load_external_models_snapshot(runner)
            return DashboardState(
                runtime=runtime,
                accounts=accounts,
                external_models=external_models,
                flash=_action_flash(payload),
                external_action=current_external_action,
            )
    except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
        return _integration_state(str(exc), flash=f"Действие завершилось с ошибкой: {exc}")
    return load_dashboard_state(
        runner,
        flash=f"Неподдерживаемое действие: {action}",
        external_action=current_external_action,
    )


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _runtime_rows(runtime: RuntimeSnapshot) -> str:
    rows = [
        ("Состояние", runtime.overall_state),
        ("Желаемый режим", runtime.desired_mode),
        ("Фактический режим", runtime.effective_mode),
        ("Эндпоинт", runtime.endpoint),
        ("Текущий прокси", runtime.current_proxy_url),
        ("Здоровье", f"{runtime.liveness} / {runtime.machine_error_code}"),
        ("Пул", f"A:{runtime.active_count} R:{runtime.reserve_count} T:{runtime.retired_count}"),
        ("Здоровье аккаунтов", f"H:{runtime.healthy_count} D:{runtime.degraded_count} X:{runtime.down_count}"),
        (
            "Аттестация",
            f"{runtime.attestation_status} / {runtime.attestation_machine_error_code} / "
            f"{runtime.attestation_source}",
        ),
        ("Следующее действие", runtime.next_action),
        ("Последняя ошибка", runtime.last_error),
        ("Интеграция", runtime.integration_error),
    ]
    return "".join(
        f"<tr><th>{_esc(label)}</th><td>{_esc(value)}</td></tr>" for label, value in rows
    )


def _event_rows(events: tuple[UiEvent, ...]) -> str:
    if not events:
        return "<tr><td colspan='3'><em>Пока пусто.</em></td></tr>"
    return "".join(
        "<tr>"
        f"<td>{_esc(event.observed_at)}</td>"
        f"<td>{_esc(event.request)}</td>"
        f"<td>{_esc(event.outcome)}</td>"
        "</tr>"
        for event in events
    )


def _account_rows(accounts: AccountPoolSnapshot) -> str:
    rows: list[str] = []
    for account in accounts.accounts:
        rows.append(
            "<tr>"
            f"<td>{_esc(account.backend_id)}</td>"
            f"<td>{_esc(account.label)}</td>"
            f"<td>{_esc(account.pool)}</td>"
            f"<td>{_esc(account.status)}</td>"
            f"<td>{_esc('да' if account.manual_hold else 'нет')}</td>"
            f"<td>{_esc(account.last_error)}</td>"
            "<td>"
            f"{_account_action_form('validate', account.backend_id, 'Проверить')}"
            f"{_account_action_form('promote', account.backend_id, 'Повысить')}"
            f"{_account_action_form('demote', account.backend_id, 'Понизить')}"
            f"{_account_action_form('hold', account.backend_id, 'Удержать')}"
            f"{_account_action_form('release', account.backend_id, 'Снять hold')}"
            f"{_account_action_form('retire', account.backend_id, 'Вывести')}"
            "</td>"
            "</tr>"
        )
    return "".join(rows) or (
        "<tr><td colspan='7'><em>Аккаунты не найдены.</em></td></tr>"
    )


def _account_action_form(action: str, backend_id: str, label: str) -> str:
    return (
        "<form method='post' action='/action' class='inline'>"
        f"<input type='hidden' name='action' value='{_esc(action)}'>"
        f"<input type='hidden' name='backend_id' value='{_esc(backend_id)}'>"
        f"<button type='submit'>{_esc(label)}</button>"
        "</form>"
    )


def _external_overview_rows(external: ExternalModelsSnapshot) -> str:
    rows = [
        ("Фаза", external.foundation_phase),
        ("Adapter state", external.adapter_state),
        ("Lifecycle mode", external.lifecycle_mode),
        ("Route count", external.routes_count),
        ("Observed route count", external.observed_routes_count),
        ("Listener proven", "да" if external.listener_proven else "нет"),
        ("Runtime claim blocked", "да" if external.runtime_claim_blocked else "нет"),
        ("Profile ready", "да" if external.profile_ready else "нет"),
        ("Local token present", "да" if external.local_token_present else "нет"),
        ("Models source", external.models_source),
        ("Интеграция", external.integration_error),
    ]
    return "".join(
        f"<tr><th>{_esc(label)}</th><td>{_esc(value)}</td></tr>" for label, value in rows
    )


def _external_route_action_form(
    action: str,
    route_id: str,
    label: str,
    *,
    confirm_message: str | None = None,
) -> str:
    confirm_attr = ""
    if confirm_message:
        confirm_attr = f" onsubmit=\"return confirm('{_esc(confirm_message)}')\""
    return (
        f"<form method='post' action='/action' class='inline'{confirm_attr}>"
        f"<input type='hidden' name='action' value='{_esc(action)}'>"
        f"<input type='hidden' name='route_id' value='{_esc(route_id)}'>"
        f"<button type='submit'>{_esc(label)}</button>"
        "</form>"
    )


def _external_route_rows(external: ExternalModelsSnapshot) -> str:
    projections = {record.route_id: record for record in external.models}
    rows: list[str] = []
    for route in external.routes:
        projection = projections.get(route.route_id)
        enabled_label = "enabled" if route.enabled else "disabled"
        adapter_state = projection.synthetic_adapter_state if projection else "unknown"
        action_toggle = (
            _external_route_action_form(
                "external_route_disable",
                route.route_id,
                "Disable",
                confirm_message=f"Disable route {route.route_id}?",
            )
            if route.enabled
            else _external_route_action_form(
                "external_route_enable",
                route.route_id,
                "Enable",
                confirm_message=f"Enable route {route.route_id}?",
            )
        )
        rows.append(
            "<tr>"
            f"<td>{_esc(route.route_id)}</td>"
            f"<td>{_esc(route.provider)}</td>"
            f"<td>{_esc(route.upstream_model)}</td>"
            f"<td>{_esc(route.compatibility)}</td>"
            f"<td>{_esc(route.cost_class)}</td>"
            f"<td>{_esc(enabled_label)}</td>"
            f"<td>{_esc(adapter_state)}</td>"
            "<td>"
            f"{_external_route_action_form('external_validate', route.route_id, 'Validate')}"
            f"{_external_route_action_form('external_check', route.route_id, 'Check')}"
            f"{_external_route_action_form('external_profile', route.route_id, 'Profile')}"
            f"{_external_route_action_form('external_evidence', route.route_id, 'Evidence')}"
            f"{action_toggle}"
            "</td>"
            "</tr>"
        )
    return "".join(rows) or (
        "<tr><td colspan='8'><em>External-models routes not found.</em></td></tr>"
    )


def _external_action_rows(action: ExternalActionResult | None) -> str:
    if action is None:
        return "<tr><td colspan='2'><em>Пока нет route-level action packet.</em></td></tr>"
    rows = [
        ("Action", action.action),
        ("Status", action.status),
        ("Machine error", action.machine_error_code),
        ("Message", action.human_message),
        ("Next action", action.next_action),
        ("Verification scope", action.verification_scope),
        ("Route state", action.route_state),
        ("Route / requested model", action.route_id),
        ("Provider", action.provider),
        ("Effective model", action.effective_model),
        ("Listener proven", "да" if action.listener_proven else "нет"),
        ("Runtime claim blocked", "да" if action.runtime_claim_blocked else "нет"),
        ("Profile ready", "да" if action.profile_ready else "нет"),
        ("Network dependent", "да" if action.network_dependent else "нет"),
        ("Fallback used", action.fallback_used),
        ("Fallback chain", action.fallback_chain),
        ("Latency ms", action.latency_ms),
        ("Request count", action.request_count),
        ("Base URL", action.base_url),
        ("Writes external config", action.writes_external_config),
        ("Prerequisite", action.prerequisite),
        ("Evidence path", action.evidence_path),
        ("Changed files", ", ".join(action.changed_files)),
    ]
    return "".join(
        f"<tr><th>{_esc(label)}</th><td>{_esc(value)}</td></tr>" for label, value in rows
    )


def render_dashboard(state: DashboardState) -> str:
    flash_class = "flash flash-error" if state.runtime.integration_error else "flash"
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Wild Boar Proxy</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f1e8;
      --panel: #fffdf8;
      --ink: #1b1a17;
      --muted: #675f55;
      --line: #d9cfbf;
      --accent: #b24a2d;
      --accent-2: #214f43;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      background:
        radial-gradient(circle at top left, rgba(178,74,45,0.08), transparent 28%),
        linear-gradient(180deg, #f8f4ea 0%, var(--bg) 100%);
      color: var(--ink);
    }}
    .page {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
    .hero {{
      display: flex; justify-content: space-between; align-items: end; gap: 16px;
      margin-bottom: 20px; padding-bottom: 14px; border-bottom: 2px solid var(--line);
    }}
    .hero h1 {{ margin: 0; font-size: 2rem; }}
    .hero p {{ margin: 6px 0 0; color: var(--muted); }}
    .flash {{
      margin: 0 0 20px; padding: 12px 14px; border-radius: 12px;
      background: rgba(33,79,67,0.08); border: 1px solid rgba(33,79,67,0.16);
    }}
    .flash-error {{
      background: rgba(178,74,45,0.10); border-color: rgba(178,74,45,0.18);
    }}
    .grid {{ display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 18px; }}
    .panel {{
      background: var(--panel); border: 1px solid var(--line); border-radius: 18px;
      padding: 18px; box-shadow: 0 10px 30px rgba(27,26,23,0.06);
    }}
    h2, h3 {{ margin: 0 0 12px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 9px 10px; border-bottom: 1px solid #ece4d8; vertical-align: top; }}
    th {{ width: 220px; color: var(--muted); font-weight: 600; }}
    .actions {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
    form {{ margin: 0; }}
    .inline {{ display: inline-block; margin: 0 6px 6px 0; }}
    input[type=text] {{
      width: 100%; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--line);
      background: #fff;
    }}
    button {{
      width: 100%; padding: 10px 12px; border: 0; border-radius: 10px; cursor: pointer;
      color: white; background: var(--accent); font: inherit;
    }}
    .inline button {{ width: auto; padding: 7px 10px; font-size: 0.92rem; }}
    .secondary button {{ background: var(--accent-2); }}
    .section-stack {{ display: grid; gap: 18px; }}
    .field {{ display: grid; gap: 8px; margin-bottom: 10px; }}
    .caption {{ color: var(--muted); font-size: 0.95rem; }}
    @media (max-width: 1100px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <div>
        <h1>Wild Boar Proxy</h1>
        <p>Минимальная локальная операторская оболочка поверх каноничных JSON owner-path команд.</p>
      </div>
      <form method="get" action="/"><button type="submit">Обновить</button></form>
    </div>
    <div class="{flash_class}">{_esc(state.flash)}</div>
    <div class="grid">
      <section class="panel">
        <h2>Состояние runtime</h2>
        <table>{_runtime_rows(state.runtime)}</table>
      </section>
      <section class="section-stack">
        <section class="panel">
          <h2>Операторские действия</h2>
          <div class="actions">
            <form method="post" action="/action"><input type="hidden" name="action" value="mode_stable"><button type="submit">Переключить в stable</button></form>
            <form method="post" action="/action"><input type="hidden" name="action" value="mode_managed"><button type="submit">Переключить в managed</button></form>
            <form method="post" action="/action"><input type="hidden" name="action" value="sync"><button type="submit">Запустить managed sync</button></form>
            <form method="post" action="/action"><input type="hidden" name="action" value="smoke"><button type="submit">Проверка smoke</button></form>
            <form method="post" action="/action"><input type="hidden" name="action" value="stable_repair"><button type="submit">Починить stable</button></form>
            <form method="post" action="/action" class="secondary"><input type="hidden" name="action" value="diagnostics"><button type="submit">Экспортировать диагностику</button></form>
          </div>
        </section>
        <section class="panel">
          <h3>Запуск клиента</h3>
          <form method="post" action="/action">
            <input type="hidden" name="action" value="launch_client">
            <label class="field">
              <span class="caption">Абсолютный путь к клиенту</span>
              <input type="text" name="client_path" placeholder="/Applications/App.app/Contents/MacOS/App">
            </label>
            <button type="submit">Запустить клиент</button>
          </form>
        </section>
        <section class="panel">
          <h3>Онбординг</h3>
          <form method="post" action="/action">
            <input type="hidden" name="action" value="onboard">
            <label class="field">
              <span class="caption">Явный путь к auth-файлу</span>
              <input type="text" name="auth_ref" placeholder="/absolute/path/to/codex-auth.json">
            </label>
            <button type="submit">Добавить explicit auth</button>
          </form>
        </section>
      </section>
    </div>
    <section class="panel" style="margin-top: 18px;">
      <h2>Пул аккаунтов</h2>
      <p class="caption">
        Реестр: {_esc(state.accounts.registry_identity_status)} / {_esc(state.accounts.registry_identity_machine_error_code)}
        · Счётчики: A:{state.accounts.active_count} R:{state.accounts.reserve_count} T:{state.accounts.retired_count}
        · Контур: {state.accounts.capacity_target} managed / 10 active по умолчанию
      </p>
      <table>
        <thead>
          <tr>
            <th>ID</th><th>Метка</th><th>Пул</th><th>Статус</th><th>На hold</th><th>Последняя ошибка</th><th>Действия</th>
          </tr>
        </thead>
        <tbody>{_account_rows(state.accounts)}</tbody>
      </table>
    </section>
    <section class="panel" style="margin-top: 18px;">
      <h2>External Models Overview</h2>
      <p class="caption">
        Synthetic lifecycle truth only. Route validation and check results below remain provider-route evidence only
        and do not prove runtime, listener, profile, or Codex readiness.
      </p>
      <table>{_external_overview_rows(state.external_models)}</table>
    </section>
    <section class="panel" style="margin-top: 18px;">
      <h2>External Models Routes</h2>
      <p class="caption">
        Packet-driven registry view. No state-file shortcuts, no background provider polling, no readiness inference.
      </p>
      <table>
        <thead>
          <tr>
            <th>Route</th><th>Provider</th><th>Upstream model</th><th>Compatibility</th><th>Cost</th><th>Enabled</th><th>Adapter</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>{_external_route_rows(state.external_models)}</tbody>
      </table>
    </section>
    <section class="panel" style="margin-top: 18px;">
      <h2>External Models Action Result</h2>
      <p class="caption">
        Provider-route evidence only. Even `verified` here is not runtime-ready, listener-ready, profile-ready, or Codex-ready.
      </p>
      <table>{_external_action_rows(state.external_action)}</table>
    </section>
    <section class="panel" style="margin-top: 18px;">
      <h2>Последние действия</h2>
      <table>
        <thead>
          <tr>
            <th>Время</th><th>Запрос</th><th>Результат</th>
          </tr>
        </thead>
        <tbody>{_event_rows(state.events)}</tbody>
      </table>
    </section>
  </div>
</body>
</html>
"""


class WildBoarWebUi:
    def __init__(self, runner: JsonCommandRunner | None = None) -> None:
        self.runner = runner or JsonCommandRunner()
        self._events: deque[UiEvent] = deque(maxlen=24)
        self._external_action: ExternalActionResult | None = None

    def _record_event(self, request: str, outcome: str) -> None:
        self._events.appendleft(
            UiEvent(
                observed_at=datetime.now().strftime("%H:%M:%S"),
                request=request,
                outcome=outcome,
            )
        )

    def get_dashboard(self, *, path: str = "/") -> DashboardState:
        state = load_dashboard_state(self.runner, external_action=self._external_action)
        self._record_event(
            f"GET {path}",
            f"{state.runtime.overall_state} / {state.runtime.effective_mode}",
        )
        return _with_events(state, tuple(self._events))

    def post_action(self, fields: dict[str, str], *, path: str = "/action") -> DashboardState:
        state = apply_action(
            self.runner,
            fields,
            current_external_action=self._external_action,
        )
        self._external_action = state.external_action
        action = fields.get("action", "").strip() or "unknown"
        self._record_event(f"POST {path} [{action}]", state.flash or state.runtime.human_message)
        return _with_events(state, tuple(self._events))


def build_handler(app: WildBoarWebUi) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self._send_html(render_dashboard(app.get_dashboard(path=self.path)))

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            parsed = {
                key: values[-1]
                for key, values in parse_qs(body, keep_blank_values=True).items()
            }
            self._send_html(render_dashboard(app.post_action(parsed, path=self.path)))

        def log_message(self, fmt: str, *args: object) -> None:
            return

        def _send_html(self, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wild-boar-proxy-web-ui")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), build_handler(WildBoarWebUi()))
    print(f"Wild Boar Proxy web UI запущен на http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
