<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Web Table Screens Repair Spec

Contour: `UI_WEB_TABLE_SCREENS_REPAIR`

Date: `2026-05-14`

Mode: implementation / visual repair / bounded UI-only.

## Goal

Repair the Accounts and API Connections table screens against the locked table
baseline while preserving action semantics, command surfaces, and runtime truth
boundaries.

## Canon Boundary

- UI is not runtime truth.
- Browser payload remains `ui_action` plus structured payload only.
- No command id, raw argv, shell, arbitrary path, token, or direct runtime file
  access is introduced.
- Visual grouping may change presentation density only.
- This contour does not change route/account eligibility, confirmation
  requirement, server preflight, command adapter templates, live server action
  execution, or runtime code.
- Desktop transfer remains blocked until owner approval.

## Baseline Anchors

- Accounts source model: `04_accounts`.
- API Connections source model: derived from Accounts table geometry.
- Table card padding: `18px 20px 14px`.
- Table header height: `42px`.
- Table row height target: `58px`.
- Filter row gap: `20px`.
- Search width: `300px`.
- Pagination height: `34px`.

## API Connections Derived Rule

API Connections has no direct source render. It is repaired as a derived table
surface using Accounts density and action grouping while preserving API route
command boundaries and avoiding route-selection, traffic-control, resilience, or
availability claims.

## Implementation Contract

- Keep existing `data-ui-action`, `data-account-id`, `data-route-id`,
  `data-route-enabled`, and `data-route-state-requirement` semantics.
- Keep Accounts and API Connections row builders aligned with their table
  headers.
- Make long live Accounts lists use bounded internal table scroll instead of
  forcing the whole screen to become an oversized table page.
- Make API Connections action grouping readable without vertical header text.
- Keep route action labels compact while preserving full meaning in titles.
- Keep destructive route removal visually separated.
- Do not fabricate accounts, routes, checks, runtime health, or activity.

## Out Of Scope

- New account actions.
- New API route actions.
- Route create/update editor.
- Secret/token/key setup.
- Runtime files.
- Live server action semantics.
- Command adapter argv templates.
- Desktop files.
- Diagnostics detail implementation.

## Verification Plan

- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- Browser smoke at `1600x1000` for Accounts live/fixture and API Connections
  live/fixture.
- JSON validation for contour artifacts.
- Scoped leak and overclaim scans before commit.

## Resume From Here

Run independent audit, closeout, final scans, commit, and push.
