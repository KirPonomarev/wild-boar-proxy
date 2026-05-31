<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Web Modal Confirmation Parity Spec

Contour: `UI_WEB_MODAL_CONFIRMATION_PARITY`

Date: `2026-05-14`

Mode: `implementation`

Type: `UI-only safety presentation repair`

## Objective

Repair the existing web UI confirmation and onboarding modal presentation so
that risky owner requests are shown with the locked Wild Boar visual baseline,
clear result-boundary copy, and no widened execution surface.

## Canon Anchors

- Wild Boar Proxy remains the managing/control layer.
- CLIProxyAPI remains the engine.
- UI confirmation confirms intent to send an allowlisted owner request.
- Result truth remains the command packet plus post-action refresh.
- UI copy must not imply a completed runtime result.
- This contour does not change backend, adapter, runtime, or desktop behavior.

## In Scope

- `confirmOverlay` visual geometry and safety presentation.
- `onboardOverlay` visual geometry and reserve-first framing.
- Modal width, radius, padding, shadow, fact rows, note area, and action footer.
- Visual severity marker derived from the existing confirmation policy.
- Static tests for modal surface markers and locked visual tokens.
- Browser smoke opening modal states without executing the final action.

## Out Of Scope

- New action surfaces.
- Backend command changes.
- Live server changes.
- Adapter command changes.
- Runtime changes.
- Desktop implementation.
- Any direct browser-owned configuration or sensitive value flow.

## Implementation Contract

- Browser request shape is unchanged.
- `confirmationInFlight` remains the duplicate-dispatch guard.
- The final confirm button is not pressed in smoke evidence.
- The onboarding modal continues to frame onboarding as reserve-first and not
  as a completed setup result.
- General confirmation continues to show action, target, severity, policy,
  mutation, refresh, scope, and dispatch state.

## Acceptance Criteria

- Existing modal surfaces use locked modal geometry tokens.
- Onboarding and general confirmation share consistent visual rhythm.
- General confirmation shows a boundary strip for owner request, not runtime result.
- Onboarding shows a boundary strip for reserve-first request and packet-backed result.
- Critical/high/medium policies can render distinct top markers.
- Static tests cover modal markers, visual tokens, and safety wiring.
- Browser smoke opens representative modal states and records screenshots.
- No backend/live server/adapter/runtime/desktop files are changed.
- Independent audit returns `PASS`.

## Verification

- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- `python3 -m unittest tests.test_web_design_ui -q`
- `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- Browser smoke packet:
  `audit_results/ui_web_modal_confirmation_parity_browser_smoke_2026-05-14.json`

## Resume From Here

Continue to independent audit and closeout for `UI_WEB_MODAL_CONFIRMATION_PARITY`.
