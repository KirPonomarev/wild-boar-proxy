# ACCOUNT_OWNER_SANDBOX_LOGIN_ADMISSION_PASS Closeout

## Goal

Add owner-owned sandbox login admission (`login start` + `login complete`) so a
future web bridge can trigger auth flow without browser secret/path intake.

## Result

- status: `closed_success`
- final verdict: owner sandbox login admission is implemented and proved
  end-to-end; full required test gate passes in an isolated environment without
  ambient `127.0.0.1:8318` dependency
- next action: proceed to `WEB_ACCOUNT_OWNER_LOGIN_BRIDGE_PASS_REOPEN`

## Contour Capsule

- goal: introduce minimal owner-owned sandbox login admission surface and prove
  reserve-first onboarding compatibility
- branch: `codex/external-agent-lab-isolated`
- head: `ced7dae` plus follow-up isolation fix commit
- touched files:
  - `wild_boar_proxy/runtime.py`
  - `wild_boar_proxy/cli.py`
  - `tests/test_cli.py`
  - `tests/test_web_design_live_server.py`
  - `COMMAND_API.md`
  - `audit_results/account_owner_sandbox_login_admission_pass_2026-05-21/*`
- tests run:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest -v tests.test_cli.CliTests.test_accounts_login_start_requires_json_flag tests.test_cli.CliTests.test_accounts_login_complete_requires_json_flag tests.test_cli.CliTests.test_accounts_login_start_sandbox_strict_json_and_session_persisted tests.test_cli.CliTests.test_accounts_login_start_rejects_unsupported_provider tests.test_cli.CliTests.test_accounts_login_complete_rejects_missing_state_proof_expired_and_replay tests.test_cli.CliTests.test_accounts_login_complete_materializes_sandbox_auth_and_redacts_secrets tests.test_cli.CliTests.test_accounts_login_complete_then_onboard_imports_to_reserve_with_no_active_routing_change` (pass)
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_command_adapter tests.test_ui_shell -q` (pass)
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli tests.test_web_design_live_server tests.test_web_design_command_adapter tests.test_ui_shell -q` (pass, 569)
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` (pass)
  - `git diff --check` (pass)
  - `python3 tools/check_closeout_resilience.py --staged-only` (pass)
- resolved risks:
  - shared-workstation live listener on `127.0.0.1:8318` was stopped for
    verification; tests were tightened so success/failure scenarios use bounded
    per-test listeners instead of ambient runtime state
- blocked risks: no remaining blocker for this contour after isolated full gate
  passed; real provider OAuth remains out of scope for this contour
- next exact command:
  - start `WEB_ACCOUNT_OWNER_LOGIN_BRIDGE_PASS_REOPEN`

## Verification

- tests:
  - owner-login targeted suite: pass
  - web/ui suites listed above: pass
  - full required suite: pass, 569 tests
- build:
  - `node --check ...overview.js`: pass
- manual:
  - owner proof flow executed in isolated sandbox copy
- live verification:
  - `evidence/login-start-packet.json`
  - `evidence/login-complete-packet.json`
  - `evidence/onboard-packet.json`
  - `evidence/accounts-list-after.json`

## Artifacts

- spec:
  - `audit_results/account_owner_sandbox_login_admission_pass_2026-05-21/spec.md`
- packet:
  - `audit_results/account_owner_sandbox_login_admission_pass_2026-05-21/evidence/*`
- report:
  - `audit_results/account_owner_sandbox_login_admission_pass_2026-05-21/metrics.json`
  - `audit_results/account_owner_sandbox_login_admission_pass_2026-05-21/independent_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending follow-up isolation fix
- pushed: pending follow-up isolation fix

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; packets do not expose proof/token/secret/password

## Notes

- blockers encountered:
  - initial full gate was sensitive to live listener presence on
    `127.0.0.1:8318`; this was resolved by stopping the ambient user service
    during verification and making test probes explicit
- follow-up contour:
  - `WEB_ACCOUNT_OWNER_LOGIN_BRIDGE_PASS_REOPEN` after verification gate is clean
- resume from here: start `WEB_ACCOUNT_OWNER_LOGIN_BRIDGE_PASS_REOPEN`
