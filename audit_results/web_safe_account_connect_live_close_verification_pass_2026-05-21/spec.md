<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: WEB_SAFE_ACCOUNT_CONNECT_LIVE_CLOSE_VERIFICATION_PASS

## Objective

Close the already-implemented live Quick Start onboarding lane with one real
sandbox execution, owner packet evidence, canonical refresh proof, and
independent audit.

## In Scope

- owner-authorization gate check
- sandbox target proof capture
- one real Quick Start dry-run preview followed by live sandbox onboarding
- owner packet capture from the live `onboard_account` lane
- canonical refresh capture from sandbox `accounts list --json`
- narrow repair of the factual blocker where sandbox actions refreshed through
  global readonly endpoints
- independent factual audit of diff and evidence

## Out of Scope

- new feature work beyond the narrow refresh-path repair
- API route work
- lifecycle actions
- desktop port
- redesign
- synthetic rollback UI claims

## Constraints

- live mutation is allowed only because the exact owner phrase required by
  `CANON.md` is present in the active thread
- browser surfaces remain forbidden from token/auth/path/backend payloads
- success cannot be inferred without `accounts onboard --json` plus
  `accounts list --json`
- rollback truth is not invented when the packet does not expose it

## Assumptions

- `WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS` code was already merged locally before
  this close contour
- sandbox action phase and Quick Start two-step modal flow were already working
- a narrow blocker discovered during close verification may be repaired inside
  this contour when it is localized, evidenced, and re-verified

## Acceptance Criteria

- [x] exact canonical owner authorization present in the active thread
- [x] sandbox target proof captured machine-readably
- [x] one real sandbox Quick Start dry-run preview executed
- [x] one real sandbox Quick Start live onboarding executed
- [x] owner packet captured with `reserve_only_success`, `selected_backend_id`,
      `reserve_first_proven`, `validate_outcome`, and `sync_outcome`
- [x] canonical refresh captured from sandbox truth
- [x] narrow refresh-mismatch blocker localized and repaired
- [x] Quick Start UI and action panel show `canonical refresh complete`
- [x] sandbox `accounts-readonly` refresh shows backend `auth` in `reserve`
- [x] independent audit found no medium-or-higher defects in the repaired lane

## Verification

- tests:
  - targeted real sandbox HTTP tests added and passed
  - existing live server/UI/adapter suites re-run
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- browser:
  - fresh sandbox Quick Start run with screenshots and persisted network trace
- live evidence:
  - `ui-run-network.json`
  - `ui-run-summary.json`
  - `accounts-list-canonical-after.json`
  - `accounts-readonly-after.json`
  - `status-canonical-after.json`

## Open Questions

- none for this contour; the remaining open product work moves to the next
  contour chosen from the master plan
