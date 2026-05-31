# SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_PROVIDER_EVIDENCE_SCOPE_ADMISSION_PASS

## Goal

Determine the narrowest canon-admissible next provider-evidence contour after the route-add STOP, without silently widening into validate+check, secret admission, token/start, or lifecycle continuation.

## Baseline Truth

- route add materialized local registry truthfully
- owner blocker stayed unchanged on `HTTP 502 unknown provider for model claude-sonnet-4-6-thinking`
- rollback restored sandbox route registry baseline
- current route shape remained `auth.type = none`

## Scope Split

- `external-models routes validate --json --route ...` is the narrower provider-evidence surface
- `external-models check --json --route ...` is a broader smoke surface
- secret-bearing provider scope is not primary under the current route shape
- combined validate+check is wider than the evidence requires

## Result Shape

- contour outcome: `GO_TO_EXACT_NEXT_REPAIR_CONTOUR`
- selected next contour: `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_VALIDATE_EVIDENCE_PASS`
- declared next write surfaces: `state.json` and `evidence/*`
- secret-scope widening: not admitted for the next contour
