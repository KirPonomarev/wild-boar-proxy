# SYNC_POLICY_DRIFT_SELECTOR_CONTRADICTION_DIAGNOSE_PASS

## Goal

Localize why canonical selector refresh through `sync --json` restores fresh
participation evidence but simultaneously re-blocks stable/runtime truth, then
choose the narrowest non-auth contour honestly.

## Scope

- diagnose only
- no sandbox `auth.json` materialization
- no onboarding rerun
- no exact auth-source admission
- no repeated `sync --json`

## Surfaces Compared

- `python3 -m wild_boar_proxy sync --json`
- `python3 -m wild_boar_proxy rollout rotation inspect --json`
- `python3 -m wild_boar_proxy status --json`

## Expected Success Shape

- contradiction is localized narrowly
- lane authority is explicit
- next contour is chosen from:
  - `GO_TO_STABLE_POLICY_RUNTIME_RECONCILIATION_PASS`
  - `GO_TO_MANAGED_SYNC_MODE_DRIFT_DIAGNOSE_PASS`
  - `STOP_AND_DIAGNOSE`
