# Execution Wave 1

## Position

Execution Wave 1 starts with a documentation and contract-freeze contour.

Execution Wave 1A is `Execution Core Spec Freeze`.

Execution Wave 1B is the later runtime-hardening implementation contour.

## Wave 1A scope

- freeze runtime truth rules in the existing runtime contract
- freeze state schema and mutation rules
- freeze explicit lifecycle transitions
- freeze strict JSON command integration expectations
- define the gates that implementation contours must satisfy

Wave 1A is spec work only.
It does not claim runtime implementation is complete.

## Explicitly out of scope

- UI implementation
- installer, reset, uninstall, packaging, codesign, or notarization work
- public release polish
- staged pool expansion beyond the current stable pool
- generic `CLIProxyAPI` manager features
- engine-layer duplication
- onboarding implementation beyond contract-level consequences

## Critical user path gate

The following path must be preserved as the controlling gate for Wave 1 work:

1. cold start
2. managed preflight
3. one-click onboarding to reserve
4. validate
5. single-account promotion
6. managed sync
7. launch client
8. forced managed failure
9. stable fallback

Without this path, neither pilot-readiness nor stable-pool claims are valid.

## Minimum blocking gates

- `RUNTIME_ATTESTATION_GATE`
- `STRICT_JSON_COMMAND_API_GATE`
- `STATE_SERIALIZATION_GATE`
- `FALLBACK_DRILL_GATE`

## Wave 1A closeout conditions

- no unresolved contradiction with `CANON.md`
- state mutation ownership is explicit
- lifecycle transitions are explicit
- invalid JSON is a hard integration failure
- no out-of-scope work has been mixed into the contour
- the contour branch is pushed to GitHub before the next contour begins

## Handoff rule

Wave 1A closes only when implementation can begin without inventing new truth
surfaces or re-deciding state semantics.

GitHub synchronization is part of contour closeout, not an optional later task.
