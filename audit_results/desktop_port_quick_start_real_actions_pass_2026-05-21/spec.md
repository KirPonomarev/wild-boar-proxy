# Spec: DESKTOP_PORT_QUICK_START_REAL_ACTIONS_PASS

## Objective

Attempt the desktop parity port only if the repository already contains a real
executable desktop shell/bridge path that can run the proven Quick Start flow
against the same admitted sandbox truth surfaces as web.

## In Scope

- verify whether a real desktop executable path exists
- verify whether desktop can reuse the proven account/API/check-all/ledger
  packet and refresh surfaces
- preserve blocker evidence if the path is missing or preview-only

## Out of Scope

- inventing a new desktop shell
- desktop-native secret/path/auth input
- redesign or desktop polish
- lifecycle expansion
- execution-core changes

## Constraints

- canon order from `AGENTS.md` must hold
- `DESKTOP_PORT_QUICK_START_REAL_ACTIONS_PASS` may close only on a real
  executable desktop path
- preview-only, support-only, or owner-gated future placeholders do not satisfy
  desktop parity
- no broadening beyond proven web semantics

## Assumptions

- the proven web continuity flow remains the only admitted semantic baseline
- a missing desktop bridge is a contour blocker, not a partial success

## Acceptance Criteria

- [ ] a real executable desktop shell/bridge path exists
- [ ] desktop can run the same Quick Start account/API/check-all/ledger flow
- [ ] desktop uses the same packet + refresh truth model as web
- [ ] desktop does not widen admitted actions or input surfaces
- [ ] desktop contour can proceed without inventing a new subsystem

## Verification

- tests:
  - evidence scan over desktop-related docs, UI copy, live server, and prior
    closeouts
- build:
  - `git diff --check`
- manual:
  - confirm the repository exposes a real executable desktop path rather than a
    preview/support surface
- live evidence:
  - stop immediately if the only desktop evidence is preview-only or
    support-only

## Open Questions

- should the blocker-resolving follow-up contour align to the older
  `DESKTOP_RENDERER_ADMISSION` language or a new, narrower
  `DESKTOP_EXECUTABLE_BRIDGE_ADMISSION_PASS` name?
