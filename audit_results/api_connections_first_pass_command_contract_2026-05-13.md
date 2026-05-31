<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# API Connections First-Pass Command Contract

Contour ID: `API_CONNECTIONS_FIRST_PASS_COMMAND_CONTRACT_SPEC`
Date: 2026-05-13
Type: spec / first-pass command-contract

## Verdict

The first `API-подключения` UI pass can be built on existing commands only.

No new backend command surface is required for a useful first-pass screen if the
screen limits itself to:

- readonly route visibility;
- route provider validation;
- route smoke check;
- route enablement as `Разрешить`;
- route disablement as `Отключить`.

The first pass must explicitly reject `Вкл`, `Сделать активным`, `Основной`,
automatic failover, key setup, route add/edit/remove, and continuous token stream
claims.

## Canon Alignment

This contour remains spec-only and does not implement UI, runtime, command, or
route mutation.

The governing boundary remains:

- Wild Boar Proxy is the managing/control layer.
- CLIProxyAPI is the engine.
- The engine owns API traffic, auth flows, provider translation, and low-level
  routing.
- UI and automation use strict JSON packets only.
- UI must not infer runtime readiness from route checks.
- No false-green or stale-green status is allowed.

Evidence:

- `CANON.md:24-32`
- `CANON.md:36-38`
- `MASTER_PLAN.md:175-176`
- `MASTER_PLAN.md:225-227`
- `MASTER_PLAN.md:416`
- `COMMAND_API.md:14`
- `AGENTS.md:51-59`

Because this is spec-only, it does not violate the rich UI/design gate.

## First-Pass Product Boundary

`API-подключения` is not a generic external API manager.

The first-pass product value is operational visibility and safe checks:

- what routes exist;
- which routes are allowed;
- which routes need attention;
- whether a route passes provider-level checks.

The first pass must not become:

- a second routing engine;
- a generic provider configuration GUI;
- a browser token/key input surface;
- a runtime readiness dashboard for provider traffic;
- a failover controller.

## Core Decision

Use existing commands only unless a hard blocker appears.

No hard blocker was found for a useful first-pass UI.

The next implementation contour may therefore proceed to
`API_CONNECTIONS_WEB_SCREEN_READONLY` before adding new backend surfaces.

## First-Pass Command Inventory

### Readonly

`external-models status --json`

- Purpose: external-models synthetic lifecycle/status packet.
- UI use: summary state only.
- Not truth for runtime readiness, host-client readiness, or continuous token
  stream.

`external-models models --json`

- Purpose: route model projection from local route registry.
- UI use: display route/model metadata.
- Not truth for active traffic.

`external-models routes list --json`

- Purpose: route registry listing.
- UI use: route table.
- Not truth for selected active route or automatic failover.

Evidence:

- `wild_boar_proxy/cli.py:222-253`
- `wild_boar_proxy/ui_shell.py:734-739`
- `wild_boar_proxy/web_ui.py:98-129`

### Safe Actions

`external-models routes validate --json --route <route_id>`

- UI copy: `Проверить`.
- Meaning: provider exposes requested route model / model visibility check.
- Browser payload: `ui_action + route_id`.
- Allowed success copy: `Маршрут проверен.`
- Forbidden success copy: `Runtime готов`, `Подключение полностью работает`,
  `Поток токенов защищен`.

Evidence:

- `wild_boar_proxy/cli.py:260-262`
- `wild_boar_proxy/external_models/__init__.py:202-210`
- `wild_boar_proxy/external_models/validate.py:245-260`
- `tests/test_cli_external_models.py:473-508`

`external-models check --json --route <route_id>`

- UI copy: `Проверить запросом`.
- Meaning: provider-route smoke check with a bounded test request.
- Browser payload: `ui_action + route_id`.
- Allowed success copy: `Маршрут отвечает.`
- Forbidden success copy: `Основной поток работает`, `Fallback готов`,
  `Desktop profile ready`.

Evidence:

- `wild_boar_proxy/cli.py:226-228`
- `wild_boar_proxy/external_models/__init__.py:90-98`
- `wild_boar_proxy/external_models/validate.py:405-420`
- `tests/test_cli_external_models.py:566-607`

`external-models routes enable --json --route <route_id>`

- UI copy: `Разрешить`.
- Meaning: set route `enabled=true`.
- Browser payload: `ui_action + route_id`.
- Allowed success copy: `Маршрут разрешен.`
- Forbidden success copy: `Маршрут активен`, `Трафик переключен`,
  `Включено как основное`.

Evidence:

- `wild_boar_proxy/cli.py:254-256`
- `wild_boar_proxy/external_models/__init__.py:184-192`
- `wild_boar_proxy/external_models/routes.py:265-271`

`external-models routes disable --json --route <route_id>`

- UI copy: `Отключить`.
- Meaning: set route `enabled=false`.
- Browser payload: `ui_action + route_id + confirmation when currently enabled`.
- Allowed success copy: `Маршрут отключен.`
- Forbidden success copy: `Трафик остановлен`, `Основной маршрут снят`,
  `Fallback переключен`.

Evidence:

- `wild_boar_proxy/cli.py:257-259`
- `wild_boar_proxy/external_models/__init__.py:193-201`
- `wild_boar_proxy/external_models/routes.py:265-271`

## Why `Вкл` Is Rejected

`Вкл` is too broad for the current command contract.

Users will likely read `Вкл` as active traffic or selected route. The current
safe command only sets `enabled=true`. The correct first-pass copy is therefore
`Разрешить`.

Decision:

- Do not use `Вкл` in first-pass UI.
- Do not use `Сделать активным`.
- Do not display `Активный маршрут` unless future owner truth exists.

## Validation Scope Guard

Route validation/check packets intentionally block stronger claims.

Successful validation/check still reports:

- `verification_scope=route_provider_only`;
- `listener_proven=false`;
- `runtime_claim_blocked=true`;
- `profile_ready=false`.

Evidence:

- `wild_boar_proxy/external_models/validate.py:245-260`
- `wild_boar_proxy/external_models/validate.py:405-420`

UI may show:

- `Маршрут проверен`;
- `Модель доступна`;
- `Маршрут отвечает`.

UI must not show:

- `Runtime готов`;
- `Профиль готов`;
- `Подключение полностью работает`;
- `Поток токенов защищен`;
- `Fallback готов`.

## Enabled Is Not Active

`enabled=true` only means that a route is allowed in the route registry.

It does not prove:

- selected active route;
- primary route;
- runtime routing change;
- provider traffic flow;
- fallback readiness.

Current scan found no first-class active/primary route owner command for
external-models. Future active/primary surfaces remain candidate-only.

## Fallback Is Deferred

The schema contains `fallback_eligible`, and validate/check packets include
`fallback_used` and `fallback_chain`.

But current validate/check paths set:

- `fallback_used=false`;
- `fallback_chain=[route_id]`.

Evidence:

- `wild_boar_proxy/external_models/validate.py:225-236`
- `wild_boar_proxy/external_models/validate.py:380-390`

Decision:

- First-pass UI may display `Резервный` only as a route role if needed.
- It must not claim automatic failover.
- Automatic failover requires `API_CONNECTIONS_FAILOVER_POLICY_DECISION`.

## Support Commands Not In First-Pass Product UI

`external-models profile codex-desktop --json --route <route_id>`

- Non-mutating profile contract packet.
- Current packet is not profile-ready, listener-ready, or runtime-ready.
- Keep as support/details, not primary product action.

`external-models evidence capture --json --route <route_id>`

- Local evidence artifact generation.
- Support-only.

`external-models start/stop --json`

- Synthetic adapter lifecycle.
- Deferred until a separate product/copy decision avoids readiness overclaim.

## Deferred Actions

Deferred until secure command contract:

- add route;
- edit route;
- remove route;
- configure API key;
- import route config;
- arbitrary provider config.

Deferred until explicit owner truth:

- make active;
- choose primary;
- route priority;
- route group;
- fallback chain mutation;
- automatic failover;
- continuous token stream display.

## Machine Error Mapping

`OK`

- UI status: `Проверено` or `Отвечает`, depending on command.
- Scope: route-level only.

`provider_auth_failed`

- UI status: `Требует ключ`.
- Operator action: user action.
- No fallback claim.

`missing_secret`, `invalid_secret`, `unsafe_secret_permissions`

- UI status: `Требует ключ`.
- Operator action: user action.

`provider_network_failed`

- UI status: `Недоступно`.
- Operator action: retry.
- May become failover input later, not now.

`model_not_available`

- UI status: `Модель недоступна`.
- Operator action: user action.

`paid_route_blocked`

- UI status: `Заблокировано политикой`.
- Operator action: user action.

`invalid_upstream_response`

- UI status: `Ошибка ответа`.
- Operator action: retry.

`schema_invalid`, `invalid_request`

- UI status: `Ошибка настройки`.
- Operator action: user action.

`integration_failure`, `invalid_json`, `timeout`

- UI status: `Ошибка интеграции`.
- Hard no-green.

## Candidate Future Surfaces

These are candidates only, not admitted by default in this contour.

If active/primary is later required:

- `external-models routes primary get --json`
- `external-models routes primary set --json --route <route_id>`

Required future semantics:

- route exists;
- route enabled;
- selected primary owner truth is explicit;
- previous and next primary route are recorded;
- `changed_files` are truthful;
- runtime routing claim remains false unless runtime owner proves it.

If failover is later required:

- run `API_CONNECTIONS_FAILOVER_POLICY_DECISION` first;
- do not design command names here;
- classify failure triggers, fallback scope, selected route owner,
  stale/unknown/degraded/down states, and runtime evidence requirements.

## Next Contour Recommendation

Recommended next contour:

`API_CONNECTIONS_WEB_SCREEN_READONLY`

Reason:

The first-pass screen can be useful using existing command packets. Backend
implementation should wait until a specific blocker is proven.

If a blocker appears during readonly UI implementation, stop and open:

`API_CONNECTIONS_SAFE_BACKEND_SURFACES`
