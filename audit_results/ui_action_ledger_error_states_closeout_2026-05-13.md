# UI_WEB_ACTION_LEDGER_AND_ERROR_STATES Closeout

Date: 2026-05-13

## Scope

UI action ledger/error-state display hardening only.

Changed:
- Added `Display state` and `Truth note` to the last-action ledger.
- Added frontend-only status display normalization for action packets and UI transport/render failures.
- Added action panel visual classes for green, amber, red, and neutral states.
- Added static test coverage for command-error, invalid-JSON, timeout, stale, unknown, and top-level status precedence.
- Added behavioral Node-backed test coverage that executes `setActionPanel()` with a DOM stub.

Not changed:
- No runtime code.
- No live server allowlist or packet contract.
- No command adapter argv templates.
- No new UI actions.
- No desktop files.
- No dirty external-agent tail.

## Verification

Targeted verification:
- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- `python3 -m unittest tests.test_web_design_ui`
- `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter`

Expected later before commit:
- full test discover
- browser smoke for visible non-green unavailable/failure ledger
- independent read-only audit

## Boundary

This contour does not change runtime truth. The UI classifies only display state:
- strict JSON packet status remains authoritative for command result status;
- browser invalid JSON becomes UI integration failure;
- timeout becomes recoverable UI integration failure;
- refresh failure marks ledger state stale and does not claim runtime success.

## Residual Risk

An inspector observed that some overview detail warnings can coexist with an overall healthy page state. That is server/runtime truth semantics, not the action ledger. It was deliberately left untouched to avoid layer mixing.
