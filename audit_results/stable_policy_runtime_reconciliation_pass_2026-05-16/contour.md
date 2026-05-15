# STABLE_POLICY_RUNTIME_RECONCILIATION_PASS

## Goal

Restore stable-policy/runtime truth after the sync-induced cross-lane
contradiction, then decide whether the next honest move is another stable
repair, runtime reproof, exact auth-source admission, or stop.

## Scope

- use canon-supported owner surfaces only
- no sandbox `auth.json` materialization
- no onboarding rerun
- no exact auth-source admission
- no repeated `sync --json`

## Owner Surfaces Used

- `python3 -m wild_boar_proxy stable repair --apply --json`
- `python3 -m wild_boar_proxy status --json`
- `python3 -m wild_boar_proxy rollout rotation inspect --json`

## Expected Success Shape

- stable repair reconciliation work closes on the approved target inventory
- post-state truth is reclassified honestly
- next contour is chosen from:
  - `GO_TO_STABLE_POLICY_SOURCE_REPAIR_PASS`
  - `GO_TO_RUNTIME_REPROOF_PASS`
  - `GO_TO_EXACT_AUTH_REF_SOURCE_ADMISSION_PASS`
  - `STOP_AND_DIAGNOSE`
