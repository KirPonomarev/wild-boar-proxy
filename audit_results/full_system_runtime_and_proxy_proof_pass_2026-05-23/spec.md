# Spec: Full System Runtime And Proxy Proof Pass

## Objective

Prove that the default managed runtime and the CLIProxy-backed proxy path are
working under bounded load, that the 25-account registry truth remains intact,
and that post-load runtime truth stays honest without false-green or current
Codex mutation.

## In Scope

- fresh runtime preflight with `status --json`, `healthcheck --json`,
  `accounts list --json`, and `rollout rotation inspect --json`
- canonical owner-path proxy smoke via `launch smoke --json`
- bounded direct proxy `/responses` load through runtime helper transport
- post-load reclear with `sync --json`, `status --json`, `healthcheck --json`,
  `accounts list --json`, and `rollout rotation inspect --json`
- runtime/proxy artifact packet, redaction audit, and independent audit

## Out of Scope

- DeepSeek direct API final proof
- isolated Codex app launch/E2E
- web menu wiring expansion
- policy-stage promotion or reserve mutation
- stable-15 or active-only-traffic claims

## Constraints

- `CANON.md` then `MASTER_PLAN.md` then runtime/contracts canon order
- JSON command packets remain the primary truth surface
- no direct edits to runtime JSON state
- no secret values in artifacts
- no current Codex mutation
- bounded load only; no retry storm

## Assumptions

- `SANDBOX_RUNTIME_AND_DEEPSEEK_PARITY_FIX_GATE` already passed materially
- owner-path `launch smoke --json` is the canonical smoke surface
- direct proxy load should reuse runtime helper transport, not ad hoc HTTP
- policy drift limits claims but does not block bounded runtime/proxy proof

## Acceptance Criteria

- [x] fresh preflight shows runtime status and healthcheck OK
- [x] 25 managed accounts truth is captured
- [x] canonical owner-path smoke passes
- [x] bounded proxy load completes at concurrency 3 across 20 requests
- [x] bounded load failures are classified honestly
- [x] post-load reclear remains OK and rotation evidence stays present
- [x] no false-green, no pool corruption, no current Codex mutation

## Verification

- tests:
  - targeted `tests.test_cli` runtime/proxy owner-surface cases
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- manual:
  - inspect baseline/proxy/load/post-load packets
- live evidence:
  - `launch smoke --json`
  - bounded `/responses` load through runtime helpers
  - post-load `sync/status/healthcheck/rotation`

## Open Questions

- none for this contour; the remaining next-step question is DeepSeek direct
  proof in the following contour
