# SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_FOUNDATION_SCOPE_ADMISSION_PASS Independent Audit

## External Inspector

- agent: `McClintock`
- mode: read-only
- accepted factual findings:
  - actual mutation surfaces are `external-models routes add|update|enable|disable|remove`, `external-models start|stop`, `external-models routes validate`, `external-models check`, and `external-models evidence capture`
  - `external-models profile codex-desktop --json --route <route_id>` is read-only and not a mutation surface
  - route registry mutation, provider evidence mutation, and local-token lifecycle mutation are separate rollback domains
  - browser/UI route-builder admission remains deferred, but that is a UI boundary, not a negation of CLI owner mutation surfaces

## My Audit of the Agent

- did the agent overclaim? no
- did the agent collapse UI admission and CLI runtime ownership? no; it explicitly kept them separate
- where I extended the audit:
  - I selected the exact next contour from the current machine-carried packets
  - I tied the next contour to the narrowest write surface: `routes.json`
  - I excluded token-first and combined contours because current packets do not require secret-bearing widening

## Independent Findings

1. `external-models routes add --json --file|--stdin` is the first exact mutation surface that can change the empty `local_routes_registry` basis behind `models_count=0` and `routes_count=0`.
2. A standalone provider/profile contour is not admissible because provider/base URL/upstream model live inside the route payload and `profile codex-desktop` is read-only.
3. A local-token-first contour is not admissible as primary because token creation exists only as a side effect of `external-models start --json` and does not populate the empty route registry.
4. A combined route+token contour would widen rollback from `routes.json` into `state.json` and `secrets.env` without current necessity.
5. Browser/UI route-builder admission remains deferred, but that does not block a runtime repair contour using the canonical CLI owner surface.

## Audit Verdict

- verdict: `AGENT_REPORT_ACCEPTED_WITH_SCOPE_BOUNDARY_CLARIFICATION`
- agreed next contour: `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_ADD_REPAIR_PASS`
