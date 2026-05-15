# READONLY_TRUTH_PACKET_BASELINE_PASS

## Goal

Build a semantic baseline across three readonly truth layers:

- canonical command packets
- live server normalized GET packets
- core UI live truth claims

without invoking any mutation surface.

## Scope

- canonical readonly command capture
- live server GET packet capture
- semantic mapping for `quick-start`, `overview`, `accounts`, and `api-connections`
- screenshots and mismatch classification only

Out of scope:

- sandbox creation
- any `POST /api/action`
- any live-action click
- any runtime/config/auth/state/log write

## Preflight

- `git status --short --untracked-files=no` -> clean
- `git log --oneline -n 10` -> latest contour `3f52cc8 Add web live readonly admission audit`
- `bash tools/install_git_hooks.sh` -> hooks path configured

## Fact Summary

- Canonical packets captured successfully:
  - `status --json`
  - `mode get --json`
  - `accounts list --json`
  - `healthcheck --json`
  - `rollout rotation inspect --json`
  - `external-models status --json`
  - `external-models models --json`
  - `external-models routes list --json`
- Live packets captured successfully:
  - `/api/live-readonly`
  - `/api/accounts-readonly`
  - `/api/api-connections-readonly`
- Core semantic result:
  - `quick-start` matched readonly baseline for account summary and zero-route API summary
  - `accounts` matched readonly baseline
  - `api-connections` matched readonly baseline
  - `overview` did **not** match readonly baseline

## Blocking Mismatch

With `?screen=overview&source=live`:

- page URL kept `source=live`
- source picker showed `live`
- but `.desktop.dataset.source` stayed `fixture`
- overview runtime fields stayed at placeholder values:
  - desired mode `-`
  - effective mode `-`
  - endpoint `-`
  - active `0`
  - reserve `0`
  - hold `0`
  - problem `0`
- sidebar/runtime copy stayed on fixture-like unknown state

At the same time:

- canonical packets reported `stable/stable`
- live normalized packet reported a healthy runtime summary
- live normalized packet preserved the rollout contradiction warning

## Interpretation

This is not a command/live contradiction.
It is a `live/UI mismatch` on a primary readonly truth screen.

Because `overview` is one of the four core baseline screens, this contour cannot
honestly authorize moving into sandbox boundary work yet.

## Decision

- status: `STOP_AND_DIAGNOSE`
- reason:
  - readonly packet chain is mostly sound
  - but `overview` in live mode does not consume that truth correctly
  - baseline trust in UI is therefore incomplete
