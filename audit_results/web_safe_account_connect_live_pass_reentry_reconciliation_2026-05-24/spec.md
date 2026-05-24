# Spec: WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS_REENTRY_RECONCILIATION

## Objective

Reconcile `MASTER_PLAN.md` slot 4 against current HEAD and close it honestly if
the live account-connect lane is already materially satisfied on the pushed
branch.

## In Scope

- Current-HEAD audit of `onboard_account`
- Current-HEAD audit of `account_login_status`
- Current-HEAD audit of `account_login_complete`
- Current-HEAD audit of `account_login_cancel`
- Reserve-first outcome proof
- Browser forbidden-field rejection proof
- Refreshed accounts truth linkage proof
- Browser smoke over Quick Start confirmation surface
- Independent audit
- Closeout normalization

## Out of Scope

- New live onboarding implementation
- Rotation/load proof
- Account lifecycle expansion beyond reserve-first connect
- Desktop/package contours
- Design polish

## Constraints

- `WBP` remains the control layer.
- Auth/login internals remain in the owner/engine lane.
- Browser cannot supply auth/token/path/backend fields.
- JSON packets remain the primary truth.
- No false-green from packet-only success without refresh linkage.

## Assumptions

- Existing closeouts from 2026-05-21 are historical evidence, not sufficient
  current-HEAD closure by themselves.
- Current HEAD `3a5617fe` is the branch truth to reconcile.

## Acceptance Criteria

- [x] Current HEAD still exposes the four live account-connect actions.
- [x] Start/status/complete/cancel lane remains machine-backed.
- [x] Completion still proves reserve-first semantics.
- [x] Browser-forbidden-field rejection still holds.
- [x] Refreshed accounts truth linkage is still present.
- [x] No repo-owned implementation gap is found.
- [x] A new canonical reconciliation closeout is added and pushed.

## Verification

- tests:
  - targeted live-server tests for start/status/complete/cancel, rejection, and real JSON runner proof
  - targeted UI tests for handoff and reserve-first rendering
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- manual:
  - local sandbox-phase handler packets for start/status/complete/rejection
- live evidence:
  - browser smoke on Quick Start live-connect confirmation surface

## Open Questions

- Slot 5 closeout normalization remains next after slot 4 reconciliation.
