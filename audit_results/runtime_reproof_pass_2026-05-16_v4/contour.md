# RUNTIME_REPROOF_PASS

## Goal

Reprove live runtime consumer truth after the runtime-primary prereq regression
and determine whether the approved repair target becomes the effective stable
runtime consumer source again before any selector or auth-adjacent follow-up.

## Canon

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`

## Guardrails

- no `sandbox auth.json` materialization
- no onboarding rerun
- no exact-source narrowing
- no selector refresh by inertia
- prefer `healthcheck --json` first
- widen to `launch smoke --json` only if `healthcheck --json` leaves the runtime
  consumer gap unresolved

## Expected Decision Boundary

- if runtime truth recovers and selector evidence remains stale:
  `GO_TO_SELECTOR_REFRESH_OWNER_PATH_PASS`
- if runtime truth stays on `observed_source_active`:
  `GO_TO_OBSERVED_SOURCE_FALLBACK_DIAGNOSE_PASS`
- if packets contradict each other:
  `STOP_AND_DIAGNOSE`
