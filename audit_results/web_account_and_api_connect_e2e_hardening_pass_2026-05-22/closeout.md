# WEB_ACCOUNT_AND_API_CONNECT_E2E_HARDENING_PASS Closeout

## Goal

Make the Quick Start web UI truthfully drive both daily operator flows:

- `Подключить аккаунт` -> owner Codex device login session -> reserve-first onboarding -> readonly refresh
- `Подключить API` -> owner credential status/admit -> route add/adopt -> validate -> readonly refresh

without browser secret intake, false-green UI, or drift from command-packet truth.

## Result

- status: `closed_success`
- final verdict: Quick Start now completes both account connect and API connect end-to-end with route-specific truth, bounded browser payloads, live browser proof, and green verification gates
- next action: continue product work on top of this web/operator checkpoint rather than reopening owner/runtime foundations

## Contour Capsule

- goal: harden the Quick Start web surface so it can add a Codex account into `reserve` and connect a validated API route through owner-side credential admission
- branch: `codex/external-agent-lab-isolated`
- head: `2bbdb7b`
- touched files:
  - `tests/test_cli_external_models.py`
  - `tests/test_web_design_live_server.py`
  - `tests/test_web_design_ui.py`
  - `wild_boar_proxy/external_models/lifecycle.py`
  - `wild_boar_proxy/external_models/routes.py`
  - `wild_boar_proxy/ui_shell.py`
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/spec.md`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/metrics.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/independent_audit.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/closeout.md`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/account-login-start.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/account-login-status.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/account-login-complete.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/accounts-refresh-after.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/api-credential-status-before.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/api-credential-admit.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/api-route-connect.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/api-route-validate.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/api-credential-status-after.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/api-routes-after.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/api-connections-refresh-after.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/browser-run-summary.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/browser-final-quick-start.png`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/composite-gate-result.txt`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/redaction-check.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/seeded-run-manifest.json`
- tests run:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` -> pass
  - `git diff --check` -> pass
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli_external_models -q` -> `Ran 25 tests in 7.151s OK`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_ui -q` -> `Ran 58 tests in 1.479s OK`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server -q` -> `Ran 67 tests in 10.737s OK`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_cli tests.test_cli_external_models tests.test_external_models -q` -> `Ran 592 tests in 193.826s OK`
- blocked risks: no blocking risks remain inside contour scope; real provider OAuth and active-pool promotion remain explicit future contours rather than hidden gaps in this one
- next exact command: `python3 tools/check_closeout_resilience.py --staged-only`

## Verification

- tests:
  - API route secret truth regression: pass
  - API route connect overlay separation regression: pass
  - full required composite suite: `Ran 592 tests in 193.826s OK`
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`: pass
  - `git diff --check`: pass
- manual:
  - seeded Quick Start browser run completed account connect into `reserve`
  - seeded Quick Start browser run completed API connect into connected openrouter route
- live verification:
  - account handoff showed real owner device URL/code and completed through `account_login_complete`
  - API connect refreshed Quick Start to `secret_ref available` plus `route check ok`
  - `api_route_connect` no longer renders the account-login overlay/window surface

## Artifacts

- spec:
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/spec.md`
- packet:
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/account-login-start.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/account-login-status.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/account-login-complete.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/api-credential-status-before.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/api-credential-admit.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/api-route-connect.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/api-route-validate.json`
- report:
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/metrics.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/independent_audit.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/browser-run-summary.json`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/composite-gate-result.txt`
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/redaction-check.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: not-yet

## Scope Check

- unrelated work mixed in: no; the contour stayed inside web account/API connect truth, regressions, and audit evidence
- private-data risk reviewed: yes; device code, temp sandbox paths, and owner-env secret literals were redacted from persisted evidence

## Notes

- blockers encountered:
  - readonly Quick Start API truth originally treated any secret in `secrets.env` as route success; this was corrected to route-specific `secret_ref` truth
  - `api_route_connect` originally reused the account-login overlay path and produced a misleading owner-login surface after API success; this was gated to account-login actions only
- follow-up contour:
  - next product contour should build on this checkpoint rather than reopen cleanup; likely account lifecycle polish or true provider-specific UX beyond owner-env admission
- resume from here: CLOSED
