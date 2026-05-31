# EXACT_AUTH_REF_SOURCE_ADMISSION_PASS

## Goal

Determine whether the current approved-target stable runtime truth now narrows
to one exact auth-ref source on a canonical machine-readable basis.

## Result

- status: `completed`
- verdict: `STOP_AND_DIAGNOSE`
- next action: do not attempt exact admission or sandbox auth materialization;
  preserve the current multi-candidate evidence and reopen the lane only after
  the exact-source narrowing path and admission command-surface mismatch are
  reconciled

## Basis

- `status --json` is green:
  - `claim_gate = clear`
  - `policy_drift = clear`
  - `effective_stable_runtime_consumer_source.status = approved_target_active_by_activation_evidence`
- `rollout rotation inspect --json` is green but family-level:
  - `machine_error_code = OK`
  - `evidence_status = participation_evidence_present`
  - `evidence_freshness = fresh`
  - `evidence_reason = multi_backend_snapshot`
- Nested `selected_backend_snapshot.selected_backend_ids` currently contains 15
  backends.
- The public exact explicit-auth owner surface is
  `accounts onboard --json --auth-ref ...`, but its success contract requires a
  newly added backend selected uniquely by exact auth-ref matching.
- Current live evidence does not identify one singleton auth-ref under the
  already active approved-target family.

## Why No Direct Admission

- There is no separate `auth ref-source admission --json` CLI command.
- `accounts onboard --json --auth-ref ...` is an onboarding/import owner path,
  not a selector for one already-existing active registry auth-ref.
- Current evidence is exact-auth-ref enumerable but still multi-candidate, so
  admitting one exact source now would be a guess.
- A relevant explicit-auth full-proof test is currently red on this branch,
  which removes the only nearby effectful owner path from the set of trustworthy
  contour-closing surfaces for this pass.
