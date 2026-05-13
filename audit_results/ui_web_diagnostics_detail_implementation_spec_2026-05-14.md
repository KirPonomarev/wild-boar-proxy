<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Web Diagnostics Detail Implementation Spec

Contour: `UI_WEB_DIAGNOSTICS_DETAIL_IMPLEMENTATION`

Date: `2026-05-14`

Mode: implementation / UI-only / bounded visual-data rendering.

## Goal

Implement the admitted Diagnostics detail regions while keeping live history,
live latest records, runtime summary, and artifact reading deferred.

## Canon Input

This implementation follows the prior admission verdict:

`DIAGNOSTICS_DETAIL_MODEL_ADMITTED_WITH_DEFERRED_LIVE_HISTORY`

Canonical inputs:

- `audit_results/ui_web_diagnostics_detail_visual_model_spec_2026-05-14.md`
- `audit_results/ui_web_diagnostics_detail_region_matrix_2026-05-14.json`
- `audit_results/ui_web_diagnostics_detail_data_contract_2026-05-14.json`
- `audit_results/ui_web_diagnostics_detail_independent_audit_2026-05-14.json`
- `audit_results/ui_web_diagnostics_detail_closeout_2026-05-14.md`

## Implemented Scope

- Added a history chart slot to `diagnosticsScreen`.
- Added a latest records slot to `diagnosticsScreen`.
- Marked fixture/demo-only chart and records with DOM attributes.
- Added live-mode deferred states for chart and latest records.
- Added source-switch rendering that hides fixture visuals in live mode and hides
  deferred states in fixture/demo mode.
- Kept diagnostics export as support-artifact metadata only.

## Out Of Scope Preserved

- No runtime summary card.
- No status/healthcheck summary inside Diagnostics.
- No new backend command.
- No live history command.
- No raw log parsing.
- No diagnostics bundle opening or reading.
- No previous bundle loading by path.
- No `runtime.py`, live server, or command adapter semantic change.
- No new mutating, runtime, or recovery action button.

## Verification Plan

- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- Browser smoke for diagnostics fixture and live at `1600x1000`.
- JSON validation for implementation artifacts.
- Scoped privacy and overclaim scans.
- Independent audit before commit.

## Resume From Here

Use the implementation closeout as the durable checkpoint after commit and push.
