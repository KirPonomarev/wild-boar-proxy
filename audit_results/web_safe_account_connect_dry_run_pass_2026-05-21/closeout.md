<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WEB_SAFE_ACCOUNT_CONNECT_DRY_RUN_PASS Closeout

## Goal

Open a real Quick Start onboarding preview path in web sandbox mode so the
operator can run a machine-backed dry-run packet without triggering live account
mutation.

## Result

- status: `verified_pending_git_close`
- final verdict:
  `QUICK_START_ACCOUNT_CONNECT_NOW_RUNS_AS_SANDBOX_DRY_RUN_PREVIEW_ONLY`
- next action: move to `WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS`

## Contour Capsule

- goal:
  move Quick Start account connect from live `onboard_account` wiring to
  sandbox-only `onboard_account_dry_run`, keep live onboarding parked, and make
  preview semantics explicit in UI and ledger
- branch: `codex/external-agent-lab-isolated`
- head: `b106da3` before contour changes
- touched files:
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_ui/index.html`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_live_server.py`
  - `tests/test_web_design_ui.py`
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-21/spec.md`
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-21/metrics.json`
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-21/closeout.md`
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-21/independent_audit.json`
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-21/screenshots/README.md`
- tests run:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter -q`
  - `git diff --check`
  - sandbox-phase HTTP verification for `/api/actions` and `/api/action`
- blocked risks:
  - real reserve-first onboarding is still deferred and intentionally remains
    parked in `sandbox_actions`
  - screenshots are deferred because this contour used unit/UI execution tests
    plus live HTTP verification instead of a local headless browser capture
- next exact command:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server -q`

## Verification

- tests:
  - live-server tests prove `onboard_account_dry_run` is parked in
    `live_readonly` and admitted in `sandbox_actions`
  - live-server tests prove `onboard_account` stays not admitted in
    `sandbox_actions`
  - UI tests prove Quick Start/modal wiring now dispatch
    `onboard_account_dry_run`
  - UI tests prove preview-only wording remains non-green and does not claim
    reserve admission
- build:
  - `git diff --check` passed
- manual:
  - local sandbox server returned
    `onboard_account_dry_run.available=true`
  - local sandbox server returned
    `onboard_account.available=false`
  - dry-run action packet returned
    `preview_only=true`, `ui_state=dry_run_ready`
  - live onboarding action returned
    `UI_ACTION_PHASE_NOT_ADMITTED`

## Artifacts

- spec:
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-21/spec.md`
- packet:
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-21/metrics.json`
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-21/independent_audit.json`
- report:
  - this closeout plus targeted unit-test and HTTP verification evidence

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed:
  `yes; browser surfaces still exclude token/path/auth/backend_id and preview action stays command-owned`

## Notes

- blockers encountered:
  - Quick Start and accounts onboarding surfaces were still wired to live
    `onboard_account` even though preview semantics already existed
  - previous sandbox-phase contour admitted live onboarding too early for the
    master-plan sequence and had to be tightened back to dry-run-only
- follow-up contour:
  - `WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS`
- resume from here:
  `dry-run preview path is now wired through Quick Start in sandbox; next move is explicit reserve-first live onboarding with proof and refresh`
