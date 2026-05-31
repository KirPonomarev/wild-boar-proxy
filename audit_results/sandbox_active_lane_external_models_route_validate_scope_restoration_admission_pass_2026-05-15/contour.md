# SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_VALIDATE_SCOPE_RESTORATION_ADMISSION_PASS

## Goal

Determine the next executable contour after provider-evidence admission selected `routes validate`, but the prior route-add contour rolled the route back and left the current sandbox registry empty.

## Baseline Truth

- route-add contour proved the candidate route shape and then rolled it back
- current sandbox truth after rollback is `routes_count = 0`, `models_count = 0`
- `external-models routes validate --json --route ...` resolves the route from current `routes.json`
- validate cannot run honestly unless the route is re-materialized first

## Scope Split

- route re-add / restoration is a registry mutation over `routes.json`
- route validate is provider-evidence execution over `state.json` and `evidence/*`
- those are separate write and rollback domains
- canon prefers the narrower split unless there is a strong reason to fuse them

## Result Shape

- contour outcome: `GO_TO_EXACT_NEXT_REPAIR_CONTOUR`
- selected next contour: `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_RESTORE_REPAIR_PASS`
- validate is deferred until the route is honestly present again in current sandbox truth
