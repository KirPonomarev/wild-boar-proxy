# SELECTOR_REFRESH_OWNER_PATH_PASS

## Goal

Refresh stale selected-backend participation evidence after runtime truth was
already reproved, then decide whether fresh selector evidence honestly reopens
auth-source work or instead reveals a new cross-lane contradiction.

## Scope

- canonical owner refresh surface only
- no sandbox `auth.json` materialization
- no onboarding rerun
- no exact auth-source admission
- no repeated runtime reproof

## Owner Surfaces Used

- `python3 -m wild_boar_proxy sync --json`
- `python3 -m wild_boar_proxy rollout rotation inspect --json`
- `python3 -m wild_boar_proxy status --json`

## Expected Success Shape

- refresh surface is named exactly and run once
- post-refresh rotation truth is judged from packets, not from sync success
- next outcome is one of:
  - `GO_TO_EXACT_AUTH_REF_SOURCE_ADMISSION_PASS`
  - `GO_TO_APPROVED_TARGET_EXACT_SOURCE_NARROWING_DIAGNOSE_PASS`
  - `STOP_AND_DIAGNOSE`
