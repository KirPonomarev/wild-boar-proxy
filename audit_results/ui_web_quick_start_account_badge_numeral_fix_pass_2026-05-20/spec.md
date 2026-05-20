<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: UI Web Quick Start Account Badge Numeral Fix

## Objective

Repair the Quick Start account index badges so the `01`, `02`, `03`, and `04`
numerals sit as centered row indexes instead of drifting toward the top-left of
the badge.

## In Scope

- Quick Start account badge typography and centering CSS.
- Static UI tests for the badge CSS guard.
- Browser evidence for the populated Quick Start fixture screen.

## Out of Scope

- Runtime logic.
- Command adapter behavior.
- Live server contracts.
- Account data mapping.
- Quick Start row height or row grid changes.
- Status/action chip changes.
- Sidebar, API card, KPI, or onboarding modal work.

## Constraints

- Do not edit `overview.js`.
- Do not change account row height or grid columns.
- Do not resize the badge unless centering cannot be fixed by CSS layout.
- Do not use top/left nudges, transforms, negative margins, or font-specific
  padding hacks.
- Center through CSS layout and numeric typography.

## Assumptions

- Badge content is already correct as two-digit text; the defect is caused by
  the row-level `span` rule overriding badge display/typography.
- Browser-computed `display:flex` is acceptable evidence for a declared
  `inline-flex` element.
- Browser-computed `line-height:12px` is expected from declared `line-height:1`
  with `font-size:12px`.

## Acceptance Criteria

- [x] Four fixture account badges render.
- [x] Badge size remains `34px` by `34px`.
- [x] Badge text is centered via flex alignment.
- [x] Badge numerals use tabular numeric rendering.
- [x] Badge line-height is normalized to `1`.
- [x] Badge text is not clipped.
- [x] Account row height remains unchanged.
- [x] Account row grid remains unchanged.
- [x] Quick Start grid remains unchanged.
- [x] No runtime, adapter, live-server, contract, or JS render path is touched.

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- tests: `/usr/bin/python3 -B -m unittest tests.test_web_design_ui -q`
- tests: `git diff --check`
- browser evidence: `audit_results/ui_web_quick_start_account_badge_numeral_fix_pass_2026-05-20/metrics.json`
- screenshot: `audit_results/ui_web_quick_start_account_badge_numeral_fix_pass_2026-05-20/screenshots/quick-start-account-badges.png`

## Open Questions

- Cross-browser optical centering can be revisited only if a later Safari/Chrome
  operator screenshot shows a font-stack-specific shift.
