# WEB_OWNER_ONBOARD_REAL_LOGIN_FLOW_REPAIR Closeout

## Goal

Repair web account connect so the live button uses the owner onboarding flow
that launches CLIProxyAPI Codex login and imports the resulting auth artifact to
reserve, without browser secret/path/auth-ref intake.

## Result

- status: closed_success
- final verdict: web live account connect no longer stays in dry-run/sandbox synthetic-login bridge; it calls `accounts onboard --json`
- next action: use the live URL and complete the CLIProxyAPI login prompt opened by the owner flow

## Contour Capsule

- goal: restore real owner onboarding from web through `accounts onboard --json` and CLIProxyAPI login
- branch: codex/external-agent-lab-isolated
- head: base 91eceb1 before closeout commit; final commit recorded by git after staging
- touched files: COMMAND_API.md; wild_boar_proxy/sandbox_owner_helpers.py; wild_boar_proxy/web_design_live_server.py; wild_boar_proxy/web_design_ui/scripts/overview.js; tests/test_cli.py; tests/test_web_design_live_server.py; audit_results/web_owner_onboard_real_login_flow_repair_2026-05-21/*
- tests run: node --check overview.js; targeted CLI/web tests; unittest tests.test_cli tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell -q
- blocked risks: real provider callback listener remains out of scope; human login completion still happens in the CLIProxyAPI-opened browser flow
- next exact command: open http://127.0.0.1:8788/?screen=quick-start&source=live and click Подключить аккаунт

## Verification

- tests: full required unittest gate passed, `Ran 624 tests in 317.630s OK`
- build: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` passed
- manual: fresh browser DOM showed live modal with `owner onboard flow`, `Live reserve-first`, and CLIProxyAPI login wording
- live verification: fresh sandbox web server on 127.0.0.1:8788 with screenshot evidence at `evidence/live-onboard-modal.png`

## Artifacts

- spec: `audit_results/web_owner_onboard_real_login_flow_repair_2026-05-21/spec.md`
- packet: `audit_results/web_owner_onboard_real_login_flow_repair_2026-05-21/metrics.json`
- report: `audit_results/web_owner_onboard_real_login_flow_repair_2026-05-21/independent_audit.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending in this closeout turn
- pushed: pending in this closeout turn

## Scope Check

- unrelated work mixed in: no; unrelated pre-existing untracked files were ignored
- private-data risk reviewed: yes; no auth files or secrets were staged, screenshot contains only UI

## Notes

- blockers encountered: full gate failed while live `io.cli-proxy-api` occupied 8318; service was temporarily stopped for the gate and restored afterward as PID 54425
- follow-up contour: WEB_API_ROUTE_CREATE_OR_ADOPT_SERVER_OWNED_PASS or real provider callback owner surface if the product needs Wild Boar-owned callback handling
- resume from here: CLOSED
