# OVERVIEW_LIVE_SOURCE_BINDING_STOP_AND_DIAGNOSE_PASS

## Goal

Localize and repair the `overview` live-source handoff defect proven by
`READONLY_TRUTH_PACKET_BASELINE_PASS`, without touching runtime truth, command
adapter wiring, or mutation surfaces.

## Scope

- `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/web_design_ui/scripts/overview.js`
- `/Volumes/Work/wild-boar-proxy/tests/test_web_design_ui.py`
- `/Volumes/Work/wild-boar-proxy/audit_results/overview_live_source_binding_stop_and_diagnose_pass_2026-05-15/*`

## Fact Pattern At Start

- `quick-start`, `accounts`, and `api-connections` rendered live readonly truth.
- `overview` at `?screen=overview&source=live` showed `sourcePicker=live` while
  `.desktop.dataset.source=fixture`.
- The observed mismatch was reproducible after page load with short waits and
  looked like fixture placeholders, not live packet truth.

## Repair Strategy

1. Reproduce the mismatch in the browser against the local live server.
2. Inspect the `overview.js` live handoff path.
3. Repair only the pending-state handoff in the UI binding layer.
4. Add a targeted test for the pending live state before fetch resolution.
5. Re-verify `overview` pending and final live states plus short regressions.

## Decision Rule

- `GO_TO_RERUN_READONLY_TRUTH_PACKET_BASELINE_PASS` only if `overview` shows an
  honest live pending state immediately and converges to live readonly truth
  after the fetch resolves.
