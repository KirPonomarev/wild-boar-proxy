# Spec: Custom Codex Recovery Rollback And Operator Ready Pass

## Objective

Close the bounded local operator surface for Codex Custom recovery and rollback without claiming production, desktop, installer, multi-user, or arbitrary process-kill readiness.

## In Scope

- Aggregate existing recovery, rollback, diagnostics, and dangerous-action packets into one read-only operator matrix.
- Expose a read-only web endpoint for the matrix.
- Render the matrix in the existing recovery panel without expanding design polish.
- Prove forbidden browser fields are rejected.
- Prove false-green guards for current Codex touch, missing packets, and diagnostics redaction failure.
- Record machine artifacts and independent audit.

## Out of Scope

- Live arbitrary process kill.
- Original Codex mutation.
- Account mutation.
- Route removal.
- Production, desktop, installer, and multi-user readiness.
- Rich UI redesign.

## Constraints

- WBP remains the control layer.
- CLIProxyAPI remains the engine.
- Current and Original Codex are protected baselines.
- JSON packets are primary truth.
- Browser payload cannot supply backend, route, path, pid, auth, token, secret, HOME, or CODEX_HOME.
- Process kill remains preflight-only in this contour.

## Assumptions

- Existing stop, cleanup, rollback, process-kill preflight, and diagnostics packets are the source packets.
- A bounded local operator surface can be ready while broad operator readiness remains explicitly false.
- Rollback live receipt surfaces are limited to existing bounded test/artifact paths.

## Acceptance Criteria

- [x] Operator matrix returns a bounded local ready verdict only when all required input packets are classified.
- [x] Missing or empty input packets block readiness.
- [x] Diagnostics redaction failure blocks readiness.
- [x] Process kill live remains disabled and unclaimed.
- [x] Browser forbidden fields are rejected for the endpoint.
- [x] UI exposes matrix proof without overwriting recovery failure chips.
- [x] Independent audit has no remaining blockers.

## Verification

- tests: recovery/session/live/UI/operator unittest gates passed.
- build: Python compile, node syntax, and git diff check passed.
- manual: Browser proof against local web server passed.
- live evidence: `browser_projection_proof.json`, `operator_recovery_matrix.json`, and `independent_audit.json`.

## Open Questions

- Next contour should decide whether to keep strengthening local operator controls or move to a separately scoped steady-state reliability pass.
