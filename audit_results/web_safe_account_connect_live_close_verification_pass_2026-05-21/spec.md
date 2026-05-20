<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: WEB_SAFE_ACCOUNT_CONNECT_LIVE_CLOSE_VERIFICATION_PASS

## Objective

Close the already-implemented live Quick Start onboarding lane with one real
sandbox execution, but only if canonical owner authorization is explicitly
present in the active thread.

## In Scope

- owner-authorization gate check
- sandbox target proof capture
- live-lane readiness proof from `/api/actions`
- dry-run preview packet capture
- blocked/live decision for execution close
- independent factual audit

## Out of Scope

- new feature work
- API route work
- lifecycle actions
- desktop port
- redesign
- synthetic rollback UI claims

## Constraints

- no live mutation without the exact owner phrase required by `CANON.md`
- browser surfaces remain forbidden from token/auth/path/backend payloads
- success cannot be inferred without `accounts onboard --json` plus
  `accounts list --json`
- if the owner gate is blocked, this contour closes only as
  `preflight_ready_but_owner_authorization_blocked`

## Assumptions

- `WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS` code is already merged locally
- sandbox action phase and Quick Start two-step modal flow are already working
- local stub verification is acceptable for technical readiness proof, but not
  for live-close proof

## Acceptance Criteria

- [x] exact canonical owner-authorization requirement localized
- [x] sandbox target proof captured machine-readably
- [x] `onboard_account` live lane shown as technically admitted in sandbox phase
- [x] dry-run preview packet captured
- [ ] one real sandbox live onboarding executed under canonical owner authorization
- [ ] owner packet + canonical refresh captured from a real run

## Verification

- tests:
  - no new code changes; rely on already green live contour tests
- build:
  - `git diff --check`
- manual:
  - local stub server packet capture for `/api/actions` and dry-run preview
- live evidence:
  - blocked until the exact owner phrase is present in the active thread

## Open Questions

- once canonical owner authorization is provided, the next exact move is a real
  sandbox Quick Start live onboarding, not another planning contour
