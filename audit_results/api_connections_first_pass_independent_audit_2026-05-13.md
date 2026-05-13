<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# API Connections First-Pass Contract Independent Audit

Contour ID: `API_CONNECTIONS_FIRST_PASS_COMMAND_CONTRACT_SPEC`
Date: 2026-05-13
Verdict: `PASS_WITH_GUARDS`

## Audit Scope

This audit checked the first-pass command-contract decision against canon,
previous admission artifacts, and current implementation facts.

No code, UI, runtime, route, state, or secret files were changed.

## Findings

### 1. First-pass on existing commands is canon-compatible

The first-pass screen can use existing readonly/safe command packets without
adding a new backend surface.

Evidence:

- `wild_boar_proxy/cli.py:222-262`
- `wild_boar_proxy/ui_shell.py:734-739`
- `audit_results/api_connections_admission_2026-05-13.md:141-190`

Guard:

- Keep first pass to refresh, validate, check, enable, and disable.

### 2. The plan avoids generic provider-manager drift

The spec rejects add/edit/remove route, API key setup, arbitrary provider config,
primary route, and failover for the first pass. That matches the master-plan
filter that generic GUI features must be needed for managed operations.

Evidence:

- `MASTER_PLAN.md:172-176`
- `MASTER_PLAN.md:225-227`
- `audit_results/api_connections_admission_2026-05-13.md:211-222`

Guard:

- Do not add browser token/config forms in the next UI contour.

### 3. The plan avoids false active-routing claims

The spec rejects `Вкл` and requires `Разрешить` for `enabled=true`.

Evidence:

- `wild_boar_proxy/external_models/__init__.py:184-201`
- `wild_boar_proxy/external_models/routes.py:265-271`
- `audit_results/api_connections_admission_2026-05-13.md:225-235`

Guard:

- Do not display `Активный` or `Основной` until explicit owner truth exists.

### 4. The plan correctly scopes validation/check

Validate/check packets carry provider-route scope and explicitly block runtime,
listener, and profile readiness claims.

Evidence:

- `wild_boar_proxy/external_models/validate.py:245-260`
- `wild_boar_proxy/external_models/validate.py:405-420`
- `tests/test_cli_external_models.py:473-508`
- `tests/test_cli_external_models.py:566-607`

Guard:

- UI may show `Маршрут проверен` or `Маршрут отвечает`, but not runtime-ready
  or continuous stream copy.

### 5. Failover remains properly deferred

The current code exposes fallback-related fields, but validate/check paths keep
`fallback_used=false` and single-route fallback chains.

Evidence:

- `wild_boar_proxy/external_models/validate.py:225-236`
- `wild_boar_proxy/external_models/validate.py:380-390`
- `audit_results/api_connections_admission_2026-05-13.md:264-282`

Guard:

- Any automatic fallback must go through a separate policy decision contour.

## Audit Conclusion

The first-pass command contract is practical and canon-aligned if the next UI
contour remains readonly/safe-action only. The main risk is copy drift: a future
screen must not reintroduce `Вкл`, `Активный`, `Основной`, or fallback language
without command-owned proof.

## External Inspector Cross-Check

A separate command/schema inspector reached the same practical verdict:

- existing commands are sufficient for a first-pass UI;
- active/primary/selected route semantics are not present;
- validate/check packets are provider-route evidence only;
- first-pass UI must avoid live runtime claims.

The inspector identified a blocker only if this contour tries to require
active/primary route semantics or live runtime claims. This contour explicitly
defers both.
