# Spec: WEB_SAFE_COMMANDS_EXPANSION_PASS_REENTRY_RECONCILIATION

## Objective

Reconcile `MASTER_PLAN.md` slot 5 against current HEAD and close it canonically
if the safe web command surface is already materially satisfied on the pushed
branch.

## In Scope

- Current-HEAD audit of readonly runtime/accounts truth surfaces
- Current-HEAD audit of machine block-reason surfaces
- Current-HEAD audit of diagnostics export support-artifact surface
- Current-HEAD audit of bounded isolated-copy launch/dispatch surface
- Explicit canon-safe defer of `open profile folder`
- Targeted tests
- Packet capture
- Browser smoke
- Independent audit
- Closeout normalization

## Out of Scope

- New runtime mutation classes
- New account or API onboarding flows
- New desktop/native opener surface
- Design polish
- Desktop/package contours
- Rotation/load proof

## Constraints

- `WBP` remains the control layer.
- JSON packets remain the primary truth.
- Browser forbidden fields remain blocked.
- `open profile folder` may stay deferred if only desktop/native or human-open
  paths are canon-safe.
- Success cannot rely on historical closeouts alone.

## Assumptions

- Historical slot-5 closeouts from `2026-05-22` are positive evidence but not a
  canonical current-HEAD closure because git fields were stale.
- Current HEAD `c230c099` is the branch truth to reconcile.

## Acceptance Criteria

- [x] Current HEAD still exposes readonly runtime truth and accounts truth.
- [x] Machine-readable block reasons remain available through metadata/result
      surfaces.
- [x] Diagnostics export remains support-artifact-only and redacted.
- [x] Bounded isolated-copy launch/dispatch remains server-owned and does not
      touch current Codex.
- [x] `open profile folder` remains explicitly deferred for canon safety.
- [x] No repo-owned implementation gap is required to close slot 5 honestly.
- [x] A new canonical reconciliation closeout is added and pushed.

## Verification

- tests:
  - targeted live-server tests for readonly APIs, metadata, diagnostics export,
    bounded client dispatch, and bounded app-copy helper execution
  - targeted UI tests for diagnostics/support-artifact rendering and bounded
    client-launch surface
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- manual:
  - local readonly/full proof servers on `127.0.0.1:8795` and `127.0.0.1:8794`
  - packet capture for readonly/runtime/accounts, diagnostics export, bounded
    dispatch, and app-copy launch
- live evidence:
  - headless local Chrome smoke for diagnostics and client-launch surfaces

## Open Questions

- Slot 6 closeout normalization remains next after slot 5 reconciliation.
