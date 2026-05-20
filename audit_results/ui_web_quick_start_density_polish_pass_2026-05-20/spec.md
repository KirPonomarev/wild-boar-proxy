<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: UI Web Quick Start Density Polish Pass

## Objective

Make the Quick Start screen feel like a precise daily control panel at 100%
browser zoom while preserving the existing read-only UI truth boundaries.

## In Scope

- Quick Start visual density in `web_design_ui/styles/overview.css`.
- Static UI assertions in `tests/test_web_design_ui.py`.
- Browser evidence for the 1600x1000 viewport and fixture/live states.

## Out of Scope

- Runtime behavior.
- Command adapter behavior.
- Live server contracts.
- Allowlist changes.
- Account/API data logic.
- Desktop/native bridge work.
- Canon document edits.

## Constraints

- Keep the contour CSS-first.
- Do not add command surfaces.
- Do not change action availability logic.
- Do not make disabled actions look primary.
- Keep visible SVG icons at zero.
- Keep Quick Start usable without horizontal overflow.

## Acceptance Criteria

- [x] Quick Start has local density tokens.
- [x] Sidebar, header, cards, rows, API panel, and buttons are visually tighter.
- [x] Four account rows render without clipping.
- [x] `Основной API` does not wrap in the 1600x1000 browser check.
- [x] `Проверить всё` remains disabled and non-primary.
- [x] No runtime, adapter, live server, allowlist, or canon files are touched.
- [x] Screenshots and metrics are captured.

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- tests: `/usr/bin/python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- tests: `git diff --check`
- browser: `http://127.0.0.1:8765/?screen=quick-start&source=live`
- evidence: `audit_results/ui_web_quick_start_density_polish_pass_2026-05-20/metrics.json`

## Open Questions

- Deeper design language polish remains deferred to a separate UI contour.
