# RUNTIME_REPROOF_PASS

## Goal

Reprove stable runtime truth after stable-policy/runtime reconciliation and
decide whether runtime truth is now strong enough to reopen auth-chain work or
whether selector freshness remains the narrowest blocker.

## Scope

- owner-path runtime reproof only
- no sandbox `auth.json` materialization
- no onboarding rerun
- no exact auth-source admission
- no repeated stable repair

## Owner Surfaces Used

- `python3 -m wild_boar_proxy healthcheck --json`
- `python3 -m wild_boar_proxy launch smoke --json`
- `python3 -m wild_boar_proxy status --json`
- `python3 -m wild_boar_proxy rollout rotation inspect --json`

## Expected Success Shape

- runtime truth settles desired/effective source honestly
- `claim_gate` and stable claim-surface `policy_drift` clear
- next contour is chosen from:
  - `GO_TO_SELECTOR_REFRESH_OWNER_PATH_PASS`
  - `GO_TO_EXACT_AUTH_REF_SOURCE_ADMISSION_PASS`
  - `GO_TO_OBSERVED_SOURCE_FALLBACK_DIAGNOSE_PASS`
  - `STOP_AND_DIAGNOSE`
