<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Web Overview Parity Repair Spec

Contour: `UI_WEB_OVERVIEW_PARITY_REPAIR`

Date: `2026-05-14`

Mode: implementation / visual repair / bounded UI-only.

## Goal

Repair the web Overview screen against the locked design baseline while
preserving the existing runtime and action semantics.

## Canon Boundary

- UI is not runtime truth.
- The browser sends only `ui_action` plus structured payload.
- No command id, raw argv, shell, arbitrary path, token, or direct runtime file
  access is introduced.
- This contour does not change command adapter semantics, live server command
  execution, or runtime code.
- Desktop transfer remains blocked until owner approval.

## Baseline Anchors

- Overview source model: `01_overview_dashboard`.
- Target shell: left-sidebar source shell.
- Working viewport: `1600x1000`.
- Top grid: `496px 1fr`, gap `24px`.
- KPI grid: `repeat(4, 1fr)`.
- KPI card height: `112px`.
- Log row: `44px`, columns `28px 1fr auto`.

## Implementation Contract

- Demote secondary Overview live controls from the main header into the mode
  card utility strip.
- Keep the primary launch control in the header, but render it as compact
  icon-only control with accessible label.
- Keep all existing `data-ui-action` names and live-action classes.
- Compact the action ledger so it reports the current action state without
  forcing viewport clipping.
- Show an honest empty events state if no event rows are supplied by the current
  JSON packet.
- Do not fabricate events, readiness, health, or activity.

## Out Of Scope

- New UI actions.
- New backend commands.
- Live server action semantics.
- Command adapter argv templates.
- Runtime files.
- Desktop files.
- Diagnostics detail implementation.
- Account/API Connections visual repair.

## Verification Plan

- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- Browser smoke at `1600x1000` for live and fixture Overview.
- Diff check and leak scans before commit.

## Resume From Here

Implement, verify, audit, and close `UI_WEB_OVERVIEW_PARITY_REPAIR`.
