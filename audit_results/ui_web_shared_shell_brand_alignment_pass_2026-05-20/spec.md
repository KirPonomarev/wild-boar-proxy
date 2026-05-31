<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: UI Web Shared Shell Brand Alignment

## Objective

Align the shared sidebar shell across all primary web screens to the Quick Start
brand lockup: one boar logo size, one `WILD BOAR PROXY` typography, no visible
brand caption, and accessible navigation.

## In Scope

- Shared `.brand` and `.nav` shell CSS.
- Brand caption clearing in existing screen render paths.
- Static UI tests for the shared shell values.
- Browser evidence for six primary screens.

## Out of Scope

- Runtime logic.
- Command adapter behavior.
- Live server contracts.
- Account/API data mapping.
- Action metadata.
- Onboarding, modal, table, card, KPI, diagnostics, settings, or content layout
  changes.
- Desktop/native bridge.
- Canon document edits.

## Constraints

- Treat this as a shell repair pass, not a screen redesign.
- Do not change main content layout.
- Do not change Quick Start grid, rows, cards, or API panel.
- Do not introduce new command surfaces.
- Keep source/runtime state outside the brand caption area.

## Assumptions

- Quick Start is the canonical shell reference for this pass.
- Source state is already available outside the brand lockup, so the brand
  caption can be hidden and cleared.
- Making `.brand` and `.nav` shared removes the need for Quick Start-only brand
  overrides.

## Acceptance Criteria

- [x] `quick-start`, `overview`, `accounts`, `api-connections`, `diagnostics`,
  and `settings` all render the boar logo at `180px`.
- [x] All six screens render brand typography at `16px / 20px`.
- [x] Brand caption is not visible on all six screens.
- [x] Sidebar navigation remains accessible on all six screens.
- [x] No horizontal overflow appears on all six screens.
- [x] Visible SVG icon count remains zero.
- [x] Broken image list is empty.
- [x] Runtime, adapter, live server, contracts, data mappings, and content
  layouts are untouched.

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- tests: `/usr/bin/python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- tests: `git diff --check`
- browser evidence: `audit_results/ui_web_shared_shell_brand_alignment_pass_2026-05-20/metrics.json`
- screenshots: `audit_results/ui_web_shared_shell_brand_alignment_pass_2026-05-20/screenshots/*-shell.png`

## Open Questions

- Smaller viewport shell fit can be reviewed in a later pass if operator
  screenshots show crowding from the larger shared logo.
