# Spec: Custom Codex Recovery Stop Cleanup Live

## Objective

Provide the first bounded live recovery action for Codex Custom from the WBP web surface: cancel and cleanup one server-selected owned custom session after a fresh preflight, without claiming broader recovery readiness.

## In Scope

- Contract packet builder for stop-cleanup live success and failure cases.
- Stable redacted session ref proof across preflight, live selection, cancel, and cleanup.
- Server endpoint `POST /api/codex/custom/recovery/stop-cleanup`.
- UI button that sends an empty request body and renders server truth.
- Tests for success, browser field rejection, preflight block, selection race, cancel failure, cleanup failure, and UI wiring.
- Independent audit of the changed code.

## Out of Scope

- Killing stuck processes.
- Recovering from WBP down.
- Recovering account auth or API credential state.
- Rollback execution.
- Full operator-ready claim.
- Desktop app packaging.

## Constraints

- WBP remains the control layer; CLIProxyAPI remains the engine.
- Browser does not choose session, backend, route, path, token, auth, home, process id, or filesystem root.
- JSON packets are primary truth.
- No false-green on preflight failure, race, cancel failure, or cleanup failure.
- No mutation of current Codex home, Original Codex, or auth material.
- Cleanup write surface is limited to the owned temporary custom session root.

## Assumptions

- A live recovery action is allowed only for a session already admitted by the recovery preflight contract.
- Raw session ids are internal implementation details and must not appear in the final live packet.
- Process-kill readiness must be a later contour with its own preflight and proof.

## Acceptance Criteria

- [x] Browser forbidden fields rejected before mutation.
- [x] Fresh preflight required before live stop-cleanup.
- [x] Same selected session ref verified before mutation.
- [x] Cancel attempted before cleanup.
- [x] Cleanup is not attempted after cancel failure.
- [x] Cleanup failure after cancel returns failed, not ok.
- [x] Success proves owned cleanup and no arbitrary path acceptance.
- [x] Packet states no process kill, no rollback live, and no operator-ready claim.
- [x] Final live packet omits raw session ids, paths, backends, auth, tokens, and secrets.

## Verification

- tests: `tests.test_codex_recovery_contract`, `tests.test_codex_custom_sessions`, `tests.test_web_design_live_server`, `tests.test_web_design_ui`, `tests.test_operator_surface`, `tests.test_web_design_command_adapter`.
- build: `py_compile` and `node --check`.
- manual: direct packet proof with browser rejection, live success, partial cleanup failure, and raw-key leak scan.
- live evidence: `live_ready_packet.json`.

## Open Questions

- The next contour must decide the separate process-kill preflight model and its rollback expectations.
