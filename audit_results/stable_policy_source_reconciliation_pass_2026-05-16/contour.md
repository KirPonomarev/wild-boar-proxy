# STABLE_POLICY_SOURCE_RECONCILIATION_PASS

## Goal

Reconcile the current family-level divergence between:

- approved repair target inventory
- current owner-path policy/source-copy family
- current runtime-consumer family

without performing any secret-bearing mutation or reopening exact-source
admission.

## Constraints

- reconciliation only
- no auth payload read
- no auth payload write or copy
- no onboarding rerun
- no exact-source selection

## Truth Basis

- approved target family count is 9
- current owner-path eligible source-copy family count is 11
- selected-backend snapshot family matches approved target exactly
- `status --json` reports desired/effective runtime source as
  `observed_stable_inventory_source`
- `stable repair --dry-run --json` reports `STABLE_POLICY_DRIFT` and emits an
  exact family delta

## Allowed Outcomes

- `GO_TO_STABLE_POLICY_SOURCE_REPAIR_PASS`
- `GO_TO_SELECTOR_REFRESH_OWNER_PATH_PASS`
- `GO_TO_EXACT_AUTH_REF_SOURCE_ADMISSION_PASS`
- `STOP_AND_DIAGNOSE`

## Verdict Rule

If the approved target family is behind the current owner-path policy/source-copy
family and `stable repair --dry-run --json` emits an exact add/prune delta while
runtime-consumer truth still canonically prefers the observed source family, do
not reopen selector or exact-source admission. Emit
`GO_TO_STABLE_POLICY_SOURCE_REPAIR_PASS`.
