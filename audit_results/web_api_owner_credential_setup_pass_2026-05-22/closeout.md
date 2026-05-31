# WEB_API_OWNER_CREDENTIAL_SETUP_PASS Closeout

## Goal

Give `Подключить API` a real owner-credential continuation path when `openrouter`
credential material is missing, without accepting secrets in the browser.

## Result

- status: completed
- final verdict: inline owner credential setup lane is now visible on both Quick Start and API Connections, with bounded credential check and retry actions.
- next action: seed owner env on the live proof server when we want to prove the green connected path end to end.

## Contour Capsule

- goal: close the product gap between `credential missing` and a usable owner-side continuation path for API connect.
- branch: `codex/external-agent-lab-isolated`
- head: `dfbb768`
- touched files: `wild_boar_proxy/web_design_live_server.py`, `wild_boar_proxy/web_design_ui/index.html`, `wild_boar_proxy/web_design_ui/scripts/overview.js`, `wild_boar_proxy/web_design_ui/styles/overview.css`, `tests/test_web_design_live_server.py`, `tests/test_web_design_ui.py`
- tests run: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter tests.test_cli_external_models tests.test_external_models -q`; `git diff --check`
- blocked risks: live proof server still has no owner env for `openrouter`, so connected-route proof stays non-green until operator-side env is present.
- next exact command: `curl -sS -X POST http://127.0.0.1:8788/api/action -H 'Content-Type: application/json' -d '{"ui_action":"api_route_credential_check"}'`

## Verification

- tests:
  - `Ran 194 tests in 20.600s`
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- manual:
  - Quick Start live missing-credential lane
  - Quick Start `Проверить credential`
  - API Connections live missing-credential lane
- live verification:
  - `audit_results/web_api_owner_credential_setup_pass_2026-05-22/evidence/browser-run-summary.json`
  - `audit_results/web_api_owner_credential_setup_pass_2026-05-22/evidence/api-route-credential-check-missing.json`
  - `audit_results/web_api_owner_credential_setup_pass_2026-05-22/evidence/api-route-connect-missing.json`

## Artifacts

- spec: `audit_results/web_api_owner_credential_setup_pass_2026-05-22/spec.md`
- packet: `audit_results/web_api_owner_credential_setup_pass_2026-05-22/evidence/api-route-connect-missing.json`
- report: `audit_results/web_api_owner_credential_setup_pass_2026-05-22/independent_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; `redaction-check.json` confirms no secret/token material in saved evidence

## Notes

- blockers encountered: live proof server restart was required so the new `api_route_credential_check` handler and metadata were actually available at `127.0.0.1:8788`.
- follow-up contour: seed owner env on the live proof server and rerun connect for a green route proof when needed.
- resume from here: CLOSED
