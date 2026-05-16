# WEB_SAFE_COMMANDS_EXPANSION_PASS

## Goal

Expose only the already-admitted safe command surfaces that were still locally
hidden or over-deferred in the web UI, without adding new command engines,
browser secrets, or new proof pipelines.

## Scope

- Expand API route action menu to surface existing admitted actions:
  - `api_route_check`
  - `api_route_allow`
  - `api_route_disable`
  - `api_route_profile`
  - `api_route_evidence_capture`
- Remove the extra client-side readonly-registry deferral for those actions and
  rely on:
  - existing action metadata
  - route-state requirement checks
  - existing readonly refresh surfaces
- Keep account actions, diagnostics export, and runtime actions unchanged.

## Out of Scope

- No onboarding changes
- No auth input
- No runtime/server architecture change
- No design polish
- No new proof pipeline

## Acceptance

- Route menu shows admitted safe actions.
- Live source plus metadata governs availability; fixture source still blocks.
- No false-green or hidden browser payload expansion.
- Existing tests and browser checks pass.
