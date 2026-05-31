# Spec: WEB_API_PROVIDER_OWNER_CONTINUATION_PASS

## Objective

Determine whether a new provider-specific owner continuation contour is still
needed after the already closed owner credential admission, owner setup
handoff, provider credential bridge, and route create/adopt contours.

## In Scope

- Re-entry baseline over the current provider continuation UX.
- Confirm whether missing credential -> owner handoff -> retry -> connected
  flow is already materially present.
- Re-run a focused gate on the continuation lane.
- Produce a closure package if the contour is unnecessary because repo truth is
  already sufficient.

## Out of Scope

- New provider auth/session framework.
- Browser secret/token/api_key input.
- Web-owned callback listener.
- Generic route builder.
- Provider dashboard automation.
- Unrelated product or runtime changes.

## Constraints

- Canon order: `CANON.md`, `MASTER_PLAN.md`, `RUNTIME_CONTRACT.md`,
  `STATE_SCHEMA.md`, `COMMAND_API.md`, `DELIVERY_RULES.md`, `README.md`.
- Browser must not accept `api_key`, `secret`, `token`, `auth`, `path`, or
  provider override inputs.
- Green requires packet truth plus readonly refresh truth.
- If current repo truth is already sufficient, do not widen scope into a new
  implementation contour.

## Assumptions

- The current provider lane is the OpenRouter owner-env bridge already closed in
  prior contours.
- Existing browser evidence from 2026-05-22 remains valid unless current tests
  contradict it.

## Acceptance Criteria

- [x] Current repo truth is classified honestly as sufficient or insufficient.
- [x] Focused continuation-lane tests pass on current HEAD.
- [x] No repo-owned UX gap requiring a new implementation contour is found.
- [x] Fresh closure artifacts are produced under the current contour name.

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - focused unittest gate for provider missing/retry/connected continuation
- build:
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- manual:
  - inspect current live server / UI continuation lane
- live evidence:
  - reuse existing browser summaries and packets from
    `audit_results/api_provider_owner_setup_handoff_pass_2026-05-22/`
    and `audit_results/web_api_provider_credential_bridge_pass_2026-05-22/`

## Open Questions

- If a future provider requires a real owner login/session bridge instead of
  dashboard/env handoff, that should be a separate provider-specific contour.
