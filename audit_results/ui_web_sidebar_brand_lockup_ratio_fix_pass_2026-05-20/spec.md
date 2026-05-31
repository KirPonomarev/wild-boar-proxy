<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: UI Web Sidebar Brand Lockup Ratio Fix

## Objective

Make the Quick Start sidebar brand lockup match the requested ratio: remove the
visible `quick start · live readonly` caption, make `WILD BOAR PROXY` quieter by
about 20%, and make the boar mark the dominant visual sign.

## In Scope

- Quick Start-specific sidebar brand CSS.
- Quick Start brand caption assignment in the UI script.
- Static UI tests for the Quick Start brand lockup.
- Browser evidence for the live Quick Start screen at `1600x1000`.

## Out of Scope

- Runtime logic.
- Command adapter behavior.
- Live server contracts.
- Account/API behavior.
- Quick Start content grid changes.
- Desktop/native bridge.
- Canon document edits.

## Constraints

- Treat this as a repair pass, not a redesign pass.
- Do not add or change command surfaces.
- Do not change the global brand lockup for other screens unless required.
- Keep navigation visible and usable after the larger logo.
- Keep visible SVG icon count at zero.

## Assumptions

- The requested `2.5x` logo increase is measured from the previous Quick Start
  override width of `72px`, giving a target of `180px`.
- The requested 20% brand-text reduction is measured from the previous Quick
  Start override of `20px`, giving a target of `16px`.
- Removing the caption means no visible Quick Start caption; the stable Quick
  Start runtime state also clears the caption text.

## Acceptance Criteria

- [x] Quick Start caption is not visible.
- [x] Stable Quick Start caption text is empty.
- [x] Quick Start boar logo width is `180px`.
- [x] Quick Start brand text is `16px` with `20px` line height.
- [x] Sidebar navigation remains accessible.
- [x] Quick Start grid columns remain unchanged.
- [x] No horizontal overflow appears at `1600x1000`.
- [x] Runtime, adapter, live server, contracts, and canon docs are untouched.

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- tests: `/usr/bin/python3 -B -m unittest tests.test_web_design_ui -q`
- tests: `git diff --check`
- browser evidence: `audit_results/ui_web_sidebar_brand_lockup_ratio_fix_pass_2026-05-20/metrics.json`
- screenshot: `audit_results/ui_web_sidebar_brand_lockup_ratio_fix_pass_2026-05-20/screenshots/quick-start-sidebar-brand-lockup-ratio.png`

## Open Questions

- Wider responsive viewport coverage can be added only if a later operator check
  shows this larger mark crowding the sidebar on smaller screens.
