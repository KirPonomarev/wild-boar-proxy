# Spec: EXECUTION_CORE_ACCOUNT_RANKING_AND_API_PULL_PASS

## Objective

Harden execution-core account ranking and API provider pull semantics before returning to UI/design work.

## In Scope

- Make live-capable account ordering deterministic and explicit.
- Preserve lifecycle gates: ranking must not bypass active/reserve/hold/retired policy.
- Make API route `check` and `routes validate` refuse disabled routes before provider network calls.
- Keep external-models route verification route-local and non-runtime-readiness-claiming.
- Add targeted tests and command-contract documentation.

## Out of Scope

- Visual design polish.
- New account login/admission surfaces.
- API credential intake redesign.
- Promotion policy changes.
- Real provider OAuth.
- Untracked artifact cleanup.

## Canonical Decisions

- `CLIProxyAPI` remains the engine.
- Wild Boar Proxy remains the control layer.
- Ranking is candidate selection input only.
- API pull/check truth remains route-local and must not claim listener/runtime readiness.

## Acceptance Criteria

- [x] Live-capable selected backend ordering uses explicit ranking policy.
- [x] Ranking policy is surfaced in `auth_pool_hygiene`.
- [x] Disabled API routes block `external-models check` before network calls.
- [x] Disabled API routes block `external-models routes validate` before network calls.
- [x] Non-green disabled-route packet includes `machine_error_code=route_disabled`.
- [x] Existing provider check and validate flows remain green.
