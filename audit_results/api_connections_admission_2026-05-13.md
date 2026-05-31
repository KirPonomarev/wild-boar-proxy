<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# API Connections Admission And Canon Alignment

Contour ID: `API_CONNECTIONS_ADMISSION_AND_CANON_ALIGNMENT`
Date: 2026-05-13
Type: admission / spec-only

## Verdict

`API-подключения` is admitted as a product-facing sidebar concept, but only as a
bounded control-layer UI over existing strict JSON command surfaces.

The current implementation already has a useful technical foundation under
`external-models routes`, but it does not yet prove a product-level active API
connection, a primary route, or automatic failover between routes.

The next implementation work must therefore keep this distinction:

- `Разрешить маршрут` may map to `external-models routes enable`.
- `Отключить маршрут` may map to `external-models routes disable`.
- `Сделать активным` is deferred until an explicit active/primary owner command
  exists.
- `Автоматический резерв` / uninterrupted token flow is deferred to a separate
  failover policy contour.

## Canon Alignment

The canon boundary is clear:

- `Wild Boar Proxy App` is the managing layer.
- `CLIProxyAPI` is the engine.
- The managing layer owns modes, pool policy, recovery, diagnostics, rollout,
  visibility, and safe command dispatch.
- The engine owns API traffic, auth flows, provider translation, and low-level
  routing.

Relevant anchors:

- `CANON.md:24-32` separates managing layer from engine-layer API traffic.
- `CANON.md:36-38` requires one active truth surface and forbids false/stale
  green.
- `MASTER_PLAN.md:225-227` requires every feature to be classified as engine or
  control layer and forbids duplicating routing/auth behavior without a blocker.
- `MASTER_PLAN.md:377` says UI and automation use JSON output as the primary
  interface.
- `MASTER_PLAN.md:416` forbids fallback to plain text or log parsing.
- `COMMAND_API.md:14` forbids UI and automation from plain-text/log parsing.
- `AGENTS.md:36` requires strict JSON command surfaces as primary truth.
- `AGENTS.md:51-59` blocks rich UI expansion/design polish before the design
  gate. This contour is admission/spec-only and does not implement rich UI.

This contour does not change runtime, UI behavior, or engine behavior. It stays
within the admission/spec lane.

## Product Vocabulary

Approved user-facing terms:

- `API-подключения`: sidebar section.
- `API-подключение`: user-facing configured connection/group.
- `маршрут`: technical route to provider/base URL/model.
- `разрешен`: route has `enabled=true`.
- `отключен`: route has `enabled=false`.
- `проверено`: route validation/check succeeded within its declared scope.
- `требует ключ`: missing/invalid secret or auth action required.
- `недоступно`: provider/network/model route unavailable.
- `резервный`: fallback-eligible route, not automatic failover proof.

Forbidden or deferred terms:

- `сетки`: forbidden product term.
- `активный`: allowed only when explicit active/primary owner truth exists.
- `непрерывный поток токенов`: forbidden until failover evidence exists.

## Current Technical Foundation

The current command parser exposes `external-models` surfaces:

- `external-models start --json`
- `external-models stop --json`
- `external-models status --json`
- `external-models models --json`
- `external-models check --json --route <route_id>`
- `external-models routes add --json --file/--stdin`
- `external-models routes update --json --route <route_id> --file/--stdin`
- `external-models routes remove --json --route <route_id>`
- `external-models routes list --json`
- `external-models routes enable --json --route <route_id>`
- `external-models routes disable --json --route <route_id>`
- `external-models routes validate --json --route <route_id>`
- `external-models profile codex-desktop --json --route <route_id>`
- `external-models evidence capture --json --route <route_id>`

Sources:

- `wild_boar_proxy/cli.py:214-282`
- `wild_boar_proxy/external_models/__init__.py:16-215`

The route schema already includes:

- `route_id`
- `display_name`
- `provider`
- `base_url`
- `endpoint_path`
- `upstream_model`
- `compatibility`
- `auth`
- `cost_class`
- `lane_role`
- `fallback_eligible`
- `enabled`

Sources:

- `wild_boar_proxy/external_models/contracts.py:14-50`
- `wild_boar_proxy/external_models/routes.py:100-164`

The observed state schema includes route observation fields:

- `availability_state`
- `evidence_level`
- `last_verified_at`
- `last_validate`
- `last_check`
- `last_error`
- `latency_ms`
- `fallback_used`
- `effective_model`

Source:

- `wild_boar_proxy/external_models/contracts.py:74-86`

## Command Classification

### Admitted Readonly

`external-models status --json`

- Product label: `Состояние подключений`.
- Scope: synthetic lifecycle/status only.
- Not truth for runtime readiness, host-client readiness, or uninterrupted
  token flow.

`external-models models --json`

- Product label: `Модели маршрутов`.
- Scope: local route registry projection.
- Not truth for active traffic or runtime readiness.

`external-models routes list --json`

- Product label: `Список маршрутов`.
- Scope: route registry listing.
- Not truth for selected active route or automatic failover.

### Admitted Safe Actions

`external-models routes validate --json --route <route_id>`

- Product label: `Проверить доступность модели`.
- Scope: provider-route validation.
- The packet explicitly carries `listener_proven=false`,
  `runtime_claim_blocked=true`, `profile_ready=false`, and
  `verification_scope=route_provider_only`.
- It may show `маршрут проверен`; it must not show `runtime готов`.

`external-models check --json --route <route_id>`

- Product label: `Проверить маршрут запросом`.
- Scope: provider-route smoke check.
- The packet has the same readiness limits as validate.
- It may show `маршрут отвечает`; it must not show `поток токенов защищен`.

`external-models routes enable --json --route <route_id>`

- Product label: `Разрешить маршрут`.
- Scope: sets `enabled=true`.
- It must not be labeled `Сделать активным`.

`external-models routes disable --json --route <route_id>`

- Product label: `Отключить маршрут`.
- Scope: sets `enabled=false`.
- It should require confirmation if future route usage could affect operator
  expectations.
- It must not claim active traffic stopped unless an active owner packet proves
  that.

### Support Or Contract Preview

`external-models profile codex-desktop --json --route <route_id>`

- Product label: `Показать профиль`.
- Scope: non-mutating profile contract packet.
- It currently reports `profile_ready=false`, `listener_proven=false`, and
  `runtime_claim_blocked=true`.
- It must not be treated as host-client readiness.

`external-models evidence capture --json --route <route_id>`

- Product label: `Собрать свидетельство`.
- Scope: local evidence artifact.
- Support-only, not first-pass product UI.

### Deferred For Product UI

`external-models routes add/update/remove --json`

- These mutate route registry.
- Product UI admission requires a secure config/secret contract first.
- Browser must not submit raw tokens, arbitrary file paths, or raw route config.

`external-models start/stop --json`

- These operate the synthetic adapter lifecycle.
- Product UI admission requires a clear copy model that avoids runtime readiness
  overclaims.

## Semantic Findings

### Enabled Is Not Active

`enabled=true` means the route is allowed in the registry. The current scan did
not find a first-class `active route`, `primary route`, or `selected route`
owner command for external models.

Decision:

- The first-pass UI may say `Разрешить маршрут`.
- It may not say `Сделать активным`.
- `Активный маршрут` must remain deferred unless a new owner surface is added.

### Validation Is Not Runtime Readiness

Route validation and route smoke check are intentionally scoped to provider-route
evidence.

Sources:

- `wild_boar_proxy/external_models/validate.py:245-260`
- `wild_boar_proxy/external_models/validate.py:405-420`
- `tests/test_cli_external_models.py:473-508`
- `tests/test_cli_external_models.py:566-607`

Both successful validate/check packets still carry:

- `listener_proven=false`
- `runtime_claim_blocked=true`
- `profile_ready=false`
- `verification_scope=route_provider_only`

Decision:

- UI may show `маршрут проверен`.
- UI must not show `runtime готов`, `профиль готов`, or `поток токенов
  непрерывен`.

### Fallback Fields Are Not Failover

The schema contains `fallback_eligible`, and validate/check packets include
`fallback_used` and `fallback_chain`.

However, the current implementation sets:

- `fallback_used=false`
- `fallback_chain=[route_id]`

Sources:

- `wild_boar_proxy/external_models/validate.py:225-236`
- `wild_boar_proxy/external_models/validate.py:380-390`

Decision:

- `fallback_eligible` may be displayed as `резервный` only with careful copy.
- It must not be presented as automatic failover.
- Automatic failover requires a separate policy decision and implementation
  contour.

### UI Path Already Uses Command Snapshots For Main External Models Truth

The current web/UI shell external models snapshot is built from command packets:

- `external-models status --json`
- `external-models models --json`
- `external-models routes list --json`

Sources:

- `wild_boar_proxy/ui_shell.py:653-739`
- `wild_boar_proxy/web_ui.py:98-129`

There are support-only actions that open the data directory, routes file, state
file, evidence directory, or latest evidence path for operator inspection.

Sources:

- `wild_boar_proxy/web_ui.py:132-208`

Decision:

- Product `API-подключения` truth must continue to come from commands.
- Support file-open actions must not become truth inputs.
- First-pass product screen should not expose support file-open actions as main
  controls.

## Future Screen Passport

Screen ID: `api_connections`

Sidebar label: `API-подключения`

Header:

- `API-подключения`

Description:

- `Подключения к внешним API и резервные маршруты.`

Summary cards:

- `Разрешенные маршруты`
- `Требуют внимания`
- `Последняя проверка`
- `Активный маршрут` only if owner truth exists; otherwise defer or show
  `Активный маршрут не выбран`.

Table columns:

- `Название`
- `Провайдер`
- `Модель`
- `Статус`
- `Роль`
- `Последняя проверка`
- `Действия`

First-pass actions:

- `Обновить`
- `Проверить доступность`
- `Проверить запросом`
- `Разрешить маршрут`
- `Отключить маршрут`

Deferred controls:

- `Сделать активным`
- `Настроить ключ`
- `Добавить маршрут`
- `Удалить маршрут`
- `Автоматический резерв`

Empty state:

- `API-подключения пока не настроены.`

Error states:

- `Требует ключ`
- `Недоступно`
- `Проверка не прошла`
- `Нет данных`
- `Ошибка интеграции`

## Missing Surfaces

The next command-contract contour should decide whether to add:

- `external-models routes activate --json --route <route_id>`
- `external-models routes primary get --json`
- `external-models routes primary set --json --route <route_id>`
- `external-models routes health --json`
- `external-models routes check-all --json`
- `external-models fallback policy get/set --json`

Naming is intentionally tentative. The next contour should choose command names
only after checking `COMMAND_API.md` conventions.

## Failover Deferral

Automatic failover is not part of this contour.

Future failover must answer:

- What failure classes trigger route replacement?
- Is `401/403` user action rather than fallback?
- Is `429/quota` a temporary fallback or route degradation?
- Is network timeout recoverable?
- How many failures before route hold/disable/degrade?
- Does the selected fallback route become active, temporary, or per-request?
- Which owner surface writes the selected route?
- How does UI display fallback without stale-green?

Minimum future evidence fields:

- selected route id
- fallback route id
- fallback reason
- observed_at
- failure class
- command owner
- `fallback_used`
- `fallback_chain`
- stale/unknown/down/degraded separation

## Stop Conditions For Next Work

Stop before implementation if:

- `Вкл` cannot be mapped to exact command meaning.
- UI wording would imply active traffic without command proof.
- Browser would send API key/token/raw route config.
- UI would read `routes.json`, `state.json`, or `secrets.env` directly as truth.
- Route validation/check would be treated as runtime readiness.
- Failover would require duplicating low-level provider routing inside UI.
- Any test shows false-green or stale-green behavior.

## Recommended Next Contours

1. `API_CONNECTIONS_COMMAND_CONTRACT_SPEC`
2. `API_CONNECTIONS_SAFE_BACKEND_SURFACES`
3. `API_CONNECTIONS_WEB_SCREEN_READONLY`
4. `API_CONNECTIONS_WEB_SAFE_ACTIONS`
5. `API_CONNECTIONS_FAILOVER_POLICY_DECISION`

## Closeout Expectation

This contour is complete only after:

- this artifact and the surface registry are committed and pushed;
- relevant external-models/web tests pass;
- static scans confirm no private reference-service traces;
- no runtime, UI behavior, or desktop files were changed.
