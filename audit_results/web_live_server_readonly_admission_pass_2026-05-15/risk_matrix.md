# WEB_LIVE_SERVER_READONLY_ADMISSION_PASS Risk Matrix

## High

### Live UI already exposes active POST-capable actions

- fact:
  - overview live mode renders multiple admitted `.live-action` buttons as enabled
  - `overview.js` wires every `.live-action` button to `maybeConfirmAndRun()` -> `fetch("api/action", { method: "POST" })`
- impact:
  - manual live inspection can become mutation work if an operator clicks past the contour boundary
- guardrail:
  - next contour must remain GET-only and avoid live-action clicks entirely

### `/api/action` exists next to readonly surfaces

- fact:
  - `do_POST` accepts `/api/action` while readonly GET endpoints are in the same server
- impact:
  - admission and mutation share one process boundary
- guardrail:
  - treat `POST /api/action` as forbidden for readonly contours

## Medium

### Several screens use the shared live snapshot renderer

- fact:
  - `overview.js` routes most live screens through `loadLiveReadonly()` and `renderSnapshot()`
- impact:
  - screen-specific readonly semantics are not yet baseline-verified for every screen
- guardrail:
  - keep this contour narrow; do full semantic comparison in `READONLY_TRUTH_PACKET_BASELINE_PASS`

### GET query extras are ignored rather than blocked

- fact:
  - probing `?command_id=sync` on readonly GET endpoints still returned normal readonly packets
- impact:
  - readonly endpoints are not using query extras, but they also do not explicitly reject them
- guardrail:
  - do not infer payload filtering rules for GET from this contour; use documented endpoint role only

## Low

### Browser-session recovery was needed

- fact:
  - the in-app browser lost the first tab binding and required reacquiring a new tab
- impact:
  - no product risk, only a tooling recovery step
- guardrail:
  - none beyond ordinary browser-session recovery
