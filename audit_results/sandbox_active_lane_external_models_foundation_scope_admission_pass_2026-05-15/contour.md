# SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_FOUNDATION_SCOPE_ADMISSION_PASS

## Goal

Determine the narrowest canon-admissible external-models foundation mutation contour after auth import cleared the primary 401 but revealed an owner-level unknown-provider blocker.

## Blocker Basis

- post-import `healthcheck --json` cleared `HTTP 401`
- post-import `healthcheck --json` remained blocked on `HTTP 502 unknown provider for model claude-sonnet-4-6-thinking`
- `external-models status --json` reports `profile_ready=false`, `routes_count=0`, `local_auth.token_present=false`
- `external-models models --json` reports `count=0` from `local_routes_registry`
- `external-models routes list --json` reports `count=0`

## Command-Surface Findings

- primary mutation surface now available: `external-models routes add --json --file|--stdin`
- provider/profile is not a standalone mutation lane; provider/base_url/upstream_model live inside the route payload
- `external-models profile codex-desktop --json --route <route_id>` is read-only
- local token creation exists only through `external-models start --json` and widens into secret-bearing writes

## Result

- final verdict: `GO_TO_EXACT_NEXT_REPAIR_CONTOUR`
- selected next contour: `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_ADD_REPAIR_PASS`
