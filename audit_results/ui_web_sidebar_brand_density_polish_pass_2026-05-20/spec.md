<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: UI Web Sidebar Brand Density Polish Pass

## Objective

Reduce the visual weight of the Quick Start sidebar brand lockup so it behaves
like navigation branding rather than a cover page.

## In Scope

- Quick Start scoped sidebar brand CSS.
- Static UI assertions for the compact brand size.
- Browser screenshot and metrics for the compact sidebar state.

## Out of Scope

- Runtime, command adapter, live server, allowlist, account logic, API logic,
  desktop bridge, and canon documents.

## Acceptance Criteria

- [x] Quick Start brand image is compact.
- [x] Quick Start brand title is materially smaller.
- [x] Navigation remains readable.
- [x] No horizontal overflow appears.
- [x] No SVG icons are introduced.

## Verification

- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- `/usr/bin/python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- `git diff --check`
- Browser screenshot at `http://127.0.0.1:8765/?screen=quick-start&source=live`
