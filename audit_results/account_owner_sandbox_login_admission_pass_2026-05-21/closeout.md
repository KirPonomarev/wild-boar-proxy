# ACCOUNT_OWNER_SANDBOX_LOGIN_ADMISSION_PASS Closeout

## Goal

Add owner-owned sandbox login admission (`login start` + `login complete`) so a
future web bridge can trigger auth flow without browser secret/path intake.

## Result

- status: `STOP_AND_DIAGNOSE`
- final verdict: implementation and owner proof are complete; full required test
  gate is blocked by live listener interference on `127.0.0.1:8318`
- next action: rerun full required unittest gate in isolated environment where
  `127.0.0.1:8318` is not occupied by live `cli-proxy`

## Contour Capsule

- goal: introduce minimal owner-owned sandbox login admission surface and prove
  reserve-first onboarding compatibility
- branch: `codex/external-agent-lab-isolated`
- head: `ab81955`
- touched files:
  - `wild_boar_proxy/runtime.py`
  - `wild_boar_proxy/cli.py`
  - `tests/test_cli.py`
  - `COMMAND_API.md`
  - `audit_results/account_owner_sandbox_login_admission_pass_2026-05-21/*`
- tests run:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest -v tests.test_cli.CliTests.test_accounts_login_start_requires_json_flag tests.test_cli.CliTests.test_accounts_login_complete_requires_json_flag tests.test_cli.CliTests.test_accounts_login_start_sandbox_strict_json_and_session_persisted tests.test_cli.CliTests.test_accounts_login_start_rejects_unsupported_provider tests.test_cli.CliTests.test_accounts_login_complete_rejects_missing_state_proof_expired_and_replay tests.test_cli.CliTests.test_accounts_login_complete_materializes_sandbox_auth_and_redacts_secrets tests.test_cli.CliTests.test_accounts_login_complete_then_onboard_imports_to_reserve_with_no_active_routing_change` (pass)
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_command_adapter tests.test_ui_shell -q` (pass)
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli tests.test_web_design_live_server tests.test_web_design_command_adapter tests.test_ui_shell -q` (fail, 6)
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` (pass)
  - `git diff --check` (pass)
  - `python3 tools/check_closeout_resilience.py --staged-only` (pass)
- blocked risks:
  - shared-workstation live listener on `127.0.0.1:8318` changes health/sync
    outcomes for parts of `tests.test_cli` that assume deterministic absence or
    controlled probe state
- next exact command:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli tests.test_web_design_live_server tests.test_web_design_command_adapter tests.test_ui_shell -q`

## Verification

- tests:
  - owner-login targeted suite: pass
  - web/ui suites listed above: pass
  - full required suite: fail with 6 assertions (see evidence)
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
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; packets do not expose proof/token/secret/password

## Notes

- blockers encountered:
  - required full gate includes `tests.test_cli` cases that are sensitive to
    live listener presence on `127.0.0.1:8318`
  - listener confirmed by `evidence/listener-8318.txt`
- follow-up contour:
  - `WEB_ACCOUNT_OWNER_LOGIN_BRIDGE_PASS_REOPEN` after verification gate is clean
- resume from here: rerun full required unittest command in isolated runtime
  environment, then finalize contour close
