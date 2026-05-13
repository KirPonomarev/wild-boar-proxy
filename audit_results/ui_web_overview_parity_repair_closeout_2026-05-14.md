<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Web Overview Parity Repair Closeout

Contour: `UI_WEB_OVERVIEW_PARITY_REPAIR`

Date: `2026-05-14`

State: `UI_WEB_OVERVIEW_PARITY_REPAIR_CLOSED`

## Summary

The Overview screen was repaired as a bounded UI-only visual contour.
Secondary live controls no longer dominate the main header, the mode card now
contains the Overview utility strip, the primary launch control remains compact
and accessible, the event log is bounded to the latest two rows with an honest
empty state, and the action ledger no longer forces first-viewport clipping.

## Files Changed

- `wild_boar_proxy/web_design_ui/index.html`
- `wild_boar_proxy/web_design_ui/styles/overview.css`
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
- `tests/test_web_design_ui.py`
- `audit_results/ui_web_overview_parity_repair_spec_2026-05-14.md`
- `audit_results/ui_web_overview_parity_repair_matrix_2026-05-14.json`
- `audit_results/ui_web_overview_parity_repair_browser_smoke_2026-05-14.json`
- `audit_results/ui_web_overview_parity_repair_independent_audit_2026-05-14.json`
- `audit_results/ui_web_overview_parity_repair_screenshots_2026-05-14/overview_live_1600x1000.png`
- `audit_results/ui_web_overview_parity_repair_screenshots_2026-05-14/overview_fixture_1600x1000.png`

## Scope Check

- New UI actions: no.
- Browser command id payload: no.
- Raw argv payload: no.
- Arbitrary path payload: no.
- Token payload: no.
- Runtime file changes: no.
- Live server semantic changes: no.
- Command adapter semantic changes: no.
- Desktop changes: no.
- Fabricated events, readiness, health, or activity: no.

The known untracked external lab tail remains outside this contour and must not
be staged with this UI commit.

## Verification

- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- `python3 -m json.tool` for the matrix and browser smoke JSON.
- Browser smoke at `1600x1000` for live and fixture Overview.
- `git diff --check`
- Scoped leak scans for service traces and private paths.

## Browser Smoke Result

- Live Overview screenshot: captured.
- Fixture Overview screenshot: captured.
- Live body horizontal scroll: false.
- Fixture body horizontal scroll: false.
- Live action panel fits window: true.
- Fixture action panel fits window: true.
- Header visible controls: 4.
- Utility strip buttons: 4.

## Independent Audit

Initial audit correctly flagged the old untracked external lab tail and the
absence of the dedicated smoke metrics file at its snapshot time. The tail is
out of scope and not staged. The missing smoke artifact was resolved.

Repeat scoped audit result: `PASS`.

## Resume From Here

Next contour: `UI_WEB_TABLE_SCREENS_REPAIR`.
