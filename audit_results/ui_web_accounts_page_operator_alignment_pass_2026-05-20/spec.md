<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: UI Web Accounts Page Operator Alignment Pass

## Objective

Align the Accounts page with the newer Quick Start and Overview visual density
without changing account lifecycle semantics, command dispatch, or runtime truth.

## In Scope

- Accounts page operator density and typography.
- Accounts table spacing, row height, chips, action menu geometry, and timestamp
  presentation.
- Account detail drawer visual copy and compact geometry.
- UI tests that preserve readonly/redacted and action-payload boundaries.
- Browser DOM metrics for the live Accounts page and drawer-open interaction.

## Out of Scope

- Runtime, command adapter, live server, `web_ui.py`, `ui_shell.py`, allowlist,
  desktop/native bridge, and canon documents.
- Account lifecycle eligibility, command dispatch, owner authorization, or backend
  mutation behavior.
- Other screens such as Quick Start, Overview, API connections, Diagnostics, and
  Settings.

## Constraints

- No new command surface.
- No browser-submitted auth, token, path, `backend_id`, `source_dir`, or file
  picker.
- Disabled account actions must remain disabled and must not dispatch.
- Account action payload remains `ui_action + account_id`.
- Command result must not be presented as account state before refresh.

## Acceptance Criteria

- [x] Accounts page uses accounts-scoped visual alignment rules.
- [x] Header, banner, filters, chips, and table are compact at 1600x1000.
- [x] Accounts table does not render raw ISO timestamps.
- [x] Account detail drawer opens from a row and remains compact.
- [x] Drawer action payloads remain `ui_action + account_id`.
- [x] No visible SVG icons, no broken images, no horizontal overflow.
- [x] No forbidden file/path/token inputs.
- [x] No runtime/adapter/live server/canon docs are changed.

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; `/usr/bin/python3 -B -m unittest tests.test_web_design_ui -q`
- build: not applicable; static web UI pass
- manual: Codex in-app browser DOM metrics at `http://127.0.0.1:8765/?screen=accounts&source=live`
- live evidence: `audit_results/ui_web_accounts_page_operator_alignment_pass_2026-05-20/metrics.json`

## Open Questions

- Screenshot capture timed out again in the browser surface. The final evidence
  records `captured: false`; no screenshot success is claimed.
