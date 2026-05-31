# Spec: Codex Custom GPT API E2E Pass

## Objective

Wire the Codex Custom session prompt path from WBP web UI to the isolated
operator-surface Codex engine runner, while preserving server-issued model and
backend selection, strict browser payload limits, redacted transcript packets,
and no false claim that the WBP/CLIProxy route is proven without an independent
trace observer.

## In Scope

- `POST /api/codex/custom/sessions/:id/prompt`
- UI `Run prompt` control for the existing Codex Custom session panel
- server-owned `model_id` forwarding to `OperatorSurfaceSession.run_prompt`
- browser payload allowlist limited to `prompt`
- bounded response preview, response digest, latency and token-usage fields
- configured/proven split for WBP/CLIProxy path claims
- tests for success, forbidden fields, runner failure, cleaned session, and UI wiring

## Out of Scope

- live GPT account token burn without owner authorization
- independent WBP request tracing
- account rotation/load
- desktop packaging
- rich UI redesign
- mutation of current `~/.codex` or `/Applications/Codex.app`

## Constraints

- Browser must not send `model_id`, `backend_id`, `route_id`, `account_id`,
  `path`, `auth`, `api_key`, `secret`, or `token`.
- `wbp_path_proven` must be false unless an independent WBP trace is observed.
- `wbp_path_configured` may be true when the isolated engine config targets the
  WBP endpoint, `cliproxy` provider, and responses wire.
- Prompt transport must use stdin, not argv.
- Current Codex profile must not be used by the isolated engine.

## Acceptance Criteria

- [x] prompt endpoint exists and routes through session manager
- [x] browser payload is prompt-only
- [x] runner receives server-issued model id
- [x] response packet includes bounded response proof fields
- [x] false WBP route proof is prevented
- [x] UI exposes the prompt action and configured/proven status
- [x] targeted tests pass
- [x] independent audit reports no remaining false-green blocker
- [ ] live prompt through GPT accounts is run after explicit owner authorization
- [ ] independent WBP trace observer proves the actual request path

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_codex_custom_sessions tests.test_web_design_live_server tests.test_web_design_ui tests.test_operator_surface -q`
  - full suite gate to be recorded in closeout
- build:
  - `git diff --check`
- manual:
  - independent skeptical audit on current diff
- live evidence:
  - not run in this contour because the active thread has not supplied the
    `CANON.md` standing approval phrase for live runtime/account/API actions

## Open Questions

- Which independent WBP trace surface should become authoritative for marking
  `independent_wbp_trace_observed=true`?
