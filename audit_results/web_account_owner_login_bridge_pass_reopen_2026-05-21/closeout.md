<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WEB_ACCOUNT_OWNER_LOGIN_BRIDGE_PASS_REOPEN Closeout

## Goal

Make the web `Подключить аккаунт` action use the owner-owned sandbox login
bridge instead of a dry-run loop or browser-side secret intake.

## Result

- status: `closed_success`
- final verdict:
  `WEB_OWNER_LOGIN_BRIDGE_CONNECTED_WITH_RESERVE_FIRST_REFRESH_PROOF`
- next action:
  real provider login/OAuth callback contour, if the product goal is actual
  user login rather than sandbox admission proof

## Contour Capsule

- goal:
  connect web onboarding to owner login start/complete and reserve-first onboard
  while preserving browser no-secret/no-path boundary
- branch: `codex/external-agent-lab-isolated`
- head: pending commit
- touched files:
  - `wild_boar_proxy/runtime.py`
  - `wild_boar_proxy/web_design_command_adapter.py`
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_cli.py`
  - `tests/test_web_design_command_adapter.py`
  - `tests/test_web_design_live_server.py`
  - `audit_results/web_account_owner_login_bridge_pass_reopen_2026-05-21/spec.md`
  - `audit_results/web_account_owner_login_bridge_pass_reopen_2026-05-21/metrics.json`
  - `audit_results/web_account_owner_login_bridge_pass_reopen_2026-05-21/independent_audit.json`
  - `audit_results/web_account_owner_login_bridge_pass_reopen_2026-05-21/closeout.md`
  - `audit_results/web_account_owner_login_bridge_pass_reopen_2026-05-21/evidence/browser-run-summary.json`
  - `audit_results/web_account_owner_login_bridge_pass_reopen_2026-05-21/evidence/browser-run-network.json`
  - `audit_results/web_account_owner_login_bridge_pass_reopen_2026-05-21/screenshots/browser-quick-start-login-bridge-after-onboard.png`
- tests run:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest -q tests.test_cli.CliTests.test_accounts_login_complete_materializes_sandbox_auth_and_redacts_secrets tests.test_cli.CliTests.test_accounts_login_complete_then_onboard_imports_to_reserve_with_no_active_routing_change`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest -q tests.test_web_design_live_server.WebDesignLiveServerTests.test_onboard_account_action_executes_exact_command_without_browser_args tests.test_web_design_command_adapter tests.test_web_design_ui.WebDesignUiTests.test_onboard_modal_switches_to_live_connect_after_admitted_preview`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`
  - `git diff --check`
- browser proof:
  - opened live Quick Start on sandbox copy
  - clicked `Подключить аккаунт`
  - confirmed `onboard_account`
  - observed login bridge completion
  - observed reserve account after accounts-readonly refresh
- blocked risks:
  - no remaining blocker inside sandbox bridge contour
- next exact command:
  - define real provider owner login/OAuth callback contour if actual provider login is required

## Verification

- full required gate:
  - `Ran 632 tests in 271.326s`
  - `OK`
- browser packet proof:
  - `final_outcome=explicit_auth_imported_to_reserve`
  - `selected_backend_id=sandbox-synthetic`
  - `reserve_first_proven=true`
  - `login_bridge.status=completed`
  - `raw_auth_ref_exposed_in_action_response=false`
- refresh proof:
  - before onboarding visible accounts: `0`
  - after onboarding visible accounts: `1`
  - visible backend `sandbox-synthetic` in `reserve`
- guard proof:
  - browser action remains only `ui_action`
  - internal auth-ref command remains `ui_enabled=false`
  - raw auth path is not emitted in web action response
- service handling:
  - `io.cli-proxy-api` on `127.0.0.1:8318` was temporarily booted out for the
    full test gate and restored afterwards

## Artifacts

- spec:
  - `audit_results/web_account_owner_login_bridge_pass_reopen_2026-05-21/spec.md`
- metrics:
  - `audit_results/web_account_owner_login_bridge_pass_reopen_2026-05-21/metrics.json`
- independent audit:
  - `audit_results/web_account_owner_login_bridge_pass_reopen_2026-05-21/independent_audit.json`
- evidence:
  - `audit_results/web_account_owner_login_bridge_pass_reopen_2026-05-21/evidence/browser-run-summary.json`
  - `audit_results/web_account_owner_login_bridge_pass_reopen_2026-05-21/evidence/browser-run-network.json`
- screenshot:
  - `audit_results/web_account_owner_login_bridge_pass_reopen_2026-05-21/screenshots/browser-quick-start-login-bridge-after-onboard.png`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: `no`
- layer boundary:
  - owner layer owns sandbox auth materialization
  - web layer only orchestrates owner command packets and refresh proof
- private-data risk reviewed:
  - yes; browser does not submit secrets or paths, and action response does not
    expose raw sandbox auth path

## Notes

- this is still sandbox login admission, not real provider OAuth
- `8318` listener was restored after the test gate
- resume from here:
  `start a real provider owner-login callback contour, or proceed to API route create/adopt if product priority shifts back to API`
