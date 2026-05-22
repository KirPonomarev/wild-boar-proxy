# ACCOUNT_LIFECYCLE_ROUTING_TRUTH_HARDENING_PASS

## Goal

Harden execution-core lifecycle/routing truth for account transitions that
blocked the design gate after `WEB_SAFE_COMMANDS_EXPANSION_PASS`.

Primary targets:

- `accounts promote <id> --json`
- `accounts retire <id> --json`

This contour stayed runtime-first. Web was used only as a verification surface.

## Problem Localized

Two different issues were surfaced by earlier browser proof:

1. `promote` could roll back even when a single promotion preserved the staged
   reserve floor, because post-status policy verification wrongly demanded:

   - `reserve_count_after == reserve_target`

   instead of verifying that reserve stayed above the floor after exactly one
   reserve->active transition.

2. Browser verification initially reproduced stale/non-canonical outcomes
   because the proof harness itself used an unsuitable sync lane:

   - default-named sync helper was auto-rewritten to the repo-owned stable lane
   - hidden-button clicking in Playwright produced unreliable UI dispatch

   Those proof-lane issues were isolated from the runtime fix and corrected only
   in the sandbox verification setup.

## Runtime Fix

`wild_boar_proxy/runtime.py`

Promotion policy verification now requires:

- `active_pool_count_after == active_pool_count_before + 1`
- `active_pool_count_after <= active_target`
- `reserve_count_after == reserve_count_before - 1`
- `reserve_count_after >= reserve_target`

This matches the canon:

- promotion must not exceed the staged active target
- promotion must not drop reserve below the staged reserve floor
- single-account promotion must still prove one real reserve->active transition

## Regression Coverage

`tests/test_cli.py`

Added:

- `test_accounts_promote_accepts_single_promotion_when_reserve_stays_above_floor`
- `test_accounts_retire_held_reserve_backend_clears_hold_and_confirms_terminal_state`

These complement existing rollback tests for:

- status verification failure
- policy verification failure
- terminal illegal hold-on-retired rejection

## Browser Verification Method

Browser verification used an isolated sandbox live server and browser-context
`POST /api/action` dispatch with page reload checks.

Reason:

- this contour was about runtime truth, not button choreography
- direct browser-context dispatch avoids hidden-button/overlay flake while still
  exercising the actual web allowlist and action endpoint

Verified green actions in browser context:

- `validate_account`
- `hold_account`
- `release_account`
- `demote_account`
- `promote_account`
- `retire_account`

## Scope Check

In scope:

- runtime promote truth
- runtime retire truth guard coverage
- browser verification evidence
- audit package

Out of scope:

- design polish
- new web features
- desktop
- rollout stage mutation
- unrelated cleanup
