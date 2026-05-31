# Spec: WEB_ACCOUNT_AND_API_CONNECT_E2E_HARDENING_PASS

## Objective

Prove that the web Quick Start screen can drive both real product-facing bounded flows:

- `Подключить аккаунт` -> owner Codex device login session -> reserve-first onboarding -> readonly refresh
- `Подключить API` -> owner credential bridge -> server-owned route add/adopt -> validate -> readonly refresh

The browser must not intake secrets, paths, auth refs, backend ids, or API keys.

## In Scope

- Fix live E2E gaps between already-closed owner/runtime contours and the Quick Start web UI.
- Verify account connect with `accounts login start/status/complete --provider codex --mode device`.
- Verify API connect with owner-side credential status/admit and route validate.
- Keep UI behavior aligned with readonly refresh truth.
- Add regression tests for the discovered API secret-status gap and the stray account-login overlay regression.
- Collect seeded sandbox evidence and browser proof.

## Out of Scope

- Desktop packaging
- OAuth callback implementation
- Promotion from `reserve` into `active`
- Cleanup of local runtime folders or unrelated untracked artifacts
- Visual redesign

## Constraints

- `CLIProxyAPI` remains the engine.
- Wild Boar Proxy remains the control layer.
- Browser payload must not include `token`, `secret`, `password`, `api_key`, `path`, `auth`, `auth_ref`, `backend_id`, or `route_id`.
- Account success is only valid after owner packet plus readonly refresh.
- API success is only valid after credential bridge, route validate, and readonly refresh.

## Assumptions

- Seeded sandbox evidence is acceptable proof for this contour.
- Owner-side credential admission may rely on `OPENROUTER_API_KEY` in the sandbox environment.
- Device login proof may use the existing fake device-login helper for bounded browser verification.

## Acceptance Criteria

- [x] Quick Start account connect shows Codex device URL/code and completes into `reserve`.
- [x] Quick Start API connect shows connected primary route after owner credential admission and validate.
- [x] Readonly refresh truth reflects both flows without false-green UI.
- [x] Browser payload stays bounded and redacted.
- [x] Targeted regressions are covered by tests.

## Verification

- tests:
  - `tests.test_cli_external_models`
  - `tests.test_web_design_live_server`
  - `tests.test_web_design_ui`
  - full required composite suite
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- manual:
  - seeded live browser run on Quick Start
- live evidence:
  - `audit_results/web_account_and_api_connect_e2e_hardening_pass_2026-05-22/evidence/*`

## Open Questions

- None for contour closeout; next work should be product lifecycle polish rather than runtime repair.
