# Spec: UI Accounts Gate Check And Read Admission

## Objective

Determine whether the active canon truthfully permits the next narrow contour
`UI_DESKTOP_HTML_ACCOUNTS_SCREEN_READONLY`.

This contour is a gate/spec/go-no-go contour only. It does not implement the
Accounts screen. It does not admit any mutation layer. It does not widen the UI
authority beyond existing strict JSON command surfaces.

## In Scope

- review `AGENTS.md`, `CANON.md`, `MASTER_PLAN.md`, and `UI_READINESS_SPEC.md`
- classify gate status as `GREEN` or `RED`
- record exact blockers when gate is `RED`
- define a machine-carried read-only Accounts passport
- define the only legal next contour for both `RED` and `GREEN` outcomes

## Out of Scope

- rendering `04_accounts`
- wiring any live Accounts screen
- mutating account actions
- onboarding, diagnostics, settings, or import flows
- typography or visual polish
- new command surfaces
- direct state, registry, or log truth

## Constraints

- `AGENTS.md` requires `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`
  before rich UI expansion or design polish
- `MASTER_PLAN.md` says the next primary contour is execution-core repair,
  reserve-first stage-20 re-entry, post-advance same-day validation, then
  canonical stop before basic companion UI
- `UI_READINESS_SPEC.md` is a readiness/spec boundary, not permission to outrun
  execution-core repair
- the Account Pool screen must read account state from `accounts list --json`
- any active-routing effect requires `accounts list --json` and `status --json`
  refresh

## Assumptions

- existing first-screen work on separate branches or PRs does not by itself earn
  the repo gate token
- no new canon artifact in the inspected repo truthfully claims
  `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`

## Acceptance Criteria

- [x] exact gate blockers are recorded from repo canon
- [x] read-only Accounts passport exists as a machine-carried artifact
- [x] mutation-layer remains fully deferred
- [x] legal next contour is named for both `RED` and `GREEN`
- [x] no implementation scope is smuggled into this contour

## Verification

- tests: `python3 -m json.tool` on machine-carried JSON artifacts
- build: not applicable
- manual:
  - reviewed `AGENTS.md`
  - reviewed `CANON.md`
  - reviewed `MASTER_PLAN.md`
  - reviewed `UI_READINESS_SPEC.md`
- live evidence: not applicable; this contour is repo-canon gate analysis only

## Open Questions

- none for the gate verdict itself; the controlling blocker is explicit in repo canon

## Gate Verdict

- status: `RED`
- reason:
  - `AGENTS.md` blocks rich UI expansion until
    `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY` is truthfully earned
  - `MASTER_PLAN.md` still places execution-core repair before basic companion UI
  - no inspected repo artifact truthfully earns the design gate token

## Legal Next Contours

- if gate remains `RED`:
  - execution-core repair / gate-closure contour
- if a later gate turns `GREEN`:
  - `UI_DESKTOP_HTML_ACCOUNTS_SCREEN_READONLY`
