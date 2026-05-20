<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: UI Web Quick Start Live Data Layout Repair

## Objective

Repair the Quick Start live-data layout after density polish so operator-facing
rows stay compact, raw account timestamps do not leak into the primary view, and
the API column remains visible on the desktop control-panel viewport.

## In Scope

- Quick Start account row presentation in `overview.js`.
- Quick Start grid, account-row, row-action, and footer-action CSS.
- UI tests proving operator-friendly account row copy and no broken check action
  chip pattern.
- Browser metrics and screenshots for live and fixture Quick Start views.

## Out of Scope

- Runtime execution logic.
- Command adapter behavior.
- Live server contracts.
- Allowlist or account mutation surfaces.
- Desktop/native bridge.
- Canon document edits.

## Constraints

- Do not introduce a new command surface for per-account check buttons.
- Do not infer success from raw runtime state.
- Do not show raw ISO timestamps or `last check` implementation copy in Quick
  Start rows.
- Keep Quick Start as a summary operator surface with accounts left and API
  status right.
- Keep visible SVG icon count at zero.

## Assumptions

- The live environment can legitimately return zero account rows; fixture rows
  are used to verify populated row geometry.
- Per-account `Проверить` remains disabled until a separate admitted action
  mapping exists.
- Non-ISO friendly date copy from fixture data is preserved as already
  operator-readable text.

## Acceptance Criteria

- [x] Quick Start keeps a two-column desktop grid at `1600x1000`.
- [x] API column remains visible when live API data is missing or deferred.
- [x] Account rows do not render raw ISO timestamps.
- [x] Account rows do not render `last check` copy.
- [x] Problem/stale/checking row control is a disabled action button, not a
  mixed status chip.
- [x] The check action button has no floating status dot.
- [x] Account row secondary copy is bounded and operator-friendly.
- [x] No runtime, adapter, live-server, allowlist, desktop, or canon files are
  touched.

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- tests: `/usr/bin/python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- tests: `git diff --check`
- live evidence: `audit_results/ui_web_quick_start_live_data_layout_repair_pass_2026-05-20/metrics.json`
- live evidence: `audit_results/ui_web_quick_start_live_data_layout_repair_pass_2026-05-20/screenshots/quick-start-live-layout-repaired.png`
- fixture evidence: `audit_results/ui_web_quick_start_live_data_layout_repair_pass_2026-05-20/screenshots/quick-start-fixture-rows-repaired.png`

## Open Questions

- Per-account live check action remains deferred until a dedicated admitted
  command mapping is designed and authorized.
