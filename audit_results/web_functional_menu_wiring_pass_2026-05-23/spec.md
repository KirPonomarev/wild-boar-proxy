# Spec: Web Functional Menu Wiring Pass

## Objective

Wire the already admitted runtime/accounts/API/diagnostics actions into the web
control surface truthfully, keep parked actions visibly parked during
`sandbox_actions`, and fix the provider split where API credential actions were
still reporting `openrouter` even though the current primary route is
`wbp-deepseek-v3`.

## In Scope

- `/api/actions` truth for important admitted and parked actions
- provider-aware `api_route_credential_check` execution
- provider-aware `api_route_connect` credential bridge selection
- targeted live-server tests for provider selection and forbidden browser fields
- browser proof that the quick-start/API surface reflects current DeepSeek route
  truth
- factual artifacts, redaction audit, and independent replay audit

## Out of Scope

- design polish or visual redesign
- new command capabilities without existing command-owner surfaces
- runtime/proxy repair reruns
- DeepSeek direct provider proof rerun
- isolated Codex app E2E

## Constraints

- canon order starts with `CANON.md`, then `MASTER_PLAN.md`
- command packets remain primary truth over UI color or copy
- sandbox phase must keep runtime mutations parked with exact disabled reasons
- browser must not supply `api_key`, `secret`, `token`, `auth`, `path`,
  `backend_id`, or `route_id`
- current working Codex must remain untouched

## Assumptions

- `FULL_SYSTEM_RUNTIME_AND_PROXY_PROOF_PASS` is already closed
- `DEEPSEEK_DIRECT_API_MINIMAL_TOKEN_PROOF_PASS` is already closed
- the live web server on `127.0.0.1:8788` is operating against the launch-copy
  sandbox
- the current primary API route truth is `wbp-deepseek-v3` / `deepseek`

## Acceptance Criteria

- [x] important admitted actions are reachable or explicitly disabled with exact
  reason
- [x] newly wired provider-aware credential actions use existing canonical
  command-owner surfaces
- [x] `api_route_credential_check` no longer reports `openrouter` when readonly
  route truth is `deepseek`
- [x] `api_route_connect` credential bridge prefers current primary route truth
  over stale fallback provider state
- [x] parked runtime actions remain parked with
  `UI_ACTION_PHASE_NOT_ADMITTED`
- [x] browser-facing API surface reflects `deepseek` +
  `DEEPSEEK_API_KEY` without leaking secret values
- [x] targeted tests, redaction audit, and independent replay audit pass

## Verification

- tests:
  - targeted `tests.test_web_design_live_server`
  - targeted `tests.test_web_design_ui`
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- manual:
  - inspect `/api/actions`, `/api/api-connections-readonly`, and live
    `api_route_credential_check` action packet
- live evidence:
  - `curl -s http://127.0.0.1:8788/api/actions`
  - `curl -s http://127.0.0.1:8788/api/api-connections-readonly`
  - `curl -s -X POST http://127.0.0.1:8788/api/action ... api_route_credential_check`

## Open Questions

- whether a later contour should add a dedicated quick-start button for
  credential status without relying on the broader API setup lane; not a blocker
  here because the admitted command surface is already reachable and truthful
