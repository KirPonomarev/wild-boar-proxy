<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: WEB_SAFE_ACCOUNT_CONNECT_DRY_RUN_PASS Reentry Reconciliation

## Objective

Determine whether slot 3 from `MASTER_PLAN.md` is already materially satisfied
by the current preview-only onboarding lane, or whether the repo still contains
an actual behavior gap in the dry-run account-connect flow.

## In Scope

- Reconcile slot 3 intent against current code, tests, and old closeouts.
- Verify that `onboard_account_dry_run` remains preview-only and machine-backed.
- Verify that browser-supplied auth/token fields remain rejected.
- Classify slot 3 as satisfied, closure-pass-needed, or repo-gap-present.

## Out of Scope

- Live onboarding behavior.
- Slot 4 reopening unless slot 3 proof directly contradicts it.
- Provider/API route work.
- General UI redesign or workflow cleanup beyond slot 3.

## Constraints

- Follow canon order from `AGENTS.md`.
- Keep the contour scoped to slot 3 only.
- Treat old closeout prose as non-authoritative without packet, test, and git
  support.
- Use only targeted tests unless a real gap is proven.

## Assumptions

- `MASTER_PLAN_FAST_PATH_COMPLETION_RECONCILIATION` is already closed.
- Current branch still contains implementation commit
  `77046277c001c464624c246d77ba1e6351993766`.
- The preview-only lane still exists in both server and UI code.

## Acceptance Criteria

- [ ] Slot 3 is classified as satisfied / closure-pass / real gap.
- [ ] Preview-only semantics remain machine-backed.
- [ ] Forbidden browser auth/token fields remain blocked.
- [ ] Slot 3 closure truth is reconciled against current branch/origin truth.

## Verification

- tests:
  - targeted dry-run live-server test
  - targeted dry-run UI preview-only test
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- manual:
  - inspect current slot-3 closeout drift against current pushed branch
- live evidence:
  - none required beyond the already-admitted targeted test evidence

## Open Questions

- Whether slots 4-6 should later be normalized one-by-one or under a broader
  closure-only contour after slot 3 is reconciled.
