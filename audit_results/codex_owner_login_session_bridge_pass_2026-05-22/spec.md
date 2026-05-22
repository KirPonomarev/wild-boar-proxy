# Spec: Codex Owner Login Session Bridge Pass

## Objective

Implement a real Codex owner login session bridge for `Подключить аккаунт` so the web UI starts an owner-controlled device login session, shows device URL and code without browser secret intake, completes owner-side onboarding, and refreshes the account surface from canonical readonly truth.

## In Scope

- `accounts login start --provider codex --mode device --json`
- `accounts login status --session <id> --json`
- `accounts login complete --session <id> --json`
- `accounts login cancel --session <id> --json`
- sandbox-scoped login session store and auth artifact detection
- web server actions for start, status, complete, cancel
- UI session handoff for device URL, device code, and completion controls
- reserve-first onboarding through `accounts onboard --json --auth-ref`
- targeted tests, browser proof artifacts, and audit results

## Out of Scope

- browser token, password, path, auth file, or backend id input
- OAuth callback listener
- desktop redesign
- promotion to `active`
- legacy runtime surface retirement

## Constraints

- owner layer remains the auth owner
- browser payload stays bounded to `ui_action` and owner-created `session_id`
- auth writes stay inside sandbox paths
- success requires strict JSON packet plus readonly refresh proof
- new backend must land in `reserve`
- `active_routing_changed` must remain `false`

## Assumptions

- `cli-proxy-api -codex-device-login -no-browser` remains stable enough to emit device URL and code
- sandbox stable probe on the configured stable port is available during proof
- inherited full `tests.test_cli` composite timeout is separate from this contour logic unless localized otherwise

## Acceptance Criteria

- [x] Web `onboard_account` starts a Codex device login session instead of blocking onboarding immediately.
- [x] UI shows device URL, device code, and session-aware status without browser secret intake.
- [x] Owner-side status detects materialized sandbox auth artifact.
- [x] Owner-side complete runs onboarding and returns reserve-first proof.
- [x] Browser proof shows a new reserve account after refresh.
- [x] Ledger evidence shows real `onboard_account` and `account_login_complete` actions.
- [ ] Full composite unittest gate completes without timeout.

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - targeted CLI session tests: 9 tests, pass
  - targeted web suites: 146 tests, pass
  - focused CLI/web regression trio: 3 tests, pass
  - full composite gate with `tests.test_cli tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter -q`: timed out after 90 seconds
- build:
  - `git diff --check`
- manual:
  - direct HTTP action flow from `onboard_account` through `account_login_complete` returned `machine_error_code=OK`
- live evidence:
  - `evidence/login-start-packet.json`
  - `evidence/login-status-waiting.json`
  - `evidence/login-complete-packet.json`
  - `evidence/accounts-readonly-after.json`
  - `evidence/browser-ui-success.png`
  - `evidence/browser-run-summary.json`

## Open Questions

- Which test inside the inherited composite `tests.test_cli` gate still causes the 90-second timeout?
- Should the UI hide the completed owner overlay automatically after a successful refresh, or keep it visible as explicit completion proof?
