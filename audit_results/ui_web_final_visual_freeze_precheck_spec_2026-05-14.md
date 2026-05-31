<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Web Final Visual Freeze Precheck Spec

Contour: `UI_WEB_FINAL_VISUAL_FREEZE_PRECHECK`

Date: `2026-05-14`

Mode: `verification / audit / tightly bounded minimal repair`

## Objective

Verify that the current web-rendered UI is coherent enough for owner design
review before desktop admission work begins.

This contour does not start desktop transfer. It checks visual fit, command
surface boundaries, deferred screen honesty, and identity preservation.

## Canon Anchors

- Wild Boar Proxy remains the managing/control layer.
- CLIProxyAPI remains the engine.
- UI is not runtime truth.
- Browser sends only bounded UI requests.
- No direct state/log/config reads.
- No runtime, backend, adapter, or desktop behavior changes.
- A closed contour must be committed and pushed.

## In Scope

- Overview screen.
- Accounts screen.
- API Connections screen.
- Diagnostics screen.
- Settings screen.
- Setup screen.
- Select Client screen.
- Import Existing screen.
- Onboard modal.
- Confirmation modal.
- Browser smoke screenshots at `1600x1000`.
- Read-only action surface audit.
- Owner-review blocker classification.

## Allowed Minimal Repair

Only tiny freeze-blocking visual defects may be repaired in this contour.

Allowed examples:

- text wrapping
- spacing
- table/card overflow
- button label fit

Not allowed:

- new actions
- command contract changes
- live server changes
- adapter changes
- runtime changes
- desktop implementation

## Verification Plan

- Use fixture/demo source only.
- Do not click final confirmation buttons.
- Capture screenshots for all review surfaces.
- Assert no horizontal scroll or text overflow at `1600x1000`.
- Assert setup-like screens remain inert.
- Assert no runtime-ready, primary-route, failover, completed-setup, or production-ready claims.

## Expected Closeout

If all checks pass, close as `UI_WEB_FINAL_VISUAL_FREEZE_PRECHECK_PASS_WITH_OWNER_REVIEW_NOTES`
and stop for owner design review.

## Resume From Here

Run browser smoke and produce matrix.
