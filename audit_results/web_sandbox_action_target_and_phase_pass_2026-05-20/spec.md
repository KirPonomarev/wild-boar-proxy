<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: WEB_SANDBOX_ACTION_TARGET_AND_PHASE_PASS

## Objective

Open a separate `sandbox_actions` phase for the web Quick Start so real actions
stop being hard-parked behind `live_readonly`, while keeping the current working
Codex untouched and preserving canonical browser safety boundaries.

## In Scope

- add a dedicated `sandbox_actions` phase in `web_design_live_server.py`
- gate parked actions by phase policy instead of widening `live_readonly`
- add sandbox target preflight for separate profile/data directories and port
- wire sandbox action metadata through `/api/actions`
- switch live source pill/footer truth to `Sandbox` only when sandbox phase is
  admitted
- add tests for phase gating, sandbox preflight, and UI source labeling

## Out of Scope

- real account onboarding execution flow
- real API route adopt/check workflow
- aggregate `Проверить всё` orchestration
- desktop port
- lifecycle actions
- runtime-core refactors outside minimal web gating

## Constraints

- keep `LIVE_READONLY_ACTION_PHASE` behavior unchanged
- do not accept browser `token`, `secret`, `path`, `auth`, or `backend_id`
- do not infer runtime truth from action metadata alone
- do not broaden sandbox phase beyond reserve-first onboarding and bounded API
  route actions

## Assumptions

- sandbox target isolation is sufficiently proven for this contour by separate
  absolute profile/data roots and a separate port
- actual sandbox runtime data seeding is deferred to the next contour
- existing allowlisted commands remain the sole action execution surface

## Acceptance Criteria

- [x] parked actions stay disabled in `live_readonly`
- [x] `sandbox_actions` opens only the admitted subset when sandbox preflight is
  admitted
- [x] invalid or missing sandbox target keeps admitted actions disabled with a
  preflight reason
- [x] `/api/actions` reports `action_phase` and sandbox preflight truth
- [x] live UI source pill shows `Sandbox` only when sandbox phase is admitted
- [x] no browser secret/path/token input surface was added

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - repo runtime Python unittest for `tests.test_web_design_live_server`
  - repo runtime Python unittest for `tests.test_web_design_ui`
  - repo runtime Python unittest for `tests.test_web_design_command_adapter`
- build:
  - `git diff --check`
- manual:
  - local `curl /api/actions` against a sandbox-phase server returns
    `action_phase=sandbox_actions`, `sandbox_preflight.status=admitted`,
    `onboard_account.available=true`, `validate_account.available=false`
- live evidence:
  - local sandbox-phase server keeps readonly snapshots on sandbox runner; with
    empty sandbox dirs the snapshot returns `integration_failure`, which is
    truthful and deferred to the next contour

## Open Questions

- seed a concrete sandbox profile/data layout before `WEB_QUICK_START_ONBOARD_ACCOUNT_SANDBOX_PASS`
- decide whether future sandbox contours need an explicit route-adoption subset
  narrower than the current API route action allowance
