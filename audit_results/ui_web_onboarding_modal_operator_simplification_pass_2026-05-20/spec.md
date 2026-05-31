<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_WEB_ONBOARDING_MODAL_OPERATOR_SIMPLIFICATION_PASS Spec

## Goal

Make the onboarding modal an operator confirmation instead of an audit/spec
screen.

## Scope

Touched product files:

- `wild_boar_proxy/web_design_ui/index.html`
- `wild_boar_proxy/web_design_ui/styles/overview.css`
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
- `tests/test_web_design_ui.py`

Forbidden product files for this contour stayed out of scope:

- `wild_boar_proxy/runtime.py`
- `wild_boar_proxy/web_design_command_adapter.py`
- `wild_boar_proxy/web_design_live_server.py`
- `COMMAND_API.md`
- `RUNTIME_CONTRACT.md`

## Required UI Shape

- title: `Подключить аккаунт`
- short description: reserve pool and active routing unchanged
- compact facts grid:
  - source: `server-owned onboarding`
  - pool: `Резерв`
  - after command: `Обновить accounts JSON`
  - success: `reserve-first proof`
- warning note: `Web не принимает токены, файлы и локальные пути.`
- technical boundaries in collapsed native `details`
- buttons: `Отмена`, `Подключить в резерв`

## Preserved Boundaries

- no browser file/path input
- no token/auth/secret input
- no browser-submitted `auth_ref`, `source_dir`, or `backend_id`
- primary action remains `onboard_account`
- no auto-promote claim
- no active-ready success claim
- command result remains packet/refresh based

## Acceptance Evidence

- `metrics.json`
- `browser_command_calls.json`
- `screenshots/quick-start-onboarding-modal-collapsed.png`
- `screenshots/quick-start-onboarding-modal-expanded-details.png`
- `screenshots/quick-start-after-cancel.png`
