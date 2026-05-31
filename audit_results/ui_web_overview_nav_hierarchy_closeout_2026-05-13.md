<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Web Overview/Nav Product Hierarchy Realignment Closeout

Contour: `UI_WEB_OVERVIEW_NAV_PRODUCT_HIERARCHY_REALIGNMENT`
Date: 2026-05-13

## Scope

Realigned the top-level web UI impression without changing runtime or command behavior.

Completed:

- Persistent sidebar now shows only core product sections: Overview, Accounts, Diagnostics and Settings.
- Setup, select-client and import-existing remain routable by direct screen id and remain inert.
- Overview uses product/operator copy instead of dominant safety/debug narrative.
- Overview has one primary CTA for client launch request.
- Secondary overview actions are visually quieter.
- Mode-card actions use secondary compact tiles.
- Last-action evidence panel moved below operational cards, KPI row and event log.
- Static tests now assert nav membership, one primary overview CTA, secondary action treatment, action panel order and deferred route inertness.

Not changed:

- runtime behavior
- `runtime.py`
- command adapter argv templates
- server allowlist behavior
- `ui_action` ids
- JSON keys
- `machine_error_code` values
- account action behavior
- diagnostics workspace semantics
- settings form semantics

## Verification

Passed:

- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- `python3 -m unittest tests.test_web_design_ui -q`
- `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- `python3 -m unittest discover -s tests -q`
- `git diff --check`
- JSON validation for contour artifacts
- changed-file scan for private external reference-service traces
- browser smoke in system Google Chrome via Playwright at `1600x1000`
- independent read-only audit

Full discovery result:

- 565 tests
- passed

## Evidence

- `audit_results/ui_web_overview_nav_hierarchy_matrix_2026-05-13.json`
- `audit_results/ui_web_overview_nav_hierarchy_browser_smoke_2026-05-13.json`
- `audit_results/ui_web_overview_nav_hierarchy_independent_audit_2026-05-13.json`

## Independent Audit

Independent read-only audit reported no findings by severity.

Verified:

- scope stayed in web UI/test files;
- deferred routes remain inert;
- one primary overview CTA remains;
- action evidence appears after core overview content;
- false-green/error protections remain;
- command and runtime contracts appear unchanged.

## Residual Risks

- Accounts, Diagnostics and Settings still need their own follow-up hierarchy contours.
- Browser smoke validates DOM hierarchy and route behavior, not pixel parity.
- Some technical terms remain in secondary details where they preserve exact command or safety meaning.

## Closeout Decision

The contour is ready for focused commit and push after staging only the changed UI files, tests and contour evidence artifacts.
