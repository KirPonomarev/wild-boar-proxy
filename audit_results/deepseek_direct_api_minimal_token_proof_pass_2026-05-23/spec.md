# Spec: DeepSeek Direct API Minimal Token Proof Pass

## Objective

Prove that the sandbox-scoped DeepSeek direct route is configured correctly,
has a present credential, passes the canonical route-level smoke check, and
stays aligned with web readonly truth without leaking secrets or overstating
runtime readiness.

## In Scope

- sandbox-scoped `external-models` route truth for `wbp-deepseek-v3`
- credential presence/status truth through owner surfaces
- canonical `external-models check --route wbp-deepseek-v3 --json`
- route validate diagnosis for `model_not_available`
- one minimal direct provider probe to disambiguate alias limitation
- web `api-connections-readonly` truth alignment after check and validate
- redaction audit and independent audit

## Out of Scope

- runtime/proxy proof rerun
- menu wiring
- isolated Codex app launch
- generic provider redesign
- browser secret intake
- non-DeepSeek routes

## Constraints

- canon order starts with `CANON.md`, then `MASTER_PLAN.md`
- command packets are primary truth, not UI color alone
- no raw secrets in artifacts
- no current Codex mutation
- minimal token burn only

## Assumptions

- `FULL_SYSTEM_RUNTIME_AND_PROXY_PROOF_PASS` already closed successfully
- the live web server is operating on a launch-copy sandbox with its own
  `WBP_EXTERNAL_MODELS_DIR`
- `routes validate` is diagnostic support, not success proof

## Acceptance Criteria

- [x] sandbox route truth is captured
- [x] sandbox credential truth is captured
- [x] canonical route smoke check passes
- [x] one minimal direct provider probe confirms upstream path
- [x] validate failure is classified honestly as alias limitation, not route break
- [x] web readonly truth stays aligned with command-packet truth
- [x] no secret leak appears in artifacts

## Verification

- tests:
  - targeted external-models and web readonly tests
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- manual:
  - inspect baseline/proof/metrics/redaction packet chain
- live evidence:
  - `external-models check --route wbp-deepseek-v3 --json`
  - `external-models routes validate --route wbp-deepseek-v3 --json`
  - one direct provider probe with max tokens 8

## Open Questions

- whether the web summary should count a validate-failed route as attention in a
  later contour; not a blocker for this contour because validation is already
  surfaced as red and no false-green validation claim remains
