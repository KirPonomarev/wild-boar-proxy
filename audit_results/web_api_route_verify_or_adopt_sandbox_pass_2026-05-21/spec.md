# Spec: WEB_API_ROUTE_VERIFY_OR_ADOPT_SANDBOX_PASS

## Objective

Give Quick Start a real sandbox API route verification lane that shows one bounded main route, exposes `provider` and `secret_ref` without secret value leakage, runs a server-owned route check, and only reports success after packet truth plus sandbox-owned readonly refresh.

## In Scope

- Quick Start API card uses bounded `api/api-connections-readonly` snapshot truth.
- `#quickStartCheckApiAction` is wired to admitted `api_route_check` in `sandbox_actions`.
- Post-action refresh uses sandbox-owned `api/api-connections-readonly` truth.
- Readonly route rows project bounded observed-route status from the canonical external-models status packet.
- Tests, browser verification, evidence pack, independent audit, closeout.

## Out of Scope

- Browser API key / secret creation.
- New route creation through web.
- Full route management UI in Quick Start.
- `Check All`, desktop port, lifecycle expansion, redesign.
- Any write into the working Codex profile/data.

## Constraints

- Browser never sends `token`, `secret`, `path`, `auth`, or `backend_id`.
- Secret value stays hidden; only `secret_ref` is displayable.
- Green UI requires action packet plus sandbox-owned readonly refresh.
- Quick Start remains verify-first; no fake adopt/create path is invented.
- Only sandbox-owned write/read surfaces are allowed.

## Assumptions

- `WEB_SANDBOX_ACTION_TARGET_AND_PHASE_PASS` is already closed.
- Account onboarding contours are already closed.
- `api_route_check` is admitted in `sandbox_actions`.
- No bounded server-owned adopt-existing lane exists yet, so this contour closes verify-only.

## Acceptance Criteria

- [x] Main API route is visible in Quick Start when a route exists.
- [x] `secret_ref` is shown and secret value is not shown.
- [x] `Проверить API` runs admitted `api_route_check` from Quick Start.
- [x] Post-action refresh uses sandbox-owned readonly route truth.
- [x] Refreshed route snapshot projects observed route verification state (`validation_label`, `last_checked`).
- [x] Green verdict only appears after packet truth plus refresh truth.
- [x] Quick Start does not become a full route-management surface.

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_ui_shell tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_ui -q`
- build:
  - `git diff --check`
- manual:
  - sandbox harness on `http://127.0.0.1:56582`
  - Quick Start button enabled, confirmation shown, action panel shows `ok_refresh_complete`, ledger records `api_route_check`
- live evidence:
  - `audit_results/web_api_route_verify_or_adopt_sandbox_pass_2026-05-21/evidence/api-route-check-packet.json`
  - `audit_results/web_api_route_verify_or_adopt_sandbox_pass_2026-05-21/evidence/api-connections-readonly-after.json`
  - `audit_results/web_api_route_verify_or_adopt_sandbox_pass_2026-05-21/evidence/ui-run-summary.json`
  - `audit_results/web_api_route_verify_or_adopt_sandbox_pass_2026-05-21/independent_audit.json`

## Open Questions

- Bounded `adopt-existing` API lane still does not exist as a server-owned surface; keep this as a future contour instead of inventing it in Quick Start.
