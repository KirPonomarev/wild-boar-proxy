<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: WEB_SAFE_ACCOUNT_CONNECT_DRY_RUN_PASS

## Objective

Turn Quick Start account connect into a real sandbox-only dry-run preview path
 so the operator can click `Подключить аккаунт`, receive a machine packet, and
 see a truthful preview-only result without mutating live account truth.

## In Scope

- admit `onboard_account_dry_run` only in `sandbox_actions`
- keep `onboard_account` parked in `sandbox_actions` for this contour
- rewire Quick Start and accounts onboarding buttons to
  `onboard_account_dry_run`
- update onboarding modal copy to preview-only semantics
- keep action ledger and onboarding result flow truthful for preview-only
- add tests for phase gating, preview-only semantics, and UI wiring

## Out of Scope

- real `onboard_account` execution
- auth import or registry mutation
- API route verify/adopt flow
- aggregate `Проверить всё`
- desktop port
- redesign beyond minimal truth-preserving copy updates

## Constraints

- browser accepts no `token`, `secret`, `path`, `auth`, or `backend_id`
- dry-run preview must not claim reserve admission or live success
- readonly refresh, if present, may prove no mutation only
- current working Codex stays untouched

## Acceptance Criteria

- [x] `onboard_account_dry_run` is disabled in `live_readonly`
- [x] `onboard_account_dry_run` is admitted in `sandbox_actions`
- [x] `onboard_account` is not admitted in `sandbox_actions` during this contour
- [x] Quick Start wiring dispatches `onboard_account_dry_run`
- [x] onboarding modal copy states preview-only semantics
- [x] action ledger and onboarding result flow stay preview-only and avoid
  false live-success wording
- [x] no browser secret/path/token/auth input surface was added

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter -q`
- build:
  - `git diff --check`
- manual HTTP evidence:
  - `/api/actions` on sandbox server reports
    `action_phase=sandbox_actions`,
    `sandbox_preflight.status=admitted`,
    `onboard_account_dry_run.available=true`,
    `onboard_account.available=false`
  - `POST /api/action {"ui_action":"onboard_account_dry_run"}` returns
    `preview_only=true`, `ui_state=dry_run_ready`,
    `final_outcome=dry_run_preview_ready`
  - `POST /api/action {"ui_action":"onboard_account"}` returns
    `integration_failure` with `UI_ACTION_PHASE_NOT_ADMITTED`

## Open Questions

- whether the next live contour should admit `onboard_account` in
  `sandbox_actions` directly or behind an additional proof flag
- whether the accounts screen should later split preview and live buttons
  explicitly instead of sharing the same “Подключить аккаунт” entrypoint
