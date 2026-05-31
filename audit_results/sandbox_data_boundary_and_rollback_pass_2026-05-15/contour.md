# SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_PASS

## Goal

Define a safe sandbox boundary for the next sandbox wave without performing any
mutation work. This contour separates observed path truth from declared policy
surfaces, classifies the old sandbox root, and prepares rollback and teardown
rules for the next contour.

## Scope

- observed path inventory
- declared writable and forbidden surfaces
- sandbox-root admissibility decision
- rollback and teardown planning
- separation proof for the next binding contour

## Non-Goals

- onboarding
- import
- config writes
- sandbox binding proof
- runtime mutation

## Result

- working/live roots and sandbox candidate roots were mapped
- the prior sandbox candidate root `.codex-custom-test` was found path-isolated
  but contaminated by prior mutable state and stale experiment configuration
- a fresh dedicated sandbox root was selected for the active sandbox wave
- rollback and teardown can be expressed cleanly because the selected root does
  not yet exist
- next contour earned: `GO_TO_SANDBOX_LIVE_SERVER_BINDING_PASS`
