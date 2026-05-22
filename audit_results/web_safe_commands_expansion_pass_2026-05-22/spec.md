# Spec: WEB_SAFE_COMMANDS_EXPANSION_PASS

## Objective

Expand the web control layer so existing safe account and API owner commands are
wired into the browser with canonical bounded payloads, post-action refresh
truth, and no false-green UI.

## In Scope

- account validate/recheck web wiring
- account lifecycle action refresh truth hardening
- API route safe action web wiring
- browser payload bounding
- ledger/refresh truth handling
- targeted tests
- browser evidence

## Out of Scope

- new runtime command surfaces
- auth/login redesign
- desktop or packaging work
- rollout stage mutation
- design polish

## Constraints

- browser payload stays bounded to safe ids only
- strict JSON command packets remain source of truth
- readonly refresh is required after mutating actions
- runtime fixes stay minimal and only unblock truthful web behavior

## Assumptions

- `CLIProxyAPI` remains the engine
- the web layer remains a control surface only
- lifecycle commands may legitimately return non-green results when runtime
  verification fails; the UI must surface that honestly

## Acceptance Criteria

- [x] validate/recheck are available in web without confirmation drift
- [x] lifecycle actions require refresh truth and do not hold stale-green state
- [x] API safe actions are wired through bounded route ids
- [x] browser payload rejects forbidden secret/path fields
- [x] targeted tests pass
- [x] browser proof shows successful safe actions and honest non-green outcomes

## Verification

- tests: `audit_results/web_safe_commands_expansion_pass_2026-05-22/evidence/full-gate.txt`
- build: `audit_results/web_safe_commands_expansion_pass_2026-05-22/evidence/node-check.txt`
- manual: account and API screen interaction in isolated full-phase sandbox
- live evidence:
  - `audit_results/web_safe_commands_expansion_pass_2026-05-22/evidence/browser-run-summary.json`
  - `audit_results/web_safe_commands_expansion_pass_2026-05-22/evidence/browser-accounts-final.png`
  - `audit_results/web_safe_commands_expansion_pass_2026-05-22/evidence/browser-api-final.png`

## Open Questions

- whether promote/retire should gain stronger isolated-runtime proof support in a
  dedicated execution-core contour rather than inside web-surface expansion
