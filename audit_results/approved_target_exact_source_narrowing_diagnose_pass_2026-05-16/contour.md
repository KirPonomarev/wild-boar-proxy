# APPROVED_TARGET_EXACT_SOURCE_NARROWING_DIAGNOSE_PASS

## Goal

Determine whether the current approved-target exact auth-ref family can be
narrowed on an existing machine-readable basis, or whether the lane must stop
because prerequisite runtime and selector truth has regressed.

## Result

- status: `completed`
- verdict: `STOP_AND_DIAGNOSE`
- next action: do not continue exact-source narrowing while runtime truth is
  blocked and selector participation evidence is stale

## Basis

- a real read-only narrowing surface exists:
  - prior family packets and `stable repair --dry-run --json` expose the current
    approved-target exact auth-ref family
- but current live prereqs for exact-source work regressed:
  - `status --json` currently shows `claim_gate = blocked`
  - `status --json` currently shows `policy_drift = detected`
  - `status --json` currently shows
    `effective_stable_runtime_consumer_source = observed_source_active`
  - `status --json` currently shows `consumer_activation_readiness = activation_pending`
  - `rollout rotation inspect --json` currently returns
    `ROTATION_EVIDENCE_STALE`
- exact-source narrowing is therefore no longer the active blocker; stale
  runtime/selector readiness outranks it

## Why The Contour Stops

- family-level narrowing surfaces exist but do not prove a singleton source
- current runtime truth is no longer green
- current selector participation evidence is no longer fresh
- continuing the exact-source lane now would mix readiness recovery with source
  identity work and violate the repo stop rule
