<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS_REOPEN Closeout

## Goal

Re-open the live web account-connect lane and close it with factual proof that
Quick Start `onboard_account` runs real sandbox onboarding, lands the new
backend in `reserve`, refreshes web truth, and records the action in ledger.

## Result

- status: `closed_success`
- final verdict:
  `LIVE_ONBOARDING_REOPEN_CLOSED_WITH_RESERVE_FIRST_PACKET_AND_REFRESH_PROOF`
- next action:
  continue master-plan sequence with `WEB_API_ROUTE_CREATE_OR_ADOPT_SERVER_OWNED_PASS`

## Contour Capsule

- goal:
  repair sandbox owner/runtime env wiring and close live onboarding proof without
  widening scope beyond this contour
- branch: `codex/external-agent-lab-isolated`
- head: `d681172`
- touched files:
  - `wild_boar_proxy/runtime.py`
  - `wild_boar_proxy/web_design_live_server.py`
  - `tests/test_cli.py`
  - `tests/test_web_design_live_server.py`
  - `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/spec.md`
  - `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/metrics.json`
  - `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/independent_audit.json`
  - `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/closeout.md`
  - `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/evidence/browser-run-summary.json`
  - `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/evidence/browser-run-network.json`
  - `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/screenshots/browser-quick-start-after-onboard.png`
- tests run:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli.CliTests.test_accounts_onboard_passes_derived_runtime_paths_to_owner_helpers tests.test_cli.CliTests.test_accounts_onboard_explicit_auth_imports_backend_to_reserve_without_sync -q`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - none at blocker severity inside this contour
- next exact command:
  - `python3 -m wild_boar_proxy.web_design_live_server --port 8788`

## Verification

- packet proof:
  - `final_outcome=reserve_only_success`
  - `selected_backend_id=auth`
  - `reserve_first_proven=true`
  - `pool_after_onboarding=reserve`
  - `active_routing_changed=false`
  - `validate_outcome=ok`
  - `sync_outcome=ok`
- refresh proof:
  - before onboarding visible accounts: `0`
  - after onboarding visible accounts: `1`
  - after onboarding reserve count: `1`
  - visible backend in reserve: `auth`
- ledger proof:
  - entry recorded with `ui_action=onboard_account`,
    `final_outcome=reserve_only_success`,
    `selected_backend_id=auth`
- guard proof:
  - tests confirm `onboard_account` rejects browser `auth_ref`, `source_dir`,
    `password`, `backend_id`
  - live packet changed-file paths remain inside sandbox profile/data tree

## Artifacts

- spec:
  - `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/spec.md`
- metrics:
  - `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/metrics.json`
- independent audit:
  - `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/independent_audit.json`
- evidence:
  - `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/evidence/browser-run-summary.json`
  - `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/evidence/browser-run-network.json`
- screenshot:
  - `audit_results/web_safe_account_connect_live_pass_reopen_2026-05-21/screenshots/browser-quick-start-after-onboard.png`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed:
  `yes; browser-side forbidden fields are rejected and no primary Codex profile writes were evidenced`

## Notes

- interruption point recovered:
  - previous run stopped after launching long browser proof command; the command
    completed successfully and returned factual JSON packet/refresh evidence
- independent audit:
  - separate agent fact-check returned `PASS` with no blocker findings
- residual risks:
  - broader runtime readiness is outside this contour and remains for later
    master-plan contours
- resume from here:
  `start WEB_API_ROUTE_CREATE_OR_ADOPT_SERVER_OWNED_PASS with the same sandbox-only evidence discipline`
