<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Web Support Settings Setup Repair Spec

Contour: `UI_WEB_SUPPORT_SETTINGS_SETUP_REPAIR`

Date: `2026-05-14`

Mode: implementation / visual repair / UI-only.

## Goal

Repair the Settings and setup-flow support screens against the locked visual
baseline while preserving strict readonly/deferred command boundaries.

Target screens:

- `settingsScreen`
- `setupScreen`
- `selectClientScreen`
- `importExistingScreen`

## Canon Anchors

- Wild Boar Proxy remains the managed companion control layer.
- CLIProxyAPI remains the engine.
- UI is not runtime truth.
- UI is not a generic config editor.
- Browser must not submit command identifiers, raw argument vectors, OS command, arbitrary paths, source
  directories, file selections, raw sensitive values, or direct configuration edits.
- Visual baseline controls geometry and identity only; it cannot create setup
  completion, import success, runtime health, or command availability.

## Implemented Scope

- Repaired Settings to the locked `07_settings` form-wrap width and row rhythm.
- Added explicit readonly visual reference markers for Settings.
- Repaired Setup, Select Client, and Import Existing with a left setup-flow rail.
- Added explicit source reference markers for setup-flow screens.
- Added inert bottom bars for setup-like screens.
- Kept setup/import/select controls disabled and visually intentional.
- Kept existing safe Settings actions unchanged.
- Added UI tests for visual reference markers and frame geometry.
- Captured browser smoke screenshots for all four target screens at `1600x1000`.

## Out Of Scope Preserved

- No new backend commands.
- No new `ui_action` families.
- No live server semantic changes.
- No command adapter semantic changes.
- No runtime file changes.
- No desktop file changes.
- No direct file discovery.
- No path, source directory, file selection, raw sensitive value, or direct configuration payload.
- No setup completion claim.
- No import success claim.

## Design Boundary

The repair follows the locked design baseline as a visual authority only. The
source setup/import references are translated into inert, deferred web
prototype controls because this contour has no admitted native picker, import
transaction, or setup completion command surface.

## Verification Plan

- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- Browser smoke for settings/setup/select-client/import-existing fixture mode
  at `1600x1000`.
- JSON validation for this contour's matrix, smoke, and audit artifacts.
- Scoped privacy, forbidden payload, and overclaim scans.
- Independent audit before commit.

## Resume From Here

Use the closeout as the durable checkpoint after commit and push.
