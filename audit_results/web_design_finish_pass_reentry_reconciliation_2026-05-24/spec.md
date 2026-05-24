# Spec: WEB_DESIGN_FINISH_PASS_REENTRY_RECONCILIATION

## Objective

Reconcile `MASTER_PLAN.md` slot 6 against current HEAD and close it canonically
if the design-finish surface is already materially satisfied on the pushed
branch.

## In Scope

- Current-HEAD verification of the design gate evidence
- Current-HEAD verification of navigation coherence
- Current-HEAD verification of truthful button states
- Current-HEAD verification of empty/error/deferred states
- Current-HEAD verification of compact action/log presentation
- Current-HEAD browser proof on previously claimed slot-6 screens
- Targeted UI/server tests that support the design-layer claim
- Independent audit
- Closeout normalization

## Out of Scope

- New HTML/CSS/JS changes unless a real repo-owned drift is proven
- Runtime repair
- New command surfaces
- Account/API flow changes
- Desktop/package work
- Opportunistic visual polish

## Constraints

- `WBP` remains a control-layer UI consumer of existing packets.
- Historical slot-6 artifacts are evidence, not authority.
- Current HEAD plus fresh verification is the closure authority.
- If fresh verification contradicts slot 6, the contour stops and re-scopes
  instead of silently repairing UI.

## Assumptions

- `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY` must remain evidenced on
  current branch.
- Slot 6 can close through reconciliation if no repo-owned drift is found.

## Acceptance Criteria

- [x] Design gate remains evidenced on current branch.
- [x] Current HEAD still shows coherent navigation on slot-6 screens.
- [x] Button states remain truthful and non-fake.
- [x] Empty/error/deferred states remain explicit and bounded.
- [x] Compact action/log presentation remains present on claimed screens.
- [x] No repo-owned UI drift requiring implementation is found.
- [x] A new canonical reconciliation closeout is added and pushed.

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - bundled Python `-m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- build:
  - `git diff --check`
- manual:
  - local design proof server at `127.0.0.1:8796`
- live evidence:
  - current-HEAD browser smoke on Quick Start, Accounts, API Connections,
    Diagnostics, and Settings / Client

## Open Questions

- Slot 7 closeout normalization remains next after slot 6 reconciliation.
