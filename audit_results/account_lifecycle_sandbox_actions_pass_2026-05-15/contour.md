# ACCOUNT_LIFECYCLE_SANDBOX_ACTIONS_PASS

## Goal

Determine whether the current sandbox state truthfully admits the canonical
account lifecycle matrix, starting from the single sandbox backend `auth` in
`reserve`.

## Result

- status: `STOP_AND_DIAGNOSE`
- blocking surface: `accounts promote auth --json`
- blocker class: staged pool-policy gate

## Why This Stopped

The current sandbox registry truth is:

- one backend: `auth`
- backend pool: `reserve`
- `manual_hold = false`
- `pool_policy.active_target = 0`
- `pool_policy.reserve_target = 0`

The real sandbox owner packet for:

`accounts promote auth --json`

returned:

- `machine_error_code = PROMOTION_POLICY_LIMIT_REACHED`
- `promotion_result.precondition_status = active_target_reached`
- `active_pool_count_before = 0`
- `active_target_observed = 0`
- `changed_files = []`

This means the lifecycle matrix is not fully admissible on the current sandbox
state. Promotion is blocked before validate/sync/routing mutation, so the
contour stops instead of silently reseeding policy or widening scope.

## Scope Integrity

- No sandbox lifecycle mutation was applied.
- No live fallback was used for the proof packet.
- Forbidden live paths remained unchanged.

## Next Honest Move

Earn `SANDBOX_POLICY_STAGE_SET_10_ADMISSION_PASS` so the sandbox policy can move
from the current `0/0/0` posture to canonical stage `10` before rerunning
lifecycle promotion proof.
