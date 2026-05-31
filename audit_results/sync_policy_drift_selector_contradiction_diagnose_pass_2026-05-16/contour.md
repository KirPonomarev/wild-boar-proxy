# SYNC_POLICY_DRIFT_SELECTOR_CONTRADICTION_DIAGNOSE_PASS

## Goal

Diagnose why the canonical selector refresh surface `sync --json` produced a
fresh selected-backend snapshot but also moved truth into a contradicted
policy-drift state, then name the narrowest next contour honestly.

## Scope

- in scope:
  - read-only comparison of `sync --json`, `status --json`,
    `rollout rotation inspect --json`, and `stable repair --dry-run --json`
  - lane classification
  - authority ranking across sync participation, stable policy, and runtime
    truth
  - next-contour decision
- out of scope:
  - sandbox `auth.json` materialization
  - onboarding rerun
  - exact auth-source admission
  - repeated `sync --json`
  - manual supervisor-state or registry edits

## Result

- contradiction localized as a sync-produced managed-lane truth that reopens
  stable policy/runtime drift
- exact auth-source admission remains unearned
- next contour: `STABLE_POLICY_RUNTIME_RECONCILIATION_PASS`
