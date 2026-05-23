<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: MASTER_PLAN Fast Path Completion Reconciliation

## Objective

Determine whether the original fast-path contours 1-8 in `MASTER_PLAN.md` are
already materially satisfied by current repo truth, or whether the chain still
contains unresolved closure drift or a real repo-owned behavior gap.

## In Scope

- Reconcile master-plan slots 1-8 against current canonical repo evidence.
- Reuse the slot-7 and slot-8 reconciliation closeouts as current desktop truth.
- Classify the chain as `fast_path_complete`,
  `fast_path_closure_pass_needed`, or `fast_path_repo_gap_present`.
- Name the next narrow contour only if the chain is not yet canonically closed.

## Out of Scope

- Re-proving all eight slots from scratch.
- Opening a new product lane by default.
- Broad repo audit beyond the fast-path chain.
- Rewriting roadmap intent or product canon.

## Constraints

- Follow canon order from `AGENTS.md`.
- Treat closeout prose as insufficient by itself without packet, test, and git
  support.
- Do not reopen reconciled slots without a concrete contradictory fact.
- Keep this contour factual and read-heavy unless a concrete repo-owned gap is
  proven.

## Assumptions

- Slot 7 is canonically reconciled by
  `desktop_app_port_pass_reentry_reconciliation_2026-05-23`.
- Slot 8 is canonically reconciled by
  `desktop_app_package_pass_reentry_reconciliation_2026-05-23`.
- Current branch and origin are aligned at contour start.
- The dry-run account-connect lane is still present in current code and tests.

## Acceptance Criteria

- [ ] Slots 1-8 are classified using current canonical evidence.
- [ ] No slot is reopened without a concrete contradictory fact.
- [ ] Remaining drift is named precisely as closure-only or behaviorally real.
- [ ] The next-track decision is gated rather than improvised.

## Verification

- tests:
  - targeted dry-run live-server test
  - targeted dry-run UI test
  - focused desktop shell suite
  - focused packaged continuity CLI test
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- manual:
  - inspect master-plan slot wording against current closeouts, commits, and
    branch/origin ancestry
- live evidence:
  - reuse existing browser/live packets only where already canonically recorded

## Open Questions

- Whether slot 3 should be repaired by a dedicated dry-run reconciliation
  contour or by a wider closure-normalization pass for slots 3-6.
