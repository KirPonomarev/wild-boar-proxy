# Spec: Runtime Launcher Owner Procedure Serialization Fix Pass

## Objective

Close the runtime-only contour that proves the stable runtime launcher owner path does not hold the shared sync mutation lock while the launcher subprocess is running, while true concurrent launcher attempts still return `LOCK_HELD`.

## In Scope

- `run_stable_runtime_launcher_attempt`
- `launcher_procedure_lock`
- `serialized_lock`
- `stable_runtime_consumer` source-selection proof
- targeted `tests/test_cli.py` regression hardening

## Out of Scope

- web UI changes
- account, route, model, or session selector changes
- CLIProxyAPI engine changes
- current Codex or `~/.codex` mutation
- stage, pilot, scale, production, desktop, or design readiness claims

## Constraints

- WBP remains the control layer.
- CLIProxyAPI remains the engine.
- JSON packets and tests are the primary truth.
- `LOCK_HELD` must stay blocked, never success.
- The launcher subprocess must not run while the shared sync mutation lock is held.
- True concurrent launcher attempts must still serialize on the launcher procedure lock.

## Assumptions

- The current implementation already uses a separate launcher lock and a short shared lock only for generated config writes.
- This contour should not rewrite runtime logic if the canonical behavior is already present.
- Regression hardening is sufficient when targeted tests prove the lock split directly.

## Acceptance Criteria

- [x] Launcher subprocess runs with `paths.launcher_lock_file` held.
- [x] Launcher subprocess runs without `paths.lock_file` held.
- [x] `run_sync` during launcher subprocess does not return `LOCK_HELD`.
- [x] True concurrent launcher attempts still return `LOCK_HELD`.
- [x] No UI, account, route, auth, current Codex, or engine scope is mixed in.

## Verification

- tests: targeted launcher tests and stable runtime tests.
- build: Python test import and execution.
- manual: runtime status, healthcheck, and invariant JSON sanity.
- live evidence: `lock_reproduction_packet.json` and `fix_verification_packet.json`.

## Open Questions

- Next contour remains `WEB_SAFE_APP_COPY_LAUNCH_PASS` if this contour closes cleanly.
