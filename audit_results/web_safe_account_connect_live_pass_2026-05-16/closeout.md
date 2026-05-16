<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS Closeout

## Goal

Connect one existing admitted server-owned live onboarding path into the web
UI, with reserve-first proof requirements, existing readonly refresh only, and
no broadening of onboarding/auth/runtime architecture.

## Result

- status: `verified_pending_git_close`
- final verdict:
  `SERVER_OWNED_LIVE_ACCOUNT_CONNECT_PATH_WIRED_WITH_TRUTHFUL_RESERVE_FIRST_RESULT`
- next action:
  move to `WEB_DESIGN_FINISH_PASS`

## Contour Capsule

- goal:
  replace the visible preview-only account-connect affordance with one existing
  live onboarding path, gated by server-owned accounts-readonly preflight and
  confirmed only through reserve-first packet proof plus canonical refresh
- branch: `codex/external-agent-lab-isolated`
- head: `58998d1` before contour changes
- touched files:
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_ui/index.html`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_live_server.py`
  - `tests/test_web_design_ui.py`
  - `audit_results/web_safe_account_connect_live_pass_2026-05-16/contour.md`
  - `audit_results/web_safe_account_connect_live_pass_2026-05-16/decision_packet.json`
  - `audit_results/web_safe_account_connect_live_pass_2026-05-16/closeout.md`
- tests run:
  - `python3 -m unittest -q tests.test_web_design_live_server tests.test_web_design_ui`
  - browser click against local fake live server at `?screen=accounts&source=live`
- blocked risks:
  - no real operator-owned auth import was run in this contour
  - browser proof used a fake live runner to avoid touching the current working Codex session
- next exact command:
  - `python3 -m unittest -q tests.test_web_design_live_server tests.test_web_design_ui`

## Verification

- tests:
  - live-server tests passed with server-owned onboarding preflight and reserve-first success gating
  - UI tests passed with visible live onboarding affordance and no false-success wording
- build:
  - decision packet JSON parses
  - `git diff --check` must pass before commit
- manual:
  - visible account buttons now point to `onboard_account`
  - onboarding modal describes one server-owned live path instead of preview-only flow
  - confirmation label is `Подключить в reserve`
- live verification:
  - browser click on local fake live server produced:
    - banner `Аккаунт добавлен в резерв. Активная маршрутизация не изменялась.`
    - display state `ok_refresh_complete`
    - selected backend `acct-new`
    - reserve proof chip `доказано`
  - current working Codex session was not launched, mutated, or interrupted

## Artifacts

- spec:
  - `audit_results/web_safe_account_connect_live_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/web_safe_account_connect_live_pass_2026-05-16/decision_packet.json`
- report:
  - `audit_results/web_safe_account_connect_live_pass_2026-05-16/independent_audit.json`
  - this closeout plus unit-test and browser-check evidence

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: atomic contour commit is created after staged verification passes
- pushed: contour branch must be pushed before closeout is final

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; browser payload stays bounded and no auth paths, secrets, or raw packets are exposed`

## Notes

- blockers encountered:
  - the visible onboarding buttons and modal were still wired to preview-only dry-run copy
  - live onboarding required a narrow server-owned preflight gate before command dispatch
- follow-up contour:
  - `WEB_DESIGN_FINISH_PASS`
- resume from here:
  `live account-connect is wired through one existing server-owned path with reserve-first proof and accounts-readonly refresh; next move is WEB_DESIGN_FINISH_PASS`
