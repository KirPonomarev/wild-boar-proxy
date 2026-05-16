# SELECTOR_REFRESH_OWNER_PATH_PASS

## Goal

Refresh `selected_backend_snapshot` through the canonical `sync --json` owner
path after runtime truth had been re-earned, then verify whether selector
participation evidence becomes fresh without reopening the runtime lane.

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
- no exact auth-source admission
- no runtime reproof by inertia inside this contour
- `sync --json` is the only selector-refresh owner path
- if runtime-green preconditions regress before refresh completion:
  `STOP_AND_DIAGNOSE`
