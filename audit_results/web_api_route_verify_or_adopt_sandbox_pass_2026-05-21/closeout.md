# WEB_API_ROUTE_VERIFY_OR_ADOPT_SANDBOX_PASS Closeout

## Goal

Give Quick Start a real sandbox API verification lane that uses bounded route snapshot truth, a server-owned route check, and sandbox-owned readonly refresh without exposing raw secrets or inventing a browser setup flow.

## Result

- status: closed
- final verdict: Quick Start now verifies an existing sandbox API route through `api_route_check`, then confirms the result through sandbox-owned `api_connections_readonly` refresh with projected observed-route state.
- next action: proceed to `WEB_QUICK_START_CHECK_ALL_ORCHESTRATOR_PASS`

## Contour Capsule

- goal: Close Quick Start API route verification in sandbox with packet truth plus sandbox-owned readonly refresh.
- branch: codex/external-agent-lab-isolated
- head: 347cede
- touched files: wild_boar_proxy/external_models/contracts.py, wild_boar_proxy/external_models/lifecycle.py, wild_boar_proxy/external_models/routes.py, wild_boar_proxy/ui_shell.py, wild_boar_proxy/web_design_live_server.py, wild_boar_proxy/web_design_ui/scripts/overview.js, tests/test_ui_shell.py, tests/test_web_design_live_server.py, tests/test_web_design_ui.py, tests/test_web_ui.py, audit_results/web_api_route_verify_or_adopt_sandbox_pass_2026-05-21/*
- tests run: node syntax check, unittest suite for ui_shell/web_design_live_server/web_design_ui/web_ui, git diff --check, closeout resilience check, live sandbox HTTP proof, browser Quick Start verification, independent audit
- blocked risks: no bounded adopt-existing server-owned lane exists yet; Quick Start remains verify-only by design
- next exact command: git push origin codex/external-agent-lab-isolated

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_ui_shell tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_ui -q`
- build:
  - `git diff --check`
- manual:
  - sandbox harness at `http://127.0.0.1:56582`
  - Quick Start API card showed `wbp-openrouter-primary`, `provider=openrouter`, `secret_ref=OPENROUTER_API_KEY`
  - Quick Start button opened confirmation and completed `api_route_check`
  - action panel reported `ok_refresh_complete`
  - action ledger recorded `api_route_check`
- live verification:
  - packet proof in `audit_results/web_api_route_verify_or_adopt_sandbox_pass_2026-05-21/evidence/api-route-check-packet.json`
  - sandbox-owned refresh proof in `audit_results/web_api_route_verify_or_adopt_sandbox_pass_2026-05-21/evidence/api-connections-readonly-after.json`
  - browser summary in `audit_results/web_api_route_verify_or_adopt_sandbox_pass_2026-05-21/evidence/ui-run-summary.json`
  - independent audit in `audit_results/web_api_route_verify_or_adopt_sandbox_pass_2026-05-21/independent_audit.json`

## Artifacts

- spec: `audit_results/web_api_route_verify_or_adopt_sandbox_pass_2026-05-21/spec.md`
- packet: `audit_results/web_api_route_verify_or_adopt_sandbox_pass_2026-05-21/evidence/api-route-check-packet.json`
- report: `audit_results/web_api_route_verify_or_adopt_sandbox_pass_2026-05-21/metrics.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: 347cede
- pushed: pending

## Scope Check

- unrelated work mixed in: no; the contour stayed inside API route verify-first behavior, bounded projection, tests, and evidence
- private-data risk reviewed: yes; artifacts retain `secret_ref` only and exclude secret value, tokens, raw paths, and browser secret input

## Notes

- blockers encountered: refreshed route rows initially stayed at `not checked` because readonly snapshot did not project bounded observed-route state from `external-models status`; fixed by surfacing sanitized observed-route data through the command packet and mapping it into the readonly row model
- follow-up contour: `WEB_QUICK_START_CHECK_ALL_ORCHESTRATOR_PASS`
- resume from here: CLOSED
