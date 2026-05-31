# WEB_LIVE_READONLY_ACTION_PARKING_REPAIR_PASS

## Goal

Align the current live-readonly phase with the corrected master plan by
parking mutation and support-artifact actions in server metadata and HTTP POST
dispatch, while keeping only readonly support actions available.

## Scope

- `wild_boar_proxy/web_design_live_server.py`
- `wild_boar_proxy/web_design_ui/README.md`
- `tests/test_web_design_live_server.py`
- audit artifact generation

Out of scope:

- runtime mutation execution
- sandbox work
- UI redesign
- action-system redesign
- account, route, or launch execution

## Findings

- default live-readonly action phase is now explicit
- default `/api/actions` metadata now reports:
  - available: `refresh_health_detail`, `stable_repair_plan`
  - parked: `20` actions
- default `POST /api/action` now blocks parked actions in the live-readonly phase
- full-capability action behavior remains available for explicit non-readonly test
  surfaces via `action_phase=FULL_ACTION_PHASE`
- README now matches repaired behavior

## Decision

- status: `GO_TO_WEB_LIVE_SERVER_READONLY_ADMISSION_PASS`
- reason:
  - plan, server metadata, client metadata consumption, and README now agree on
    the current live-readonly phase
  - parked actions are no longer truthfully available by default
  - readonly support actions remain available without widening scope

## Next Guardrails

- keep the next contour GET-first and readonly
- do not treat `/api/actions` metadata as runtime proof
- do not reopen parked actions before sandbox admission evidence
