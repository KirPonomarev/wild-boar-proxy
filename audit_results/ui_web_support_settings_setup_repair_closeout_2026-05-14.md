<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Web Support Settings Setup Repair Closeout

Contour: `UI_WEB_SUPPORT_SETTINGS_SETUP_REPAIR`

Date: `2026-05-14`

Final state: `UI_WEB_SUPPORT_SETTINGS_SETUP_REPAIRED`

## Capsule

- goal: repair Settings and setup-flow support screens before modal parity and visual freeze
- branch: `codex/external-agent-lab-isolated`
- touched files: web design UI HTML, CSS, UI tests, contour artifacts, screenshots
- tests run: `node --check`, targeted UI/live-server/adapter unittest suite, browser smoke at `1600x1000`
- blocked risks: real setup discovery, native picker, import transaction, config mutation, arbitrary path payload
- next exact command: `git status --short --untracked-files=no`

## Completed

- Repaired Settings to the locked form width and row rhythm.
- Added explicit readonly/source-reference markers to Settings.
- Added left setup-flow rail to Setup, Select Client, and Import Existing.
- Added inert bottom bars to setup-like screens.
- Kept all setup-like controls disabled and non-executable.
- Preserved Settings safe actions as existing allowlisted requests only.
- Captured browser smoke screenshots for all four target screens.

## Not Done By Design

- No new backend command.
- No new `ui_action`.
- No live server or command adapter semantic change.
- No runtime or desktop change.
- No direct file discovery.
- No browser path/source directory/file selection/raw sensitive value/direct configuration payload.
- No setup completion claim.
- No import success claim.

## Evidence

- Spec: `audit_results/ui_web_support_settings_setup_repair_spec_2026-05-14.md`
- Matrix: `audit_results/ui_web_support_settings_setup_repair_matrix_2026-05-14.json`
- Browser smoke: `audit_results/ui_web_support_settings_setup_repair_browser_smoke_2026-05-14.json`
- Independent audit: `audit_results/ui_web_support_settings_setup_repair_independent_audit_2026-05-14.json`
- Screenshots: `audit_results/ui_web_support_settings_setup_repair_screenshots_2026-05-14/`

## Verification

- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- `python3 -m json.tool audit_results/ui_web_support_settings_setup_repair_matrix_2026-05-14.json`
- `python3 -m json.tool audit_results/ui_web_support_settings_setup_repair_browser_smoke_2026-05-14.json`
- `python3 -m json.tool audit_results/ui_web_support_settings_setup_repair_independent_audit_2026-05-14.json`
- scoped privacy, forbidden payload, and overclaim scans
- `git diff --check`

## Scope Check

- UI-only visual repair.
- No execution-core behavior changed.
- No route/account/runtime/desktop mutation added.
- No external reference service traces added to repo artifacts.

## Resume From Here

Proceed to `UI_WEB_MODAL_CONFIRMATION_PARITY`.
