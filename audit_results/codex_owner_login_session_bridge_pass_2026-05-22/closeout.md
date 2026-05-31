# CODEX_OWNER_LOGIN_SESSION_BRIDGE_PASS Closeout

## Goal

Make `Подключить аккаунт` use a real owner-controlled Codex device login session bridge, then complete reserve-first onboarding through owner-side packets and readonly refresh proof.

## Result

- status: `closed_success`
- final verdict: the sessionized Codex owner login bridge is now formally closed with full gate, browser proof, reserve-first proof, and sandbox isolation proof
- next action: `LEGACY_CODEX_RUNTIME_SURFACES_RETIREMENT_PASS`

## Contour Capsule

- goal: sessionize Codex account login so web starts owner login, shows device handoff, completes owner onboarding, and refreshes reserve state
- branch: `codex/external-agent-lab-isolated`
- head: `32eba15`
- touched files:
  - `tests/test_cli.py`
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/spec.md`
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/metrics.json`
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/independent_audit.json`
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/closeout.md`
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/evidence/composite-gate-result.txt`
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/evidence/sandbox-isolation-proof.json`
- tests run:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` -> pass
  - `git diff --check` -> pass
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli -q` -> `Ran 407 tests in 178.812s OK`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter -q` -> `Ran 553 tests in 194.179s OK`
- blocked risks:
  - none for this contour
  - the earlier 90-second wrapper was shorter than the real suite duration
- next exact command: `python3 tools/check_closeout_resilience.py --staged-only`

## Verification

- tests:
  - `tests.test_cli`: pass
  - `tests.test_cli tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter`: pass
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- manual:
  - direct HTTP action flow previously reached `machine_error_code=OK`, `final_outcome=explicit_auth_imported_to_reserve`, `selected_backend_id=device-login`
- live verification:
  - saved browser quick-start proof reached one reserve backend after refresh and recorded a successful `account_login_complete` ledger entry
  - sandbox isolation proof records `current_session_untouched=true`, `separate_profile=true`, `separate_data_dir=true`, `separate_port=true`

## Artifacts

- spec:
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/spec.md`
- packet:
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/evidence/login-start-packet.json`
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/evidence/login-status-waiting.json`
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/evidence/login-complete-packet.json`
- report:
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/metrics.json`
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/independent_audit.json`
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/evidence/browser-run-summary.json`
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/evidence/composite-gate-result.txt`
  - `audit_results/codex_owner_login_session_bridge_pass_2026-05-22/evidence/sandbox-isolation-proof.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: not-yet

## Scope Check

- unrelated work mixed in: no unrelated subsystem expansion; edits stayed inside this contour's test and audit truth surfaces
- private-data risk reviewed: yes; no token or password value was emitted, and the saved evidence remains redacted

## Notes

- blockers encountered:
  - the earlier 90-second wrapper was shorter than the real composite suite duration
  - a stale sandbox-era test expected `LOGIN_PROVIDER_UNSUPPORTED` for `provider=codex` without `mode=device`; the current command contract correctly returns `LOGIN_MODE_UNSUPPORTED`
- follow-up contour:
  - `LEGACY_CODEX_RUNTIME_SURFACES_RETIREMENT_PASS`
- resume from here: CLOSED after commit + push
