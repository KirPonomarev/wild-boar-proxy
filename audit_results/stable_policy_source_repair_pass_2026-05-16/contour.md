# STABLE_POLICY_SOURCE_REPAIR_PASS

## Goal

Reconcile the approved control-owned target family to the current owner-path
policy/source-copy family by using only `stable repair --apply --json`, then
separate target-family alignment truth from runtime-consumer truth before
naming the next contour.

## Scope

- in scope:
  - owner-path `stable repair --apply --json`
  - approved target inventory reconciliation
  - changed-files scope proof
  - post-repair family verification
  - rollback verification
- out of scope:
  - sandbox `auth.json` materialization
  - onboarding rerun
  - exact-source admission
  - runtime activation claims
  - selector refresh mutation

## Result

- family repair apply succeeded
- approved target family aligned to the current owner-path source-copy family
- runtime-consumer truth still reports activation pending and does not yet earn
  exact-source admission
- next contour: `RUNTIME_REPROOF_PASS`
