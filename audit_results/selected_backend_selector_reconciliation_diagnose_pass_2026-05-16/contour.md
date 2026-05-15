# SELECTED_BACKEND_SELECTOR_RECONCILIATION_DIAGNOSE_PASS

## Goal

Reconcile the current divergence between selected-backend participation
surfaces, approved repair-target family surfaces, and current stable
policy/source-copy truth surfaces, without reading secrets or performing any
mutation.

## Constraints

- diagnose only
- no auth payload read
- no auth payload write or copy
- no onboarding rerun
- no source guessing

## Truth Basis

- sandbox destination remains fixed at
  `/Users/kirillponomarev/.codex-custom-sandbox-20260515/auth.json`
- `rollout rotation inspect --json` reports contradicted participation evidence
  because stable policy drift is detected
- `stable repair --dry-run --json` reports the current policy/source-copy family
- `status --json` reports runtime consumer desired/effective source truth
- `selected_backend_snapshot` matches the current approved repair-target
  inventory exactly, but not the current policy/source-copy family

## Allowed Outcomes

- `GO_TO_SELECTOR_REFRESH_OWNER_PATH_PASS`
- `GO_TO_EXACT_AUTH_REF_SOURCE_ADMISSION_PASS`
- `GO_TO_STABLE_POLICY_SOURCE_RECONCILIATION_PASS`
- `GO_TO_NARROWER_POLICY_SOURCE_FAMILY_PASS`
- `STOP_AND_DIAGNOSE`

## Verdict Rule

If the current divergence is localized to family-level policy/source drift and
stale participation evidence, do not reopen exact-source admission. Emit the
narrowest family-reconciliation contour instead.
