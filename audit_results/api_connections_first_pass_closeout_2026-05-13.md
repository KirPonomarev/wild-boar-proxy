<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# API Connections First-Pass Contract Closeout

Contour ID: `API_CONNECTIONS_FIRST_PASS_COMMAND_CONTRACT_SPEC`
Date: 2026-05-13
Status: verified

## Scope Check

Completed within spec-only scope:

- Confirmed first-pass `API-подключения` screen can use existing commands.
- Rejected `Вкл` as first-pass button copy.
- Defined exact first-pass actions:
  - `Обновить`
  - `Проверить`
  - `Проверить запросом`
  - `Разрешить`
  - `Отключить`
- Deferred active/primary, failover, key setup, and route add/edit/remove.
- Added machine-error-to-Russian-status mapping.
- Added independent audit.

Not changed:

- No UI files changed.
- No runtime files changed.
- No command behavior changed.
- No route/state/secret files changed.
- No desktop files changed.

## Artifacts

- `audit_results/api_connections_first_pass_command_contract_2026-05-13.md`
- `audit_results/api_connections_first_pass_action_matrix_2026-05-13.json`
- `audit_results/api_connections_first_pass_independent_audit_2026-05-13.md`
- `audit_results/api_connections_first_pass_closeout_2026-05-13.md`

## Verification

Verification completed:

- `python3 -m unittest tests.test_external_models`: PASS, 11 tests.
- `python3 -m unittest tests.test_cli_external_models`: PASS, 17 tests.
- `python3 -m unittest tests.test_web_ui`: PASS, 10 tests.
- JSON validation for `api_connections_first_pass_action_matrix_2026-05-13.json`:
  PASS.
- `git diff --check` for this contour's artifacts: PASS.
- service-specific private reference trace scan: PASS.
- active/primary/fallback static scan: PASS; no active/primary route owner
  surface found, fallback fields remain non-execution proof.
- independent command/schema inspector: PASS_WITH_GUARDS; existing commands are
  sufficient for first pass, active/primary/live runtime claims remain blockers
  only if they are required.

## Next Contour

Recommended next contour:

`API_CONNECTIONS_WEB_SCREEN_READONLY`

Reason:

No hard blocker was found for a useful first-pass screen on existing command
packets.
