# RUNTIME_SELECTOR_PREREQUISITE_REGRESSION_DIAGNOSE_PASS

## Goal

Determine whether the current prereq regression for the exact-source lane is
primarily selector staleness, primarily runtime activation-evidence loss, or a
mixed blocker.

## Result

- status: `completed`
- verdict: `GO_TO_RUNTIME_REPROOF_PASS`
- next action: refresh runtime activation evidence first; selector refresh
  remains secondary while claim-gate truth is blocked

## Basis

- current `status --json` shows:
  - `claim_gate = blocked`
  - `policy_drift = detected`
  - `effective_stable_runtime_consumer_source = observed_source_active`
  - `consumer_activation_readiness = activation_pending`
- current `rollout rotation inspect --json` shows:
  - `ROTATION_EVIDENCE_STALE`
  - `selected_backend_snapshot_stale`
  - `selected_backend_count = 15`
- code and contract split these lanes:
  - claim-gate truth is derived from policy-drift and registry-identity claim
    blockers
  - selector snapshot freshness is a separate rotation evidence surface
- current activation evidence snapshot is stale and newer than the stale
  selector snapshot, which makes runtime reproof the stronger next recovery lane
  even though both prereq surfaces are regressed

## Why Runtime Comes First

- stale selector evidence does not directly block claim-gate truth
- stale or missing runtime activation evidence does directly force
  `observed_source_active` and `activation_pending`
- exact-source work remains parked either way, but runtime blocked truth is the
  stronger and more authoritative blocker for the next move
- this is therefore a mixed prereq regression with runtime-primary dominance,
  not a selector-only regression
