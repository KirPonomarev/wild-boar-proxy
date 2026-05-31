# Spec: Custom Codex Recovery Process Kill Preflight

## Objective

Add a preflight-only process-kill readiness surface for future stuck Codex Custom process recovery. The contour must not kill, terminate, or signal any process.

## In Scope

- Contract builder `build_custom_recovery_process_kill_preflight_packet`.
- GET-only web API `GET /api/codex/custom/recovery/process-kill/preflight`.
- Read-only UI renderer and refresh button.
- Regression tests for eligible, blocked, browser-injected, current Codex, and Original Codex candidates.
- Machine proof packets and independent audit.

## Out of Scope

- POST process-kill route.
- `SIGTERM`, `SIGKILL`, or equivalent live process mutation.
- Cleanup after kill.
- Rollback execution.
- Operator-ready claim.
- Account rotation/load.

## Constraints

- WBP remains the control layer.
- CLIProxyAPI remains the engine and is not touched.
- Current Codex and Original Codex must be rejected as process candidates.
- Browser cannot provide process, session, path, home, backend, route, auth, token, API key, or secret selectors.
- JSON packet truth is primary.
- `process_kill_eligible` is not live readiness.

## Assumptions

- Normal current Custom sessions have no live process candidate metadata yet and must block honestly.
- Synthetic owned candidate packets can prove the contract redaction and guard rules for the later live contour.

## Acceptance Criteria

- [x] Browser forbidden fields rejected before source read.
- [x] Missing process candidate blocks.
- [x] Current Codex process candidate blocks.
- [x] Original Codex process candidate blocks.
- [x] Non-owned process candidate blocks.
- [x] Eligible candidate keeps `process_kill_ready`, `process_kill_live_ready`, `process_kill_admitted`, `process_kill_claimed`, and `process_kill_performed` false.
- [x] UI uses GET-only refresh and no live kill affordance.
- [x] Tests and independent audit pass.

## Verification

- tests: contract, live server, UI, operator surface, command adapter.
- build: Python compile and JavaScript syntax check.
- manual: direct packet proof.
- live evidence: endpoint regression test.

## Open Questions

- A later live contour must define process identity observation, owner proof, signal strategy, timeout, receipt, rollback expectations, and stop conditions.
