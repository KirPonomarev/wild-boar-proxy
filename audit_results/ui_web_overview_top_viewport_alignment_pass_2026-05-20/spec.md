<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: UI Web Overview Top Viewport Alignment Pass

## Objective

Align the Overview top viewport with the already polished Quick Start shell:
smaller header rhythm, compact live notice, balanced top cards, and tighter KPI
tiles.

## In Scope

- Overview-only CSS density overrides.
- Static UI test coverage for overview-scoped selectors.
- Browser DOM metrics for Overview live and Quick Start regression check.

## Out of Scope

- Runtime, command adapter, live server, allowlist, and contract documents.
- Quick Start, Accounts, API connections, Diagnostics, Settings, desktop/native
  bridge, and lower Overview sections.
- Data/status semantics and command surfaces.

## Constraints

- Do not change shared shell rules unless the change is explicitly scoped to
  `data-screen="overview"`.
- Do not change JavaScript render logic.
- Do not claim screenshots were captured unless the file exists and is valid.

## Acceptance Criteria

- [x] Overview header rhythm is reduced with overview-scoped CSS.
- [x] Overview top grid renders as two columns at 1600x1000.
- [x] Overview fixture banner remains compact.
- [x] Overview KPI cards are shorter and aligned.
- [x] No visible SVG icons.
- [x] No broken images.
- [x] Quick Start brand lockup remains unchanged by this pass.
- [x] Runtime/adapter/live server/contracts are untouched.

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; `/usr/bin/python3 -B -m unittest tests.test_web_design_ui -q`
- build: not applicable; static web UI pass
- manual: Codex in-app browser DOM metrics at `http://127.0.0.1:8765/?screen=overview&source=live`
- live evidence: `audit_results/ui_web_overview_top_viewport_alignment_pass_2026-05-20/metrics.json`

## Open Questions

- PNG screenshot capture was unavailable in this environment. The failed capture
  attempts are recorded in `metrics.json`; DOM viewport metrics are the evidence
  for this contour.
