# RUNTIME_TAIL_OWNER_DECISION_GATE Closeout

Date: 2026-05-13

Branch: `codex/external-agent-lab-isolated`

Input commit: `0222cd5 Prepare generated evidence decision gate`

## Scope

This contour was decision-only. It inspected the dirty `wild_boar_proxy/runtime.py` diff and did not edit, revert, format, stage, or commit runtime code. It did not run live runtime commands, capture command packets, or generate runtime evidence.

## Runtime Diff

- File: `wild_boar_proxy/runtime.py`
- Diff stat: 1 file changed, 16 insertions, 1 deletion.
- Broader than the known two areas: no.

Behavior areas:

- `dispatch_external_client`: detached executable launch now waits up to 1.25 seconds for short-lived child processes to materialize side effects before returning.
- `run_promote`: when `lock_acquired` is true, local `routing_change_observed` no longer requires selected-backend membership; caller postflight is expected to own that proof.

## Affected Surfaces

- `launch client --json`
- `accounts promote <id> --json`
- `rollout stage advance ... --json`

## Existing Test Coverage Identified

- Launch client detached dispatch and bounded claim tests in `tests/test_cli.py`.
- Launch client UI/shell boundary tests in `tests/test_ui_shell.py` and `tests/test_web_design_live_server.py`.
- Direct accounts promote success and rollback tests in `tests/test_cli.py`.
- Stage advance lock-acquired and stage success coverage in `tests/test_cli.py`.

## Missing Later-Contour Tests

- A launch-client settle-window proof with no post-return polling.
- A bounded-latency guard for detached launch.
- A lock-acquired promotion case where selected-backend membership is delegated to caller postflight.
- A direct promote guard proving non-lock promotion still requires selected-backend verification.
- A stage-advance postflight guard proving the delegated selected-backend proof is enforced.

## Independent Inspection

Read-only inspector `Locke` confirmed the diff is confined to the two known behavior areas and recommended split ownership if one owner should not cover both launch/client timing and rollout/stage promotion semantics.

## Owner Options

- Open `RUNTIME_TAIL_REVIEW_AND_TEST_GATE`.
- Open `RUNTIME_TAIL_REVERT_EXECUTION_GATE`.
- Open `RUNTIME_TAIL_SPLIT_DECISION_GATE`.
- Keep pending as runtime blocker.

Recommended default: `RUNTIME_TAIL_SPLIT_DECISION_GATE`.

## Final State

`RUNTIME_TAIL_DECISION_READY_OWNER_APPROVAL_REQUIRED`

UI backfill remains blocked on this branch while `wild_boar_proxy/runtime.py` is dirty.
