# ACCOUNT_LIFECYCLE_SANDBOX_ACTIONS_PASS

## Goal

Rerun the sandbox lifecycle matrix after stage-10 policy admission and prove
the first lifecycle step, `accounts promote auth --json`, before proceeding to
later lifecycle actions.

## Result

- status: `STOP_AND_DIAGNOSE`
- blocking action: `accounts promote auth --json`
- blocking class: post-promotion status attestation failure

## What Was Proven

- promotion preconditions passed:
  - `precondition_status = eligible_reserve_backend`
  - policy gate passed with `active_target_observed = 10`
  - `validate_outcome = ok`
  - `sync_outcome = ok`
- the owner path attempted routing-impacting promotion
- failed verification triggered rollback
- rollback completed
- post-refresh backend truth returned to:
  - `pool = reserve`
  - `manual_hold = false`
- forbidden live paths stayed unchanged

## What Blocked The Contour

The real promote packet returned:

- `machine_error_code = PROMOTION_STATUS_FAILED`
- `status_observed.machine_error_code = ATTESTATION_FAILED`
- `routing_change_observed = false`
- `final_outcome = rollback_completed_after_failed_verification`

The paired status packet recorded:

- `launch_readiness.blocking_reason = models_surface_unavailable_or_invalid`
- `last_error = HTTP 401: {"error":"Invalid API key"}`

So this is no longer a policy-gate problem. It is a post-promotion runtime
attestation blocker on the active lane.

## Next Honest Move

Open a narrow repair contour for post-promotion status attestation on the active
sandbox auth lane before rerunning lifecycle proof.
