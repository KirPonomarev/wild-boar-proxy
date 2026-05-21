<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS_REOPEN

## Objective

Re-open and close `WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS` by proving one real
Quick Start live onboarding run in sandbox copy with reserve-first packet
evidence, canonical refresh proof, and action-ledger evidence.

## In Scope

- verify sandbox runner env carries full owner/runtime `WBP_*` path surface
- ensure owner-side helper subprocesses inherit derived runtime paths
- execute real sandbox web flow:
  `?screen=quick-start&source=live` -> `onboard_account`
- capture owner packet and refresh proof from sandbox-only surfaces
- verify forbidden browser fields are rejected by live onboarding action
- run mandatory verification commands and targeted tests

## Out of Scope

- API route create/import contour work
- desktop flow changes
- packaging/release work
- lifecycle promotion to active
- broad runtime/design refactors

## Constraints

- no browser intake for `token`, `secret`, `path`, `auth`, `backend_id`
- live success requires `accounts onboard --json` packet and accounts refresh
- new backend must land in `reserve`
- `active_routing_changed` must remain `false`
- sandbox copy only; primary working Codex profile is untouched

## Acceptance Criteria

- [x] sandbox Quick Start live path executes `onboard_account`
- [x] live packet returns `final_outcome=reserve_only_success`
- [x] packet proves `selected_backend_id` and `reserve_first_proven=true`
- [x] packet proves `pool_after_onboarding=reserve`
- [x] packet proves `active_routing_changed=false`
- [x] refresh after action shows new reserve account in web snapshot
- [x] action ledger shows real onboarding action
- [x] forbidden browser onboarding fields are rejected
- [x] mandatory test set passes
- [x] independent audit returns PASS with no blocker-level finding

## Verification

- required:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- targeted:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli.CliTests.test_accounts_onboard_passes_derived_runtime_paths_to_owner_helpers tests.test_cli.CliTests.test_accounts_onboard_explicit_auth_imports_backend_to_reserve_without_sync -q`

## Evidence

- `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/evidence/browser-run-network.json`
- `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/evidence/browser-run-summary.json`
- `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/screenshots/browser-quick-start-after-onboard.png`
